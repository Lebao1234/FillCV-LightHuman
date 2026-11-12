---
name: senior-security
description: Checklist bảo mật và bảo vệ dữ liệu cá nhân của dự án FillCV-LightHuman (app xử lý CV ứng viên). Dùng khi review bảo mật, sửa code đụng tới tải file, dựng PDF, log, lưu trữ, Docker, CI/CD, hoặc trước khi commit, push và triển khai.
---

# Bảo mật — FillCV-LightHuman

Tài sản cần bảo vệ là dữ liệu cá nhân của ứng viên: CV gốc, hồ sơ PDF đã xuất, họ tên, thông tin liên hệ. App không có đăng nhập và không gọi dịch vụ ngoài.

## Nguyên tắc không được phá

1. **CV không rời máy chủ.** Không thêm lệnh gọi API, dịch vụ AI, analytics hay CDN nhận dữ liệu CV.
2. **Không có dữ liệu thật trong repo.** Repo có thể công khai. Test, fixture, ví dụ trong tài liệu và commit chỉ dùng hồ sơ giả. Không chép nội dung CV thật vào code, log, tài liệu hay câu trả lời.
3. **App chỉ nghe trên localhost.** `server.address = "localhost"` trong `.streamlit/config.toml`. Mở cho người khác dùng thì đặt sau Cloudflare Access hoặc reverse proxy có xác thực.
4. **Không tải được PDF khi còn thông tin liên hệ.** Luật khoá nút Tải nằm ở `core/pdf_status.py`; không thêm đường tắt.

## Checklist khi review

**Dữ liệu và git**
- [ ] `git status` không có file trong `data/`, file `.pdf`, `.docx`, `.env`, `.log`, `.pem`, `.key` chờ commit.
- [ ] `.gitignore` ở gốc repo có `data/` (áp dụng cho cả `data/` và `system/data/`).
- [ ] Fixture và ví dụ mới là dữ liệu bịa, không sửa từ CV thật.

**Đầu vào (file tải lên)**
- [ ] File đi qua `extraction.check_file` (rỗng, quá `MAX_UPLOAD_MB`) trước mọi xử lý.
- [ ] PDF dài hơn `MAX_CV_PAGES` rơi về khung nhập tay, không xử lý toàn bộ.
- [ ] Code mới đọc file nén hoặc ảnh có giới hạn kích thước sau giải nén.
- [ ] Tên file do người dùng đặt không được ghép vào đường dẫn; tên file xuất đi qua `render.build_filename`.

**Hiển thị**
- [ ] Mọi chữ từ CV ghép vào HTML giao diện đi qua `E()` (`html.escape`) trong `ui/components.py`.
- [ ] `services/pdf/template.html` không dùng `|safe`; filter `bold` escape trước khi thêm thẻ.
- [ ] `st.markdown(..., unsafe_allow_html=True)` chỉ nhận HTML do `ui/components.py` dựng.

**Thông tin nhạy cảm trong hồ sơ**
- [ ] Trường mới của hồ sơ được `scan_pii` quét (mọi chuỗi trong JSON, trừ `SKIP_FIELDS`).
- [ ] Chữ mới đưa vào PDF ngoài hồ sơ (như tên dự án, vị trí) được thêm vào `scan_pii_export`.
- [ ] PDF thành phẩm được quét lại bằng `scan_pdf`.
- [ ] Thông tin công ty được phép xuất hiện lấy từ `config/company.toml`, không viết thẳng vào code.

**Log**
- [ ] Không ghi nội dung CV, họ tên, tên file gốc. Tên file dùng `mask_filename()`.
- [ ] Log chỉ có số lượng, thời gian, mã `run_id`, và mô tả do code soạn.
- [ ] Traceback và đường dẫn máy chỉ vào log, không hiện trên giao diện.

**Tiến trình con và Chromium**
- [ ] `subprocess.run` nhận danh sách tham số, không `shell=True`, có `timeout`.
- [ ] Chromium giữ sandbox; `CHROMIUM_NO_SANDBOX=1` chỉ đặt trong Docker.
- [ ] HTML đưa cho Chromium không tải tài nguyên từ mạng.

**Docker và triển khai**
- [ ] Cổng publish gắn `127.0.0.1` (`"127.0.0.1:8501:8501"`), không phải `"8501:8501"`.
- [ ] Container chạy bằng user thường (`appuser`).
- [ ] `data/` không nằm trong image (`.dockerignore`).
- [ ] Thư mục `data/output` trên máy chủ chỉ người vận hành đọc được.

**CI/CD**
- [ ] Workflow giữ `permissions: contents: read`; job nào cần thêm thì tự khai báo.
- [ ] Bí mật chỉ nằm trong GitHub Secrets, không in ra log.
- [ ] Job `hygiene` vẫn chặn `data/`, `.env`, khoá, và PDF ngoài `assets`, `docs`, `tests/fixtures`.

## Điểm yếu đã biết

Kiểm tra lại trước khi coi là còn đúng; sửa xong mục nào thì xoá mục đó khỏi danh sách.

| Mức | Vấn đề | Nơi sửa |
|---|---|---|
| Cao | `docker-compose.yml` publish `"8501:8501"`, mở app ra toàn mạng mà không có đăng nhập | `docker-compose.yml` |
| Trung bình | Bộ quét không chặn địa chỉ, số CCCD, tình trạng hôn nhân; các mục này chỉ được bỏ theo nhãn lúc đọc CV | `services/privacy/checks.py` |
| Trung bình | PDF hết hạn chỉ được xoá lúc khởi động app | `app.py` (`_cleanup_on_startup`), `infra/storage.py` |
| Trung bình | Chromium chạy không sandbox trong Docker | `Dockerfile` |
| Thấp | Ảnh trong DOCX được giải nén không giới hạn kích thước | `services/pdf/render.py` (`extract_photo_from_docx`) |
| Thấp | Loại file chỉ kiểm theo đuôi | `services/extraction/base.py` (`check_file`) |
| Thấp | `pip-audit` trong CI chưa chặn pipeline; action ghim theo tag | `.github/workflows/ci-cd-web-app.yml` |

## Cách báo cáo

- Xếp theo mức độ, nghiêm trọng nhất trước. Mỗi mục ghi: vấn đề, file và dòng, ai khai thác được và bằng cách nào, cách sửa.
- Phân biệt điều đã xác minh (đã đọc code hoặc đã chạy lệnh) với điều suy đoán.
- Nêu cả những phần đã kiểm tra và thấy ổn.
- Không tự sửa khi chỉ được yêu cầu kiểm tra. Thay đổi làm lộ hoặc xoá dữ liệu (đổi quyền repo, xoá lịch sử git, xoá file trong `data/`) phải hỏi trước.
