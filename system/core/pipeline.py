# Gói core/: nghiệp vụ thuần Python (không Streamlit) — pipeline xử lý hồ sơ, luật trạng thái/khoá tải.
"""Nghiệp vụ xử lý hồ sơ (A1/A2) — thuần Python, không Streamlit, import được trong test.

Gọi các module khác qua TÊN MODULE (render.build_pdf, extraction.get_extractor...) chứ không import thẳng tên hàm,
để test thay được bằng bản giả (monkeypatch) và để app.py chỉ còn lo giao diện + state.
"""
import hashlib
import json
import logging
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from services.privacy import checks
from services.extraction import base as extraction
from services.pdf import render
from infra.logging_setup import mask_filename, set_run_id
from infra.settings import extract_max_concurrent, extract_queue_timeout, render_max_concurrent, render_queue_timeout
from infra.storage import unique_path
from services.ai.models import CVData

# Giữ tên logger "app" như trước khi tách file -> dòng log vẫn dạng "[run_id] app: ..."
log = logging.getLogger("app")


# Lỗi đọc CV, thông điệp hiển thị cho người dùng
class CVReadError(Exception):
    """Đọc CV thất bại; thông điệp là câu tiếng Việt hiển thị thẳng cho người dùng."""


# Kết quả đọc CV: hồ sơ + ảnh chân dung + kênh riêng của bộ trích xuất (cảnh báo, độ tin cậy, giai đoạn)
@dataclass
class ReadResult:
    cv: dict
    photo: bytes | None
    warnings: list[extraction.ReviewNote] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    stages: list[extraction.StageRun] = field(default_factory=list)
    backend: str = ""


# Kết quả dựng PDF: file, tên, checklist, tin nhắn tóm tắt
@dataclass
class PdfResult:
    pdf_bytes: bytes
    filename: str
    checklist: list[dict]
    summary: str


# Các giai đoạn sau phần trích xuất (do pipeline chạy, chung cho mọi bộ trích xuất)
PHOTO_STAGE = extraction.Stage("photo", "Lấy ảnh chân dung từ CV gốc")
PDF_STAGE = extraction.Stage("pdf", "Kiểm tra thông tin nhạy cảm, dựng PDF và checklist chất lượng")


# Nhãn các bước thật cho màn hình "đang xử lý": bước của bộ trích xuất + ảnh chân dung + dựng PDF
def stage_labels() -> list[str]:
    """Nhãn các bước thật: bước của bộ trích xuất đang cấu hình, rồi ảnh chân dung, rồi dựng PDF."""
    try:
        labels = [s.label for s in extraction.get_extractor().stages]
    except extraction.ExtractionError:     # cấu hình sai -> vẫn vẽ được màn hình chờ; read_cv sẽ báo lỗi rõ ràng
        labels = ["Đọc CV gốc"]
    return labels + [PHOTO_STAGE.label, PDF_STAGE.label]


# ----- Hàng đợi đọc CV (dùng chung cho mọi phiên; riêng với hàng đợi dựng PDF) -----
_extract_slots = threading.BoundedSemaphore(extract_max_concurrent())
_extract_waiting = 0
_extract_lock = threading.Lock()


# Giành một lượt đọc CV; phải chờ thì báo vị trí trong hàng qua `on_wait`
def _take_extract_slot(on_wait: Callable[[int], None] | None) -> None:
    global _extract_waiting
    if _extract_slots.acquire(blocking=False):
        return
    with _extract_lock:
        _extract_waiting += 1
        pos = _extract_waiting
    try:
        log.info("Chờ tới lượt đọc CV (vị trí %d trong hàng)", pos)
        if on_wait:
            on_wait(pos)
        if not _extract_slots.acquire(timeout=extract_queue_timeout()):
            raise extraction.ExtractionError(f"Đang có nhiều CV được đọc cùng lúc, đã chờ quá {extract_queue_timeout()} "
                                             "giây. Vui lòng gửi lại sau ít phút.")
    finally:
        with _extract_lock:
            _extract_waiting -= 1


# Đọc CV qua bộ trích xuất đang cấu hình + lấy ảnh chân dung
def read_cv(data: bytes, filename: str, project: str, position: str,
            on_progress: Callable[[int], None] | None = None,
            on_wait: Callable[[int], None] | None = None) -> ReadResult:
    """Đọc CV + lấy ảnh chân dung. Mọi lỗi -> CVReadError có câu thông báo dễ hiểu (không để traceback lọt ra).

    `on_progress(i)`: gọi khi BẮT ĐẦU bước thứ i trong stage_labels() -> màn hình chờ chỉ hiện bước đang chạy thật.
    `on_wait(n)`: đang xếp hàng chờ tới lượt đọc (vị trí n) — tối đa EXTRACT_MAX_CONCURRENT lượt đọc cùng lúc
    (một lượt = trích xuất + lấy ảnh chân dung).
    Kết quả trích xuất luôn được kiểm tra lại bằng CVData (đúng schema) dù bộ trích xuất là gì.
    """
    try:
        extraction.check_file(data, filename)          # S7: chặn trước mọi bộ trích xuất
        extractor = extraction.get_extractor()
        keys = [s.key for s in extractor.stages]
        report = (lambda key: on_progress(keys.index(key))) if on_progress else None
        doc = extraction.SourceDoc(data, filename, project, position, render.today_vn())
        _take_extract_slot(on_wait)
        try:
            res = extractor.extract(doc, report)
            cv = CVData.model_validate(res.cv).model_dump()
            if on_progress:
                on_progress(len(keys))
            # Dò khuôn mặt (OpenCV) tốn CPU -> chạy TRONG lượt đọc để cũng bị giới hạn số lượt đồng thời
            photo = render.extract_photo(data, filename)                 # PDF / DOCX / ảnh; lỗi -> None
        finally:
            _extract_slots.release()
    except extraction.ExtractionError as e:
        raise CVReadError(str(e)) from e
    except ValidationError as e:
        log.error("Bộ trích xuất trả dữ liệu sai schema (%d lỗi)", e.error_count())
        raise CVReadError("Bộ đọc CV trả về dữ liệu sai cấu trúc. Hãy thử lại hoặc nhập tay.") from e
    except Exception as e:   # file hỏng, lỗi mạng, lỗi bất ngờ...
        log.exception("Lỗi khi đọc CV %s", mask_filename(filename))   # S6: không ghi tên file
        raise CVReadError(read_error_message(e)) from e
    for st in res.stages:    # R4: mỗi giai đoạn một dòng log (có run_id), không ghi nội dung CV
        log.info("Giai đoạn %s: %.1f giây (%s) %s", st.key, st.seconds, st.status, st.detail)
    log.info("Đọc CV xong (%s): %d mục, %d cảnh báo, ảnh chân dung: %s", res.backend, len(cv["sections"]),
             len(res.warnings), "có" if photo else "không")
    warnings, confidence = list(res.warnings), dict(res.confidence)
    if position.strip():     # người dùng nhập Vị trí -> ghi đè chức danh cào từ CV (dòng dưới họ tên trong PDF)
        cv["target_title"] = position.strip()
        confidence.pop("target_title", None)             # do người dùng nhập -> không còn nhãn "Cần xem"
        warnings = [w for w in warnings if w.path != "target_title"]
    return ReadResult(cv, photo, warnings, confidence, list(res.stages), res.backend)


# ----- Hàng đợi dựng PDF (dùng chung cho MỌI phiên Streamlit — chúng chạy chung 1 tiến trình) -----
_render_slots = threading.BoundedSemaphore(render_max_concurrent())
_queue_length = 0
_queue_lock = threading.Lock()


# Chờ hàng đợi dựng PDF quá lâu
class RenderQueueTimeout(RuntimeError):
    """Chờ tới lượt dựng PDF quá RENDER_QUEUE_TIMEOUT giây."""


# Số người đang chờ dựng PDF
def queue_length() -> int:
    """Số người đang xếp hàng chờ dựng PDF (để hiển thị)."""
    return _queue_length


# Dựng PDF (qua hàng đợi dùng chung) + checklist + tóm tắt
def make_pdf(cv: dict, project: str, position: str, photo: bytes | None,
             on_wait: Callable[[int], None] | None = None) -> PdfResult:
    """Dựng PDF vào thư mục tạm + checklist + tin nhắn tóm tắt. Lỗi -> ném ra (app ghi log và báo).

    Tối đa RENDER_MAX_CONCURRENT lượt dựng chạy cùng lúc trên toàn app; người tới sau xếp hàng.
    Phải chờ thì gọi `on_wait(queue_pos)` trước để giao diện báo "đang xếp hàng".
    """
    global _queue_length
    if not _render_slots.acquire(blocking=False):
        with _queue_lock:
            _queue_length += 1
            queue_pos = _queue_length
        try:
            log.info("Chờ tới lượt dựng PDF (vị trí %d trong hàng)", queue_pos)
            if on_wait:
                on_wait(queue_pos)
            if not _render_slots.acquire(timeout=render_queue_timeout()):
                raise RenderQueueTimeout(f"Đang có nhiều hồ sơ dựng cùng lúc, đã chờ quá {render_queue_timeout()} giây. "
                                    "Vui lòng bấm Cập nhật PDF lại sau ít phút.")
        finally:
            with _queue_lock:
                _queue_length -= 1
    try:
        with tempfile.TemporaryDirectory() as tmp:
            p = render.build_pdf(cv, project, position, photo, Path(tmp))
            checklist = checks.scan_pdf(p)
            result = PdfResult(p.read_bytes(), p.name, checklist, summary_message(cv, project, position))
    finally:
        _render_slots.release()
    log.info("Đã dựng PDF, checklist %d/%d đạt", sum(r["ok"] for r in checklist), len(checklist))
    return result


# Lưu bản sao PDF đã xuất, không ghi đè
def save_copy(folder: Path, filename: str, pdf_bytes: bytes, run_id: str | None = None) -> Path:
    """Lưu bản sao PDF đã xuất; trùng tên thì thêm hậu tố giờ (Q5), không ghi đè.

    `run_id`: hàm này chạy trong callback của nút Tải — chạy TRƯỚC khi script kịp gắn run_id cho lượt chạy,
    nên phải gắn lại ở đây để dòng log mang đúng mã của hồ sơ.
    """
    if run_id:
        set_run_id(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = unique_path(folder, filename)
    target.write_bytes(pdf_bytes)
    log.info("Đã lưu bản xuất vào thư mục output (%s)", "tên chuẩn" if target.name == filename else "thêm hậu tố giờ")
    return target


# Đọc ô đúng/sai trong bảng chữ
def is_truthy(v) -> bool:
    """Ô đúng/sai trong bảng chữ: chỉ 'x' (hoặc có/yes/true/1) mới là đúng."""
    return v is True or str(v or "").strip().lower() in {"x", "có", "co", "yes", "true", "1"}


# Kiểm tra hồ sơ đã sửa theo CVData
def validate_structure(cv: dict) -> tuple[dict | None, list[str]]:
    """Kiểm tra lại hồ sơ đã sửa bằng CVData. Trả (hồ sơ chuẩn hoá | None, danh sách lỗi)."""
    try:
        return CVData.model_validate(cv).model_dump(), []
    except ValidationError as e:
        errors = []
        for err in e.errors():
            where = ".".join(str(x) for x in err["loc"]) or "hồ sơ"
            errors.append(f"{where}: {err['msg'].removeprefix('Value error, ')}")
        return None, errors


# Mã băm nội dung để biết PDF còn khớp không
def content_fingerprint(cv: dict, project: str, position: str, photo: bytes | None) -> str:
    """Mã nhận diện nội dung đầu vào của PDF -> biết PDF đã xuất còn khớp màn hình không."""
    payload = json.dumps([cv, project, position], ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload + (photo or b"")).hexdigest()


# Tin nhắn tóm tắt gửi kèm hồ sơ
def summary_message(cv: dict, project: str, position: str) -> str:
    """Khung tin nhắn mục 8 SKILL.md, giọng trung tính."""
    n = cv["model_notes"]
    title = position or cv.get("target_title") or ""
    bullet_lines = lambda xs: "\n".join(f"  - {x}" for x in xs) if xs else "  - (không có)"
    return (
        f"Hồ sơ ứng viên: {cv['full_name']} – {title}\n\n"
        f"• Dự án đã gắn: {project or '(để trống)'}\n"
        f"• Thông tin đã bỏ khỏi CV:\n{bullet_lines(n['removed'])}\n"
        f"• Lương mong muốn: {cv.get('expected_salary') or 'CV không ghi'} (đã bỏ khỏi CV)\n"
        f"• Hệ thống tự lập/điều chỉnh:\n{bullet_lines(n['self_created'])}\n\n"
        f"Lưu ý cần xác minh trước khi gửi khách:\n{bullet_lines(n['recruiting_flags'] + n['other'])}\n"
    )


# Đổi lỗi kỹ thuật thành câu dễ hiểu
def read_error_message(e: Exception) -> str:
    """Đổi lỗi kỹ thuật (không phải ExtractionError) thành câu thông báo dễ hiểu."""
    error_name = type(e).__name__
    if error_name in ("BadZipFile", "PackageNotFoundError", "UnidentifiedImageError") or "zip" in str(e).lower():
        return ("File CV bị hỏng hoặc không đúng định dạng. Hãy mở file, lưu lại thành PDF hoặc DOCX "
                "rồi gửi lại.")
    if isinstance(e, (ConnectionError, TimeoutError, OSError)):
        return "Không đọc được file CV trên máy chủ (lỗi đọc/ghi tệp). Vui lòng gửi lại sau ít phút."
    return "Có lỗi không mong muốn khi đọc CV. Vui lòng gửi lại, nếu vẫn lỗi hãy thử file khác."
