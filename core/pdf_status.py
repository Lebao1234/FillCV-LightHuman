"""Luật khoá/mở nút "Tải PDF" và nhãn trạng thái của bản PDF (A2) — thuần Python, không Streamlit.

Trước đây logic này nằm lẫn trong app.py (không import được trong test). Giữ nguyên hành vi cũ:
chỉ cho tải khi có PDF, PDF khớp nội dung đang sửa, đã tick đủ 2 ô xác nhận, hồ sơ hợp lệ, không còn
thông tin nhạy cảm trong dữ liệu lẫn trong chính file PDF.
"""
from dataclasses import dataclass

from services.privacy.checks import pdf_sach

GOI_Y_KHOA_TAI = "Cần tick 2 ô xác nhận, PDF mới nhất và không còn thông tin nhạy cảm"


@dataclass(frozen=True)
class TrangThaiPdf:
    cu: bool          # PDF đang hiển thị không còn khớp nội dung đang sửa -> cần "Cập nhật PDF"
    pdf_ban: bool     # chính file PDF vẫn còn thông tin liên hệ của ứng viên (checklist mục 'pii')
    cho_tai: bool     # nút "Tải PDF" được bật
    pill_loai: str    # ok | warn | err | idle (class CSS của nhãn trạng thái)
    pill_chu: str     # chữ trên nhãn trạng thái


def pdf_cu(co_pdf: bool, dau_pdf: str | None, dau_hien_tai: str) -> bool:
    """PDF đã dựng nhưng nội dung/ảnh/dự án đã đổi sau đó."""
    return co_pdf and dau_pdf != dau_hien_tai


def tinh_trang_thai(*, co_pdf: bool, dau_pdf: str | None, dau_hien_tai: str, checklist: list[dict] | None,
                    co_vi_pham: bool, co_loi_cau_truc: bool, da_kiem_tu_lap: bool, da_duyet: bool) -> TrangThaiPdf:
    """Tính toàn bộ trạng thái của khung PDF từ dữ liệu hiện có."""
    cu = pdf_cu(co_pdf, dau_pdf, dau_hien_tai)
    pdf_ban = co_pdf and not cu and not pdf_sach(checklist)
    cho_tai = (co_pdf and da_kiem_tu_lap and da_duyet and not cu and not co_vi_pham
               and not co_loi_cau_truc and not pdf_ban)
    if co_loi_cau_truc or co_vi_pham or pdf_ban:
        pill = ("err", "Cần sửa")
    elif cu:
        pill = ("warn", "Cần cập nhật")
    elif cho_tai:
        pill = ("ok", "Sẵn sàng tải")
    elif co_pdf:
        pill = ("idle", "Chờ duyệt")
    else:
        pill = ("idle", "Chưa dựng")
    return TrangThaiPdf(cu=cu, pdf_ban=pdf_ban, cho_tai=cho_tai, pill_loai=pill[0], pill_chu=pill[1])
