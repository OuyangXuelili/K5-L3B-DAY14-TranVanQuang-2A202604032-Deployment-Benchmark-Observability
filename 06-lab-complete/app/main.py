"""Authenticated mock agent with shared limits and structured request logs."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import time
import uuid
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from redis.exceptions import RedisError
from utils.mock_llm import ask as llm_ask
from .auth import verify_api_key
from .config import settings
from .cost_guard import check_budget, record_cost
from .rate_limiter import check_rate_limit
from .redis_client import r, redis_healthy

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {"ts": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                   "event": record.getMessage(), **getattr(record, "fields", {})}
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger("day14.agent")
logger.handlers = [handler]
logger.setLevel(settings.log_level)
logger.propagate = False

@asynccontextmanager
async def lifespan(app):
    logger.info("startup", extra={"fields": {"environment": settings.environment}})
    yield
    # Uvicorn drains in-flight requests before entering lifespan teardown.
    r.close()
    logger.info("shutdown_complete")

app = FastAPI(title="Day 14 Agent", lifespan=lifespan)

@app.middleware("http")
async def request_log(request: Request, call_next):
    started = time.perf_counter()
    request_id = uuid.uuid4().hex
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        logger.info("http_request", extra={"fields": {"request_id": request_id,
                    "method": request.method, "path": request.url.path, "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3)}})

@app.exception_handler(RedisError)
async def redis_error(request, exc):
    logger.warning("redis_unavailable")
    return JSONResponse(status_code=503, content={"detail": "State service unavailable"})

@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logger.error("request_failed", extra={"fields": {"exception_type": type(exc).__name__}})
    return JSONResponse(status_code=500, content={"detail": "Internal service error"})

class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = Field(default=None, max_length=128)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("question must contain text")
        return value

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/ready")
def ready():
    ok = redis_healthy()
    return JSONResponse(status_code=200 if ok else 503,
                        content={"status": "ready" if ok else "not_ready", "redis": ok})

@app.post("/ask")
def ask(body: AskRequest, key: str = Depends(verify_api_key)):
    check_rate_limit(key)
    check_budget()
    answer = llm_ask(body.question)
    input_tokens, output_tokens = max(1, len(body.question) // 4), max(1, len(answer) // 4)
    cost = record_cost(input_tokens, output_tokens)
    return {"question": body.question, "answer": answer, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "cost_usd": cost, "model": "mock-llm"}
