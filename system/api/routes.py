# Định nghĩa các endpoint API giao tiếp với frontend
"""Lớp API mỏng điều phối giữa giao diện web và các module nghiệp vụ trong core/.

Tuân thủ nghiêm ngặt các quy tắc từ CLAUDE.md:
- Không chứa logic nghiệp vụ; chỉ gọi qua tên module của core/, services/, infra/.
- Không ghi nội dung CV, họ tên hay tên file vào log hay thông báo lỗi.
- Chuỗi thông báo lỗi trả về cho người dùng hoàn toàn bằng tiếng Việt viết sẵn.
"""
import asyncio
import base64
import hashlib
import io
import json
import logging
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from core import pdf_status, pipeline
from infra import logging_setup, settings
from services.extraction import base as extraction
from services.pdf import labels, render
from services.privacy import checks
from api.state import RunData, run_store

log = logging.getLogger("app")

# Cache ảnh xem trước PDF (hash sha256 + page -> bytes png)
_preview_cache: dict[tuple[str, int], bytes] = {}
_preview_cache_lock = asyncio.Lock()
MAX_PREVIEW_CACHE = 64


# Lưu ảnh render trang PDF vào cache
def _cache_preview(pdf_hash: str, page: int, png_bytes: bytes) -> None:
    if len(_preview_cache) >= MAX_PREVIEW_CACHE and (pdf_hash, page) not in _preview_cache:
        oldest_key = next(iter(_preview_cache))
        _preview_cache.pop(oldest_key, None)
    _preview_cache[(pdf_hash, page)] = png_bytes


# Kiểm tra sức khoẻ của ứng dụng
async def health(request: Request) -> JSONResponse:
    """Kiểm tra server còn sống, thay thế /_stcore/health của Streamlit."""
    return JSONResponse({"status": "ok"})


# Lấy cấu hình khởi tạo cho client
async def get_config(request: Request) -> JSONResponse:
    """Trả về các thông số cấu hình và logo header dạng base64."""
    try:
        buf = io.BytesIO()
        cropped = render.crop_logo(settings.logo_header(), 640)
        cropped.save(buf, "PNG", optimize=True)
        logo_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        log.exception("Không tạo được logo header base64")
        logo_b64 = ""

    return JSONResponse({
        "max_upload_mb": settings.MAX_UPLOAD_MB,
        "allowed_extensions": list(settings.CV_EXTENSIONS),
        "image_extensions": list(settings.IMAGE_EXTENSIONS),
        "pdf_languages": dict(labels.PDF_LANGS),
        "logo_header_b64": logo_b64,
        "default_stage_labels": pipeline.stage_labels(),
    })


# Trích xuất nội dung CV và stream tiến độ/kết quả qua SSE
async def extract_cv(request: Request) -> Response:
    """Nhận file CV tải lên, xử lý qua pipeline.read_cv và stream tiến độ qua SSE."""
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        return JSONResponse({"error": "Yêu cầu phải là multipart/form-data."}, status_code=400)

    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "Dữ liệu gửi lên không đúng định dạng."}, status_code=400)

    file_field = form.get("file")
    if not file_field or not hasattr(file_field, "read"):
        return JSONResponse({"error": "Chị vui lòng đính kèm file CV trước khi gửi."}, status_code=400)

    filename = getattr(file_field, "filename", "") or "cv"
    project = str(form.get("project") or "").strip()
    position = str(form.get("position") or "").strip()

    file_bytes = await file_field.read()
    if not file_bytes:
        return JSONResponse({"error": "File CV rỗng, vui lòng chọn file khác."}, status_code=400)

    # Kiểm tra kích thước và loại file trước khi đưa vào hàng đợi
    try:
        extraction.check_file(file_bytes, filename)
    except extraction.ExtractionError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    run_id = logging_setup.new_run_id()
    logging_setup.set_run_id(run_id)
    log.info("Nhận CV %s (%.0f KB)", logging_setup.mask_filename(filename), len(file_bytes) / 1024)

    run = run_store.get_or_create(run_id)
    run.original_bytes = file_bytes
    run.original_name = filename
    run.project = project
    run.position = position

    # Generator tạo sự kiện Server-Sent Events (SSE)
    async def sse_event_stream():
        event_queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        labels_list = pipeline.stage_labels()

        # Báo vị trí trong hàng đợi
        def on_wait(pos: int) -> None:
            loop.call_soon_threadsafe(
                event_queue.put_nowait,
                ("wait", {"queue_pos": pos, "what": "đọc CV"}),
            )

        # Báo tiến độ giai đoạn thật
        def on_progress(step: int) -> None:
            step_label = labels_list[step] if step < len(labels_list) else ""
            loop.call_soon_threadsafe(
                event_queue.put_nowait,
                ("progress", {"step": step, "label": step_label, "labels": labels_list}),
            )

        # Chạy trích xuất trong worker thread để không chặn event loop
        def run_extraction():
            logging_setup.set_run_id(run_id)
            try:
                res = pipeline.read_cv(
                    file_bytes,
                    filename,
                    project,
                    position,
                    on_progress=on_progress,
                    on_wait=on_wait,
                )
                loop.call_soon_threadsafe(event_queue.put_nowait, ("result", res))
            except Exception as exc:
                loop.call_soon_threadsafe(event_queue.put_nowait, ("exception", exc))

        asyncio.create_task(asyncio.to_thread(run_extraction))

        while True:
            item_type, item_data = await event_queue.get()
            if item_type == "wait":
                yield f"event: wait\ndata: {json.dumps(item_data, ensure_ascii=False)}\n\n"
            elif item_type == "progress":
                yield f"event: progress\ndata: {json.dumps(item_data, ensure_ascii=False)}\n\n"
            elif item_type == "result":
                res = item_data
                run.photo = res.photo
                payload = {
                    "run_id": run_id,
                    "cv": res.cv,
                    "has_photo": res.photo is not None,
                    "photo_url": f"/api/photo/preview/{run_id}" if res.photo is not None else None,
                    "warnings": [{"path": w.path, "message": w.message} for w in res.warnings],
                    "confidence": res.confidence,
                    "original_filename": filename,
                }
                yield f"event: done\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
                break
            elif item_type == "exception":
                err = item_data
                error_msg = str(err) if isinstance(err, (pipeline.CVReadError, extraction.ExtractionError)) else pipeline.read_error_message(err)
                yield f"event: error\ndata: {json.dumps({'error': error_msg}, ensure_ascii=False)}\n\n"
                break

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Xác thực cấu trúc hồ sơ và thông tin nhạy cảm
async def validate_cv(request: Request) -> JSONResponse:
    """Kiểm tra hồ sơ theo schema CVData và quét vi phạm PII."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Dữ liệu JSON không hợp lệ."}, status_code=400)

    cv = body.get("cv") or {}
    project = str(body.get("project") or "")
    position = str(body.get("position") or "")

    cv_normalized, structure_errors = pipeline.validate_structure(cv)
    active_cv = cv_normalized if not structure_errors else cv
    violations = checks.scan_pii_export(active_cv, project, position)

    return JSONResponse({
        "valid": not structure_errors and not violations,
        "structure_errors": structure_errors,
        "violations": violations,
        "normalized_cv": cv_normalized,
    })


# Dựng file PDF cho hồ sơ
async def build_pdf(request: Request) -> Response:
    """Dựng PDF từ hồ sơ đang sửa, kiểm tra checklist và tính toán trạng thái."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Dữ liệu JSON không hợp lệ."}, status_code=400)

    run_id = str(body.get("run_id") or "")
    cv = body.get("cv")
    if not cv:
        return JSONResponse({"error": "Thiếu dữ liệu hồ sơ CV."}, status_code=400)

    project = str(body.get("project") or "")
    position = str(body.get("position") or "")
    lang = str(body.get("lang") or "vi")

    run = run_store.get_or_create(run_id) if run_id else RunData(run_id=logging_setup.new_run_id())
    logging_setup.set_run_id(run.run_id)

    # Chạy make_pdf trong worker thread
    def do_build():
        logging_setup.set_run_id(run.run_id)
        return pipeline.make_pdf(
            cv,
            project,
            position,
            run.photo,
            on_wait=None,
            lang=lang,
        )

    try:
        pdf_res = await asyncio.to_thread(do_build)
    except pipeline.RenderQueueTimeout as e:
        return JSONResponse({"error": str(e)}, status_code=429)
    except Exception as e:
        log.exception("Dựng PDF thất bại")
        return JSONResponse({"error": f"Dựng PDF thất bại. {str(e)}"}, status_code=400)

    fingerprint = pipeline.content_fingerprint(cv, project, position, run.photo, lang)

    # Lưu vào run_store
    run.pdf_bytes = pdf_res.pdf_bytes
    run.pdf_name = pdf_res.filename
    run.pdf_cv = cv
    run.pdf_lang = pdf_res.lang
    run.pdf_fingerprint = fingerprint
    run.checklist = pdf_res.checklist
    run.summary = pdf_res.summary
    run.project = project
    run.position = position

    # Đếm số trang PDF
    import pymupdf as fitz
    with fitz.open(stream=pdf_res.pdf_bytes, filetype="pdf") as doc:
        page_count = doc.page_count

    # Tính trạng thái ban đầu
    status_obj = pdf_status.compute_status(
        has_pdf=True,
        pdf_fingerprint=fingerprint,
        current_fingerprint=fingerprint,
        checklist=pdf_res.checklist,
        has_violations=False,
        has_structure_errors=False,
        checked_generated=False,
        reviewed=False,
    )

    return JSONResponse({
        "run_id": run.run_id,
        "filename": pdf_res.filename,
        "fingerprint": fingerprint,
        "lang": pdf_res.lang,
        "page_count": page_count,
        "summary": pdf_res.summary,
        "checklist": pdf_res.checklist,
        "status": {
            "outdated": status_obj.outdated,
            "pdf_dirty": status_obj.pdf_dirty,
            "can_download": status_obj.can_download,
            "pill_kind": status_obj.pill_kind,
            "pill_text": status_obj.pill_text,
        },
    })


# Tính toán trạng thái thanh status bar và nút tải
async def get_pdf_status(request: Request) -> JSONResponse:
    """Tính toán trạng thái theo luật của core/pdf_status.py."""
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Dữ liệu JSON không hợp lệ."}, status_code=400)

    has_pdf = bool(body.get("has_pdf"))
    pdf_fingerprint = body.get("pdf_fingerprint")
    current_fingerprint = str(body.get("current_fingerprint") or "")
    checklist = body.get("checklist")
    has_violations = bool(body.get("has_violations"))
    has_structure_errors = bool(body.get("has_structure_errors"))
    checked_generated = bool(body.get("checked_generated"))
    reviewed = bool(body.get("reviewed"))

    st = pdf_status.compute_status(
        has_pdf=has_pdf,
        pdf_fingerprint=pdf_fingerprint,
        current_fingerprint=current_fingerprint,
        checklist=checklist,
        has_violations=has_violations,
        has_structure_errors=has_structure_errors,
        checked_generated=checked_generated,
        reviewed=reviewed,
    )

    return JSONResponse({
        "outdated": st.outdated,
        "pdf_dirty": st.pdf_dirty,
        "can_download": st.can_download,
        "pill_kind": st.pill_kind,
        "pill_text": st.pill_text,
    })


# Xem trước hình ảnh một trang của file CV gốc
async def preview_original_page(request: Request) -> Response:
    """Trả về hình ảnh PNG của trang thứ {page} của CV gốc."""
    run_id = request.path_params.get("run_id", "")
    try:
        page_num = int(request.path_params.get("page", 1))
    except ValueError:
        return JSONResponse({"error": "Số trang không hợp lệ."}, status_code=400)

    run = run_store.get(run_id)
    if not run or not run.original_bytes:
        return JSONResponse({"error": "Không tìm thấy phiên xử lý hoặc file gốc."}, status_code=404)

    ext = Path(run.original_name).suffix.lower()
    if ext in settings.IMAGE_EXTENSIONS:
        return Response(run.original_bytes, media_type="image/png")

    if ext != ".pdf":
        return JSONResponse({"error": "File DOCX: không xem trước được, hãy mở file gốc để đối chiếu."}, status_code=400)

    try:
        import pymupdf as fitz
        with fitz.open(stream=run.original_bytes, filetype="pdf") as doc:
            if page_num < 1 or page_num > doc.page_count:
                return JSONResponse({"error": "Trang xem trước không tồn tại."}, status_code=404)
            pix = doc[page_num - 1].get_pixmap(dpi=110)
            png_bytes = pix.tobytes("png")
        return Response(png_bytes, media_type="image/png")
    except Exception:
        log.exception("Không xem trước được file gốc %s", logging_setup.mask_filename(run.original_name))
        return JSONResponse({"error": "Không xem trước được file gốc."}, status_code=400)


# Lấy thông tin số trang và trạng thái xem trước của CV gốc
async def preview_original_info(request: Request) -> JSONResponse:
    """Trả về số trang và định dạng của file CV gốc."""
    run_id = request.path_params.get("run_id", "")
    run = run_store.get(run_id)
    if not run or not run.original_bytes:
        return JSONResponse({"error": "Không tìm thấy phiên xử lý."}, status_code=404)

    ext = Path(run.original_name).suffix.lower()
    if ext in settings.IMAGE_EXTENSIONS:
        return JSONResponse({
            "page_count": 1,
            "file_type": "image",
            "can_preview": True,
            "message": None,
        })

    if ext == ".docx":
        return JSONResponse({
            "page_count": 0,
            "file_type": "docx",
            "can_preview": False,
            "message": "File DOCX: không xem trước được, hãy mở file gốc để đối chiếu.",
        })

    try:
        import pymupdf as fitz
        with fitz.open(stream=run.original_bytes, filetype="pdf") as doc:
            count = doc.page_count
        return JSONResponse({
            "page_count": count,
            "file_type": "pdf",
            "can_preview": True,
            "message": None,
        })
    except Exception:
        return JSONResponse({
            "page_count": 0,
            "file_type": "unknown",
            "can_preview": False,
            "message": "Không xem trước được file gốc (có thể file có mật khẩu hoặc định dạng đặc biệt).",
        })


# Xem trước hình ảnh một trang của file PDF đã dựng
async def preview_pdf_page(request: Request) -> Response:
    """Trả về ảnh PNG trang thứ {page} của bản PDF vừa dựng."""
    run_id = request.path_params.get("run_id", "")
    try:
        page_num = int(request.path_params.get("page", 1))
    except ValueError:
        return JSONResponse({"error": "Số trang không hợp lệ."}, status_code=400)

    run = run_store.get(run_id)
    if not run or not run.pdf_bytes:
        return JSONResponse({"error": "Chưa có bản PDF cho phiên này."}, status_code=404)

    pdf_hash = hashlib.sha256(run.pdf_bytes).hexdigest()
    cached = _preview_cache.get((pdf_hash, page_num))
    if cached:
        return Response(cached, media_type="image/png")

    try:
        import pymupdf as fitz
        with fitz.open(stream=run.pdf_bytes, filetype="pdf") as doc:
            if page_num < 1 or page_num > doc.page_count:
                return JSONResponse({"error": "Trang xem trước không tồn tại."}, status_code=404)
            pix = doc[page_num - 1].get_pixmap(dpi=110)
            png_bytes = pix.tobytes("png")
        _cache_preview(pdf_hash, page_num, png_bytes)
        return Response(png_bytes, media_type="image/png")
    except Exception:
        log.exception("Không tạo được ảnh xem trước PDF")
        return JSONResponse({"error": "Không tạo được ảnh xem trước PDF."}, status_code=400)


# Lấy thông tin số trang của bản PDF đã dựng
async def preview_pdf_info(request: Request) -> JSONResponse:
    """Trả về số trang của bản PDF vừa dựng."""
    run_id = request.path_params.get("run_id", "")
    run = run_store.get(run_id)
    if not run or not run.pdf_bytes:
        return JSONResponse({"error": "Chưa có bản PDF cho phiên này."}, status_code=404)

    try:
        import pymupdf as fitz
        with fitz.open(stream=run.pdf_bytes, filetype="pdf") as doc:
            count = doc.page_count
        return JSONResponse({"page_count": count})
    except Exception:
        return JSONResponse({"page_count": 0})


# Tải file PDF về máy và lưu bản sao trên server
async def download_pdf(request: Request) -> Response:
    """Tải PDF về máy người dùng. Có save_copy=true thì lưu kèm bản sao trong data/output."""
    run_id = request.path_params.get("run_id", "")
    save_copy = request.query_params.get("save_copy", "true").lower() in ("true", "1")

    run = run_store.get(run_id)
    if not run or not run.pdf_bytes:
        return JSONResponse({"error": "Không tìm thấy file PDF để tải về."}, status_code=404)

    save_error = None
    if save_copy:
        save_error = pipeline.store_export(
            settings.output_dir(),
            run.pdf_name or "ho-so.pdf",
            run.pdf_bytes,
            run_id=run.run_id,
            cv=run.pdf_cv,
            project=run.project,
            position=run.position,
            lang=run.pdf_lang,
        )

    headers = {
        "Content-Disposition": f'attachment; filename="{run.pdf_name or "ho-so.pdf"}"',
        "Content-Type": "application/pdf",
    }
    if save_error:
        # Lỗi lưu bản sao không làm hỏng lượt tải về của người dùng (Q5/CLAUDE.md)
        headers["X-Save-Copy-Error"] = base64.b64encode(save_error.encode("utf-8")).decode("ascii")

    return Response(run.pdf_bytes, media_type="application/pdf", headers=headers)


# Cắt ảnh chân dung tỉ lệ 29:38
async def crop_photo(request: Request) -> JSONResponse:
    """Cắt ảnh chân dung thành tỉ lệ 29:38 theo khuôn mặt (OpenCV)."""
    try:
        form = await request.form()
    except Exception:
        return JSONResponse({"error": "Dữ liệu form không hợp lệ."}, status_code=400)

    file_field = form.get("file")
    if not file_field or not hasattr(file_field, "read"):
        return JSONResponse({"error": "Vui lòng chọn file ảnh để tải lên."}, status_code=400)

    filename = getattr(file_field, "filename", "") or "photo.png"
    photo_bytes = await file_field.read()
    if not photo_bytes:
        return JSONResponse({"error": "File ảnh rỗng."}, status_code=400)

    try:
        extraction.check_file(photo_bytes, filename)
        cropped_png = render.crop_portrait(photo_bytes)
        photo_b64 = "data:image/png;base64," + base64.b64encode(cropped_png).decode("ascii")
        photo_id = f"photo_{hashlib.md5(photo_bytes).hexdigest()[:10]}"
        return JSONResponse({
            "photo_b64": photo_b64,
            "photo_id": photo_id,
        })
    except extraction.ExtractionError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception:
        log.exception("Không đọc được ảnh chân dung tải lên %s", logging_setup.mask_filename(filename))
        return JSONResponse({"error": "Không đọc được file ảnh này, hãy thử ảnh khác."}, status_code=400)


# Xem trước ảnh chân dung của phiên
async def preview_photo(request: Request) -> Response:
    """Lấy ảnh chân dung dạng PNG của phiên."""
    run_id = request.path_params.get("run_id", "")
    run = run_store.get(run_id)
    if not run or not run.photo:
        return JSONResponse({"error": "Không có ảnh chân dung."}, status_code=404)
    return Response(run.photo, media_type="image/png")


# Bỏ ảnh chân dung khỏi phiên
async def delete_photo(request: Request) -> JSONResponse:
    """Xoá ảnh chân dung của phiên hiện tại."""
    run_id = request.path_params.get("run_id", "")
    run_store.clear_photo(run_id)
    return JSONResponse({"ok": True})
