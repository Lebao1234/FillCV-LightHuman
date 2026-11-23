# Hợp đồng API (API Contract) — FillCV Light Human

Tài liệu này là **nguồn sự thật duy nhất** về hợp đồng giao tiếp giữa Server (Starlette API) và Client (`web/src/api/client.js`).
Mọi endpoint đều tuân thủ các quy tắc bảo mật từ [CLAUDE.md](file:///e:/FillCV-LightHuman/CLAUDE.md):
- Không ghi nội dung CV, tên file, họ tên ứng viên vào log hay câu báo lỗi.
- Thông báo lỗi trả về cho client là các câu tiếng Việt viết sẵn, lịch sự, dễ hiểu.
- Không tự sinh tài liệu/schema (không `/docs`, không `/openapi.json`).

---

## 1. Hệ thống & Cấu hình

### 1.1. Health Check
* **Endpoint:** `GET /health`
* **Mô tả:** Kiểm tra sức khoẻ ứng dụng (thay thế cho `/_stcore/health` của Streamlit). Dùng cho Docker HEALTHCHECK, Nginx và giám sát.
* **Headers:** Không yêu cầu.
* **Response `200 OK`:**
```json
{
  "status": "ok"
}
```

### 1.2. Cấu hình ứng dụng
* **Endpoint:** `GET /api/config`
* **Mô tả:** Cung cấp thông số vận hành ban đầu cho client (giới hạn upload, đuôi file hỗ trợ, danh sách ngôn ngữ xuất, logo header dạng base64, các nhãn bước mặc định).
* **Response `200 OK`:**
```json
{
  "max_upload_mb": 20,
  "allowed_extensions": [".pdf", ".docx", ".png", ".jpg", ".jpeg"],
  "image_extensions": [".png", ".jpg", ".jpeg"],
  "pdf_languages": {
    "vi": "Tiếng Việt",
    "en": "English"
  },
  "logo_header_b64": "iVBORw0KGgo...",
  "default_stage_labels": [
    "Đọc CV gốc",
    "Lấy ảnh chân dung từ CV gốc",
    "Kiểm tra thông tin nhạy cảm, dựng PDF và checklist chất lượng"
  ],
  "translation": {
    "available": true,
    "source": "vi",
    "target": "en",
    "engine": "opus-mt-vi-en"
  }
}
```

---

## 2. Trích xuất CV (Upload & Extraction)

### 2.1. Đọc và trích xuất CV
* **Endpoint:** `POST /api/cv/extract`
* **Mô tả:** Nhận file CV từ người dùng, sinh `run_id`, đưa vào hàng đợi đọc CV (`_extract_slots`) và stream tiến độ/kết quả qua Server-Sent Events (SSE).
* **Content-Type:** `multipart/form-data`
* **Request Form Fields:**
  * `file`: File nhị phân (bắt buộc, <= `max_upload_mb`).
  * `project`: Chuỗi (không bắt buộc, tên dự án).
  * `position`: Chuỗi (không bắt buộc, vị trí ứng tuyển).
  * `keep_contact`: `"true"` (không bắt buộc, mặc định cắt bỏ): giữ SĐT/email/địa chỉ/link của ứng viên và đưa vào `facts` (nhãn "Điện thoại", "Email", "Địa chỉ", "Website", "Mạng xã hội"; tiếng Anh: "Phone", "Address"...) thay vì cắt bỏ. Các loại đã giữ không còn nằm trong `model_notes.removed`.
* **Accept:** `text/event-stream` (mặc định cho web client) hoặc `application/json`.
* **Response Stream (`text/event-stream`):**
  * *Khi phải xếp hàng:*
    ```text
    event: wait
    data: {"queue_pos": 1, "what": "đọc CV"}
    ```
  * *Khi bắt đầu từng giai đoạn trích xuất thật:*
    ```text
    event: progress
    data: {"step": 0, "label": "Đọc CV gốc", "labels": ["Đọc CV gốc", "Lấy ảnh chân dung từ CV gốc", "..."]}
    ```
  * *Khi hoàn thành trích xuất thành công:*
    ```text
    event: done
    data: {
      "run_id": "run_20261119_153000_abc123",
      "cv": {
        "full_name": "Nguyễn Văn A",
        "target_title": "Kế toán trưởng",
        "birth_year": 1990,
        "gender": "Nam",
        "expected_salary": "30 triệu",
        "facts": [{"label": "Mong muốn", "value": "Làm việc tại TP.HCM"}],
        "stats": [{"value": "10+", "label": "Năm kinh nghiệm"}],
        "sections": [],
        "model_notes": {
          "removed": ["Số điện thoại", "Email"],
          "self_created": ["Số năm kinh nghiệm"],
          "recruiting_flags": [],
          "other": []
        }
      },
      "has_photo": true,
      "photo_url": "/api/photo/preview/run_20261119_153000_abc123",
      "warnings": [
        {"path": "sections[0]", "message": "Tiêu đề mục chưa rõ ràng"}
      ],
      "confidence": {
        "full_name": 0.95
      },
      "original_filename": "CV_NguyenVanA.pdf",
      "elapsed_seconds": 0.85
    }
    ```
  * *Khi xảy ra lỗi:*
    ```text
    event: error
    data: {"error": "File CV bị hỏng hoặc không đúng định dạng. Hãy mở file, lưu lại thành PDF hoặc DOCX rồi gửi lại."}
    ```
* **Mã lỗi HTTP (nếu gửi request sai hoặc vượt dung lượng/tần suất trước khi stream):**
  * `400 Bad Request`: `{"error": "Chị vui lòng đính kèm file CV trước khi gửi."}` hoặc file quá lớn/rỗng.
  * `429 Too Many Requests`: `{"error": "Bạn đang gửi CV quá nhanh. Vui lòng chờ ít phút rồi thử lại."}` khi gửi vượt quá 15 yêu cầu / phút trên một IP.

---

## 3. Kiểm tra tính hợp lệ & PII (Validation)

### 3.1. Xác thực cấu trúc hồ sơ và thông tin nhạy cảm
* **Endpoint:** `POST /api/cv/validate`
* **Mô tả:** Kiểm tra hồ sơ đang sửa xem có hợp lệ theo schema `CVData` hay không và quét các vi phạm PII (SĐT, email, link, ngày sinh đầy đủ). Trước khi kiểm tra, hồ sơ được **dọn** (`pipeline.clean_cv`): cắt khoảng trắng hai đầu, bỏ dòng trống trong danh sách, bỏ hàng/ô/công việc trống hoàn toàn. `normalized_cv` và `fingerprint` tính trên bản đã dọn.
* **Content-Type:** `application/json`
* **Request JSON:**
```json
{
  "cv": {
    "full_name": "Nguyễn Văn A",
    "target_title": "Kế toán trưởng",
    "sections": []
  },
  "project": "Message Coffee",
  "position": "Kế toán trưởng"
}
```
* **Response `200 OK`:**
```json
{
  "valid": true,
  "structure_errors": [],
  "violations": [],
  "normalized_cv": {
    "full_name": "Nguyễn Văn A"
  },
  "fingerprint": "a1b2c3d4..."
}
```
* **Khi có lỗi:**
```json
{
  "valid": false,
  "structure_errors": ["full_name: Họ tên không được để trống"],
  "violations": [
    {"field": "sections[0].jobs[0].meta[0]", "kind": "Số điện thoại", "value": "0901234567"}
  ],
  "normalized_cv": null
}
```

### 3.2. Dịch nội dung hồ sơ sang tiếng Anh (dịch máy offline)
* **Endpoint:** `POST /api/cv/translate`
* **Mô tả:** Dịch phần chữ tự do của hồ sơ từ tiếng Việt sang tiếng Anh bằng dịch máy **chạy ngay trên máy chủ** (CTranslate2 + Opus-MT, không gọi dịch vụ ngoài). Hồ sơ được dọn + kiểm tra cấu trúc (như 3.1) trước khi dịch. Chỉ dịch: chức danh mục tiêu, đoạn văn, gạch đầu dòng, thẻ năng lực (tên + ý), chức danh trong lộ trình/công việc/người tham chiếu, tên vị trí con, dòng phụ, nhóm việc, tên văn bằng. **Không dịch:** họ tên, tên công ty, tên trường, người tham chiếu (tên/công ty), thẻ kỹ năng, thời gian, ô số liệu. Thuật ngữ trong bảng cố định (`pdf_labels.toml`) được tra trước; đoạn không có dấu tiếng Việt bị bỏ qua. Mỗi đoạn dịch xong phải qua kiểm tra (số liệu giữ nguyên, không rỗng, độ dài hợp lý) — không đạt thì **giữ tiếng Việt** và báo trong `items`. Có đoạn được dịch thì `model_notes.self_created` được thêm một dòng nhắc phải đọc lại.
* **Content-Type:** `application/json`
* **Request JSON:** `{"cv": { ... }, "run_id": "tuỳ chọn, chỉ để gắn log"}`
* **Response `200 OK`:**
```json
{
  "cv": { ... },
  "engine": "opus-mt-vi-en (CTranslate2 int8)",
  "summary": {"translated": 31, "glossary": 4, "kept": 2, "skipped": 6},
  "items": [
    {"path": "sections[0].jobs[0].groups[0].bullets[1]", "status": "kept", "reason": "số liệu không khớp bản gốc"},
    {"path": "sections[0].jobs[1].role", "status": "skipped", "reason": "không có dấu tiếng Việt (đã là tiếng Anh hoặc gõ không dấu)"}
  ]
}
```
  `items` chỉ liệt kê đoạn `kept` / `skipped` và **không chứa nội dung CV**. `status` đầy đủ: `translated` (dịch máy), `glossary` (bảng thuật ngữ), `kept`, `skipped`.
* **Mã lỗi:**
  * `400 Bad Request`: thiếu `cv`, hoặc `{"error": "Hồ sơ chưa hợp lệ nên chưa dịch được: ..."}`
  * `429 Too Many Requests`: chờ quá `TRANSLATE_QUEUE_TIMEOUT` giây tới lượt dịch
  * `503 Service Unavailable`: chưa bật dịch máy / chưa cài mô hình (`CV_TRANSLATOR=none` hoặc thiếu `data/models/...`); giao diện chỉ hiện nút dịch khi `/api/config` có `translation.available = true`
  * `500 Internal Server Error`: `{"error": "Dịch máy gặp lỗi. ..."}`

---

## 4. Dựng PDF & Trạng thái (PDF & Status)

### 4.1. Dựng file PDF
* **Endpoint:** `POST /api/pdf/build`
* **Mô tả:** Nhận dữ liệu hồ sơ và thông tin dự án, **dọn + kiểm tra cấu trúc** (cùng luật với `/api/cv/validate`), rồi đưa vào hàng đợi dựng PDF (`_render_slots`), gọi Playwright headless shell, quét checklist và tính toán trạng thái ban đầu. PDF luôn dựng từ hồ sơ đã chuẩn hoá; đây cũng là thao tác "Lưu" của tab Chỉnh sửa nội dung (bản đã lưu nằm trong phiên `run_id`). Response trả lại hồ sơ đã chuẩn hoá trong `cv` để giao diện đồng bộ lại form.
* **Content-Type:** `application/json`
* **Request JSON:**
```json
{
  "run_id": "run_20261119_153000_abc123",
  "cv": { ... },
  "project": "Message Coffee",
  "position": "Kế toán trưởng",
  "lang": "vi"
}
```
* **Accept:** `application/json` hoặc `text/event-stream`.
* **Response `200 OK`:**
```json
{
  "run_id": "run_20261119_153000_abc123",
  "filename": "LH - CV Ke toan truong - Nguyen Van A - 19112026.pdf",
  "fingerprint": "8f3b2c1a...",
  "lang": "vi",
  "page_count": 2,
  "summary": "Hồ sơ ứng viên: Nguyễn Văn A – Kế toán trưởng...",
  "checklist": [
    {"code": "pii", "item": "Không còn SĐT, email, link, ngày sinh của ứng viên", "ok": true, "detail": "Sạch"},
    {"code": "pages", "item": "Số trang gọn (1-2 trang)", "ok": true, "detail": "2 trang (độ đầy trang cuối: 85%)"}
  ],
  "cv": { ... },
  "status": {
    "outdated": false,
    "pdf_dirty": false,
    "can_download": false,
    "pill_kind": "idle",
    "pill_text": "Chờ duyệt"
  }
}
```
* **Mã lỗi:**
  * `429 Too Many Requests`: `{"error": "Đang có nhiều hồ sơ dựng cùng lúc, đã chờ quá 60 giây. Vui lòng bấm Cập nhật PDF lại sau ít phút."}`
  * `400 Bad Request`: `{"error": "Dựng PDF thất bại. Chi tiết lỗi..."}`
  * `400 Bad Request` (hồ sơ sai cấu trúc, không dựng PDF): `{"error": "Hồ sơ chưa hợp lệ nên chưa lưu và dựng PDF được: full_name: Họ tên ứng viên đang trống"}`

### 4.2. Tính toán trạng thái khung PDF
* **Endpoint:** `POST /api/pdf/status`
* **Mô tả:** Tính toán trạng thái thanh status bar và quyền tải PDF dựa trên luật của `core/pdf_status.compute_status()`. Frontend chỉ hiển thị kết quả, không viết lại luật.
* **Content-Type:** `application/json`
* **Request JSON:**
```json
{
  "has_pdf": true,
  "pdf_fingerprint": "8f3b2c1a...",
  "current_fingerprint": "8f3b2c1a...",
  "checklist": [ ... ],
  "has_violations": false,
  "has_structure_errors": false,
  "checked_generated": true,
  "reviewed": true
}
```
* **Response `200 OK`:**
```json
{
  "outdated": false,
  "pdf_dirty": false,
  "can_download": true,
  "pill_kind": "ok",
  "pill_text": "Sẵn sàng tải"
}
```

---

## 5. Xem trước & Tải về (Preview & Download)

### 5.1. Xem trước trang CV gốc
* **Endpoint:** `GET /api/preview/original/{run_id}/{page}`
* **Mô tả:** Trả về hình ảnh PNG trang thứ `page` (bắt đầu từ 1) của CV gốc.
* **Response `200 OK`:** `image/png`
* **Mã lỗi:**
  * `404 Not Found`: Không tìm thấy phiên hoặc trang yêu cầu.
  * `400 Bad Request`: File không xem trước được (như DOCX) hoặc file bị lỗi.

### 5.2. Thông tin số trang CV gốc
* **Endpoint:** `GET /api/preview/original/{run_id}/info`
* **Response `200 OK`:**
```json
{
  "page_count": 3,
  "file_type": "pdf",
  "can_preview": true,
  "message": null
}
```

### 5.3. Xem trước trang PDF đã dựng
* **Endpoint:** `GET /api/preview/pdf/{run_id}/{page}`
* **Mô tả:** Trả về hình ảnh PNG trang thứ `page` của bản PDF vừa dựng xong.
* **Response `200 OK`:** `image/png`

### 5.4. Thông tin số trang PDF đã dựng
* **Endpoint:** `GET /api/preview/pdf/{run_id}/info`
* **Response `200 OK`:**
```json
{
  "page_count": 2
}
```

### 5.5. Tải file PDF về máy
* **Endpoint:** `GET /api/pdf/download/{run_id}`
* **Query Params:** `?save_copy=true` (mặc định: `true`).
* **Mô tả:** Tải file PDF đã dựng về máy. Nếu `save_copy=true`, server lưu bản sao PDF và file JSON cùng tên trong `data/output/`.
* **Response `200 OK`:**
  * `Content-Type`: `application/pdf`
  * `Content-Disposition`: `attachment; filename="LH - CV ... .pdf"`
  * `X-Save-Copy-Error`: (nếu có lỗi ghi đĩa trên server, kèm thông báo lỗi; không làm hỏng lượt tải về của người dùng).
* **Mã lỗi:** `404 Not Found` nếu chưa có bản PDF cho `run_id`.

---

## 6. Xử lý Ảnh Chân dung (Portrait)

### 6.1. Cắt ảnh chân dung tỉ lệ 29:38
* **Endpoint:** `POST /api/photo/crop`
* **Mô tả:** Nhận file ảnh tải lên, cắt khuôn mặt tỉ lệ chuẩn 29:38.
* **Content-Type:** `multipart/form-data` (`file`)
* **Response `200 OK`:**
```json
{
  "photo_b64": "data:image/png;base64,iVBORw0KGgo...",
  "photo_id": "photo_1732001234"
}
```
* **Mã lỗi:** `400 Bad Request` nếu file không phải ảnh hợp lệ hoặc không cắt được.

### 6.2. Lấy ảnh chân dung của phiên
* **Endpoint:** `GET /api/photo/preview/{run_id}`
* **Response `200 OK`:** `image/png`
* **Mã lỗi:** `404 Not Found` nếu phiên chưa có ảnh chân dung.

### 6.3. Bỏ ảnh chân dung khỏi phiên
* **Endpoint:** `DELETE /api/photo/{run_id}`
* **Response `200 OK`:**
```json
{
  "ok": true
}
```

