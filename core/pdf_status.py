"""Luật khoá/mở nút "Tải PDF" và nhãn trạng thái của bản PDF (A2) — thuần Python, không Streamlit.

Trước đây logic này nằm lẫn trong app.py (không import được trong test). Giữ nguyên hành vi cũ:
chỉ cho tải khi có PDF, PDF khớp nội dung đang sửa, đã tick đủ 2 ô xác nhận, hồ sơ hợp lệ, không còn
thông tin nhạy cảm trong dữ liệu lẫn trong chính file PDF.
"""
from dataclasses import dataclass

from services.privacy.checks import pdf_clean

DOWNLOAD_LOCKED_HINT = "Cần tick 2 ô xác nhận, PDF mới nhất và không còn thông tin nhạy cảm"


# Trạng thái khung PDF (cũ/bẩn/được tải + nhãn)
@dataclass(frozen=True)
class PdfStatus:
    outdated: bool          # PDF đang hiển thị không còn khớp nội dung đang sửa -> cần "Cập nhật PDF"
    pdf_dirty: bool     # chính file PDF vẫn còn thông tin liên hệ của ứng viên (checklist mục 'pii')
    can_download: bool     # nút "Tải PDF" được bật
    pill_kind: str    # ok | warn | err | idle (class CSS của nhãn trạng thái)
    pill_text: str     # chữ trên nhãn trạng thái


# PDF có còn khớp nội dung đang sửa không
def pdf_outdated(has_pdf: bool, pdf_fingerprint: str | None, current_fingerprint: str) -> bool:
    """PDF đã dựng nhưng nội dung/ảnh/dự án đã đổi sau đó."""
    return has_pdf and pdf_fingerprint != current_fingerprint


# Tính trạng thái khung PDF và luật mở nút Tải
def compute_status(*, has_pdf: bool, pdf_fingerprint: str | None, current_fingerprint: str, checklist: list[dict] | None,
                    has_violations: bool, has_structure_errors: bool, checked_generated: bool, reviewed: bool) -> PdfStatus:
    """Tính toàn bộ trạng thái của khung PDF từ dữ liệu hiện có."""
    outdated = pdf_outdated(has_pdf, pdf_fingerprint, current_fingerprint)
    pdf_dirty = has_pdf and not outdated and not pdf_clean(checklist)
    can_download = (has_pdf and checked_generated and reviewed and not outdated and not has_violations
               and not has_structure_errors and not pdf_dirty)
    if has_structure_errors or has_violations or pdf_dirty:
        pill = ("err", "Cần sửa")
    elif outdated:
        pill = ("warn", "Cần cập nhật")
    elif can_download:
        pill = ("ok", "Sẵn sàng tải")
    elif has_pdf:
        pill = ("idle", "Chờ duyệt")
    else:
        pill = ("idle", "Chưa dựng")
    return PdfStatus(outdated=outdated, pdf_dirty=pdf_dirty, can_download=can_download, pill_kind=pill[0], pill_text=pill[1])
