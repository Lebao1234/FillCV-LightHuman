---
name: senior-architect
description: Kiến trúc của dự án FillCV-LightHuman - 4 lớp ui/core/services/infra, hợp đồng của bộ trích xuất CV, tiến trình dựng PDF, bố cục repo và Docker. Dùng khi thêm tính năng hoặc module mới, quyết định đặt code ở đâu, thêm bộ trích xuất, đổi cách triển khai, di chuyển thư mục, hoặc đánh giá một đề xuất thiết kế.
---

# Kiến trúc — FillCV-LightHuman

App nội bộ một tiến trình Python (Streamlit): tải CV lên → bộ trích xuất chạy trên máy chủ dựng hồ sơ JSON → nhân viên duyệt và sửa → xuất PDF đã bỏ thông tin liên hệ của ứng viên. Không gọi dịch vụ ngoài.

## Bố cục repo

```
(gốc)    README.md  CLAUDE.md  .gitignore  docker-compose.yml  .github/  docs/  data/
system/  mã nguồn, Dockerfile, .dockerignore, requirements*.txt, .streamlit/, tests/
```

- `system/` là build context của Docker và thư mục làm việc của mọi lệnh Python và job CI.
- `PROJECT_ROOT` (`infra/settings.py`) trỏ tới `system/`. Các thư mục là namespace package, không có `__init__.py`.
- Đổi tên hoặc di chuyển `system/` thì phải sửa cùng lúc: `.github/workflows/ci-cd-web-app.yml`, `.github/dependabot.yml`, `docker-compose.yml`, `README.md`, `CLAUDE.md`.

## Bốn lớp

Phụ thuộc chỉ đi xuống. Lớp dưới không import lớp trên.

| Lớp | Thư mục | Trách nhiệm |
|---|---|---|
| Giao diện | `app.py`, `ui/` | Điều phối Streamlit, `session_state`, HTML/CSS |
| Nghiệp vụ | `core/` | `pipeline.py`: đọc CV, dựng PDF, lưu bản sao. `pdf_status.py`: luật mở nút Tải PDF |
| Chuyên môn | `services/` | `extraction/`, `pdf/`, `privacy/`, `ai/models.py` (schema Pydantic) |
| Hạ tầng | `infra/` | `settings.py`, `tokens.py`, `logging_setup.py`, `storage.py` |

Chọn nơi đặt code mới:

- Hiển thị hoặc nhập liệu → `ui/`.
- Thứ tự các bước, quyết định cho phép hay chặn → `core/`.
- Đọc file, dựng PDF, quét thông tin nhạy cảm → `services/`.
- Cấu hình, log, lưu trữ, token giao diện → `infra/`.

## Ràng buộc không được phá

**Một tiến trình duy nhất.** Trạng thái nằm trong bộ nhớ tiến trình: hai semaphore trong `core/pipeline.py` giới hạn số lượt đọc CV và dựng PDF cho mọi phiên (`EXTRACT_MAX_CONCURRENT`, `RENDER_MAX_CONCURRENT`, mặc định 2). Chạy nhiều bản sao sau load balancer sẽ làm mất giới hạn này và có thể cạn RAM. Muốn mở rộng thì phải thiết kế lại hàng đợi trước.

**Dựng PDF ở tiến trình riêng.** `render.build_pdf` gọi `python -m services.pdf.render_worker` với `cwd=PROJECT_ROOT`, vì API đồng bộ của Playwright xung đột với event loop của Streamlit. Không gọi Playwright trực tiếp trong tiến trình app. Cả ba cỡ chữ được dựng trong một lần mở Chromium.

**Hợp đồng bộ trích xuất** (`services/extraction/base.py`):
- Trả `ExtractionResult(cv, warnings, confidence, stages, backend)`.
- `cv` phải khớp `CVData` đúng từng trường; schema cấm trường thừa, nên độ tin cậy và cảnh báo đi trong `ExtractionResult`, không nằm trong JSON.
- Khai báo `stages` và gọi `progress(stage.key)` khi bắt đầu mỗi giai đoạn (dùng `base.stage_run`). Màn hình chờ chỉ hiện giai đoạn thật.
- Đăng ký backend mới trong `base.BACKENDS`; chọn bằng biến môi trường `CV_EXTRACTOR`.
- `read_cv` luôn kiểm tra lại kết quả bằng `CVData`, bất kể backend nào.

**Bộ đọc theo luật** (`services/extraction/rules/`): mỗi giai đoạn một module (`pdf_text`, `sections`, `personal`, `content`, `analysis`, `translation`); thứ tự chạy và danh sách giai đoạn khai báo trong `extractor.py`. Thêm bước xử lý thì thêm module và khai báo giai đoạn, không nhồi vào module có sẵn. Phiên bản bộ đọc gồm `version` và hash của `config/extraction_rules.toml`.

**Mẫu PDF phải giữ đúng `docs/SKILL.md`.** Đụng tới `render.py`, `template.html`, `template.css` hoặc token PDF thì phải so ảnh từng trang trước và sau trên hồ sơ giả. Thay đổi làm PDF khác đi là đổi chuẩn hồ sơ, cần người phụ trách nghiệp vụ duyệt.

**Nguồn duy nhất.** Mỗi thông tin chỉ có một nơi gốc; nơi khác phải khớp theo:

| Nguồn gốc | Phải khớp |
|---|---|
| `infra/tokens.py` | `.streamlit/config.toml` (màu), `ui/styles.css`, bảng trong `docs/design-system.md` |
| `infra/settings.MAX_UPLOAD_MB` | `server.maxUploadSize` trong `.streamlit/config.toml` |
| `services/ai/models.py` | `prompts/schema.json` |
| `config/company.toml` | header và footer PDF, danh sách được phép trong `services/privacy/checks.py` |
| `tokens.PDF_MARGIN_MM` | lề `@page` và footer của Chromium |

## Triển khai

- Hỗ trợ: máy nội bộ hoặc VPS chạy Docker, đặt sau Cloudflare Access hoặc reverse proxy có xác thực. App không có đăng nhập.
- Không hỗ trợ: Cloudflare Workers/Pages, hay nền tảng serverless nào khác; app cần tiến trình Python chạy lâu và Chromium.
- `server.address` giữ `localhost`; chỉ container mới nghe `0.0.0.0`, và cổng publish phải gắn với `127.0.0.1`.
- Ghim `opencv-python-headless<5`; bản 5.x bỏ Haar cascade dùng để cắt ảnh chân dung.

## Khi đánh giá một đề xuất

Trả lời bốn câu trước khi đồng ý:

1. Dữ liệu CV có rời máy chủ không? Nếu có thì từ chối; đây là ràng buộc của dự án.
2. Có cần nhiều hơn một tiến trình hay một bản sao không? Nếu có, hàng đợi và cache dùng chung xử lý ra sao?
3. PDF thành phẩm có đổi không? Nếu có, ai duyệt?
4. Thay đổi nằm ở lớp nào, và có buộc lớp dưới biết về lớp trên không?

Đưa ra một khuyến nghị kèm lý do và cái giá phải trả, không liệt kê mọi phương án.
