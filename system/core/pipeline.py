# Gói core/: nghiệp vụ thuần Python (không Streamlit) — pipeline xử lý hồ sơ, luật trạng thái/khoá tải.
"""Nghiệp vụ xử lý hồ sơ (A1/A2) — thuần Python, không Streamlit, import được trong test.

Gọi các module khác qua TÊN MODULE (render.build_pdf, extraction.get_extractor...) chứ không import thẳng tên hàm,
để test thay được bằng bản giả (monkeypatch) và để app.py chỉ còn lo giao diện + state.
"""
import hashlib
import json
import logging
import re
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime
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

# Định danh + phiên bản cấu trúc file JSON lưu kèm PDF (đổi cấu trúc thì tăng số)
EXPORT_FORMAT = "fillcv-lighthuman/export-1"


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
    lang: str = "vi"          # ngôn ngữ xuất của bản PDF này


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
            on_wait: Callable[[int], None] | None = None, keep_contact: bool = False) -> ReadResult:
    """Đọc CV + lấy ảnh chân dung. `keep_contact`: giữ thông tin liên hệ của ứng viên (SĐT, email, địa chỉ, link) thay vì cắt bỏ. Mọi lỗi -> CVReadError có câu thông báo dễ hiểu (không để traceback lọt ra).

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
        doc = extraction.SourceDoc(data, filename, project, position, render.today_vn(), keep_contact=keep_contact)
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
             on_wait: Callable[[int], None] | None = None, lang: str = "vi",
             keep_contact: bool = False) -> PdfResult:
    """Dựng PDF vào thư mục tạm + checklist + tin nhắn tóm tắt. Lỗi -> ném ra (app ghi log và báo).

    Tối đa RENDER_MAX_CONCURRENT lượt dựng chạy cùng lúc trên toàn app; người tới sau xếp hàng.
    Phải chờ thì gọi `on_wait(queue_pos)` trước để giao diện báo "đang xếp hàng".
    `lang`: ngôn ngữ xuất PDF ('vi' | 'en') — nhãn cố định, tiêu đề mục chuẩn, tên file, checklist header.
    `keep_contact`: tuỳ chọn giữ nguyên thông tin liên hệ (True) hoặc cắt bỏ PII liên hệ như cũ (False).
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
            p = render.build_pdf(cv, project, position, photo, Path(tmp), lang=lang)
            checklist = checks.scan_pdf(p, lang=lang, keep_contact=keep_contact)
            result = PdfResult(p.read_bytes(), p.name, checklist, summary_message(cv, project, position), lang)
    finally:
        _render_slots.release()
    log.info("Đã dựng PDF (%s), checklist %d/%d đạt", lang, sum(r["ok"] for r in checklist), len(checklist))
    return result


# Lưu bản sao khi bấm Tải PDF; lỗi thì ghi log an toàn và trả câu báo cho người dùng
def store_export(folder: Path, filename: str, pdf_bytes: bytes, **kwargs) -> str | None:
    """Gọi save_copy trong callback nút Tải. Trả None khi lưu được, hoặc câu báo lỗi (không chứa đường dẫn).

    Không ghi chuỗi lỗi/traceback vào log: thông báo của OSError chứa đường dẫn = họ tên ứng viên (S6).
    Lỗi không làm hỏng lượt tải: file PDF vẫn tải về máy người dùng bình thường.
    """
    try:
        save_copy(folder, filename, pdf_bytes, **kwargs)
    except Exception as e:
        log.error("Không lưu được bản sao vào thư mục output: %s (errno %s)", type(e).__name__,
                  getattr(e, "errno", None))
        hint = " Thư mục lưu không có quyền ghi." if isinstance(e, PermissionError) else ""
        return f"File PDF vẫn tải về máy bình thường, nhưng máy chủ chưa lưu được bản sao.{hint} Hãy báo người quản trị."
    return None


# Lưu bản sao PDF đã xuất, không ghi đè
def save_copy(folder: Path, filename: str, pdf_bytes: bytes, run_id: str | None = None,
              cv: dict | None = None, project: str = "", position: str = "", lang: str = "vi") -> Path:
    """Lưu bản sao PDF đã xuất; trùng tên thì thêm hậu tố giờ (Q5), không ghi đè.

    Có `cv` -> lưu kèm file .json cùng tên (hồ sơ đúng như lúc dựng PDF) để sau này sửa lại không phải đọc CV gốc.
    `run_id`: hàm này chạy trong callback của nút Tải — chạy TRƯỚC khi script kịp gắn run_id cho lượt chạy,
    nên phải gắn lại ở đây để dòng log mang đúng mã của hồ sơ.
    """
    if run_id:
        set_run_id(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    target = unique_path(folder, filename)
    target.write_bytes(pdf_bytes)
    if cv is not None:
        target.with_suffix(".json").write_text(export_json(cv, project, position, lang), encoding="utf-8")
    log.info("Đã lưu bản xuất vào thư mục output (%s%s)", "tên chuẩn" if target.name == filename else "thêm hậu tố giờ",
             ", kèm JSON" if cv is not None else "")
    return target


# Nội dung file JSON lưu kèm PDF
def export_json(cv: dict, project: str, position: str, lang: str = "vi") -> str:
    """JSON lưu kèm PDF: thông tin lượt xuất + hồ sơ (đúng schema CVData, không có ảnh chân dung).

    Hồ sơ nằm riêng trong khoá "cv" vì CVData cấm trường thừa; đọc lại thì lấy data["cv"] rồi CVData.model_validate.
    """
    record = {
        "format": EXPORT_FORMAT,
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "extractor": extraction.extractor_version(),
        "project": project,
        "position": position,
        "pdf_language": lang,          # ngôn ngữ xuất PDF; "cv" là hồ sơ gốc chưa đổi nhãn
        "cv": cv,
    }
    return json.dumps(record, ensure_ascii=False, indent=2)


# Đọc ô đúng/sai trong bảng chữ
def is_truthy(v) -> bool:
    """Ô đúng/sai trong bảng chữ: chỉ 'x' (hoặc có/yes/true/1) mới là đúng."""
    return v is True or str(v or "").strip().lower() in {"x", "có", "co", "yes", "true", "1"}


# Cắt khoảng trắng hai đầu của một chuỗi (giá trị khác kiểu giữ nguyên)
def _strip(v):
    return v.strip() if isinstance(v, str) else v


# Chuỗi tuỳ chọn: rỗng sau khi cắt -> None
def _opt(v):
    v = _strip(v)
    return v if v != "" else None


# Danh sách chuỗi: cắt khoảng trắng và bỏ dòng trống (không phải danh sách thì giữ nguyên để schema báo lỗi)
def _clean_lines(items):
    if not isinstance(items, list):
        return items
    return [s for s in (_strip(x) for x in items) if s != ""]


# Danh sách dòng phụ (nhãn + nội dung): bỏ dòng không có nội dung
def _clean_meta(items):
    if not isinstance(items, list):
        return items
    rows = [{**m, "label": _opt(m.get("label")), "text": _strip(m.get("text", ""))} for m in items if isinstance(m, dict)]
    return [m for m in rows if m["text"] != ""]


# Danh sách nhóm việc: bỏ nhóm không có tiêu đề lẫn gạch đầu dòng
def _clean_groups(items):
    if not isinstance(items, list):
        return items
    rows = [{**g, "title": _opt(g.get("title")), "bullets": _clean_lines(g.get("bullets", []))} for g in items if isinstance(g, dict)]
    return [g for g in rows if g["title"] is not None or g["bullets"]]


# Dọn một công việc; trả None nếu công việc hoàn toàn trống
def _clean_job(job):
    if not isinstance(job, dict):
        return job
    subs = []
    for s in job.get("sub_roles") or []:
        if not isinstance(s, dict):
            continue
        s = {**s, "name": _strip(s.get("name", "")), "period": _opt(s.get("period")),
             "meta": _clean_meta(s.get("meta", [])), "groups": _clean_groups(s.get("groups", []))}
        if s["name"] != "" or s["meta"] or s["groups"]:
            subs.append(s)
    j = {**job, "company": _strip(job.get("company", "")), "period": _opt(job.get("period")), "role": _opt(job.get("role")),
         "meta": _clean_meta(job.get("meta", [])), "groups": _clean_groups(job.get("groups", [])), "sub_roles": subs}
    empty = j["company"] == "" and j["period"] is None and j["role"] is None and not (j["meta"] or j["groups"] or subs)
    return None if empty else j


# Dọn các dòng của mục dạng bảng: cắt khoảng trắng các trường, bỏ dòng trống hoàn toàn
def _clean_rows(items, required: tuple[str, ...], optional: tuple[str, ...] = ()):
    if not isinstance(items, list):
        return items
    rows = []
    for r in items:
        if not isinstance(r, dict):
            continue
        r = {**r, **{k: _strip(r.get(k, "")) for k in required}, **{k: _opt(r.get(k)) for k in optional}}
        if any(r[k] not in ("", None) for k in required + optional):
            rows.append(r)
    return rows


# Dọn một mục nội dung theo từng loại
def _clean_section(sec):
    if not isinstance(sec, dict):
        return sec
    cards = [{**c, "title": _strip(c.get("title", "")), "items": _clean_lines(c.get("items", []))}
             for c in (sec.get("cards") or []) if isinstance(c, dict)]
    jobs = [j for j in (_clean_job(j) for j in (sec.get("jobs") or [])) if j is not None]
    return {
        **sec,
        "title": _strip(sec.get("title", "")),
        "paragraphs": _clean_lines(sec.get("paragraphs", [])),
        "bullets": _clean_lines(sec.get("bullets", [])),
        "tags": _clean_lines(sec.get("tags", [])),
        "cards": [c for c in cards if c["title"] != "" or c["items"]],
        "career_path": _clean_rows(sec.get("career_path", []), ("period", "title", "company")),
        "education": _clean_rows(sec.get("education", []), ("title",), ("detail", "period")),
        "references": _clean_rows(sec.get("references", []), ("name",), ("title", "company")),
        "jobs": jobs,
    }


# Tách một dòng thông tin liên hệ khi bị dính nhiều thông tin trên 1 dòng (ngăn bởi •, SĐT, email...)
def _unpack_contact_fact(fact: dict) -> list[dict]:
    lbl = str(fact.get("label") or "").strip()
    val = str(fact.get("value") or "").strip()
    if not val:
        return []
    from services.privacy import checks
    found = checks.scan_text(val)
    if not found:
        if lbl.lower() in ("address", "địa chỉ", "dia chi"):
            val = re.sub(r"\s*[•·●▪|]\s*", ", ", val)
            val = re.sub(r"\s{2,}", " ", val).strip(" ,;|:–-")
            return [{"label": lbl, "value": val}]
        return [fact]
    emails = {v for k, v in found if k == "Email"}
    found_filtered = [(k, v) for k, v in found if not (k == "Đường link" and any(v in e for e in emails))]
    from services.extraction.rules import personal
    cleaned = personal._scrub(val, set())
    cleaned = re.sub(r"^(?:phone|email|address|điện thoại|địa chỉ|dia chi|sdt)\s*:\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*[•·●▪|]\s*", ", ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,;|:–-")
    if len(re.sub(r"[\W\d_]", "", cleaned)) < 3 and len(found_filtered) <= 1:
        return [fact]
    en = lbl.lower() in ("phone", "email", "address", "website", "social")
    res = []
    seen = set()
    for k, v in found_filtered:
        kind = personal._KIND_OF_CHECK.get(k, "phone")
        if kind == "phone":
            label_name = "Phone" if en else "Điện thoại"
        elif kind == "email":
            label_name = "Email"
        elif kind == "link":
            label_name = "Website"
        else:
            label_name = "Address" if en else "Địa chỉ"
        if v not in seen:
            seen.add(v)
            res.append({"label": label_name, "value": v})
    if cleaned and len(re.sub(r"[\W\d_]", "", cleaned)) >= 3:
        addr_lbl = "Address" if en else "Địa chỉ"
        res.append({"label": addr_lbl, "value": cleaned})
    return res if res else [fact]


# Dọn hồ sơ trước khi kiểm tra/dựng PDF
def clean_cv(cv: dict) -> dict:
    """Dọn hồ sơ người dùng vừa sửa tay: cắt khoảng trắng, bỏ dòng/hàng/ô trống.

    Ô nhập nhiều dòng (gạch đầu dòng, thẻ...) rất dễ để lại dòng trống -> nếu không dọn, template dựng ra
    gạch đầu dòng rỗng. Không đổi thứ tự, không thêm nội dung; không phải dict thì giữ nguyên để schema báo lỗi.
    """
    if not isinstance(cv, dict):
        return cv
    out = dict(cv)
    if "full_name" in out:
        out["full_name"] = _strip(out["full_name"])
    for key in ("target_title", "gender", "expected_salary"):
        if key in out:
            out[key] = _opt(out[key])
    if isinstance(out.get("facts"), list):
        facts = []
        for f in out["facts"]:
            if isinstance(f, dict):
                f_clean = {**f, "label": _strip(f.get("label", "")), "value": _strip(f.get("value", ""))}
                if f_clean["value"]:
                    facts.extend(_unpack_contact_fact(f_clean))
        out["facts"] = [f for f in facts if f["value"] != ""]
    if isinstance(out.get("stats"), list):
        stats = [{**s, "value": _strip(s.get("value", "")), "label": _strip(s.get("label", ""))}
                 for s in out["stats"] if isinstance(s, dict)]
        out["stats"] = [s for s in stats if s["value"] != "" or s["label"] != ""]
    if isinstance(out.get("sections"), list):
        out["sections"] = [_clean_section(s) for s in out["sections"]]
    return out


# Kiểm tra hồ sơ đã sửa theo CVData
def validate_structure(cv: dict) -> tuple[dict | None, list[str]]:
    """Dọn (clean_cv) rồi kiểm tra lại hồ sơ đã sửa bằng CVData. Trả (hồ sơ chuẩn hoá | None, danh sách lỗi)."""
    try:
        return CVData.model_validate(clean_cv(cv)).model_dump(), []
    except ValidationError as e:
        errors = []
        for err in e.errors():
            where = ".".join(str(x) for x in err["loc"]) or "hồ sơ"
            errors.append(f"{where}: {err['msg'].removeprefix('Value error, ')}")
        return None, errors


# Mã băm nội dung để biết PDF còn khớp không
def content_fingerprint(cv: dict, project: str, position: str, photo: bytes | None, lang: str = "vi",
                        keep_contact: bool = False) -> str:
    """Mã nhận diện nội dung đầu vào của PDF (cả ngôn ngữ xuất và tuỳ chọn liên hệ) -> biết PDF đã xuất còn khớp màn hình không."""
    payload = json.dumps([cv, project, position, lang, keep_contact], ensure_ascii=False, sort_keys=True).encode("utf-8")
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
