"""Web app nội bộ: CV ứng viên -> Hồ sơ ứng viên PDF chuẩn Light Human. Chạy: streamlit run app.py

Chỉ điều phối giao diện + session state (A1). Nghiệp vụ: core/pipeline.py, core/pdf_status.py.
Giao diện: ui/components.py (+ ui/styles.css), ui/profile_form.py, ui/preview.py.
"""
import base64
import io
import logging

import streamlit as st

from infra.settings import DUOI_CV, logo_header, loai_cho_uploader, thu_muc_output
from services.privacy.checks import scan_pii_xuat
from core import pipeline
from core.pdf_status import GOI_Y_KHOA_TAI, pdf_cu, tinh_trang_thai
from services.ai.extract import ExtractError, kiem_tra_file
from infra.logging_setup import an_ten_file, cau_hinh_logging, dat_run_id, tao_run_id
from infra.storage import don_file_het_han, so_ngay_luu
from services.pdf.render import cat_logo
from ui import components as ui
from ui.profile_form import sua_anh_chan_dung, sua_ho_so
from ui.preview import anh_cac_trang_pdf, xem_file_goc, xem_pdf

THU_MUC_DATA = thu_muc_output()        # OUTPUT_DIR trong .env, mặc định data/output

st.set_page_config(page_title="Hồ sơ ứng viên – Light Human", page_icon=":material/description:", layout="wide")


@st.cache_resource(show_spinner=False)
def _don_dep_khi_khoi_dong() -> int:
    """S2: xoá PDF quá hạn trong data/output — chạy 1 lần mỗi khi khởi động app."""
    return len(don_file_het_han(THU_MUC_DATA, so_ngay_luu()))


cau_hinh_logging()               # R4: data/logs/app.log (gọi lại nhiều lần vẫn chỉ 1 handler)
log = logging.getLogger("app")
_don_dep_khi_khoi_dong()

ss = st.session_state
ss.setdefault("run", 0)          # đổi mỗi lần xử lý CV mới -> làm mới các ô nhập
ss.setdefault("chat", [])        # lịch sử chat: [{role, kind, text | html, ...}]
ss.setdefault("cv0", None)       # hồ sơ AI trích xuất (chưa sửa)
ss.setdefault("pending", None)   # CV vừa gửi, đang chờ xử lý
ss.setdefault("auto_build", False)
ss.setdefault("pdf_bytes", None)
ss.setdefault("anh_ver", 0)
dat_run_id(ss.get("run_id"))     # R4: mọi dòng log của lượt chạy này mang run_id của CV đang xử lý


@st.cache_data(show_spinner=False)
def logo_b64() -> str:
    """Logo gốc rất lớn và có viền trong suốt -> cắt sát viền, thu nhỏ cho header."""
    buf = io.BytesIO()
    cat_logo(logo_header(), 640).save(buf, "PNG", optimize=True)   # cùng hàm cắt logo với PDF
    return base64.b64encode(buf.getvalue()).decode("ascii")


def html_block(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def noi(role: str, text: str = "", kind: str = "text", html: str | None = None, **kw) -> None:
    """Thêm tin nhắn vào khung chat. `text` sẽ được escape; `html` chỉ nhận HTML dựng sẵn từ ui.components (Q4)."""
    tin = {"role": role, "kind": kind, **kw}
    if html is not None:
        tin["html"] = html
    else:
        tin["text"] = text
    ss.chat.append(tin)


def dung_pdf(cv: dict, dau: str, khung=None) -> bool:
    """Dựng PDF vào bộ nhớ phiên (chỉ lưu ra đĩa khi tải về). Phải xếp hàng -> `khung` hiện vị trí trong hàng."""
    khi_cho = (lambda n: khung.markdown(ui.stage(True, 2, so_cho=n), unsafe_allow_html=True)) if khung else None
    try:
        kq = pipeline.dung_pdf(cv, ss.project, ss.position, ss.photo, khi_cho=khi_cho)
    except Exception as e:
        log.exception("Dựng PDF thất bại")
        ss.pdf_bytes = None
        noi("assistant", kind="error", html=ui.tin_loi("Dựng PDF thất bại.", str(e)))
        return False
    ss.pdf_bytes, ss.pdf_name, ss.checklist, ss.tin_nhan, ss.pdf_dau = (
        kq.pdf_bytes, kq.ten, kq.checklist, kq.tin_nhan, dau)
    return True


def luu_ban_xuat() -> None:
    pipeline.luu_ban_sao(THU_MUC_DATA, ss.pdf_name, ss.pdf_bytes, run_id=ss.get("run_id"))
    noi("assistant", html=ui.tin_da_xuat(ss.pdf_name))


def lam_moi() -> None:
    for k in ("cv0", "pending", "pdf_bytes", "pdf_dau", "checklist", "tin_nhan", "photo"):
        ss[k] = None
    ss.chat = []
    ss.auto_build = False
    ss.run += 1


def nhan_cv(f, prj: str, pos: str) -> None:
    """Người dùng bấm Gửi CV: kiểm tra file rồi đưa vào hàng chờ xử lý."""
    if not f:
        noi("assistant", "Chị vui lòng đính kèm file CV trước khi gửi.", kind="error")
        return
    data = f.getvalue()
    try:
        kiem_tra_file(data, f.name)          # S7: chặn file quá lớn/rỗng trước khi gọi AI
    except ExtractError as e:
        noi("assistant", kind="error", html=ui.tin_loi("Chưa gửi được.", str(e)))
        return
    noi("user", kind="file", ten=f.name, project=prj, position=pos)
    ss.pending = {"data": data, "ten": f.name, "project": prj, "position": pos}
    ss.run_id = tao_run_id()
    dat_run_id(ss.run_id)
    log.info("Nhận CV %s (%.0f KB)", an_ten_file(f.name), len(data) / 1024)


def xu_ly_cv_dang_cho() -> None:
    """AI đọc CV trong hàng chờ, rồi chuyển sang trạng thái 'đã có hồ sơ' (luôn kết thúc bằng rerun)."""
    p = ss.pending
    khung = st.empty()
    khung.markdown(ui.stage(True, 0), unsafe_allow_html=True)
    try:
        kq = pipeline.doc_cv(p["data"], p["ten"], p["project"], p["position"])
    except pipeline.LoiDocCV as e:
        ss.pending = None        # xoá trạng thái chờ -> các lần rerun sau không gọi lại API
        ss.loi_doc = str(e)
        noi("assistant", kind="error", html=ui.tin_loi("Không đọc được CV.", str(e)))
        st.rerun()
    khung.markdown(ui.stage(True, 1), unsafe_allow_html=True)
    ss.update(cv0=kq.cv, goc=p["data"], ten_goc=p["ten"], project=p["project"], position=p["position"],
              photo=kq.photo, run=ss.run + 1, pending=None, auto_build=True, pdf_bytes=None, pdf_dau=None)
    noi("assistant", kind="notes", name=kq.cv["full_name"], notes=kq.cv["model_notes"],
        salary=kq.cv.get("expected_salary"), co_anh=kq.photo is not None)
    st.rerun()


def khung_pdf(cv: dict, loi_cau_truc: list[str], vi_pham: list[dict], dau_hien_tai: str) -> None:
    """Tab Bản PDF: thanh trạng thái, cảnh báo, xác nhận, nút Cập nhật/Tải, checklist, xem trước."""
    if ss.auto_build and not loi_cau_truc:       # dựng tự động lần đầu sau khi AI đọc xong
        khung = st.empty()
        khung.markdown(ui.stage(True, 2), unsafe_allow_html=True)
        ok = dung_pdf(cv, dau_hien_tai, khung)
        ss.auto_build = False
        khung.empty()
        if not ok:
            st.rerun()   # khung chat đã vẽ trước đó -> vẽ lại để hiện thông báo lỗi
    co_pdf = bool(ss.pdf_bytes)
    cu = pdf_cu(co_pdf, ss.get("pdf_dau"), dau_hien_tai)
    o_thanh = st.empty()       # thanh trạng thái trên cùng, điền sau khi biết trạng thái duyệt
    o_canh_bao = st.container()
    if co_pdf:
        c1, c2 = st.columns(2)
        da_kiem_tu_lap = c1.checkbox("Đã kiểm tra các mục hệ thống tự lập", key=f"{ss.run}xn1",
                                     value=not ss.cv0["model_notes"]["self_created"])
        da_duyet = c2.checkbox("Đã đọc và duyệt toàn bộ hồ sơ", key=f"{ss.run}xn2")
    else:
        da_kiem_tu_lap = da_duyet = False
    tt = tinh_trang_thai(co_pdf=co_pdf, dau_pdf=ss.get("pdf_dau"), dau_hien_tai=dau_hien_tai,
                         checklist=ss.get("checklist"), co_vi_pham=bool(vi_pham),
                         co_loi_cau_truc=bool(loi_cau_truc), da_kiem_tu_lap=da_kiem_tu_lap, da_duyet=da_duyet)
    canh_bao = ui.canh_bao_html(loi_cau_truc, vi_pham, cu, tt.pdf_ban, ss.get("checklist"))
    if canh_bao:
        o_canh_bao.markdown(canh_bao, unsafe_allow_html=True)
    so_trang = len(anh_cac_trang_pdf(ss.pdf_bytes)) if co_pdf else 0
    o_thanh.markdown(ui.thanh_trang_thai(ss.pdf_name if co_pdf else "Chưa có bản PDF",
                                         f"A4 · {so_trang} trang" if so_trang else "Bấm Cập nhật PDF để dựng",
                                         tt.pill_loai, tt.pill_chu), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("Cập nhật PDF", width="stretch", disabled=bool(loi_cau_truc), icon=":material/refresh:",
                 type="primary" if (cu or not co_pdf) else "secondary"):
        khung = st.empty()
        khung.markdown(ui.stage(True, 2), unsafe_allow_html=True)
        dung_pdf(cv, dau_hien_tai, khung)
        st.rerun()
    c2.download_button("Tải PDF", ss.pdf_bytes or b"", file_name=ss.get("pdf_name") or "ho-so.pdf",
                       mime="application/pdf", type="primary" if tt.cho_tai else "secondary", width="stretch",
                       disabled=not tt.cho_tai, on_click=luu_ban_xuat, icon=":material/download:",
                       help=None if tt.cho_tai else GOI_Y_KHOA_TAI)
    if co_pdf:
        with st.expander(f"Checklist chất lượng · {sum(r['ok'] for r in ss.checklist)}/{len(ss.checklist)} đạt"):
            html_block(ui.checklist_html(ss.checklist))
        with st.container(height=780, border=True):
            xem_pdf(ss.pdf_bytes)


# ===================================================================== GIAO DIỆN
html_block(ui.css_trang())
html_block(ui.header_html(logo_b64()))
trai, phai = st.columns([5, 7], gap="large")

with trai:   # ---------------- CỘT TRÁI: KHUNG CHAT
    c1, c2 = st.columns([3, 1], vertical_alignment="center")
    c1.markdown(ui.tieu_de_panel("Trợ lý hồ sơ"), unsafe_allow_html=True)
    c2.button("Làm mới", on_click=lam_moi, width="stretch", disabled=not ss.chat,
              icon=":material/restart_alt:", type="tertiary")
    with st.container(height=540, border=True):
        html_block(ui.ve_tin({"role": "assistant", "kind": "text", "html": ui.LOI_CHAO_HTML}))
        for m in ss.chat:
            html_block(ui.ve_tin(m))
        if ss.pending:
            html_block(ui.TIN_DANG_GO)
        vung_cuoi = st.empty()   # tin "trực tiếp" (lỗi cần sửa, tin nhắn tóm tắt) — điền ở cuối script
    with st.form("gui_cv", clear_on_submit=True, border=False):
        f = st.file_uploader("File CV gốc", type=loai_cho_uploader(DUOI_CV))
        c1, c2 = st.columns(2)
        prj = c1.text_input("Tên dự án", placeholder="Message Coffee")
        pos = c2.text_input("Vị trí", placeholder="Kế toán trưởng (không bắt buộc)")
        gui = st.form_submit_button("Gửi CV", type="primary", width="stretch", icon=":material/arrow_upward:",
                                    disabled=bool(ss.pending))
    if gui:
        nhan_cv(f, prj, pos)
        st.rerun()

with phai:   # ---------------- CỘT PHẢI: PDF
    st.empty().markdown(ui.tieu_de_panel("Hồ sơ PDF"), unsafe_allow_html=True)
    if ss.get("loi_doc"):
        st.error(f"Không đọc được CV. {ss.pop('loi_doc')}")
    if ss.pending:
        xu_ly_cv_dang_cho()
    elif not ss.cv0:
        html_block(ui.stage(False))
    else:
        tab_pdf, tab_sua, tab_goc = st.tabs(["Bản PDF", "Chỉnh sửa nội dung", "CV gốc"])
        with tab_sua:            # chạy TRƯỚC tab PDF để có bản hồ sơ mới nhất khi dựng PDF
            c1, c2 = st.columns(2)
            ss.project = c1.text_input("Tên dự án", ss.project, key=f"{ss.run}prj")
            ss.position = c2.text_input("Vị trí (dùng cho tên file)", ss.position or ss.cv0.get("target_title") or "",
                                        key=f"{ss.run}pos")
            sua_anh_chan_dung(ss)
            cv = sua_ho_so(ss.cv0, f"{ss.run}-")
        with tab_goc:
            xem_file_goc(ss.goc, ss.ten_goc)

        cv_chuan, loi_cau_truc = pipeline.kiem_tra_cau_truc(cv)
        if not loi_cau_truc:
            cv = cv_chuan
        vi_pham = scan_pii_xuat(cv, ss.project, ss.position)   # cả tên dự án + vị trí cũng vào PDF
        dau_hien_tai = pipeline.dau_van_tay(cv, ss.project, ss.position, ss.photo)
        with tab_pdf:
            khung_pdf(cv, loi_cau_truc, vi_pham, dau_hien_tai)

        with vung_cuoi.container():   # tin trực tiếp ở cuối khung chat
            if loi_cau_truc or vi_pham:
                html_block(ui.ve_tin({"role": "assistant", "kind": "error",
                                      "html": ui.tin_so_loi(len(loi_cau_truc) + len(vi_pham))}))
            if ss.pdf_bytes and not pdf_cu(True, ss.get("pdf_dau"), dau_hien_tai) and ss.get("tin_nhan"):
                html_block(ui.NHAN_TIN_TOM_TAT)
                st.code(ss.tin_nhan, language=None, wrap_lines=True)
