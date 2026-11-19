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
  ]
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
      "original_filename": "CV_NguyenVanA.pdf"
    }
    ```
  * *Khi xảy ra lỗi:*
    ```text
    event: error
    data: {"error": "File CV bị hỏng hoặc không đúng định dạng. Hãy mở file, lưu lại thành PDF hoặc DOCX rồi gửi lại."}
    ```
* **Mã lỗi HTTP (nếu gửi request sai hoặc vượt dung lượng trước khi stream):**
  * `400 Bad Request`: `{"error": "Chị vui lòng đính kèm file CV trước khi gửi."}` hoặc file quá lớn/rỗng.

---

## 3. Kiểm tra tính hợp lệ & PII (Validation)

### 3.1. Xác thực cấu trúc hồ sơ và thông tin nhạy cảm
* **Endpoint:** `POST /api/cv/validate`
* **Mô tả:** Kiểm tra hồ sơ đang sửa xem có hợp lệ theo schema `CVData` hay không và quét các vi phạm PII (SĐT, email, link, ngày sinh đầy đủ).
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

---

## 4. Dựng PDF & Trạng thái (PDF & Status)

### 4.1. Dựng file PDF
* **Endpoint:** `POST /api/pdf/build`
* **Mô tả:** Nhận dữ liệu hồ sơ và thông tin dự án, đưa vào hàng đợi dựng PDF (`_render_slots`), gọi Playwright headless shell, quét checklist và tính toán trạng thái ban đầu.
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

