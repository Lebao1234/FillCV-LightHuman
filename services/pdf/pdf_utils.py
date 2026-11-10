"""Tiện ích đọc PDF đã dựng (A3) — dùng chung cho render.py (chọn cỡ chữ) và checks.py (checklist).

Tách khỏi render.py để checks.py không phải phụ thuộc vào module dựng PDF.
"""
from pathlib import Path

from infra.tokens import A4_MM, PDF_LE_MM


def pdf_layout(pdf_path: Path) -> tuple[int, float]:
    """Trả (số trang, độ đầy trang cuối 0..1) — để chọn cỡ chữ."""
    import pymupdf as fitz
    with fitz.open(pdf_path) as doc:
        n = doc.page_count
        last = doc[-1]
        h = last.rect.height
        # vùng nội dung = bỏ lề trên và lề dưới (lề dưới chứa footer) — A7: lấy từ tokens
        top, bottom = PDF_LE_MM["tren"] / A4_MM[1] * h, h - PDF_LE_MM["duoi"] / A4_MM[1] * h
        y_max = max((b[3] for b in last.get_text("blocks") if b[3] < bottom), default=top)
        return n, max(0.0, min(1.0, (y_max - top) / (bottom - top)))
