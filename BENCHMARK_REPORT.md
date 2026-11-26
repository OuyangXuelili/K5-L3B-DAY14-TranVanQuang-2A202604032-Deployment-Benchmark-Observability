# Benchmark & Observability Report — Day 14

**Họ tên:** Trần Văn Quang — 2A202604032

**Ngày chạy:** 26/11/2026 (GMT+7)

**Môi trường:** Windows, Intel Core i7-1165G7 (4 nhân/8 luồng), RAM danh nghĩa 8 GB. Docker Desktop Linux dùng 8 CPU logic, giới hạn RAM 3.935.961.088 bytes (khoảng 3,67 GiB). Agent production bị giới hạn 0,5 CPU và 256 MB mỗi instance, một Uvicorn worker/container. Xem [hardware.json](reports/hardware.json).

**Trạng thái:** đã có JSON/CSV, đủ bảy ảnh minh chứng, hai alert cùng firing và trace khớp log. Agent Part 6 đã Live trên Render Free, bốn phép thử public đạt 200/200/401/200; xem [DEPLOYMENT.md](DEPLOYMENT.md). Các số đo tải dưới đây được thực hiện local.

## 1. SLO của agent

| SLI | SLO | Lý do |
|---|---|---|
| p95 `/ask` | ≤ 500 ms | Theo ngưỡng của load_test.py để so sánh cùng chuẩn |
| Error rate `/ask` | ≤ 2% | Cao hơn mức lỗi mock mặc định 1%, vẫn phát hiện quá tải |
| Accuracy golden dataset | ≥ 85%, không regression | Quality gate tối thiểu của Exercise 7.3; bản sửa cuối kiểm tra ở 100% |

Load test dùng 300 request mỗi lượt, mock nhỏ, `MOCK_ERROR_RATE=0.01`; bốn mức concurrency dùng `MOCK_SLOW_RATE=0.03`. Ba lượt so sánh slow rate đều concurrency 20. Tập câu hỏi và generator giống nhau, thứ tự chọn ngẫu nhiên, không khóa seed. Mỗi cấu hình chạy một lượt; kết quả chưa phải ước lượng có khoảng tin cậy. [Cấu hình chạy](reports/load-environment.json).

Đợt đầu chạy cùng nhiều dịch vụ khi Windows chỉ còn 208.104 KiB RAM trống. Giữ nguyên kết quả đó trong [initial-memory-pressure](reports/initial-memory-pressure/). Bảng chính dùng đợt chạy lại sau khi dừng các stack Day 14 khác, không chạy build đồng thời. Các dự án khác trên máy vẫn được giữ nguyên.

## 2. Benchmark hiệu năng — develop

### 2.1. Concurrency và latency

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.24 | 202.8 | 234.3 | 1707.1 | 1.33% | PASS |
| 10 | 33.68 | 220.8 | 296.8 | 1696.7 | 0.67% | PASS |
| 50 | 20.82 | 1252.0 | 6851.9 | 11017.9 | 0.67% | FAIL |
| 100 | 20.45 | 3134.5 | 11770.1 | 14132.2 | 1.00% | FAIL |

Nguồn: `reports/load_v2_c1.json`, `c10`, `c50`, `c100`. C1/C10 đạt cả hai ngưỡng; C50/C100 trượt latency. RPS không tăng tuyến tính, và còn giảm ở tải cao: CPU, bộ nhớ, serialization/logging và lịch chạy trên host dùng chung tạo hàng đợi. Không quy toàn bộ chậm trễ cho mock LLM hoặc suy ra năng lực cloud từ máy này. Latency của load_test.py là phía client và chỉ lấy request 200; error rate tính trên toàn bộ request. Timeout của httpx áp dụng cho từng thao tác mạng, không phải deadline tổng thời gian đo.

### 2.2. Tail latency

| MOCK_SLOW_RATE | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 593.0 | 1517.6 | 2175.8 |
| 0.03 | 582.3 | 1694.8 | 2980.2 |
| 0.1 | 564.6 | 1883.9 | 2043.1 |

Nguồn: ba file `reports/load_v2_slow_*.json`. p95 tăng qua ba lượt, nhưng average và p99 không tăng đều. Ngay lượt slow rate 0 vẫn có tail lớn do host/hàng đợi; 300 mẫu và một lần chạy chưa tách được ảnh hưởng riêng của lỗi chậm được tiêm. Không chỉnh hay thay số để tạo đường tăng đều. Theo phân bố, p99 nhạy với nhóm request chậm hiếm; p95 thể hiện rõ hơn khi tỷ lệ chậm vượt 5%. Average có thể che trải nghiệm xấu của nhóm nhỏ, nên cần p95/p99 và error rate cùng với average.

### 2.3. Metrics — Exercise 7.1

- Counter: `http_requests_total`; chỉ tăng từ lần khởi động process.
- Gauge: `agent_in_flight_requests`; tăng/giảm theo số request đang xử lý.
- Histogram: `http_request_duration_seconds` và metric mới `agent_question_length_chars`.

Đã thêm histogram độ dài ở develop và production, bucket 20/50/100/200/500/1000/2000 ký tự. [metrics-smoke.txt](reports/metrics-smoke.txt) có count 301 (300 request và một warm-up) và sum 12.048 ký tự. Không đặt từng độ dài làm label.

Middleware dùng route template hoặc `unmatched`: hai URL không tồn tại được gom vào đúng một tổ hợp label `route="unmatched", status="404"`, count 2 trong bằng chứng. Dùng nguyên URL làm label sẽ sinh hàng nghìn time series khi bot quét URL lạ, làm tốn RAM và chậm truy vấn.

## 3. Benchmark chất lượng — eval

| Chỉ số | v1 | v2 ban đầu | v2 sửa KB |
|---|---|---|---|
| Accuracy | 1/23 (4.3%) | 21/23 (91.3%) | 23/23 (100.0%) |
| Avg tokens/câu | 57.5 | 108.8 | 119.0 |
| Tổng cost mô phỏng (USD) | 0.000409 | 0.000757 | 0.000836 |
| Cost/câu đúng (USD) | 0.00040935 | 3.607e-05 | 3.635e-05 |
| Quality gate | FAIL (80%) | PASS (80%) | PASS (100%), 0 regression |

Các file `eval_v1.json`, `eval_v2.json`, `eval_v2_fixed.json` dùng đúng 23 câu của đề; tắt lỗi ngẫu nhiên với `MOCK_ERROR_RATE=0` để kiểm tra nội dung. Golden dataset và evaluator không sửa. Chấm bằng keyword theo script, không phải đánh giá ngữ nghĩa độc lập hoặc chứng minh đúng trên mọi câu hỏi thực tế.

| ID sai ở v2 ban đầu | Phần thiếu | Sửa trong KNOWLEDGE_BASE |
|---|---|---|
| security-02 | Khác biệt API key/JWT, chữ ký, hết hạn | Thêm tài liệu JWT có chữ ký và expiry, so với key cố định |
| scaling-03 | HPA/autoscaler và chỉ số dùng để scale | Thêm tài liệu HPA theo CPU/memory/custom metrics, RPS, queue |

Tài liệu được bổ sung vào cả develop và production. Không hardcode câu trả lời theo ID trong dataset. v2 tăng token do thêm retrieval/context, nhưng cost trên mỗi câu đúng giảm mạnh so với v1. Bản sửa cuối tăng tổng cost nhẹ để trả đúng cả hai câu còn thiếu. Cost là mô phỏng của đề, không phải khoản tiền đã thanh toán. Mẫu eval nhỏ, một lượt và có jitter/tail ngẫu nhiên; không dùng latency của eval để kết luận tác động hiệu năng của sửa KB.

Quality gate trong CI: khởi động v2 với lỗi mock bằng 0, chờ `/health`, rồi chạy:

```bash
python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85 \
  --baseline reports/eval_v2.json --out reports/eval_ci.json
```

Giữ exit code của lệnh; không thêm `|| true`. Chỉ cho merge khi job này là required check và thành công. Đã chạy v1 so với baseline v2 ở ngưỡng 85%: có **20 regression**, exit code **1**, đúng hành vi chặn bản giảm chất lượng. [ci-gate.json](reports/ci-gate.json), [eval_v1_regression.json](reports/eval_v1_regression.json).

## 4. Observability stack — production

### 4.1. Bằng chứng và Exercise 7.4

- [x] [Grafana khi đang có tải](screenshots/grafana-dashboard.png).
- [x] [Jaeger trace chậm](screenshots/jaeger-slow-trace.png).
- [x] [Jaeger trace lỗi có exception](screenshots/jaeger-error-trace.png).
- [x] [Prometheus: hai alert hiển thị firing](screenshots/prometheus-alert-firing.png).

Stack đã chạy agent/Nginx/Prometheus/Jaeger/Grafana/Locust từ Compose. Trong các phép đo headless, dừng Grafana và Locust web để giảm áp lực RAM, vẫn bật Prometheus và Jaeger; dùng Locust headless riêng. Đợt chụp GUI chạy tải riêng, bật Grafana và xem dashboard thật; UI refresh 30 giây để giảm tải trình duyệt, Prometheus vẫn scrape 5 giây. Các số dưới đây lấy từ snapshot Prometheus của thí nghiệm A, khác thời điểm ảnh GUI.

Snapshot hai instance trước lúc pause, 2026-11-26T08:28:45.050522+00:00, 30 users/ramp 5, đang tiêm lỗi 20%:

- p95 **294.83 ms**, average **226.22 ms**. p95 cao hơn average cho thấy phần đuôi chậm hơn đa số request. Đây là quantile nội suy từ histogram phía server trong cửa sổ một phút.
- RPS theo instance: `172.20.0.4:8000` = 9.33, `172.20.0.6:8000` = 9.36. Phân phối gần đều trong cửa sổ này; chưa đủ để khẳng định luôn đều với mọi workload.
- Tokens/s: input = 1232.34, output = 676.10. Input gồm system prompt, câu hỏi và retrieved context; output mock ngắn hơn, nên input lớn hơn output.
- Gọi `/metrics` qua Nginx trả **404** đúng cấu hình chặn công khai; Prometheus scrape trực tiếp từng agent trong mạng Compose.

Truy vấn, timestamp, kết quả từng instance và trạng thái target được lưu trong [observability.json](reports/observability.json). Histogram ở server có phạm vi khác latency phía client/Locust, nên các p95 này không được dùng thay cho nhau.

Ảnh Grafana là một lượt quan sát GUI riêng: traffic 15,9 req/s, error 0,80%, p95 299,71 ms. Panel Instances up có thời điểm chỉ 1 dù Compose chạy 2 container; không coi container đang chạy đồng nghĩa target scrape thành công. Máy dùng chung tài nguyên và việc scrape có lúc timeout; cần đo thêm để khoanh nguyên nhân cụ thể.

Ảnh Alerts được chụp khi lặp lại A/D để lấy bằng chứng GUI; thời gian phát hiện ở bảng dưới vẫn lấy từ đợt đo đầu. [ui-alerts.json](reports/ui-alerts.json) ghi giai đoạn replay. [alert-screenshot.json](reports/alert-screenshot.json) lưu thời điểm file ảnh và metric ALERTS tại thời điểm đó: vẫn có hai alert firing (error và latency), trong khi trang UI còn hiển thị error và instance down từ lần cập nhật trước. Các lớp làm mới không đồng bộ từng thời điểm; không lấy thời gian phát hiện bằng cách đọc ảnh.

### 4.2. Alerts và chaos

Rules giữ nguyên: error >5% trong 1 phút, p95 >1 giây trong 2 phút, instance down trong 30 giây, cost burn >2 USD/giờ trong 2 phút. `promtool test rules` thành công; [alert-rules.txt](reports/alert-rules.txt).

| Thí nghiệm | Thay đổi | Alert quan sát | Từ yêu cầu đổi đến firing | Panel liên quan |
|---|---|---|---|---|
| A | MOCK_ERROR_RATE=0.2; 30 users/ramp 5 | AgentHighErrorRate | 101.6 giây | Error rate /ask |
| B | Không chạy riêng; slow rate đã so sánh ở mục 2.2 | Không gán kết quả | — | p95 / latency histogram |
| C | Không đổi model lớn | Không gán kết quả | — | Cost burn |
| D | docker pause 1 trong 2 instance, giữ A active | AgentInstanceDown | 41.0 giây | Target up / instance RPS |
| E | Kiểm tra v1 bằng eval offline | Quality gate FAIL; metric không đo accuracy | Không thực nghiệm alert riêng | Eval theo release |

Đã làm hai thí nghiệm bắt buộc A và D. Poll Alerts API mỗi 5 giây; thời gian trên tính đến lần đầu quan sát firing và gồm thời gian tạo lại service ở A. Lúc **2026-11-26T08:29:31.034359+00:00**, `AgentHighErrorRate` và `AgentInstanceDown` cùng firing. Instance đã được unpause sau khi lấy bằng chứng.

Lần pause đầu dùng tên instance cũ đã bị Compose xóa khi giảm replica. Lệnh không thực hiện được; chọn lại container đang chạy và đo D từ lần pause hợp lệ. Cả hai lần và cách xử lý có trong JSON, không tính lần thất bại là phép đo thành công.

`LLMCostBurnRateHigh` cũng đã xuất hiện do tải ở benchmark trước đó; không gán thời gian phát hiện này cho việc đổi model hoặc thí nghiệm A. Nó dùng cửa sổ 5 phút nên có thể tiếp tục firing sau khi tải giảm. Đây vẫn là tiền mô phỏng.

v1 có thể trả HTTP 200 nhanh nhưng nội dung sai, nên metric HTTP/cost không phát hiện được suy giảm chất lượng. Cần chạy golden eval trong CI trước release, canary theo phiên bản, và đánh giá định kỳ một mẫu phản hồi có nhãn trong production; thêm quality SLI riêng khi có nhãn đáng tin cậy.

### 4.3. Debug bằng trace — Exercise 7.5

Trace chậm dài nhất trong các log `llm_call` của đợt chaos mà Jaeger vẫn lưu: `3815ac88954c76c33e184d321332c130`. Tổng span server **1715.693 ms**; `chat mock-llm-small` chiếm **1695.126 ms (98.80%)**. Retrieval mất 15.379 ms. `agent.run` là span cha bao cả retrieval và LLM, không cộng duration cha/con vì chúng chồng lặp.

Dòng log khớp trace:

```json
{"ts": "2026-11-26T08:27:51.765839+00:00", "level": "INFO", "service": "observable-agent", "instance": "07a3a38c43db", "event": "llm_call", "trace_id": "3815ac88954c76c33e184d321332c130", "span_id": "059b6dbde25bb83d", "request_id": "ef44cd287917", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 76, "output_tokens": 39, "cost_usd": 3.5e-05, "llm_ms": 1693.1}
```

Trace lỗi: `2f24bdd1a7d54c33b33a966608d27e92`. Có **2 event `exception`** trong các span LLM/agent, lỗi mock upstream 503; [trace-error.json](reports/trace-error.json). Stack trace nằm trong telemetry nội bộ, response HTTP chỉ trả thông báo dịch vụ upstream không khả dụng.

```json
{"ts": "2026-11-26T08:26:08.503189+00:00", "level": "INFO", "service": "observable-agent", "instance": "07a3a38c43db", "event": "llm_error", "trace_id": "2f24bdd1a7d54c33b33a966608d27e92", "span_id": "11901a4abcc95526", "request_id": "43246a34c2dc", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

JSON của trace chậm: [trace-slow.json](reports/trace-slow.json); hai log được chọn: [trace-evidence.json](reports/trace-evidence.json). Hai ảnh Jaeger ở trên mở đúng các trace ID này.

## 5. Benchmark scaling — Locust headless

Cả hai lượt dùng `-u 100 -r 10 -t 2m`, cùng tập câu hỏi và cấu hình mock small/error 1%/slow 3%, một worker mỗi container. Prometheus và Jaeger hoạt động, Grafana không chạy trong phép đo. Bảng lấy riêng dòng **POST /ask** trong CSV cuối cùng, không trộn với `/health` hoặc `Aggregated`.

| Instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 34.73 | 420 | 5700 | 10000 | 128/3928 (3.26%) |
| 3 | 46.84 | 230 | 2600 | 4200 | 59/5583 (1.06%) |

Từ 1 lên 3 instance, RPS tăng **1.35 lần**, p95 giảm **54.39%**. Có cải thiện nhưng chưa tuyến tính và p95 vẫn cao hơn SLO 500 ms. Mỗi container bị giới hạn CPU, trong khi host 8 GB RAM dùng chung với Docker và ứng dụng khác. Tải một instance còn có 504 từ Nginx ngoài lỗi mock 503; không quy mọi failure cho tỷ lệ lỗi được tiêm. Cần thêm đo CPU throttling, event-loop lag, RSS/host swap và nhiều lần chạy để xác định nút thắt chính xác.

Nguồn: [scale_1_stats.csv](benchmark-results/scale_1_stats.csv), [scale_3_stats.csv](benchmark-results/scale_3_stats.csv), kèm failures/exceptions/history CSV nguyên bản. Locust trả exit code 1 khi có request thất bại; file số đo vẫn được giữ và báo cáo đúng. `-t 2m` là thời gian tải được yêu cầu; thời gian chạy lệnh ngoài còn gồm khởi động và dừng container.

## 6. Kết luận và giới hạn

1. Tăng concurrency hoặc replica cần đo lại: p95/p99 và lỗi bộc lộ hàng đợi mà average che đi; máy phát tải và máy chủ dùng chung tài nguyên là một giới hạn của phép đo này.
2. Chất lượng và độ sẵn sàng khác nhau: v1 HTTP 200 vẫn chỉ đúng 1/23 câu. Eval phát hiện regression mà các alert hạ tầng không thấy.
3. Metrics giúp nhận biết ảnh hưởng tổng thể; trace phân biệt thời gian retrieval/LLM; trace ID nối request với log để kiểm tra nguyên nhân. Alert cần cả ngưỡng và thời gian duy trì để tránh báo động do spike.

Nếu vận hành thật, bổ sung độ dài queue, CPU throttling/event-loop lag, token và cost thực từ provider, số request bị rate/budget guard chặn, quality theo phiên bản và synthetic checks cho public URL. Benchmark mock không chứng minh độ trễ hoặc giá của LLM thật.

Đã chụp đủ bốn ảnh Part 7 trong giao diện thật và ba ảnh deploy. Agent Part 6 chạy tại https://day14-agent-r4n7.onrender.com; bằng chứng kiểm tra public và giới hạn Render Free trong [DEPLOYMENT.md](DEPLOYMENT.md). Các SLO trượt ở tải cao được giữ nguyên trong báo cáo; hoàn tất hồ sơ không có nghĩa mọi cấu hình tải đều đạt SLO.
