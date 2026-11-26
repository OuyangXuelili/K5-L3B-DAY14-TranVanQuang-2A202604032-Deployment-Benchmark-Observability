# Deployment

## Trạng thái

Nền tảng đã chọn: **Render Free**, gồm web service Docker và Render Key Value Free trong cùng region Singapore. **Chưa có URL public đã xác minh**. Tab Render hiện đã vào Dashboard. Code local chưa được commit/push trong đợt này; cần đưa bản code đã kiểm tra lên main trước khi triển khai và xác minh service public.

Không sử dụng API LLM trả phí. Giá token trong ứng dụng là số mô phỏng của mock.

## Cấu hình triển khai

- Repository: bản fork cá nhân hiện tại, nhánh `main`.
- Blueprint Path: `06-lab-complete/render.yaml`.
- Root Directory: `06-lab-complete`.
- Dockerfile: `./Dockerfile`; build context: `.`.
- Web service: `day14-agent-r4n7`, plan `free`.
- Key Value: `day14-state-r4n7`, plan `free`, không mở truy cập Redis từ Internet.
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

Gói free có thể cold start sau thời gian không có tải. Key Value Free không bảo đảm lưu bền khi restart; reset state cũng reset bộ đếm rate/budget. Cấu hình này phục vụ lab, chưa đủ để quản lý ngân sách LLM thật.

## Bốn lệnh xác minh sau deploy

Đặt `BASE` thành URL Render thực tế và lấy `AGENT_API_KEY` từ kho biến môi trường của service. Các lệnh chỉ in status, không in key:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -d '{"question":"Hello"}'
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" \
  -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
```

Kỳ vọng theo thứ tự: **200, 200, 401, 200**. Chưa ghi các mã này là kết quả cloud khi chưa chạy thật.

## Bằng chứng deploy còn cần bổ sung

`screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png` phải được chụp sau khi Render có service chạy và bốn lệnh trên đã được xác minh. Không dùng ảnh local thay cho ảnh deploy public.

Blueprint đã được kiểm tra với JSON Schema chính thức của Render, hợp lệ và cả hai service dùng plan `free`: [deploy-config-validation.json](reports/deploy-config-validation.json). Đây là kiểm tra cấu hình, chưa phải bằng chứng đã deploy.
