"""Xem trước PDF đã dựng và CV gốc (Streamlit)."""
import logging
from pathlib import Path

import streamlit as st

from infra.settings import DUOI_ANH
from infra.logging_setup import an_ten_file

log = logging.getLogger("app")


@st.cache_data(show_spinner=False, max_entries=8)
def anh_cac_trang_pdf(data: bytes) -> list[bytes]:
    """Rasterize PDF 1 lần cho mỗi file (cache) — không vẽ lại mỗi lần gõ phím."""
    import pymupdf as fitz
    with fitz.open(stream=data, filetype="pdf") as doc:
        return [p.get_pixmap(dpi=110).tobytes("png") for p in doc]


def xem_pdf(pdf_bytes: bytes) -> None:
    for png in anh_cac_trang_pdf(pdf_bytes):
        st.image(png, width="stretch")


def xem_file_goc(data: bytes, ten: str) -> None:
    """Hiện CV gốc để đối chiếu; file không xem được thì báo nhẹ, không làm hỏng app (N2)."""
    duoi = Path(ten).suffix.lower()
    try:
        if duoi == ".pdf":
            xem_pdf(data)
        elif duoi in DUOI_ANH:
            st.image(data, width="stretch")
        else:
            st.info("File DOCX: không xem trước được, hãy mở file gốc để đối chiếu.")
    except Exception:
        # N2: PDF có mật khẩu / định dạng lạ mà PyMuPDF không mở được -> không để cả app báo lỗi đỏ
        log.exception("Không xem trước được file gốc %s", an_ten_file(ten))
        st.info("Không xem trước được file gốc (có thể file có mật khẩu hoặc định dạng đặc biệt). "
                "Hãy mở file gốc trên máy để đối chiếu.")
