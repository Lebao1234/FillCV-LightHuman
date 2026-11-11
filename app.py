"""Web app nội bộ: CV ứng viên -> Hồ sơ ứng viên PDF chuẩn Light Human. Chạy: streamlit run app.py
Chỉ điều phối giao diện + session state (A1). Nghiệp vụ: core/. Giao diện: ui/ (components, profile_form, preview)."""
import logging

import streamlit as st

from infra.settings import CV_EXTENSIONS, logo_header, uploader_types, output_dir
from services.privacy.checks import scan_pii_export
from core import pipeline
from core.pdf_status import DOWNLOAD_LOCKED_HINT, pdf_outdated, compute_status
from services.extraction.base import ExtractionError, check_file
from infra.logging_setup import mask_filename, setup_logging, set_run_id, new_run_id
from infra.storage import delete_expired_files, retention_days
from services.pdf.render import crop_logo
from ui import components as ui
from ui.profile_form import edit_portrait, edit_profile
from ui.preview import pdf_page_images, png_b64, show_original, show_pdf

OUTPUT_DIR = output_dir()        # biến môi trường OUTPUT_DIR, mặc định data/output

st.set_page_config(page_title="Hồ sơ ứng viên – Light Human", page_icon=":material/description:", layout="wide")


# Dọn PDF hết hạn một lần khi khởi động app
@st.cache_resource(show_spinner=False)
def _cleanup_on_startup() -> int:
    """S2: xoá PDF quá hạn trong data/output — chạy 1 lần mỗi khi khởi động app."""
    return len(delete_expired_files(OUTPUT_DIR, retention_days()))


setup_logging()               # R4: data/logs/app.log (gọi lại nhiều lần vẫn chỉ 1 handler)
log = logging.getLogger("app")
_cleanup_on_startup()

ss = st.session_state
# run: đổi mỗi CV mới -> làm mới ô nhập · chat: [{role, kind, text | html, ...}] · cv0: hồ sơ trích xuất (chưa sửa)
for k, v in {"run": 0, "chat": [], "cv0": None, "pending": None, "auto_build": False, "pdf_bytes": None,
             "photo_ver": 0}.items():   # pending: CV vừa gửi, đang chờ xử lý
    ss.setdefault(k, v)
set_run_id(ss.get("run_id"))     # R4: mọi dòng log của lượt chạy này mang run_id của CV đang xử lý


# Logo header dạng base64 (cache)
@st.cache_data(show_spinner=False)
def logo_b64() -> str:
    """Logo gốc rất lớn và có viền trong suốt -> cắt sát viền, thu nhỏ cho header."""
    return png_b64(crop_logo(logo_header(), 640))   # cùng hàm cắt logo với PDF


# Vẽ một khối HTML dựng sẵn
def html_block(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


# Thêm một tin nhắn vào khung chat
def add_message(role: str, text: str = "", kind: str = "text", html: str | None = None, **kw) -> None:
    """Thêm tin nhắn vào khung chat. `text` sẽ được escape; `html` chỉ nhận HTML dựng sẵn từ ui.components (Q4)."""
    ss.chat.append({"role": role, "kind": kind, **kw, **({"html": html} if html is not None else {"text": text})})


# Khung A4 "đang xử lý" với các bước thật của lượt hiện tại (step=-1: bước cuối là dựng PDF)
def stage_html(step: int = -1, queue_pos: int = 0, queue_what: str = "dựng PDF") -> str:
    labels = ss.get("stage_labels") or pipeline.stage_labels()
    return ui.stage(True, step % len(labels), queue_pos=queue_pos, labels=labels, queue_what=queue_what)


# Dựng PDF cho hồ sơ đang sửa, lưu kết quả vào session
def make_pdf(cv: dict, fingerprint: str, slot=None) -> bool:
    """Dựng PDF vào bộ nhớ phiên (chỉ lưu ra đĩa khi tải về). Phải xếp hàng -> `slot` hiện vị trí trong hàng."""
    on_wait = (lambda n: slot.markdown(stage_html(queue_pos=n), unsafe_allow_html=True)) if slot else None
    try:
        result = pipeline.make_pdf(cv, ss.project, ss.position, ss.photo, on_wait=on_wait)
    except Exception as e:
        log.exception("Dựng PDF thất bại")
        ss.pdf_bytes = None
        add_message("assistant", kind="error", html=ui.error_message("Dựng PDF thất bại.", str(e)))
        return False
    ss.pdf_bytes, ss.pdf_name, ss.checklist, ss.summary, ss.pdf_fingerprint = (
        result.pdf_bytes, result.filename, result.checklist, result.summary, fingerprint)
    return True


# Callback nút Tải PDF: lưu bản sao + báo trong chat
def save_export() -> None:
    pipeline.save_copy(OUTPUT_DIR, ss.pdf_name, ss.pdf_bytes, run_id=ss.get("run_id"))
    add_message("assistant", html=ui.exported_message(ss.pdf_name))


# Nút Làm mới: xoá hồ sơ và lịch sử chat
def reset_chat() -> None:
    ss.update(dict.fromkeys(("cv0", "pending", "pdf_bytes", "pdf_fingerprint", "checklist", "summary", "photo",
                             "review"), None), chat=[], auto_build=False, run=ss.run + 1)


# Nhận CV người dùng gửi, đưa vào hàng chờ
def receive_cv(f, prj: str, pos: str) -> None:
    """Người dùng bấm Gửi CV: kiểm tra file rồi đưa vào hàng chờ xử lý."""
    if not f:
        add_message("assistant", "Chị vui lòng đính kèm file CV trước khi gửi.", kind="error")
        return
    data = f.getvalue()
    try:
        check_file(data, f.name)          # S7: chặn file quá lớn/rỗng trước khi xử lý
    except ExtractionError as e:
        add_message("assistant", kind="error", html=ui.error_message("Chưa gửi được.", str(e)))
        return
    add_message("user", kind="file", filename=f.name, project=prj, position=pos)
    ss.pending = {"data": data, "filename": f.name, "project": prj, "position": pos}
    ss.run_id = new_run_id()
    set_run_id(ss.run_id)
    log.info("Nhận CV %s (%.0f KB)", mask_filename(f.name), len(data) / 1024)


# Đọc CV đang chờ qua bộ trích xuất rồi chuyển sang bước sửa
def process_pending_cv() -> None:
    """Đọc CV trong hàng chờ (mỗi bước trên màn hình chờ = một giai đoạn thật), rồi sang 'đã có hồ sơ' (luôn rerun)."""
    p, slot, ss.stage_labels = ss.pending, st.empty(), pipeline.stage_labels()
    show = lambda i: slot.markdown(stage_html(i), unsafe_allow_html=True)   # bộ trích xuất báo bước 0 ngay khi bắt đầu
    try:
        result = pipeline.read_cv(p["data"], p["filename"], p["project"], p["position"], on_progress=show,
                                  on_wait=lambda n: slot.markdown(stage_html(0, n, "đọc CV"), unsafe_allow_html=True))
    except pipeline.CVReadError as e:
        ss.pending = None        # xoá trạng thái chờ -> các lần rerun sau không đọc lại CV
        ss.read_error = str(e)
        add_message("assistant", kind="error", html=ui.error_message("Không đọc được CV.", str(e)))
        st.rerun()
    ss.update(cv0=result.cv, original_bytes=p["data"], original_name=p["filename"], project=p["project"], position=p["position"],
              photo=result.photo, run=ss.run + 1, pending=None, auto_build=True, pdf_bytes=None, pdf_fingerprint=None,
              review={"confidence": result.confidence, "notes": [(w.path, w.message) for w in result.warnings]})
    add_message("assistant", kind="notes", name=result.cv["full_name"], notes=result.cv["model_notes"],
        salary=result.cv.get("expected_salary"), has_photo=result.photo is not None,
        review=[w.message for w in result.warnings])
    st.rerun()


# Tab Bản PDF: trạng thái, cảnh báo, xác nhận, nút, xem trước
def pdf_panel(cv: dict, structure_errors: list[str], violations: list[dict], current_fingerprint: str) -> None:
    """Tab Bản PDF: thanh trạng thái, cảnh báo, xác nhận, nút Cập nhật/Tải, checklist, xem trước."""
    if ss.auto_build and not structure_errors:       # dựng tự động lần đầu sau khi đọc CV xong
        slot = st.empty()
        slot.markdown(stage_html(), unsafe_allow_html=True)
        ok = make_pdf(cv, current_fingerprint, slot)
        ss.auto_build = False
        slot.empty()
        if not ok:
            st.rerun()   # khung chat đã vẽ trước đó -> vẽ lại để hiện thông báo lỗi
    has_pdf = bool(ss.pdf_bytes)
    outdated = pdf_outdated(has_pdf, ss.get("pdf_fingerprint"), current_fingerprint)
    bar_slot = st.empty()       # thanh trạng thái trên cùng, điền sau khi biết trạng thái duyệt
    warning_slot = st.container()
    if has_pdf:
        c1, c2 = st.columns(2)
        checked_generated = c1.checkbox("Đã kiểm tra các mục hệ thống tự lập", key=f"{ss.run}ack1",
                                     value=not ss.cv0["model_notes"]["self_created"])
        reviewed = c2.checkbox("Đã đọc và duyệt toàn bộ hồ sơ", key=f"{ss.run}ack2")
    else:
        checked_generated = reviewed = False
    status = compute_status(has_pdf=has_pdf, pdf_fingerprint=ss.get("pdf_fingerprint"), current_fingerprint=current_fingerprint,
                         checklist=ss.get("checklist"), has_violations=bool(violations),
                         has_structure_errors=bool(structure_errors), checked_generated=checked_generated, reviewed=reviewed)
    warnings = ui.warnings_html(structure_errors, violations, outdated, status.pdf_dirty, ss.get("checklist"))
    if warnings:
        warning_slot.markdown(warnings, unsafe_allow_html=True)
    page_count = len(pdf_page_images(ss.pdf_bytes)) if has_pdf else 0
    bar_slot.markdown(ui.status_bar(ss.pdf_name if has_pdf else "Chưa có bản PDF",
                                         f"A4 · {page_count} trang" if page_count else "Bấm Cập nhật PDF để dựng",
                                         status.pill_kind, status.pill_text), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Cập nhật PDF", width="stretch", disabled=bool(structure_errors), icon=":material/refresh:",
                 type="primary" if (outdated or not has_pdf) else "secondary"):
        slot = st.empty()
        slot.markdown(stage_html(), unsafe_allow_html=True)
        make_pdf(cv, current_fingerprint, slot)
        st.rerun()
    c2.download_button("Tải PDF", ss.pdf_bytes or b"", file_name=ss.get("pdf_name") or "ho-so.pdf",
                       mime="application/pdf", type="primary" if status.can_download else "secondary", width="stretch",
                       disabled=not status.can_download, on_click=save_export, icon=":material/download:",
                       help=None if status.can_download else DOWNLOAD_LOCKED_HINT)
    if has_pdf:
        with st.expander(f"Checklist chất lượng · {sum(r['ok'] for r in ss.checklist)}/{len(ss.checklist)} đạt"):
            html_block(ui.checklist_html(ss.checklist))
        with st.container(height=780, border=True):
            show_pdf(ss.pdf_bytes)


# ===================================================================== GIAO DIỆN
html_block(ui.page_css())
html_block(ui.header_html(logo_b64()))
left_col, right_col = st.columns([5, 7], gap="large")

with left_col:   # ---------------- CỘT TRÁI: KHUNG CHAT
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    c1.markdown(ui.panel_title("Trợ lý hồ sơ"), unsafe_allow_html=True)
    c2.button("Làm mới", on_click=reset_chat, width="stretch", disabled=not ss.chat,
              icon=":material/restart_alt:", type="tertiary")
    with st.container(height=540, border=True):
        html_block(ui.render_message({"role": "assistant", "kind": "text", "html": ui.GREETING_HTML}))
        for m in ss.chat:
            html_block(ui.render_message(m))
        if ss.pending:
            html_block(ui.TYPING_HTML)
        chat_tail = st.empty()   # tin "trực tiếp" (lỗi cần sửa, tin nhắn tóm tắt) — điền ở cuối script
    with st.form("cv_form", clear_on_submit=True, border=False):
        f = st.file_uploader("File CV gốc", type=uploader_types(CV_EXTENSIONS))
        c1, c2 = st.columns(2)
        prj = c1.text_input("Tên dự án", placeholder="Message Coffee")
        pos = c2.text_input("Vị trí", placeholder="Kế toán trưởng (không bắt buộc)")
        submitted = st.form_submit_button("Gửi CV", type="primary", width="stretch", icon=":material/arrow_upward:",
                                    disabled=bool(ss.pending))
    if submitted:
        receive_cv(f, prj, pos)
        st.rerun()

with right_col:   # ---------------- CỘT PHẢI: PDF
    st.empty().markdown(ui.panel_title("Hồ sơ PDF"), unsafe_allow_html=True)
    if ss.get("read_error"):
        st.error(f"Không đọc được CV. {ss.pop('read_error')}")
    if ss.pending:
        process_pending_cv()
    elif not ss.cv0:
        html_block(ui.stage(False))
    else:
        tab_pdf, tab_edit, tab_original = st.tabs(["Bản PDF", "Chỉnh sửa nội dung", "CV gốc"])
        with tab_edit:            # chạy TRƯỚC tab PDF để có bản hồ sơ mới nhất khi dựng PDF
            c1, c2 = st.columns(2)
            ss.project = c1.text_input("Tên dự án", ss.project, key=f"{ss.run}prj")
            ss.position = c2.text_input("Vị trí (dùng cho tên file)", ss.position or ss.cv0.get("target_title") or "",
                                        key=f"{ss.run}pos")
            edit_portrait(ss)
            cv = edit_profile(ss.cv0, f"{ss.run}-", ss.get("review"))
        with tab_original:
            show_original(ss.original_bytes, ss.original_name)

        cv_normalized, structure_errors = pipeline.validate_structure(cv)
        if not structure_errors:
            cv = cv_normalized
        violations = scan_pii_export(cv, ss.project, ss.position)   # cả tên dự án + vị trí cũng vào PDF
        current_fingerprint = pipeline.content_fingerprint(cv, ss.project, ss.position, ss.photo)
        with tab_pdf:
            pdf_panel(cv, structure_errors, violations, current_fingerprint)

        with chat_tail.container():   # tin trực tiếp ở cuối khung chat
            if structure_errors or violations:
                html_block(ui.render_message({"role": "assistant", "kind": "error",
                                      "html": ui.error_count_message(len(structure_errors) + len(violations))}))
            if ss.pdf_bytes and not pdf_outdated(True, ss.get("pdf_fingerprint"), current_fingerprint) and ss.get("summary"):
                html_block(ui.SUMMARY_LABEL_HTML)
                st.code(ss.summary, language=None, wrap_lines=True)
