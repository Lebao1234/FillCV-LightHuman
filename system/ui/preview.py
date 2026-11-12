"""Xem trước PDF đã dựng và CV gốc (Streamlit)."""
import base64
import io
import logging
from pathlib import Path

import streamlit as st

from infra.settings import IMAGE_EXTENSIONS, max_cv_pages
from infra.logging_setup import mask_filename

log = logging.getLogger("app")


# Ảnh PIL -> chuỗi base64 PNG (để nhúng vào HTML)
def png_b64(image) -> str:
    """Lưu ảnh PIL thành PNG (tối ưu dung lượng) rồi mã hoá base64."""
    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# Cache dùng chung cho MỌI phiên; mỗi người chiếm 2 file (PDF đã dựng + CV gốc) -> 64 đủ cho ~30 người,
# ít hơn thì cache bị đẩy ra liên tục và mỗi lần gõ phím phải vẽ lại.
PREVIEW_CACHE_ENTRIES = 64


# Ảnh PNG từng trang PDF (cache)
@st.cache_data(show_spinner=False, max_entries=PREVIEW_CACHE_ENTRIES)
def pdf_page_images(data: bytes, max_pages: int | None = None) -> list[bytes]:
    """Rasterize PDF 1 lần cho mỗi file (cache) — không vẽ lại mỗi lần gõ phím. `max_pages`: chỉ vẽ các trang đầu."""
    import pymupdf as fitz
    with fitz.open(stream=data, filetype="pdf") as doc:
        return [p.get_pixmap(dpi=110).tobytes("png") for p in doc[:max_pages]]


# Số trang của PDF (cache)
@st.cache_data(show_spinner=False, max_entries=PREVIEW_CACHE_ENTRIES)
def pdf_page_count(data: bytes) -> int:
    """Số trang PDF — để báo khi bản xem trước bị cắt bớt."""
    import pymupdf as fitz
    with fitz.open(stream=data, filetype="pdf") as doc:
        return doc.page_count


# Hiện PDF dạng ảnh
def show_pdf(pdf_bytes: bytes, max_pages: int | None = None) -> None:
    """Vẽ từng trang PDF; có `max_pages` và PDF dài hơn -> chỉ vẽ các trang đầu, kèm dòng báo."""
    for png in pdf_page_images(pdf_bytes, max_pages):
        st.image(png, width="stretch")
    if max_pages and (total := pdf_page_count(pdf_bytes)) > max_pages:
        st.info(f"Chỉ xem trước {max_pages}/{total} trang đầu. Hãy mở file gốc trên máy để xem các trang còn lại.")


# Hiện CV gốc để đối chiếu
def show_original(data: bytes, name: str) -> None:
    """Hiện CV gốc để đối chiếu; file không xem được thì báo nhẹ, không làm hỏng app (N2)."""
    ext = Path(name).suffix.lower()
    try:
        if ext == ".pdf":
            show_pdf(data, max_cv_pages())
        elif ext in IMAGE_EXTENSIONS:
            st.image(data, width="stretch")
        else:
            st.info("File DOCX: không xem trước được, hãy mở file gốc để đối chiếu.")
    except Exception:
        # N2: PDF có mật khẩu / định dạng lạ mà PyMuPDF không mở được -> không để cả app báo lỗi đỏ
        log.exception("Không xem trước được file gốc %s", mask_filename(name))
        st.info("Không xem trước được file gốc (có thể file có mật khẩu hoặc định dạng đặc biệt). "
                "Hãy mở file gốc trên máy để đối chiếu.")
