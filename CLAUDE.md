# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Dự án là gì

Web app nội bộ của Light Human (công ty tuyển dụng nhân sự): kiến trúc tách biệt gồm backend API Starlette mỏng tự viết và frontend React + Vite viết bằng JavaScript/JSX thuần (không TypeScript). Luồng xử lý: tải CV ứng viên (PDF/ảnh/DOCX) → bộ trích xuất chạy trên máy chủ dựng JSON hồ sơ → nhân viên xem/sửa → xuất PDF "Hồ sơ ứng viên" theo mẫu thương hiệu, đã bỏ thông tin liên hệ của ứng viên. **Không gọi AI/API bên ngoài** (không OpenAI; dữ liệu CV không được rời máy chủ) — kể cả khi thêm tính năng dịch: chỉ dùng bảng dịch cố định trên máy chủ.

Tài liệu nghiệp vụ & kỹ thuật:
- `docs/SKILL.md` — **quy chuẩn PDF** (bố cục, thứ phải bỏ, tên file `LH - CV <Vị trí> - <Họ tên> - <ddmmyyyy>.pdf`, checklist). Template và bộ kiểm tra hiện thực hoá file này.
- `docs/api.md` — **hợp đồng API độc lập**, là nguồn duy nhất định nghĩa endpoint, method, tham số và cấu trúc response giữa backend và frontend.
- `docs/design-system.md` — hệ thống design tokens (nguồn duy nhất từ `system/infra/tokens.py`, sinh ra `web/src/tokens.css`).
- `docs/prompts/system_prompt.txt` — prompt OpenAI cuối cùng (lưu trữ), là đặc tả chi tiết cho bộ trích xuất theo luật.
- `docs/de_xuat_bo_openai.md` — kế hoạch thay OpenAI. `docs/data-privacy-policy.md` — chính sách dữ liệu. `docs/proposals.md`, `docs/deployment-cloudflare-tunnel.md` — triển khai.

Người dùng giao tiếp bằng tiếng Việt. Định danh viết tiếng Anh (PEP 8: hàm, biến, lớp, khoá dict, khoá trong `config/*.toml`, tên file); chuỗi hiển thị, chữ trong PDF, comment/docstring viết tiếng Việt. Mỗi hàm/lớp Python và mỗi hàm/component JavaScript có một dòng comment `#` hoặc `//` tiếng Việt ngay phía trên — giữ quy ước này cho code mới.

## Bố cục repo

- Thư mục gốc: `README.md`, `CLAUDE.md`, `docs/`, `.github/` (CI + dependabot), `data/` (không bao giờ commit), và phần triển khai:
  - `Dockerfile` + `.dockerignore` ở gốc — **Dockerfile duy nhất của toàn bộ dự án** (build context = gốc repo), multi-stage build: stage 1 dùng Node 22 build `web/` ra `web/dist`, stage 2 cài Python 3.13 + Chromium, stage 3 runtime non-root `appuser`. Dùng chung cho Docker Compose, CI/CD và PaaS.
  - `web/` — frontend React + Vite + Tailwind CSS + Vitest. Build ra `web/dist`. Toàn bộ giao tiếp mạng đi qua MỘT module `web/src/api/client.js`; không rải `fetch()` trong component.
  - `system/` — backend Starlette API (`api/`) và toàn bộ lõi xử lý (`core/`, `services/`, `infra/`, `config/`, `tests/`), `requirements*.txt`.
  - `docker-compose.yml` — build từ gốc repo (`build: .`), mount `data/` ở gốc; app chỉ `expose` 8000, service `nginx` mở cổng 80 (`nginx/conf.d/fillcv.conf`: tắt buffering cho SSE `/api/cv/extract`, `client_max_body_size` ↔ `MAX_UPLOAD_MB`).
- `system/` — thư mục làm việc cho mọi lệnh Python và job CI backend. Đường dẫn bên dưới (`infra/…`, `services/…`, `config/…`, `api/…`) tính từ `system/`; `docs/…` và `web/…` tính từ gốc repo.

## Lệnh

### Backend (Python & API)

```powershell
cd system                                         # chạy từ system/
python -m pip install -r requirements-dev.txt     # thư viện app + dev/test
python -m playwright install chromium             # bắt buộc: PDF được dựng bằng Chromium
python -m api.server                              # chạy API server tại http://127.0.0.1:8000

python -m pytest -q                               # toàn bộ test backend
python -m pytest -q -m "not slow"                 # bỏ qua test dựng PDF bằng Chromium thật
python -m pytest -q tests/test_api_contract.py    # test hợp đồng API theo docs/api.md
python -m pytest -q tests/test_smoke_e2e.py       # smoke test E2E với Playwright và fake_candidate.json
python -m infra.tokens --write                    # sinh web/src/tokens.css và in bảng markdown
```

### Frontend (React & Vite)

```powershell
cd web                                            # chạy từ web/
npm install                                       # cài đặt dependencies
npm run dev                                       # chạy dev server Vite tại http://localhost:5173 (proxy sang 8000)
npm run lint                                      # kiểm tra ESLint
npm run test                                      # chạy kiểm thử unit/component bằng Vitest
npm run build                                     # build giao diện tĩnh ra web/dist
```

### Docker

```powershell
# Chạy từ gốc repo
docker compose up -d --build                      # truy cập http://localhost (cổng 80 qua nginx)
```

- **Kiểm thử**:
  - Backend: `system/tests/test_api_contract.py` (kiểm tra toàn bộ hợp đồng API với `docs/api.md`, monkeypatch extractor và render), `system/tests/test_smoke_e2e.py` (smoke test E2E Playwright trên `fake_candidate.json`), `system/tests/test_export_language_logging.py`, `system/tests/test_rules_layout.py`.
  - Frontend: `web/src/__tests__/` (Vitest + Testing Library: kiểm thử `StatusBar`, `ReviewBadge`, `client.js`).
  - Khi sửa code backend mới, dùng `ruff check --isolated --select E4,E7,E9,F system/api system/tests` để đảm bảo code mới sạch lỗi.
- Trên Windows, đặt `PYTHONIOENCODING=utf-8` khi script in tiếng Việt nếu console báo `UnicodeEncodeError`. Script chạy ngoài `system/` cần `PYTHONPATH=.` (từ `system/`).
- Cấu hình: mọi giá trị có mặc định trong `infra/settings.py` (hoặc `config/company.toml`) và chỉ ghi đè được bằng **biến môi trường** (`HOST`, `PORT`, `CV_EXTRACTOR`, `EXTRACT_MAX_CONCURRENT`, `EXTRACT_QUEUE_TIMEOUT`, `MAX_UPLOAD_MB`, `MAX_CV_PAGES`, `OUTPUT_DIR`, `LOG_DIR`, `OUTPUT_RETENTION_DAYS`, `RENDER_*`, `COMPANY_CONFIG`, `LOGO_PATH`, `LOGO_HEADER_PATH`, `CHROMIUM_NO_SANDBOX`). Không có `.env` / `python-dotenv`.

## Kiến trúc

Monolith phân tầng, một tiến trình Python, giữ nguyên semaphore điều phối tài nguyên:

- `system/api/` — lớp API mỏng tự viết tay:
  - `server.py`: Starlette app, mount static files `web/dist`, CORS middleware, startup/lifespan dọn dẹp file hết hạn. Tắt hoàn toàn auto-docs (`/docs`, `/openapi.json`).
  - `routes.py`: hiện thực các endpoint theo đúng hợp đồng `docs/api.md`: `/health`, `/api/config`, `/api/cv/extract` (SSE), `/api/cv/validate`, `/api/pdf/build`, `/api/pdf/status`, `/api/preview/*`, `/api/pdf/download/*`, `/api/photo/*`. Gọi `core/pipeline.py`, KHÔNG chứa logic nghiệp vụ. Chuỗi lỗi trả về tiếng Việt viết sẵn.
  - `state.py`: `RunStore` lưu trữ trong bộ nhớ tạm thời (`RunData`) cho các phiên xử lý (ảnh gốc, PDF bytes, photo bytes).
- `web/` — frontend React + Vite + Tailwind CSS:
  - `src/api/client.js`: nguồn gọi API duy nhất của client.
  - `src/components/`: các component giao diện (`Header`, `ChatPanel`, `OriginalCvPreview`, `PdfPanel`, `StatusBar`, `StageScreen`).
  - `src/components/profile/`: form chỉnh sửa hồ sơ (`ProfileForm`, `ReviewBadge`, `GeneralInfoEditor`, `PortraitEditor`, `StatsEditor`, `SectionEditors`).
- `core/pipeline.py` — luồng nghiệp vụ giữ nguyên: `read_cv()` (kiểm tra file → trích xuất → kiểm schema → ảnh chân dung), `make_pdf()` (dựng + checklist), `save_copy()` (ghi PDF + `.json` khi tải), `content_fingerprint()`, `stage_labels()`.
- `core/pdf_status.py` — `compute_status()`: luật khoá/mở nút "Tải PDF" và nhãn trạng thái nằm ở backend. Frontend chỉ hiển thị kết quả, không viết lại luật.
- `services/extraction/` — bộ trích xuất theo luật (`rules/`) hoặc khung trống nhập tay (`manual.py`).
- `services/pdf/` — `render.py`, `render_worker.py` (Chromium Playwright độc lập), `template.html` + `template.css`, `labels.py`.
- `services/privacy/checks.py` — phát hiện PII + checklist chất lượng PDF.
- `infra/` — `settings.py`, `tokens.py`, `logging_setup.py`, `storage.py`.

## Tên phải đồng bộ giữa các file

- **Hợp đồng API**: `docs/api.md` ↔ `system/api/routes.py` ↔ `web/src/api/client.js`.
- **Design tokens**: `system/infra/tokens.py` ↔ `web/src/tokens.css` ↔ `docs/design-system.md`.
- Biến trong `template.html` ↔ kwargs của `render.render_html()`.
- Placeholder `{name}` trong `footer_intro` ↔ `render_worker.footer_html()`.
- Khoá `[text.vi]`/`[text.en]` trong `pdf_labels.toml` ↔ `t.*` trong template và `labels.texts()`.
- Dict checklist `{code, item, ok, detail}` và dict PII `{field, kind, value}`.
- Giới hạn upload 20 MB phải khớp ở `MAX_UPLOAD_MB` và `client_max_body_size` của nginx.

## Ràng buộc

- **Không gọi AI/API ngoài**: không OpenAI, không dịch tự động qua mạng, toàn bộ dữ liệu CV không rời máy chủ.
- **Bảo vệ quyền riêng tư**: Không bao giờ ghi nội dung CV, họ tên hay tên file gốc vào log hoặc response lỗi. Dùng `mask_filename()` (`pdf#<sha8>`).
- **Giữ nguyên từng điểm ảnh**: PDF xuất ra phải khớp từng điểm ảnh với mẫu mốc SKILL.md.
- **Tiến trình đơn**: App chạy 1 tiến trình duy nhất (Starlette + uvicorn trên 127.0.0.1:8000; container bind 0.0.0.0:8000 nhưng không publish trực tiếp ra ngoài máy chủ).
- Ghim `opencv-python-headless<5` — bản 5.x bỏ Haar cascade dùng để cắt ảnh chân dung.
- Dữ liệu thử nghiệm chỉ dùng dữ liệu giả trong `system/tests/fixtures/fake_candidate.json`.
