# Đánh giá hiện trạng và đề xuất kiến trúc khi bỏ OpenAI API

> Báo cáo phân tích, **chưa thực hiện bất kỳ thay đổi nào trong code**. Số dòng trích dẫn theo mã nguồn tại thời điểm
> viết (11/2026, sau đợt đổi tên định danh sang tiếng Anh, chưa commit). Chỗ nào là suy đoán đều ghi rõ "(suy đoán)".

## Tóm tắt điều hành

1. Bỏ OpenAI là **khả thi về kiến trúc**: chỉ một điểm gọi AI (`core/pipeline.py:55` → `extract.extract_cv`). Schema,
   template PDF, form duyệt, hàng đợi dựng PDF, log `run_id`, kiểm tra PII lớp 2–3 giữ nguyên được.
2. Cái khó nằm ở **chất lượng**, không ở kiến trúc. Hiện AI làm 4 việc mà code thường khó làm tốt: tách công việc/nhóm
   việc/vị trí con, chọn `type` cho từng mục, giữ thứ tự khi CV nhiều cột, và lập `stats` cùng `recruiting_flags`.
3. **Khuyên dùng phương án B**: bộ đọc theo luật (PyMuPDF/python-docx) + OCR Tesseract tiếng Việt cho bản scan + nhập tay
   dự phòng, có điểm tin cậy cho từng trường. Thiết kế qua một interface `Extractor` để vẫn cắm lại được OpenAI hoặc
   LLM chạy local (phương án C) cho CV khó mà không phải đổi kiến trúc.
4. **Không bỏ OpenAI ngay.** Trước hết phải đo trên bộ CV giả (mục B.9). Chỉ tắt OpenAI khi: 0 lần lọt thông tin nhạy cảm,
   và thời gian sửa trung vị không quá 1,5 lần so với khi có AI (ngưỡng đề xuất).
5. **Rủi ro lớn nhất:** (a) lớp lọc PII số 1 (prompt) đang làm phần việc mà code không làm. Địa chỉ nhà, quê quán, tình
   trạng hôn nhân, quốc tịch, lương **không** được `services/privacy/checks.py` phát hiện, nên bỏ AI mà không bổ sung
   luật là lọt dữ liệu lên PDF. (b) Repo **hiện không có test nào** (`tests/` đã bị xoá), không có lưới an toàn khi sửa lớn.

---

# PHẦN A — ĐÁNH GIÁ TRẠNG THÁI HIỆN TẠI

## A.1. Tổng quan

```text
app.py              Streamlit: điều phối giao diện + session_state
ui/                 components.py (HTML thuần) · profile_form.py (form sửa) · preview.py · table_text.py · styles.css
core/               pipeline.py (đọc CV, hàng đợi dựng PDF, lưu bản sao) · pdf_status.py (luật mở nút Tải)
services/ai/        extract.py (OpenAI) · models.py (Pydantic, khớp prompts/schema.json)
services/pdf/       render.py (HTML/ảnh chân dung/chọn cỡ chữ) · render_worker.py (Chromium) · pdf_utils.py · template.html/.css
services/privacy/   checks.py (quét PII + checklist PDF)
infra/              settings.py · tokens.py · logging_setup.py · storage.py
config/company.toml · prompts/ (system_prompt, user, fix_json, schema.json, version) · docs/ · SKILL.md
```

| Tầng | Số dòng Python | File lớn nhất |
|---|---:|---|
| `app.py` | 259 | — |
| `ui/` | 523 (+128 CSS) | `profile_form.py` 224 |
| `core/` | 232 | `pipeline.py` 184 |
| `services/ai/` | 463 | `extract.py` 316 |
| `services/pdf/` | 614 (+176 template.html, +415 template.css) | `render.py` 484 |
| `services/privacy/` | 236 | `checks.py` 236 |
| `infra/` | 444 | `settings.py` 147 |
| **Tổng** | **2 771** | |

- **Lớn và phức tạp nhất:** `services/pdf/render.py`. Khoảng một nửa file là xử lý ảnh chân dung (tìm mặt Haar, avatar
  tròn, chọn ảnh: `render.py:127–353`), phần còn lại là dựng HTML, chạy Chromium và chọn cỡ chữ (`render.py:356–484`).
- **Phức tạp về logic nghiệp vụ:** `services/privacy/checks.py` (regex SĐT/email/link/ngày sinh, whitelist công ty)
  và `services/ai/extract.py` (timeout, thử lại, sửa JSON).
- Phần **phụ thuộc OpenAI** chỉ nằm gọn trong `services/ai/extract.py` (316 dòng) và `prompts/`.

## A.2. Kết quả test

- Lệnh `python -m pytest -q -m "not slow"` cho kết quả **`no tests ran`**: thư mục `tests/`, `pytest.ini` và
  `.coveragerc` đang bị xoá (git status: ` D tests/...`). 0 pass / 0 fail / 0 skip.
- Bối cảnh (không thuộc repo hiện tại): bộ test cũ gồm 207 test, chạy lại trên bản sao ngoài dự án sau đợt đổi tên, đạt
  206/207. Bài duy nhất không đạt là giới hạn `app.py` < 250 dòng.
- **Vùng test mỏng, kể cả khi còn bộ test cũ** (suy ra từ cấu trúc bộ test và code):
  - Không có bộ CV chuẩn (golden set) đo **độ đúng của trích xuất**. Test chỉ dùng client OpenAI giả trả JSON dựng sẵn,
    nên chất lượng thật của AI chưa bao giờ được đo.
  - Không đo chất lượng `recruiting_flags` / `stats`.
  - Form sửa (`ui/profile_form.py`) chỉ được kiểm qua vài kịch bản AppTest.
  - Không có test chịu tải tự động (kiểm thử tải trước đây làm thủ công).

## A.3. Luồng "đang xử lý" hiện tại (upload → màn hình duyệt)

```text
[Người dùng] chọn file + dự án + vị trí → bấm "Gửi CV" (app.py:218–223, nút bị khoá khi ss.pending: app.py:220)
   │
   ▼ receive_cv (app.py:108–124)
   │   check_file(): rỗng / > MAX_UPLOAD_MB → tin lỗi trong chat (app.py:115–118, extract.py:67–74)
   │   ss.pending = {data, filename, project, position}; ss.run_id = new_run_id(); set_run_id()  (app.py:120–122)
   │   log "Nhận CV pdf#<sha8>"  — không ghi tên file (mask_filename)
   ▼ st.rerun() → cột phải: if ss.pending → process_pending_cv (app.py:229–230)
   │   Khung chat hiện bong bóng "đang gõ" TYPING_HTML (app.py:211–212)
   │   Khung A4 stage(True, 0): bước 1 "Đọc CV gốc và trích xuất nội dung" sáng (app.py:131, components.py:166)
   │
   │   pipeline.read_cv (core/pipeline.py:52–63)  ← CHẠY ĐỒNG BỘ trong luồng script, KHÔNG qua hàng đợi
   │     extract.extract_cv (extract.py:245–285)
   │        vòng thử: 1 + JSON_RETRY_COUNT(2) lần; hạn tổng OPENAI_TOTAL_DEADLINE=180 s;
   │        timeout mỗi lần = min(OPENAI_TIMEOUT=90, thời gian còn lại / (1+OPENAI_MAX_RETRIES))  (extract.py:261–267)
   │        JSON hỏng → gửi fix_json.txt (previous_response_id nếu OPENAI_STORE=1)  (extract.py:270–280)
   │     render.extract_photo (render.py:335) — lỗi → None, không chặn
   │   Lỗi → CVReadError → tin lỗi đỏ trong chat + st.error ở cột phải (app.py:134–138, 226–227)
   │
   │   stage(True, 1): bước 2 "Bỏ thông tin liên hệ, chuẩn hoá theo mẫu" (app.py:139)
   │        ⚠ chỉ hiện trong tích tắc, vì việc này AI đã làm xong ở bước 1 → bước 2 hiện là bước "giả"
   │   ss.update(cv0=..., auto_build=True, ...) + tin "notes" (model_notes, lương, ảnh) → st.rerun()  (app.py:140–144)
   ▼
[Rerun] tab "Chỉnh sửa nội dung" chạy trước (edit_profile) → validate_structure → scan_pii_export → fingerprint
   │   (app.py:236–249)
   ▼ pdf_panel: auto_build → stage(True, 2) "Dựng PDF và kiểm tra chất lượng" (app.py:150–157)
   │   pipeline.make_pdf (core/pipeline.py:84–115)
   │     _render_slots = BoundedSemaphore(RENDER_MAX_CONCURRENT=2)  (pipeline.py:67)
   │     hết lượt → _queue_length++ → on_wait(vị trí) → stage(..., queue_pos=n) "Đang xếp hàng dựng PDF"
   │       (app.py:79, components.py:182–184); chờ tối đa RENDER_QUEUE_TIMEOUT=300 s → RenderQueueTimeout
   │     render.build_pdf → subprocess render_worker (Chromium, 3 cỡ chữ một lần, RENDER_TIMEOUT=120 s) → scan_pdf
   ▼
[Màn hình duyệt] thanh trạng thái + cảnh báo + 2 ô xác nhận + nút Cập nhật/Tải + checklist + ảnh trang PDF
```

- **`run_id`**: sinh ở `receive_cv`, gắn đầu mỗi lần rerun (`app.py:48`), trong callback tải (`pipeline.py:125`), và
  truyền sang render_worker qua argv. Mọi dòng log có dạng `[run_id] logger: ...` (`infra/logging_setup.py`).
- **Thông báo lỗi**: mọi lỗi OpenAI đổi thành câu tiếng Việt (`extract.py:221–241`). Lỗi khác qua
  `read_error_message` (`pipeline.py:176`).
- **Không huỷ được** khi đang chờ OpenAI (`docs/proposals.md:31`).

## A.4. Bản đồ phụ thuộc vào OpenAI

Phân loại: **(a) phải thay** · **(b) giữ được** · **(c) bỏ được**.

| Vị trí | Phụ thuộc gì | Loại | Ghi chú |
|---|---|---|---|
| `services/ai/extract.py:178–285` (`_client`, `_call_api`, `_raise_openai_error`, `extract_cv`, `parse_json_text`) | SDK `openai`, Responses API, retry, sửa JSON | (a) | Toàn bộ lõi trích xuất |
| `extract.py:33–54` `MODEL`, `MAX_TOKENS`, `JSON_RETRY_COUNT`, `OPENAI_TIMEOUT/MAX_RETRIES/TOTAL_DEADLINE/STORE` | cấu hình AI | (c) | Bỏ cùng backend AI |
| `extract.py:26` `load_dotenv()` | **nạp `.env` cho cả app** | (a) **ẩn** | Chỉ file này gọi `load_dotenv`. `infra/settings.py` (OUTPUT_DIR, LOG_DIR, RENDER_*, COMPANY_CONFIG…) chỉ đọc được `.env` vì `app.py:16` import `extract` trước khi gọi `output_dir()` (`app.py:24`). Xoá `extract.py` thì các biến này **lặng lẽ mất** |
| `extract.py:30–31` đọc `system_prompt.txt`, `schema.json` **lúc import** | file prompt | (a) | Thiếu file thì app không khởi động |
| `extract.py:58, 62–74` `MAX_UPLOAD_MB`, `ExtractError`, `check_file` | kiểm file tải lên | (b), cần **chuyển chỗ** | Dùng ở `app.py:16, 115` và `ui/profile_form.py:15, 210` → UI đang phụ thuộc module AI |
| `extract.py:87–104` `_docx_to_text` | python-docx | (b) | Tái dùng cho bộ đọc theo luật |
| `extract.py:107–130` `_build_file_part` | gói file cho OpenAI | (c) | |
| `extract.py:168` `validate` (CVData) | Pydantic | (b) | Mọi backend đều nên qua bước này |
| `extract.py:289–316` CLI `python -m services.ai.extract` | | (a) | Thay bằng CLI chung cho mọi backend |
| `services/ai/models.py` | schema dữ liệu | (b) | Giữ nguyên. Lưu ý `extra="forbid"` (`models.py:17–20`) → không nhét điểm tin cậy vào JSON được |
| `prompts/schema.json` | đặc tả JSON gửi AI | (b) | Giữ làm đặc tả chuẩn (đang khớp `models.py`) |
| `prompts/system_prompt.txt`, `user.txt`, `fix_json.txt` | nội dung prompt | (c) / giữ nếu chọn C | `system_prompt.txt` đang là **đặc tả nghiệp vụ** đầy đủ nhất cho bộ luật, nên giữ làm tài liệu |
| `prompts/version.txt`, `infra/settings.py:125–147` `read_prompt`, `prompt_version` | phiên bản prompt | (a) | Đổi thành phiên bản của bộ trích xuất |
| `services/pdf/render.py:474–484` `write_metadata` → keywords `prompt <version>` | metadata PDF | (a) | Ghi tên backend + phiên bản |
| `core/pipeline.py:52–63` `read_cv` gọi `extract.extract_cv`, bắt `extract.ExtractError` | điểm cắm | (a) | Điểm duy nhất cần đổi trong nghiệp vụ |
| `core/pipeline.py:160–173` `summary_message`, `ui/components.py:40–60` (tin "notes"), `app.py:142–143, 165` | đọc `model_notes` | (b) | Giữ nếu backend mới vẫn điền `model_notes` |
| `ui/profile_form.py:172`, `ui/table_text.py:42–63` `keep_stat_sources` | cờ `source` original/generated | (b) | |
| Chữ hiển thị "AI" / "OpenAI" (`app.py` docstring, `components.py:166–186` "Đọc CV gốc và trích xuất nội dung", `extract.py` các câu lỗi) | | (a) nhẹ | Sửa câu chữ |
| `requirements.txt` `openai==3.46.0`; `requirements-dev.txt` `httpx` (để giả lỗi OpenAI) | | (c) | |
| `.env.example:2–4, 13–18` `OPENAI_*` | | (c) | |
| `README.md:3, 14, 63, 71–74, 118, 144, 150–154`; `CLAUDE.md:7, 14, 16, 30, 42`; `docs/proposals.md:24, 31` | tài liệu | (a) | |
| `docs/data-privacy-policy.md:12–45, 64` (chuyển dữ liệu cho OpenAI) | pháp lý | (a) | Bỏ AI thì mục 3 gần như không còn, đây là **lợi ích chính** |
| `docs/prompts/` (bản sao cũ của prompt; `user.txt` **khác** bản trong `prompts/`) | | (c) | Nợ kỹ thuật: hai nguồn prompt lệch nhau |
| Bộ test cũ (`tests/test_extract.py`, fixture `fake_candidate.json`, `sample_candidate.json` — đang bị xoá) | client giả | (a)/(b) | Fixture JSON vẫn rất có giá trị làm "đáp án" |
| Log `extract` (`extract.py:28, 210, 273`) | | (a) | Đổi thành log theo từng giai đoạn |
| `services/pdf/render.py:335` `extract_photo` (OpenCV) | **không** dùng AI | (b) | Ảnh chân dung đã chạy hoàn toàn trên máy |
| `services/privacy/checks.py`, `core/pdf_status.py` | **không** dùng AI | (b) | Nhưng phải bổ sung luật (A.5, B.5) |

## A.5. Những chỗ đang giả định dữ liệu "sạch" do AI trả về

Căn cứ: `prompts/system_prompt.txt`, `prompts/schema.json`, SKILL.md mục 3.2–4.4.

| Việc AI đang làm (prompt) | Code dùng ở đâu | Code thường làm được? | Ghi chú |
|---|---|---|---|
| Chia `sections` đúng thứ tự gốc, giữ tiêu đề | template `SECTIONS` (`template.html`), form `EDITORS_BY_TYPE` | **Được, khá** (CV 1 cột) | Nhận tiêu đề mục qua từ điển + cỡ chữ/in đậm/IN HOA (PyMuPDF `get_text("dict")`). CV 2 cột/sidebar: thứ tự đọc dễ sai |
| Chọn `type` (8 loại: text/bullets/cards/tags/career_path/experience/education/references) | `models.py:96–97` | **Được một phần** | Ánh xạ theo tên mục ("Kinh nghiệm" → experience, "Học vấn" → education…). `cards` và `tags` khó (suy đoán) |
| Tách công việc: company/period/role/meta/groups/sub_roles | `template.html` `section_experience`, form `_edit_job` | **Khó** — phần khó nhất | Dựa vào mẫu ngày tháng, dòng in đậm/IN HOA; mỗi CV một kiểu trình bày. `sub_roles` và `meta` (Ngành/Dự án) rất khó |
| `**in đậm**` chỉ khi CV gốc in đậm | `render.bold_filter` (`render.py:356`) | **Được** với PDF có chữ và DOCX (cờ bold của span/run); **không** với bản scan | |
| Sửa lỗi chính tả / ngắt dòng | — | Ngắt dòng: **được** (nối dòng theo heuristic); chính tả: **không nên** | |
| Lọc PII: SĐT, email, MXH, link, địa chỉ nhà, nơi sinh, hôn nhân, quốc tịch, ngày sinh → năm, lương → `expected_salary`, liên hệ người tham chiếu | `checks.py` chỉ kiểm SĐT/email/link/MXH/ngày sinh đầy đủ (`checks.py:35–55`) | SĐT/email/link/ngày sinh: **được** (đã có regex). Địa chỉ/quê quán/hôn nhân/quốc tịch/lương: **được theo nhãn dòng**, khó khi không có nhãn | **Lỗ hổng**: các trường này hiện chỉ dựa vào prompt (B.5) |
| `full_name` viết hoa đầu chữ, `target_title`, `gender`, `birth_year` | header PDF | **Được** (dòng chữ to nhất trang 1, dòng ngay dưới, nhãn "Giới tính"/regex năm) | |
| `facts` (vd "Mong muốn: …") | `template.html` khối nhận diện | **Được một phần** | Theo nhãn |
| `stats` 4 ô: giữ ô gốc, nếu không có thì tự lập từ số liệu thật | `template.html` hàng ô số liệu, `_edit_stats` | Ô gốc: **khó** nhận diện. Tự lập: **được nếu đã tách được ngày tháng công việc** (tổng năm kinh nghiệm, số công ty, bằng cấp cao nhất) | Nhãn sẽ rập khuôn hơn AI |
| `model_notes.removed` / `self_created` | tin "notes", `summary_message` | **Được, dễ** (code biết mình đã bỏ/lập gì) | |
| `recruiting_flags`: chồng chéo, khoảng trống ≥ 3 tháng, quản lý < 12 tháng, chức danh vs số năm | `summary_message`, tin "notes" | **Được và có thể tốt hơn AI** khi ngày tháng đã tách đúng (tính toán xác định) | Kế toán trưởng vs chứng chỉ: được một phần. Ảnh kém: được một phần (ảnh xám, độ nét Laplacian bằng OpenCV có sẵn) |
| CV song ngữ: chỉ giữ phần tiếng Việt | `language` | Phát hiện: **được** (tỉ lệ ký tự có dấu). Tách đúng phần tiếng Việt: **khó** | |
| Thống nhất chức danh | — | **Không** — để người duyệt | |

## A.6. Rủi ro, nợ kỹ thuật, điểm yếu khác

| # | Vấn đề | Căn cứ | Mức |
|---|---|---|---|
| 1 | **Không còn test nào trong repo** | `git status`: ` D tests/*`, `pytest` → `no tests ran` | Cao |
| 2 | **PII ngoài SĐT/email/link/ngày sinh chỉ dựa vào prompt** (địa chỉ, quê quán, hôn nhân, quốc tịch, CCCD, lương) | `checks.py:35–55` chỉ có 5 mẫu; `SKIP_FIELDS` (`checks.py:67`) | Cao (càng cao khi bỏ AI) |
| 3 | `.env` chỉ được nạp gián tiếp qua import `services.ai.extract` | `extract.py:26`; `infra/settings.py` không gọi `load_dotenv` | Trung bình |
| 4 | Module AI đọc file prompt ngay lúc import; UI import `check_file`/`ExtractError` từ module AI | `extract.py:30–31`; `app.py:16`, `profile_form.py:15` | Trung bình |
| 5 | Bước trích xuất **không giới hạn đồng thời** (chỉ dựng PDF có semaphore). Với OpenAI thì ổn vì chỉ chờ mạng; với OCR thì sẽ ngốn CPU/RAM | `pipeline.py:52–63` vs `pipeline.py:67` | Trung bình (thành Cao nếu thêm OCR) |
| 6 | Không huỷ được tác vụ dài; bước 2 trên màn hình chờ là "giả" | `docs/proposals.md:31`; `app.py:139` | Thấp |
| 7 | Mọi trạng thái nằm trong `session_state` (RAM). Tải lại trang là mất bản đang sửa. Mỗi phiên giữ file gốc (tới 20 MB) và PDF | `app.py:140`; Streamlit giữ session trong bộ nhớ | Trung bình |
| 8 | Không có đăng nhập, chỉ an toàn khi chạy `localhost` | `.streamlit/config.toml [server] address`; `docs/proposals.md` mục 1 | Cao nếu mở ra mạng |
| 9 | `docs/prompts/` là bản sao prompt cũ, `user.txt` đã lệch so với `prompts/` | so sánh file | Thấp |
| 10 | `MAX_UPLOAD_MB` khai báo ở module AI, trùng với `.streamlit/config.toml maxUploadSize` (chỉ test cũ giữ hai bên khớp) | `extract.py:58` | Thấp |
| 11 | `app.py` 259 dòng, vượt mức 250 mà test cấu trúc cũ đặt ra | `wc -l` | Thấp |
| 12 | Nhiều file chưa vào git (`CLAUDE.md`, `services/pdf/template.css`, `.vscode/`, `.claude/`) và rất nhiều sửa đổi chưa commit | `git status` | Trung bình (dễ mất việc) |
| 13 | (Từ trao đổi trước, không thấy trong code) Repo GitHub công khai và commit cũ có dữ liệu ứng viên thật vẫn truy cập được bằng SHA. Chưa có quyết định chuyển private/tạo lại repo | lịch sử làm việc | Cao, cần xử lý độc lập với đề xuất này |
| 14 | Có `.env` và `data/logs/render_worker.log` trên máy (đã gitignore, không đọc nội dung) | `ls` | Ghi nhận |

---

# PHẦN B — ĐỀ XUẤT KIẾN TRÚC KHÔNG DÙNG OPENAI

## B.1. Ranh giới trích xuất (interface)

Đề xuất một module mới `core/extraction.py` (thuần Python, không Streamlit):

```python
# core/extraction.py — đề xuất, chưa thực hiện
from dataclasses import dataclass, field
from typing import Callable, Protocol

@dataclass
class SourceDoc:                 # đầu vào chung cho mọi backend
    data: bytes
    filename: str
    project: str
    position: str
    today: date

@dataclass
class ExtractResult:
    cv: dict                                         # LUÔN hợp lệ theo CVData (prompts/schema.json)
    confidence: dict[str, float] = field(default_factory=dict)   # "sections[2].jobs[0].period" -> 0..1
    source_text: str = ""                            # văn bản thô đã đọc (cho chế độ nhập tay)
    backend: str = ""                                # "rules-0.1+<hash>" -> ghi vào metadata PDF

Progress = Callable[[str, float], None]              # (tên giai đoạn, 0..1) -> cập nhật màn hình chờ

class Extractor(Protocol):
    name: str
    def extract(self, doc: SourceDoc, progress: Progress) -> ExtractResult: ...

def get_extractor() -> Extractor: ...                # chọn theo biến môi trường EXTRACTOR=rules|manual|openai|local_llm
```

- **Điểm tin cậy để ngoài `cv`**: `CVData` cấm trường lạ (`extra="forbid"`, `models.py:17–20`), nên đưa vào JSON là
  `validate` báo lỗi. Để riêng trong `ExtractResult` thì schema, template và PII giữ nguyên 100%.
- `pipeline.read_cv` gọi `extraction.get_extractor().extract(...)` **qua tên module** (giữ quy ước monkeypatch), rồi luôn
  chạy `CVData.model_validate` (chính là `extract.validate`) ở cuối, bất kể backend nào.
- Các backend:
  - `services/extract/rules/` — bộ đọc theo luật (mới).
  - `services/extract/manual.py` — khung trống + văn bản thô (mới).
  - `services/ai/extract.py` — giữ, bọc thành `OpenAIExtractor` trong giai đoạn đo song song.
  - Tuỳ chọn sau: `local_llm.py`.

| Giữ nguyên | Đổi nhẹ | Thêm mới |
|---|---|---|
| `services/ai/models.py`, `prompts/schema.json`, `services/pdf/*`, `template.*`, `services/privacy/checks.py` (chỉ thêm mẫu), `core/pdf_status.py`, `infra/tokens.py`, `infra/storage.py`, `infra/logging_setup.py`, `ui/components.py` (trừ nhãn bước), `ui/preview.py`, `ui/table_text.py` | `core/pipeline.py` (`read_cv` + semaphore trích xuất), `app.py` (`process_pending_cv` truyền callback tiến độ), `ui/profile_form.py` (đánh dấu trường kém tin cậy), `ui/components.py` (`stage` nhận danh sách bước), `infra/settings.py` (`load_dotenv`, `MAX_UPLOAD_MB`, `check_file`, phiên bản backend), `services/pdf/render.py:474–484` (metadata) | `core/extraction.py`, `services/extract/…`, bộ test + golden set |

## B.2. Pipeline trích xuất mới

```text
SourceDoc
  │ G1 Đọc văn bản ─────────── PDF có lớp chữ: PyMuPDF get_text("dict") (đã có, pymupdf==2.1)
  │                            DOCX: python-docx (đã có _docx_to_text, extract.py:87) + run.bold
  │                            Scan/ảnh: OCR Tesseract (vie+eng) qua pytesseract hoặc page.get_textpage_ocr của PyMuPDF
  │   → danh sách "dòng" {text, page, bbox, size, bold, upper, cột}
  │ G2 Tách mục ────────────── tiêu đề mục = khớp từ điển (vi/en) ∪ (cỡ chữ > thân / IN HOA / in đậm, dòng ngắn)
  │                            + so mờ (rapidfuzz) cho biến thể chính tả
  │ G3 Tách công việc/học vấn ─ mẫu thời gian ("03/2019 – nay", "2019 - Present", "T3/2019") làm mốc;
  │                            dòng in đậm/IN HOA gần mốc = công ty; dòng nghiêng/ngay sau = chức danh; gạch đầu dòng
  │ G4 Bỏ thông tin cá nhân ── luật theo nhãn dòng + regex có sẵn của checks.py; ngày sinh → năm; lương → expected_salary
  │ G5 Dựng stats/cảnh báo ──── tính năm kinh nghiệm, khoảng trống, chồng chéo… từ mốc thời gian G3
  │ G6 Chuyển sang schema ──── dựng dict, model_notes, rồi CVData.model_validate; điểm tin cậy từng trường
  ▼
ExtractResult
```

Mức chính xác dưới đây là **suy đoán**, chỉ để định hướng, phải đo theo B.9.

| Giai đoạn | Thư viện | Kỳ vọng (suy đoán) | Thất bại điển hình |
|---|---|---|---|
| G1 PDF có chữ | PyMuPDF (đã cài) | ~98% ký tự đúng | Font nhúng thiếu bảng mã Unicode → ra ký tự rác (phát hiện bằng tỉ lệ ký tự lạ → chuyển sang OCR); PDF xuất từ Canva có chữ cắt vụn |
| G1 DOCX | python-docx (đã cài) | ~98% | Nội dung nằm trong textbox/shape (python-docx không đọc) → cần đọc XML `w:txbxContent`; bảng lồng nhau |
| G1 OCR | Tesseract 5 + `vie.traineddata` | 85–95% ký tự với scan 300 dpi sạch; thấp hơn nhiều với ảnh chụp điện thoại | Dấu tiếng Việt sai; nghiêng/mờ; nhiều cột; không có thông tin in đậm |
| G2 Tách mục | regex + từ điển + rapidfuzz | 85–95% với CV 1 cột; 50–75% với 2 cột/sidebar | Tiêu đề lạ ("Hành trình của tôi"); mục không có tiêu đề; sidebar đọc xen vào thân |
| G3 Tách công việc | regex ngày tháng + bố cục | 70–85% đủ company/period/role với CV 1 cột | Mốc thời gian nằm khác dòng; nhiều vị trí trong một công ty (sub_roles); ngày ghi bằng chữ |
| G4 PII | regex + nhãn | SĐT/email/link ~99% (đã có mẫu); địa chỉ/hôn nhân khi có nhãn ~95%, không nhãn thấp | Địa chỉ không nhãn ở header; số CCCD |
| G5 Stats/cảnh báo | Python thuần | Đúng nếu G3 đúng | Sai dây chuyền từ G3 |
| G6 Schema | Pydantic (đã có) | 100% hợp lệ cú pháp | — |

## B.3. Giữ trải nghiệm "đang xử lý"

**Bắt buộc**

1. **Tiến độ theo giai đoạn thật.** `stage()` (`components.py:166`) nhận danh sách bước và bước hiện tại. `app.py`
   truyền một callback `progress(tên, tỉ lệ)` xuống `read_cv`. Callback này vẽ lại `slot` giống cơ chế `on_wait` đang
   dùng cho hàng đợi PDF (`app.py:79`). Các bước hiển thị: "Đọc văn bản (trang 2/3)" → "Tách mục và công việc" →
   "Lọc thông tin liên hệ" → "Dựng PDF". Bỏ bước 2 "giả" hiện tại (`app.py:139`).
2. **Semaphore riêng cho trích xuất** (`_extract_slots`, `EXTRACT_MAX_CONCURRENT`, mặc định 1–2 tuỳ RAM), viết giống
   `make_pdf` (`pipeline.py:84–115`): xếp hàng, hiển thị vị trí, `EXTRACT_QUEUE_TIMEOUT`. OCR và Chromium cùng ngốn
   CPU/RAM. Có thể dùng một "ngân sách" chung, ví dụ tổng OCR + dựng PDF ≤ 3, nhưng tách hai semaphore đơn giản và dễ
   hiểu hơn.
3. **Timeout**: OCR mỗi trang có `timeout` (pytesseract hỗ trợ tham số này, Tesseract chạy như tiến trình con nên có
   thể kill), cộng hạn tổng `EXTRACT_TOTAL_DEADLINE` giống logic `extract.py:261–267`. Quá hạn thì chuyển sang
   **chế độ nhập tay** với phần văn bản đã đọc được, không báo lỗi trắng.
4. **Log theo `run_id`**: mỗi giai đoạn ghi một dòng `[run_id] extract: G1 xong 3 trang, 1.8 s, ocr=có`. Không ghi nội
   dung CV (giữ nguyên tắc `mask_filename`).
5. **Lỗi**: giữ `CVReadError` với câu tiếng Việt. Thêm loại "đọc được một phần" để sang màn hình duyệt kèm cảnh báo,
   thay vì dừng hẳn.

**Cải tiến thêm (không bắt buộc)**

- **Nút "Huỷ"**: khi tiến độ được vẽ sau mỗi trang, Streamlit có điểm để dừng script khi người dùng bấm nút khác
  (cần kiểm chứng trên phiên bản `streamlit==1.67.0`). Kết hợp với OCR chạy theo từng trang thì huỷ được thật, khác
  với lời gọi OpenAI hiện tại.
- Chạy OCR trong `ProcessPoolExecutor` hoặc tiến trình con riêng (giống `render_worker`), để một CV nặng không làm chậm
  các phiên khác.
- Cache kết quả theo sha256 của file: gửi lại cùng CV thì không OCR lại.

## B.4. Độ tin cậy và dự phòng

- **Cách chấm điểm (đề xuất)**: mỗi trường nhận điểm 0..1 từ các tín hiệu:
  - nguồn chữ (lớp chữ 1.0 / OCR theo điểm `conf` của Tesseract);
  - mục khớp từ điển chính xác hay chỉ khớp mờ;
  - công việc có đủ company + period + role hay thiếu;
  - mốc thời gian parse được hay không;
  - có phải trang nhiều cột hay không.
- **Form duyệt**: `edit_profile` nhận thêm `confidence`, gắn nhãn "Cần xem" (`st.caption` hoặc viền cảnh báo, dùng token
  `warn` có sẵn) cho trường dưới ngưỡng (vd 0,7). Thêm mục "Cần xem" vào tin `notes` trong chat (`model_notes.other`).
- **Chuyển sang nhập tay**: khi điểm trung bình < ngưỡng, hoặc G2 không tìm được mục nào, hoặc quá hạn.
  - `manual` backend trả khung trống đúng schema: `full_name` lấy từ dòng chữ lớn nhất hoặc tên file, vì validator
    `_name_not_empty` không cho trống.
  - `source_text` hiển thị cạnh form (tab "CV gốc" đã có, `ui/preview.py:show_original`) để người dùng chép, dán.
- **Trường hợp khó**:
  - Nhiều cột/sidebar: gom khối theo toạ độ x (PyMuPDF trả bbox), đọc cột hẹp như sidebar (kỹ năng/liên hệ) tách khỏi
    cột chính. Nếu phát hiện ≥ 2 cột thì hạ điểm tin cậy toàn CV.
  - Song ngữ: tỉ lệ ký tự có dấu theo đoạn. Đặt `language="bilingual_vi_en"`, cảnh báo, **không** tự cắt phần tiếng Anh
    (để người duyệt).
  - Thiếu mục: không tìm thấy "Học vấn" thì thêm `recruiting_flags` đúng theo prompt hiện tại.

## B.5. Hệ quả lên các lớp bảo vệ PII

Hiện có 3 lớp:
1. Prompt (`system_prompt.txt` mục "BẢO MẬT").
2. `scan_pii_export` (`checks.py:158`).
3. `scan_pdf` + `pdf_clean` khoá nút Tải (`checks.py:168, 202`; `pdf_status.py:35`).

Bỏ AI là **mất lớp 1**. Đề xuất:

1. **Thay lớp 1 bằng giai đoạn G4** (lọc trong bộ trích xuất): bỏ dòng theo nhãn (Địa chỉ/Address, Quê quán/Nơi
   sinh/Place of birth, Tình trạng hôn nhân/Marital status, Quốc tịch/Nationality, CMND/CCCD/ID/Passport, Zalo,
   Facebook…); ngày sinh → `birth_year`; dòng lương → `expected_salary`; người tham chiếu chỉ giữ tên/chức danh/công ty.
   Mỗi loại bị bỏ ghi vào `model_notes.removed` (như AI đang làm).
2. **Bổ sung lớp 2–3** (`checks.py`, cùng dùng cho mọi backend, kể cả OpenAI):
   - mẫu **số CCCD/CMND/hộ chiếu** (9/12 chữ số, có ngữ cảnh "CCCD/CMND/ID");
   - **nhãn nhạy cảm** còn sót trong nội dung ("Địa chỉ:", "Quê quán", "Hôn nhân", "Quốc tịch"…);
   - **lương** ("lương", "salary", "triệu/tháng", "VND", "USD" đi cùng số) → cảnh báo;
   - mẫu **địa chỉ không nhãn** (số nhà + "đường/phường/quận/P./Q.") ở mức **cảnh báo, không chặn**, vì dễ báo nhầm
     địa chỉ công ty. Whitelist địa chỉ Light Human đã có sẵn trong `company.toml`.
3. Thêm **mục checklist PDF thứ 6**: "Không còn nhãn thông tin cá nhân" (trong `scan_pdf`).
4. Bộ test PII riêng: mỗi loại thông tin có ít nhất 3 cách viết (có nhãn, không nhãn, tiếng Anh) và yêu cầu 0 lần lọt.

## B.6. Hệ quả lên test, prompts, phiên bản, biến môi trường, hạ tầng, tài liệu

| Hạng mục | Thay đổi đề xuất |
|---|---|
| Test | Khôi phục `tests/` (đã có bản port sang tên mới, chạy 206/207). Thêm: test từng giai đoạn G1–G6, golden set CV giả (B.9), test PII mở rộng, test semaphore trích xuất (giống test hàng đợi PDF cũ). `test_extract.py` (client giả) giữ chừng nào còn backend OpenAI |
| `prompts/` | `schema.json` giữ (đặc tả chuẩn). `system_prompt.txt` giữ làm **đặc tả nghiệp vụ cho bộ luật**, hoặc chuyển nội dung sang SKILL.md. `user.txt`, `fix_json.txt` bỏ nếu không chọn C. Xoá `docs/prompts/` (bản lệch) |
| `prompt_version` | Thay bằng `extractor_version()`: tên backend + số phiên bản + băm các file luật (từ điển tiêu đề, mẫu ngày). Metadata PDF: `FillCV-LightHuman; extractor rules-0.1+<hash>` (`render.py:482`) |
| Biến môi trường | Bỏ `OPENAI_*` (giữ nếu còn backend AI tuỳ chọn). Thêm `EXTRACTOR`, `OCR_LANG=vie+eng`, `TESSERACT_CMD`, `EXTRACT_MAX_CONCURRENT`, `EXTRACT_QUEUE_TIMEOUT`, `EXTRACT_TOTAL_DEADLINE`, `OCR_PAGE_TIMEOUT`, `OCR_DPI` |
| `load_dotenv` | Chuyển vào `infra/settings.py` (bắt buộc, xem A.4) |
| requirements | Bỏ `openai` (và `httpx` ở dev). Thêm `pytesseract`, `rapidfuzz`; tuỳ chọn `opencv` (đã có) để chỉnh nghiêng ảnh scan |
| Hạ tầng | Hiện **chưa có Dockerfile**. Máy đang chạy chưa có Tesseract (`pytesseract` chưa cài, `tesseract` không có trong PATH). Windows: bộ cài Tesseract + `vie.traineddata`; Linux/Docker: `apt install tesseract-ocr tesseract-ocr-vie`. RAM (suy đoán): Tesseract ~100–300 MB/tiến trình/trang, cộng Chromium 300–400 MB mỗi lượt dựng (theo docstring `render_max_concurrent`, `infra/settings.py:82–89`). Máy 4 GB nên đặt EXTRACT=1, RENDER=2 |
| Tài liệu | `README.md` (giới thiệu, cài đặt, cấu hình, sự cố), `CLAUDE.md` (kiến trúc, lệnh, các tên phải khớp), `.env.example`, `docs/data-privacy-policy.md` (mục 3 → "dữ liệu không rời máy chủ"), `docs/proposals.md` (nút Huỷ thành khả thi) |

## B.7. So sánh phương án

| | **A. Luật thuần** (chỉ PDF có chữ + DOCX; scan → nhập tay) | **B. Luật + OCR + nhập tay dự phòng + điểm tin cậy** | **C. B + LLM chạy local cho CV khó** | **D. Giữ OpenAI làm tuỳ chọn sau interface** |
|---|---|---|---|---|
| Chính xác (suy đoán) | CV 1 cột tốt; scan 0% tự động | Như A + scan ở mức trung bình | Gần OpenAI với CV khó nếu model đủ tốt tiếng Việt (chưa kiểm chứng) | Như hiện tại |
| Công sức | M | M–L | L | S |
| RAM/hạ tầng | Không thêm | + Tesseract, +CPU khi OCR | +8–16 GB RAM hoặc GPU; mỗi CV có thể mất vài phút trên CPU (suy đoán) | Không thêm |
| Bảo trì | Từ điển/luật cần chỉnh dần | Như A + cấu hình OCR | Như B + model, prompt, cập nhật runtime (Ollama/llama.cpp) | Chi phí API, điều khoản dữ liệu |
| Dữ liệu rời máy chủ | Không | Không | Không | **Có** |
| Rủi ro | Nhiều CV phải nhập tay | Như A nhưng ít hơn; lọt PII nếu luật thiếu | Model sai/bịa (cần lớp PII giữ nguyên); máy yếu | Không đạt mục tiêu bỏ OpenAI |

**Khuyên dùng B, xây trên interface ở B.1.**
- B là phương án duy nhất vừa đạt cả ba mục tiêu (chi phí, dữ liệu ở lại máy chủ, ít phụ thuộc), vừa xử lý được CV scan.
- Interface cho phép giữ D trong thời gian đo (so song song trên CV giả) và mở đường cho C sau này mà không phải viết lại.
- Chỉ cân nhắc C nếu số đo cho thấy tỉ lệ CV phải nhập tay vẫn cao (vd > 30%) **và** có máy đủ RAM/GPU.

## B.8. Kế hoạch theo giai đoạn

| GĐ | Việc | Công sức | Tiêu chí nghiệm thu | Quay lui |
|---|---|---|---|---|
| 0 | Khôi phục bộ test (bản port), commit trạng thái hiện tại; chuyển `load_dotenv`, `check_file`, `MAX_UPLOAD_MB` sang `infra/settings.py` | S | Toàn bộ test xanh; PDF mẫu giống từng điểm ảnh | `git revert` |
| 1 | `core/extraction.py` + bọc OpenAI thành `OpenAIExtractor`; `read_cv` gọi qua interface; tiến độ thật + semaphore trích xuất | S–M | Hành vi không đổi với `EXTRACTOR=openai`; test hàng đợi trích xuất; log mỗi giai đoạn có `run_id` | Đặt `EXTRACTOR=openai` |
| 2 | Golden set CV giả + công cụ chấm điểm (B.9); đo **baseline OpenAI** | M | ≥ 30 CV có đáp án; báo cáo điểm baseline | — |
| 3 | Bổ sung PII lớp 2–3 (B.5) cho **mọi** backend | M | 0 lần lọt trên bộ test PII; số báo nhầm có ghi nhận | Tắt từng mẫu mới qua cấu hình |
| 4 | Backend `manual` + `rules` G1/G2/G6 (PDF có chữ, DOCX): tách mục, header, PII theo nhãn | M | ≥ 85% mục đúng tiêu đề/loại trên CV 1 cột (ngưỡng đề xuất) | `EXTRACTOR=openai` |
| 5 | G3 + G5: công việc, học vấn, ngày tháng, `stats`, `recruiting_flags` | L | ≥ 75% công việc đủ company+period+role; cảnh báo khoảng trống/chồng chéo khớp đáp án ≥ 90% | Như trên |
| 6 | Điểm tin cậy + đánh dấu "Cần xem" trong form | M | Trường dưới ngưỡng hiển thị đúng; người dùng thử xác nhận hữu ích | Ẩn bằng cờ cấu hình |
| 7 | OCR (Tesseract vie) cho scan/ảnh, có timeout/huỷ | M | CV scan giả 300 dpi: ≥ 85% ký tự đúng; RAM đỉnh trong ngân sách | Scan → `manual` |
| 8 | Chạy thử song song (shadow): nhân viên dùng `rules`, so với OpenAI trên CV **giả/đã che** | M | Đạt ngưỡng B.9 | Giữ OpenAI |
| 9 | Bỏ OpenAI: gỡ backend, `requirements`, `OPENAI_*`, cập nhật tài liệu và chính sách dữ liệu | S | Không còn import `openai`; test xanh | Khôi phục từ commit GĐ 8 |

## B.9. Đo trước khi cam kết

- **Bộ CV thử, chỉ dữ liệu giả hoặc đã che**, khoảng 30–50 CV:
  - Lấy các JSON giả (vd `fake_candidate.json`, `sample_candidate.json` đã ẩn danh) làm **đáp án**, rồi dựng thành CV gốc
    theo nhiều kiểu: Word 1 cột, Word có bảng, mẫu 2 cột có sidebar, PDF kiểu "xuất từ trang tuyển dụng", tiếng Anh,
    song ngữ.
  - In ra rồi scan/chụp điện thoại để có bản ảnh.
  - Mỗi CV có file đáp án JSON. **Không** dùng CV thật trong `data/` hay commit chúng.
- **Chỉ số**:
  - Độ đúng theo trường:
    - đúng/sai tuyệt đối: `full_name`, `birth_year`, `gender`, `target_title`;
    - theo cặp khớp: số mục và `type`; công việc khớp (company, period, role);
    - F1 theo token cho bullet;
    - `stats`/`recruiting_flags` khớp đáp án.
  - **Số lần lọt PII trên PDF** (phải bằng 0).
  - **Thời gian sửa đến khi tải được PDF**, đo trên 5–10 CV giả với 2–3 nhân viên, so ba cách: OpenAI / bộ luật / làm
    tay từ đầu.
  - Thời gian xử lý p50/p95 và RAM đỉnh.
  - Tỉ lệ CV rơi vào chế độ nhập tay.
- **Ngưỡng quyết định (đề xuất, chị/anh chốt)**:
  - Tiếp tục bỏ AI nếu: 0 lần lọt PII **và** thời gian sửa trung vị ≤ 1,5 lần so với OpenAI **và** ≤ 50% so với làm tay
    **và** tỉ lệ nhập tay ≤ 20%.
  - Thời gian sửa từ 1,5 đến 2,5 lần OpenAI: cân nhắc C.
  - Trên 2,5 lần: giữ AI (hoặc C).

## B.10. Câu hỏi còn mở

1. CV đến chủ yếu từ đâu (Word ứng viên tự làm, PDF tải từ trang tuyển dụng, Canva, LinkedIn)? Tỉ lệ ước chừng?
2. Tỉ lệ CV **scan/ảnh chụp**, và tỉ lệ CV tiếng Anh/song ngữ?
3. Số CV mỗi ngày, số người dùng cùng lúc lúc cao điểm?
4. Máy chủ dự kiến: Windows hay Linux, bao nhiêu RAM/CPU, có GPU không? (quyết định C có khả thi không)
5. Thời gian chờ chấp nhận được cho một CV (hiện 30–90 giây)?
6. "Dữ liệu không rời máy chủ" là yêu cầu pháp lý bắt buộc hay ưu tiên? Có chấp nhận giữ OpenAI làm tuỳ chọn (tắt mặc
   định) cho CV khó không?
7. Nhân viên chấp nhận sửa nhiều hơn ở mức nào (vd thêm 2–3 phút/CV)?
8. Có cần giữ `stats` "tự lập" và `recruiting_flags` ở mức như AI không, hay chấp nhận chỉ nhóm cảnh báo tính được bằng
   ngày tháng?
9. Có muốn khôi phục `tests/` vào repo trước khi bắt đầu không? (đề xuất: có, là GĐ 0)

## Giả định và điểm chưa chắc

- Mọi con số độ chính xác, RAM, thời gian trong B.2/B.7 là **suy đoán** dựa trên kinh nghiệm chung với các thư viện
  nêu tên, chưa đo trên dữ liệu của dự án.
- Khả năng huỷ tác vụ qua điểm vẽ tiến độ của Streamlit (B.3) cần kiểm chứng trên `streamlit==1.67.0`.
- Chất lượng OCR tiếng Việt của Tesseract phụ thuộc mạnh vào chất lượng ảnh, chưa kiểm chứng.
- Kết quả 206/207 của bộ test port là từ bản sao ngoài repo, không phải từ repo hiện tại (repo không có test).
- Mục A.6 #13 (repo công khai) lấy từ trao đổi trước, không suy ra từ code.

## Danh sách file sẽ phải đổi nếu theo phương án B — đề xuất, chưa thực hiện

| File | Thay đổi |
|---|---|
| `core/extraction.py` (mới) | Interface `Extractor`, `SourceDoc`, `ExtractResult`, `get_extractor()` |
| `services/extract/rules/*.py` (mới) | G1–G6: đọc văn bản, tách mục, tách công việc, PII theo nhãn, stats/cảnh báo, dựng schema |
| `services/extract/manual.py` (mới) | Backend nhập tay |
| `services/extract/ocr.py` (mới) | Tesseract, timeout từng trang |
| `core/pipeline.py` | `read_cv` gọi interface, semaphore + hàng đợi trích xuất, truyền `progress` |
| `app.py` | `process_pending_cv`: callback tiến độ, chế độ nhập tay, (tuỳ chọn) nút Huỷ |
| `ui/components.py` | `stage()` nhận danh sách bước thật; câu chữ "AI" |
| `ui/profile_form.py` | Nhận `confidence`, đánh dấu "Cần xem"; import `check_file` từ `infra/settings.py` |
| `services/privacy/checks.py` | Mẫu CCCD, nhãn nhạy cảm, lương, địa chỉ (cảnh báo); mục checklist thứ 6 |
| `infra/settings.py` | `load_dotenv`, `MAX_UPLOAD_MB`, `check_file`/`ExtractError` (đổi tên chung), `extractor_version()`, biến OCR/EXTRACT_* |
| `services/pdf/render.py` | `write_metadata` ghi phiên bản backend |
| `services/ai/extract.py` | Bọc thành `OpenAIExtractor` (giai đoạn đo), sau đó gỡ |
| `services/ai/models.py`, `prompts/schema.json` | Giữ nguyên (có thể chuyển `models.py` sang `core/` sau) |
| `prompts/system_prompt.txt`, `user.txt`, `fix_json.txt`, `version.txt`, `docs/prompts/` | Giữ làm đặc tả / bỏ khi gỡ AI; xoá bản lệch `docs/prompts/` |
| `requirements.txt`, `requirements-dev.txt` | − `openai`, − `httpx`; + `pytesseract`, `rapidfuzz` |
| `.env.example` | − `OPENAI_*`; + `EXTRACTOR`, `OCR_*`, `EXTRACT_*` |
| `tests/` (khôi phục + mới) | Golden set, test giai đoạn, test PII mở rộng, test hàng đợi trích xuất |
| `README.md`, `CLAUDE.md`, `docs/data-privacy-policy.md`, `docs/proposals.md` | Cập nhật kiến trúc, cài Tesseract, chính sách dữ liệu |
