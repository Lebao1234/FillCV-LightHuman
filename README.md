# 📄 Hồ sơ ứng viên – Light Human

> Web app nội bộ dành cho **Light Human** (công ty tuyển dụng nhân sự): tải CV gốc lên → bộ trích xuất chạy **ngay trên máy chủ** dựng hồ sơ → người dùng duyệt/sửa → xuất PDF chuẩn thương hiệu Light Human.

**🔒 Dữ liệu CV không rời máy chủ** — không gọi bất kỳ dịch vụ AI hay API bên ngoài nào.

---

## ✨ Tính năng chính

- **Trích xuất tự động** — Bộ đọc PDF theo luật (`rules`): đọc chữ + cỡ chữ/in đậm, tách mục, tách kinh nghiệm/học vấn, lọc thông tin nhạy cảm, lập ô số liệu và lưu ý tuyển dụng
- **Bảo mật thông tin ứng viên** — Tự động xoá SĐT, email, địa chỉ, link cá nhân, nơi sinh, tình trạng hôn nhân; chỉ giữ năm sinh; lương mong muốn chỉ báo nội bộ
- **Xuất PDF chuẩn thương hiệu** — Header Light Human, font Times New Roman, ảnh chân dung cắt tự động (nhận diện khuôn mặt OpenCV), tự chọn cỡ chữ phù hợp
- **Kiểm tra trước khi tải** — Khoá nút tải PDF nếu còn sót thông tin nhạy cảm (quét cả dữ liệu lẫn file PDF)
- **Giao diện 2 cột** — Trái: chat + tải CV; Phải: xem trước PDF + chỉnh sửa nội dung
- **Hàng đợi thông minh** — Giới hạn số lượt dựng PDF / đọc CV chạy đồng thời, tự xếp hàng khi đông
- **Tự dọn dẹp** — PDF đã xuất tự xoá sau 30 ngày (tuỳ chỉnh được)

---

## 📋 Mục lục

- [Cài đặt](#-cài-đặt)
- [Chạy](#-chạy)
- [Cách dùng](#-cách-dùng)
- [Cấu hình](#-cấu-hình)
- [Cấu trúc mã nguồn](#-cấu-trúc-mã-nguồn)
- [Chạy test](#-chạy-test)
- [Bảo mật](#-bảo-mật)
- [Log](#-log)
- [Sự cố thường gặp](#-sự-cố-thường-gặp)
- [Tài liệu liên quan](#-tài-liệu-liên-quan)

---

## 🛠 Cài đặt

**Yêu cầu:** Python 3.13+, Windows

```powershell
# Cài thư viện
python -m pip install -r requirements.txt

# Cài trình duyệt Chromium (dùng để dựng PDF)
python -m playwright install chromium
```

> **Lưu ý:**
> - Phiên bản thư viện được ghim trong `requirements.txt` — nâng cấp thì đổi số, cài lại, chạy `pytest`
> - **Không dùng** `opencv-python-headless` bản 5.x (đã bỏ bộ nhận diện khuôn mặt Haar cascade mà app dùng để cắt ảnh chân dung)

**Cho người phát triển** (thêm pytest, coverage, python-docx):

```powershell
python -m pip install -r requirements-dev.txt
```

---

## 🚀 Chạy

```powershell
python -m streamlit run app.py
```

Trình duyệt sẽ mở `http://localhost:8501`.

---

## 📖 Cách dùng

### Bước 1 — Gửi CV

Ở **cột trái (khung chat)**: đính kèm file CV (PDF / ảnh / DOCX), nhập tên dự án (và vị trí nếu muốn) → bấm **Gửi CV**.

- Khung bên phải hiện **các bước đang chạy thật** của bộ trích xuất, rồi bước dựng PDF
- Trợ lý trả lời: đã bỏ gì, lương mong muốn, hệ thống tự lập, lưu ý tuyển dụng, **phần cần xem lại**, có lấy được ảnh chân dung không; cuối khung là **tin nhắn tóm tắt** để sao chép

> **Bộ trích xuất mặc định** là `rules` (đọc PDF theo luật, không AI, không mạng). CV không đọc tự động được (DOCX/ảnh, PDF scan, chữ lỗi font) → **khung hồ sơ trống để nhập tay** kèm lý do. Hiện chỉ đọc tự động **PDF có lớp chữ** (chưa OCR).

### Bước 2 — Xem & sửa hồ sơ

Ở **cột phải**:
- **Tab "Chỉnh sửa nội dung"**: sửa từng mục, thay/bỏ ảnh. Phần không chắc chắn có nhãn **Cần xem**. Các ô dạng bảng: mỗi dòng 1 mục, cột cách nhau bằng `|` (ô chứa `|` hiện là `\|`). Sửa xong bấm **Cập nhật PDF**
- **Tab "CV gốc"**: đối chiếu với file gốc

### Bước 3 — Tải PDF

Tick 2 ô xác nhận → bấm **Tải PDF** (bản sao lưu vào `data/output`; trùng tên thì thêm hậu tố giờ, không ghi đè).

> **Nút Tải PDF bị khoá khi:** còn số điện thoại / email / link / ngày sinh (trong nội dung, tên dự án, vị trí hoặc trong chính file PDF), hồ sơ chưa hợp lệ, hoặc PDF chưa cập nhật theo nội dung mới — app sẽ chỉ ra chỗ cần sửa.

---

## ⚙ Cấu hình

### File cấu hình

| File | Nội dung |
|---|---|
| `config/company.toml` | Tên, địa chỉ, SĐT, email, website Light Human + câu footer, ghi chú người tham chiếu. **Nguồn duy nhất**: header PDF, footer và bộ lọc thông tin nhạy cảm cùng đọc từ đây — đổi SĐT công ty chỉ cần sửa file này |
| `config/extraction_rules.toml` | Bảng từ khoá của bộ đọc theo luật (viết không dấu): tiêu đề mục → loại mục, nhãn thông tin nhạy cảm cần bỏ, nhãn dòng phụ/nhóm việc, từ nhận ra công ty/chức danh/văn bằng. Nhận thêm một cách viết = thêm vào đây |
| `prompts/schema.json` | Cấu trúc JSON hồ sơ (phải khớp `services/ai/models.py`) |
| `infra/tokens.py` | Màu, chữ, khoảng cách, lề trang PDF — dùng chung cho web app, mẫu PDF, footer. Xem `docs/design-system.md` |
| `.streamlit/config.toml` | Theme Streamlit + `[server]` (localhost, giới hạn upload). Màu phải khớp `infra/tokens.py` |

### Biến môi trường

Không đặt = dùng mặc định. Dự án **không đọc** file `.env`.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `CV_EXTRACTOR` | `rules` | Bộ trích xuất CV: `rules` (đọc PDF theo luật) hoặc `manual` (luôn khung trống nhập tay). Tên + phiên bản ghi vào metadata PDF |
| `EXTRACT_MAX_CONCURRENT` | `2` | Số lượt đọc CV (trích xuất + lấy ảnh chân dung) chạy cùng lúc (người tới sau **xếp hàng**) |
| `EXTRACT_QUEUE_TIMEOUT` | `300` | Giây chờ tối đa khi xếp hàng đọc CV |
| `MAX_UPLOAD_MB` | `20` | Dung lượng tối đa file tải lên (phải khớp `server.maxUploadSize`) |
| `MAX_CV_PAGES` | `20` | Số trang tối đa của CV PDF được đọc tự động và xem trước; dài hơn → khung nhập tay, tab CV gốc chỉ vẽ các trang đầu |
| `OUTPUT_RETENTION_DAYS` | `30` | Số ngày giữ PDF đã xuất (`0` = không tự xoá) |
| `OUTPUT_DIR` | `data/output` | Thư mục lưu bản sao PDF |
| `LOG_DIR` | `data/logs` | Thư mục file log |
| `LOGO_PATH` | `assets/logo.png` | Logo trong PDF |
| `LOGO_HEADER_PATH` | `Logo.png` | Logo header (không có thì dùng logo PDF) |
| `COMPANY_CONFIG` | `config/company.toml` | File thông tin công ty |
| `RENDER_TIMEOUT` | `120` | Giây tối đa cho một lần Chromium dựng PDF |
| `RENDER_MAX_CONCURRENT` | `2` | Số lượt dựng PDF chạy cùng lúc (~300–400 MB RAM mỗi lượt) |
| `RENDER_QUEUE_TIMEOUT` | `300` | Giây tối đa chờ tới lượt dựng PDF |
| `CHROMIUM_NO_SANDBOX` | *(trống)* | Chỉ đặt `1` khi chạy Docker / root |

---

## 🏗 Cấu trúc mã nguồn

Mã chia **4 lớp**, mỗi lớp một thư mục; lớp trên gọi lớp dưới, **không gọi ngược**:

```
app.py                  ← Điểm khởi chạy Streamlit
│
├── ui/                 ← GIAO DIỆN
│   ├── components.py       HTML + CSS các thành phần
│   ├── styles.css          CSS giao diện
│   ├── profile_form.py     Form sửa hồ sơ (mỗi loại mục một hàm)
│   ├── preview.py          Xem trước PDF và CV gốc
│   └── table_text.py       Đổi bảng ↔ chữ cho ô dạng bảng
│
├── core/               ← NGHIỆP VỤ
│   ├── pipeline.py         Đọc CV → dựng PDF → lưu bản sao → tóm tắt
│   └── pdf_status.py       Luật khoá/mở nút Tải PDF
│
├── services/           ← XỬ LÝ CHUYÊN MÔN
│   ├── extraction/         Bộ trích xuất CV
│   │   ├── base.py             Interface + chọn bộ trích xuất
│   │   ├── manual.py           Bộ "nhập tay" (khung hồ sơ trống)
│   │   └── rules/              Bộ đọc PDF theo luật (mỗi giai đoạn 1 module)
│   ├── ai/
│   │   └── models.py           Cấu trúc hồ sơ Pydantic (tên thư mục giữ từ thời dùng AI)
│   ├── pdf/
│   │   ├── render.py           Dựng HTML → PDF, chọn cỡ chữ, cắt ảnh chân dung
│   │   ├── render_worker.py    Chạy Chromium xuất PDF trong tiến trình riêng
│   │   ├── pdf_utils.py        Đo bố cục PDF (số trang, độ đầy trang cuối)
│   │   ├── template.html       Mẫu Jinja của PDF
│   │   └── template.css        CSS tĩnh của PDF
│   └── privacy/
│       └── checks.py           Quét thông tin nhạy cảm + checklist PDF
│
├── infra/              ← HẠ TẦNG
│   ├── settings.py         Cấu hình chung (mặc định + biến môi trường)
│   ├── tokens.py           Design tokens (màu, cỡ chữ, khoảng cách)
│   ├── logging_setup.py    Cấu hình log + run_id + che tên file
│   └── storage.py          Tự xoá PDF hết hạn, tên bản sao không ghi đè
│
└── config/ prompts/ assets/ docs/
```

> **Quy ước:** Định danh trong code (hàm, biến, lớp, key) đặt **tiếng Anh** theo PEP 8; chữ hiển thị cho người dùng, nội dung PDF và chú thích giữ **tiếng Việt**. Các thư mục là *namespace package* (không có `__init__.py`) — luôn chạy lệnh từ **thư mục gốc** dự án.

### Vì sao xuất PDF bằng tiến trình riêng?

Streamlit và Playwright đều cần "event loop" riêng; chạy chung dễ treo. Tách Playwright ra một chương trình nhỏ (`services/pdf/render_worker.py`) chạy độc lập là cách ổn định nhất.

---

## 🧪 Chạy test

```powershell
# Toàn bộ (~260 test, có dựng PDF bằng Chromium thật)
python -m pytest -q

# Bỏ các test chạy Chromium, nhanh hơn
python -m pytest -q -m "not slow"

# Đo độ phủ từng module
python -m coverage run -m pytest -q && python -m coverage report
```

- Test chỉ dùng hồ sơ giả (`tests/fixtures/`, `tests/synthetic_cvs.py`); bộ trích xuất được thay bằng bản giả qua fixture `stub_extractor`
- **Không bao giờ** dùng CV thật trong test/fixture/commit

### Đo bộ đọc trên một CV

Chỉ in **con số**, không in nội dung — dùng được với CV thật, file để **ngoài** thư mục dự án:

```powershell
python -m services.extraction.rules.measure "D:\cv\mot_cv.pdf"

# Có đáp án → so sánh tỉ lệ trường đúng
python -m services.extraction.rules.measure "cv_gia.pdf" --expect "tests\fixtures\fake_candidate.json"
```

---

## 🔐 Bảo mật

| Biện pháp | Chi tiết |
|---|---|
| **Chỉ mở trên localhost** | `server.address = "localhost"` — máy khác trong mạng không truy cập được |
| **Không có API bên ngoài** | CV được đọc hoàn toàn trên máy chủ, không gửi đi đâu |
| **Chặn xuất khi còn PII** | Quét cả dữ liệu lẫn file PDF trước khi cho tải |
| **Log không chứa PII** | Tên file CV được ghi dạng mã băm `pdf#1a2b3c4d` |
| **Giới hạn upload** | Tối đa 20 MB (`MAX_UPLOAD_MB`) |
| **Tự xoá PDF cũ** | PDF hết hạn tự xoá khi khởi động app (mặc định 30 ngày) |
| **Chromium sandbox** | Giữ sandbox mặc định; chỉ tắt khi chạy Docker/root |
| **Hàng đợi tài nguyên** | Tối đa 2 lượt dựng PDF song song, tránh cạn RAM |

**Mở cho mạng nội bộ:** Không đổi `address` thành `0.0.0.0`. Hãy để app ở `localhost` và đặt một reverse proxy có xác thực phía trước (Caddy/Nginx với đăng nhập, hoặc Cloudflare Access). Máy chạy app cho ~30 người nên còn trống ≥ 4 GB RAM.

Chính sách xử lý dữ liệu cá nhân: xem [`docs/data-privacy-policy.md`](docs/data-privacy-policy.md).

---

## 📝 Log

- **`data/logs/app.log`** (app) và **`data/logs/render_worker.log`** (tiến trình dựng PDF), xoay vòng 1 MB × 5 file
- Mỗi lần gửi CV có một mã `run_id` 8 ký tự, ví dụ `[a1b2c3d4]`. Tìm mã này trong cả hai file để xem trọn một lượt xử lý
- **Không ghi** nội dung CV, họ tên hay tên file gốc

---

## ❓ Sự cố thường gặp

| Lỗi | Cách xử lý |
|---|---|
| `DLL load failed ... Application Control policy has blocked this file` | Windows Smart App Control chặn thư viện; app không dùng tới tính năng đó |
| `Chưa có bộ trích xuất '...'` | Biến `CV_EXTRACTOR` sai tên — xoá biến (mặc định `rules`) hoặc đặt `manual` |
| Hồ sơ ra khung trống "nhập tay" | CV là DOCX/ảnh, PDF scan, hoặc PDF lỗi font — lý do ghi trong khung chat. Xuất CV thành PDF (có chữ chọn được) rồi gửi lại, hoặc nhập tay |
| Bộ đọc bỏ sót / nhận sai tiêu đề mục | Thêm cách viết đó (không dấu) vào `config/extraction_rules.toml` |
| `File CV bị hỏng hoặc không đúng định dạng` | Mở file, lưu lại thành PDF rồi gửi lại |
| `Trình dựng PDF (Chromium) gặp lỗi` | Chạy lại `python -m playwright install chromium`; xem chi tiết trong `data/logs/` |
| App không khởi động sau khi sửa `config/company.toml` | File sai cú pháp TOML — kiểm tra dấu ngoặc kép và dấu `=` |

**Đổi cấu hình:** đặt biến môi trường trước khi chạy, ví dụ:

```powershell
$env:RENDER_MAX_CONCURRENT = "1"
python -m streamlit run app.py
```

---

## 📚 Tài liệu liên quan

| Tài liệu | Mô tả |
|---|---|
| [`SKILL.md`](SKILL.md) | Quy chuẩn hồ sơ PDF (bố cục, thông tin bỏ/giữ, đặt tên file, checklist) |
| [`docs/design-system.md`](docs/design-system.md) | Hệ thống giao diện: design tokens, nguyên tắc màu sắc, cách đổi token |
| [`docs/data-privacy-policy.md`](docs/data-privacy-policy.md) | Chính sách xử lý dữ liệu cá nhân ứng viên (bản nháp, chờ pháp chế) |
| [`docs/proposals.md`](docs/proposals.md) | Đề xuất dài hạn: đăng nhập/phân quyền, CI, cải tiến khác |

---

## 🧰 Tech Stack

| Thành phần | Công nghệ |
|---|---|
| Web framework | [Streamlit](https://streamlit.io/) |
| Đọc PDF | [PyMuPDF](https://pymupdf.readthedocs.io/) |
| Cấu trúc dữ liệu | [Pydantic](https://docs.pydantic.dev/) |
| Template PDF | [Jinja2](https://jinja.palletsprojects.com/) |
| Xuất PDF | [Playwright](https://playwright.dev/python/) (Chromium) |
| Xử lý ảnh | [Pillow](https://pillow.readthedocs.io/) + [OpenCV](https://opencv.org/) |
| Giao diện | HTML/CSS + Streamlit components |
