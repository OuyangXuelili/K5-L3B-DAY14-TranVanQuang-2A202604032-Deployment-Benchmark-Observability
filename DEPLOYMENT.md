# Deployment

## Trạng thái

Agent Part 6 đã triển khai trên **Render Free** cùng **Render Key Value Free**, region Singapore. Dashboard báo **Live** với bản code [`b806a95`](https://github.com/OuyangXuelili/K5-L3B-DAY14-TranVanQuang-2A202604032-Deployment-Benchmark-Observability/commit/b806a95459ae2d0fa1779557710c3637fcd7939c). Các cập nhật hồ sơ sau commit này không thay đổi code chạy trên cloud.

- Public URL: **https://day14-agent-r4n7.onrender.com**
- Health: https://day14-agent-r4n7.onrender.com/health
- Readiness: https://day14-agent-r4n7.onrender.com/ready
- Swagger: https://day14-agent-r4n7.onrender.com/docs

Không sử dụng API LLM trả phí. Giá token trong ứng dụng là số mô phỏng của mock. Web service và Key Value đều dùng gói Free.

## Cấu hình triển khai

- Repository: bản fork cá nhân hiện tại, nhánh `main`.
- Blueprint Path: `06-lab-complete/render.yaml`.
- Root Directory: `06-lab-complete`.
- Dockerfile: `./Dockerfile`; build context: `.`.
- Web service: `day14-agent-r4n7`, plan `free`.
- Key Value: `day14-state-r4n7`, plan `free`, 25 MB, tối đa 50 kết nối. Runtime hiển thị Valkey 8.1.10, tương thích giao thức Redis mà app sử dụng.
- Redis kết nối qua mạng nội bộ; danh sách cho phép truy cập ngoài rỗng, Internet không truy cập được Key Value.
- Health check: `/health`.

| Biến | Cách đặt |
|---|---|
| `PORT` | Render cấp; CMD đọc từ env |
| `ENVIRONMENT` | `production` |
| `AGENT_API_KEY` | Blueprint tạo bằng `generateValue`; không chép vào repo/ảnh |
| `REDIS_URL` | `fromService.connectionString`; giữ ngoài Git |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1` |
| `MONTHLY_BUDGET_USD` | `10` |
| `LOG_LEVEL` | `INFO` |

## Kết quả xác minh public

Đã chạy bằng **curl.exe** ngày **26/11/2026 lúc 18:02 (GMT+7)**, tương ứng timestamp UTC trong [public-smoke.json](reports/public-smoke.json). Bốn phép thử đều đạt:

| Request | API key | HTTP thực tế | Kết quả |
|---|---|---:|---|
| `GET /health` | Không gửi | 200 | `status: ok` |
| `GET /ready` | Không gửi | 200 | `status: ready`, `redis: true` |
| `POST /ask` | Không gửi | 401 | Từ chối truy cập |
| `POST /ask` | Hợp lệ | 200 | Trả câu trả lời mock và usage |

Output rút gọn: [public-curl.txt](reports/public-curl.txt). API key được đọc từ `.env` local đã bỏ qua bởi Git và truyền cho curl qua stdin; không ghi giá trị vào báo cáo hoặc ảnh.

Để kiểm tra lại trong Bash, đặt `AGENT_API_KEY` trong môi trường shell từ kho secret của service, rồi chạy:

```bash
BASE=https://day14-agent-r4n7.onrender.com
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

Mã kỳ vọng theo thứ tự: **200, 200, 401, 200**. PowerShell dùng `curl.exe` thay cho alias `curl`.

## Ảnh minh chứng

- [dashboard.png](screenshots/dashboard.png): trang Render hiển thị service **Free**, trạng thái **Live**, commit và URL public.
- [running.png](screenshots/running.png): Swagger trên URL public đã thực thi `/ready`, nhận **200** và `redis: true`.
- [test.png](screenshots/test.png): ảnh trang tổng hợp dữ liệu curl đã ghi trong `reports/public-smoke.json`, hiển thị đủ bốn phép thử. Trang chỉ trình bày kết quả đã chạy; không tự gửi request trình duyệt và không chứa secret.

Blueprint cũng đã được kiểm tra với JSON Schema chính thức của Render: [deploy-config-validation.json](reports/deploy-config-validation.json).

## Giới hạn vận hành

Render Free có thể tạm dừng web khi không có tải; request đầu tiên có thể mất **50 giây hoặc hơn** để khởi động lại. Key Value Free không bật persistence và dùng eviction `allkeys-lru`; restart hoặc thiếu bộ nhớ có thể làm mất state, gồm bộ đếm rate limit/budget. Cấu hình này phục vụ lab với mock LLM; trước khi dùng ngân sách LLM thật cần state lưu bền và cơ chế reservation atomic như phân tích trong Mission Answers.

Service được tạo qua Blueprint từ URL repo public. Khi thay đổi code, kiểm tra deployment mới đã Live; nếu không có auto-deploy, dùng **Manual Deploy → Deploy latest commit**. Các phép đo tải và observability trong Benchmark Report được chạy local; không coi chúng là benchmark của Render Free.
