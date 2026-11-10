# Hồ sơ ứng viên – Light Human

Web app nội bộ: tải CV gốc lên → AI (OpenAI) đọc và trích xuất → người dùng duyệt/sửa → xuất PDF chuẩn Light Human.
Quy chuẩn hồ sơ: [SKILL.md](SKILL.md). Hệ thống giao diện: [docs/design-system.md](docs/design-system.md).
Dữ liệu cá nhân (bản nháp, chờ pháp chế): [docs/data-privacy-policy.md](docs/data-privacy-policy.md). Đề xuất dài hạn: [docs/proposals.md](docs/proposals.md).

## Cài đặt (Windows, làm 1 lần)

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Chép `.env.example` thành `.env` và điền `OPENAI_API_KEY`. Các biến còn lại đều có mặc định, xem mục **Cấu hình**.

Người phát triển (thêm công cụ test, đo độ phủ): `python -m pip install -r requirements-dev.txt`.
Phiên bản thư viện được ghim trong `requirements.txt` — nâng cấp thì đổi số, cài lại, chạy `pytest`.
Không dùng `opencv-python-headless` bản 5.x (đã bỏ bộ nhận diện khuôn mặt mà app dùng để cắt ảnh chân dung).

## Chạy

```powershell
python -m streamlit run app.py
```

Trình duyệt mở `http://localhost:8501`.

### Bảo mật khi chạy

- App **chỉ mở trên chính máy đang chạy** (`server.address = "localhost"` trong `.streamlit/config.toml`).
  Máy khác trong mạng không truy cập được — app không có đăng nhập, ai mở được là dùng được API key và xem được CV.
- **Mở cho mạng nội bộ:** đừng đổi `address` thành `0.0.0.0`. Hãy để app ở `localhost` và đặt một
  reverse proxy có xác thực phía trước (ví dụ Caddy/Nginx với đăng nhập cơ bản, hoặc Cloudflare Access),
  chỉ proxy được mở ra mạng.
- File tải lên tối đa **20 MB** (`server.maxUploadSize`, khớp `MAX_UPLOAD_MB`).
- PDF đã xuất trong `data/output` **tự xoá sau 30 ngày** (đổi bằng `OUTPUT_RETENTION_DAYS`, `0` = tắt), chạy mỗi lần khởi động app.
- Chạy trong Docker / bằng root mà Chromium không khởi động được: đặt `CHROMIUM_NO_SANDBOX=1`.
  Trên máy Windows bình thường **không** đặt biến này (giữ sandbox).
- Log không chứa họ tên ứng viên: tên file CV được ghi dạng `pdf#1a2b3c4d`.
- **Nhiều người dùng cùng lúc:** tối đa 2 lượt dựng PDF chạy song song (`RENDER_MAX_CONCURRENT`), người tới sau thấy
  "Đang xếp hàng dựng PDF" và được dựng tự động khi tới lượt. Máy chạy app cho ~30 người nên còn trống ≥ 4 GB RAM.

## Cách dùng

1. **Cột trái – khung chat:** đính kèm file CV (PDF/ảnh/DOCX), nhập tên dự án (và vị trí nếu muốn) → bấm **Gửi CV** (30–90 giây, tối đa 180 giây).
   Trợ lý trả lời: đã bỏ gì, lương mong muốn, hệ thống tự lập, lưu ý tuyển dụng, có lấy được ảnh chân dung không;
   cuối khung là **tin nhắn tóm tắt** để sao chép.
2. **Cột phải – Hồ sơ PDF:** PDF được dựng tự động và hiển thị để xem.
   - Tab **Chỉnh sửa nội dung**: sửa từng mục, thay/bỏ ảnh. Các ô dạng bảng: mỗi dòng 1 mục, cột cách nhau bằng `|`
     (ô có chứa dấu `|` hiện là `\|`). Sửa xong bấm **Cập nhật PDF**.
   - Tab **CV gốc**: đối chiếu với file gốc.
3. Tick 2 ô xác nhận → bấm **Tải PDF** (bản sao lưu vào `data/output`; trùng tên thì thêm hậu tố giờ, không ghi đè).

App **khoá** nút Tải PDF khi: còn số điện thoại / email / link / ngày sinh (trong nội dung, tên dự án, vị trí hoặc
trong chính file PDF), hồ sơ chưa hợp lệ, hoặc PDF chưa cập nhật theo nội dung mới — và chỉ ra chỗ cần sửa.

## Cấu hình

| Ở đâu | Nội dung |
|---|---|
| `.env` | Bí mật và tham số chạy (mẫu: `.env.example`). Không đưa lên git. |
| `config/company.toml` | Tên, địa chỉ, SĐT, email, website Light Human + câu footer, ghi chú người tham chiếu. **Nguồn duy nhất**: header PDF, footer và bộ lọc thông tin nhạy cảm cùng đọc từ đây — đổi SĐT công ty chỉ cần sửa file này. |
| `prompts/` | Câu lệnh gửi AI (`system_prompt.txt`, `user.txt`, `fix_json.txt`) + cấu trúc dữ liệu (`schema.json`, phải khớp `models.py`). Số phiên bản ở `version.txt`; phiên bản (kèm mã băm nội dung) được ghi vào metadata *Keywords* của mỗi PDF. |
| `infra/tokens.py` | Màu, chữ, khoảng cách, lề trang PDF — dùng chung cho web app, mẫu PDF, footer. Xem `docs/design-system.md`. |
| `.streamlit/config.toml` | Theme + `[server]` (localhost, giới hạn upload). Màu phải khớp `infra/tokens.py` (test kiểm tra). |

Biến `.env` (bỏ trống = mặc định):

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `OPENAI_API_KEY` | — | Bắt buộc |
| `OPENAI_MODEL` / `OPENAI_MAX_TOKENS` | `gpt-4.1` / `8000` | Model và độ dài kết quả tối đa |
| `OPENAI_TIMEOUT` / `OPENAI_MAX_RETRIES` / `OPENAI_TOTAL_DEADLINE` | `90` / `1` / `180` | Giây mỗi lần gọi · số lần SDK tự thử lại · hạn tổng cho 1 CV |
| `OPENAI_STORE` | `1` | `1` = OpenAI lưu phản hồi (mặc định của API; sửa JSON không cần gửi lại file). `0` = không lưu |
| `MAX_UPLOAD_MB` | `20` | Phải khớp `server.maxUploadSize` |
| `OUTPUT_RETENTION_DAYS` | `30` | Số ngày giữ PDF đã xuất (`0` = không tự xoá) |
| `OUTPUT_DIR` / `LOG_DIR` | `data/output` / `data/logs` | Thư mục bản sao PDF / file log |
| `LOGO_PATH` / `LOGO_HEADER_PATH` | `assets/logo.png` / `Logo.png` | Logo trong PDF / logo header (không có thì dùng logo PDF) |
| `COMPANY_CONFIG` | `config/company.toml` | File thông tin công ty |
| `RENDER_TIMEOUT` | `120` | Giây tối đa cho một lần Chromium dựng PDF |
| `RENDER_MAX_CONCURRENT` | `2` | Số lượt dựng PDF chạy cùng lúc trên toàn app; người tới sau **xếp hàng** (mỗi lượt ~300–400 MB RAM) |
| `RENDER_QUEUE_TIMEOUT` | `300` | Giây tối đa một người chờ tới lượt dựng PDF |
| `CHROMIUM_NO_SANDBOX` | trống | Chỉ đặt `1` khi chạy Docker/root |

## Log

- `data/logs/app.log` (app) và `data/logs/render_worker.log` (tiến trình dựng PDF), xoay vòng 1 MB × 5 file.
- Mỗi lần gửi CV có một mã `run_id` 8 ký tự, ví dụ `[a1b2c3d4]`. Tìm mã này trong cả hai file để xem trọn một lượt xử lý.
- Không ghi nội dung CV, họ tên hay tên file gốc.

## Cấu trúc mã nguồn

Mã chia 4 lớp, mỗi lớp một thư mục; lớp trên gọi lớp dưới, không gọi ngược:

```text
app.py              điểm khởi chạy Streamlit (giữ ở gốc)
ui/                 GIAO DIỆN       components.py + styles.css · profile_form.py · preview.py · table_text.py
core/               NGHIỆP VỤ       pipeline.py · pdf_status.py
services/           XỬ LÝ CHUYÊN MÔN
  ai/               extract.py · models.py
  pdf/              render.py · render_worker.py · pdf_utils.py · template.html
  privacy/          checks.py
infra/              HẠ TẦNG          settings.py · tokens.py · logging_setup.py · storage.py
config/ prompts/ assets/ docs/ tests/
```

| File | Việc |
|---|---|
| `app.py` | Điều phối giao diện + session state (2 cột: chat / PDF) |
| `ui/components.py`, `ui/styles.css` | HTML + CSS các thành phần giao diện (dữ liệu từ CV luôn được escape) |
| `ui/profile_form.py` | Form sửa hồ sơ (mỗi loại mục một hàm) + ảnh chân dung |
| `ui/preview.py` | Xem trước PDF và CV gốc |
| `ui/table_text.py` | Đổi bảng ↔ chữ cho các ô dạng bảng trong form |
| `core/pipeline.py` | Nghiệp vụ: đọc CV, dựng PDF (hàng đợi), lưu bản sao, kiểm tra cấu trúc, tin nhắn tóm tắt |
| `core/pdf_status.py` | Luật khoá/mở nút Tải PDF và nhãn trạng thái |
| `services/ai/extract.py` | Gửi CV cho OpenAI, nhận JSON, giới hạn thời gian, sửa JSON hỏng (chạy thử: `python -m services.ai.extract "duong/dan/cv.pdf" --project "X"`) |
| `services/ai/models.py` | Kiểm tra cấu trúc JSON (phải khớp `prompts/schema.json`) |
| `services/pdf/template.html` | Mẫu trình bày PDF (CSS theo SKILL.md mục 5) |
| `services/pdf/render.py` | Dựng HTML → PDF, tên file, chọn cỡ chữ, ảnh chân dung (OpenCV tìm khuôn mặt, cắt 29:38) |
| `services/pdf/render_worker.py` | Chạy Chromium xuất PDF trong tiến trình riêng (`python -m services.pdf.render_worker`) |
| `services/pdf/pdf_utils.py` | Đo bố cục PDF (số trang, độ đầy trang cuối) |
| `services/privacy/checks.py` | Quét thông tin nhạy cảm + checklist PDF |
| `infra/settings.py` | Đọc cấu hình chung: thông tin công ty, đuôi file, đường dẫn, phiên bản prompt, hàng đợi |
| `infra/tokens.py` | Design tokens (`python -m infra.tokens` in bảng token cho docs) |
| `infra/logging_setup.py` | Cấu hình log + run_id + che tên file |
| `infra/storage.py` | Tự xoá PDF hết hạn, tên bản sao không ghi đè |

**Vì sao xuất PDF bằng tiến trình riêng?** Streamlit và Playwright đều cần "event loop" riêng; chạy chung dễ treo.
Tách Playwright ra một chương trình nhỏ (`services/pdf/render_worker.py`) chạy độc lập là cách ổn định nhất.

## Chạy test

```powershell
python -m pytest -q                      # toàn bộ (~200 test, có dựng PDF bằng Chromium thật)
python -m pytest -q -m "not slow"        # bỏ các test chạy Chromium, nhanh hơn
python -m coverage run -m pytest -q && python -m coverage report    # độ phủ từng module
```

Test không gọi OpenAI thật (dùng client giả) và chỉ dùng hồ sơ giả `tests/fixtures/fake_candidate.json` khi dựng PDF.

## Sự cố thường gặp

- **"DLL load failed ... Application Control policy has blocked this file"**: Windows Smart App Control chặn một số
  thư viện (pandas, pyarrow — Streamlit cài kèm). App không dùng tới tính năng cần chúng (vd không dùng `st.data_editor`).
- **"API key OpenAI không hợp lệ"**: kiểm tra `OPENAI_API_KEY` trong `.env`.
- **"Hết thời gian chờ phản hồi từ OpenAI"**: mạng chậm hoặc OpenAI quá tải; gửi lại sau ít phút, hoặc tăng `OPENAI_TOTAL_DEADLINE`.
- **"Trình dựng PDF (Chromium) gặp lỗi"**: chạy lại `python -m playwright install chromium`; chi tiết lỗi nằm trong `data/logs/`.
- **App không khởi động sau khi sửa `config/company.toml`**: file sai cú pháp TOML — kiểm tra dấu ngoặc kép và dấu `=`.
- Đổi model AI: đặt `OPENAI_MODEL=...` trong `.env`.
