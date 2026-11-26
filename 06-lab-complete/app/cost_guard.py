"""Track mock token charges in Redis using UTC accounting periods."""
from datetime import datetime, timezone
from fastapi import HTTPException
from .config import settings
from .redis_client import r

PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006

def _keys():
    now = datetime.now(timezone.utc)
    return f"day14:cost:daily:{now:%Y-%m-%d}", f"day14:cost:monthly:{now:%Y-%m}"

def check_budget() -> None:
    daily, monthly = r.mget(_keys())
    if float(daily or 0) >= settings.daily_budget_usd or float(monthly or 0) >= settings.monthly_budget_usd:
        raise HTTPException(status_code=402, detail="Token budget exhausted")

def record_cost(input_tokens: int, output_tokens: int) -> float:
    cost = (input_tokens * PRICE_INPUT_PER_1K + output_tokens * PRICE_OUTPUT_PER_1K) / 1000
    daily, monthly = _keys()
    with r.pipeline(transaction=True) as pipe:
        pipe.incrbyfloat(daily, cost)
        pipe.expire(daily, 172800)
        pipe.incrbyfloat(monthly, cost)
        pipe.expire(monthly, 5356800)
        pipe.execute()
    return cost
