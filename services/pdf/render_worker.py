"""Chương trình phụ: đổi 1 file HTML thành PDF bằng Playwright (Chromium).

Vì sao tách riêng? Streamlit tự chạy một "event loop" bên trong, còn Playwright
bản đồng bộ (sync) cũng cần event loop riêng -> chạy chung dễ treo/lỗi.
Chạy Playwright trong một tiến trình (process) riêng là cách ổn định nhất.

Cách gọi (từ gốc dự án):  python -m services.pdf.render_worker <file.html> <file.pdf> [run_id]
                          python -m services.pdf.render_worker <danh_sach.json> [run_id]   (nhiều bản)
(run_id do app truyền sang để log của hai tiến trình cùng mã — xem logging_setup.py)
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from html import escape

from infra.settings import cong_ty
from infra.logging_setup import cau_hinh_logging, dat_run_id
from infra.tokens import FONT, MAU, PDF_LE_MM

log = logging.getLogger("render_worker")

def footer_html() -> str:
    """Footer theo mục 4.6 + mục 6 SKILL.md. Chữ từ config/company.toml (A4), lề từ tokens (A7).

    Footer của Chromium không đọc được CSS của trang -> màu/font phải ghi thẳng vào style.
    """
    ct, pdf = cong_ty()["cong_ty"], cong_ty()["pdf"]
    ten = f'<b style="color:{MAU["navy"]}">{escape(ct["ten"])}</b>'
    gioi_thieu = escape(pdf["footer_gioi_thieu"]).replace("{ten}", ten)
    return f"""
<div style="width:100%; margin:0 {PDF_LE_MM['phai']}mm 0 {PDF_LE_MM['trai']}mm; padding-top:1.5mm; border-top:0.5pt solid {MAU['line']};
            font-family:{FONT['serif-pdf'].replace('"', "'")}; font-size:8px; color:{MAU['muted']};
            display:flex; justify-content:space-between; -webkit-print-color-adjust:exact;">
  <span>{gioi_thieu}</span>
  <span>{escape(ct["ten_mien"])} · Trang <span class="pageNumber"></span>/<span class="totalPages"></span></span>
</div>"""


def chromium_args() -> list[str]:
    """Tham số khởi động Chromium (S4).

    Mặc định GIỮ sandbox — lớp bảo vệ khi dựng HTML có nội dung từ CV.
    Chỉ tắt khi đặt CHROMIUM_NO_SANDBOX=1 (Docker / chạy bằng root, nơi sandbox không khởi động được).
    """
    return ["--no-sandbox"] if os.getenv("CHROMIUM_NO_SANDBOX") == "1" else []


def html_to_pdf_nhieu(cac_viec: list[tuple[str, str]]) -> None:
    """Dựng nhiều cặp (file HTML -> file PDF) trong MỘT lần khởi động Chromium.

    Khởi động Python + Chromium là phần tốn nhất (~2 s, ~300 MB). Trước đây mỗi cỡ chữ cần thử là một tiến trình
    riêng (tới 3 lần); giờ cả 3 cỡ chữ dựng chung một lần — mỗi bản in thêm chỉ mất ~0.1 s.
    """
    footer = footer_html()
    with sync_playwright() as p:
        browser = p.chromium.launch(args=chromium_args())
        try:
            for html_path, pdf_path in cac_viec:
                page = browser.new_page()            # trang mới cho mỗi bản -> không mang trạng thái của bản trước
                page.goto(Path(html_path).resolve().as_uri(), wait_until="load")
                page.pdf(
                    path=pdf_path,
                    format="A4",
                    print_background=True,
                    prefer_css_page_size=True,
                    display_header_footer=True,
                    header_template="<span></span>",
                    footer_template=footer,
                )
                page.close()
        finally:
            browser.close()


def html_to_pdf(html_path: str, pdf_path: str) -> None:
    html_to_pdf_nhieu([(html_path, pdf_path)])


def _doc_viec(argv: list[str]) -> tuple[list[tuple[str, str]], str | None]:
    """2 cách gọi: '<danh_sach.json> [run_id]' (nhiều bản) hoặc '<file.html> <file.pdf> [run_id]' (1 bản)."""
    if argv[1].lower().endswith(".json"):
        cac_viec = [tuple(x) for x in json.loads(Path(argv[1]).read_text(encoding="utf-8"))]
        return cac_viec, argv[2] if len(argv) > 2 else None
    return [(argv[1], argv[2])], argv[3] if len(argv) > 3 else None


if __name__ == "__main__":
    cau_hinh_logging("render_worker.log")
    viec, run_id = _doc_viec(sys.argv)
    dat_run_id(run_id)
    t0 = time.time()
    try:
        html_to_pdf_nhieu(viec)
    except Exception:
        log.exception("Dựng PDF thất bại")
        raise
    log.info("Dựng %d bản PDF xong trong %.1f giây (sandbox: %s)", len(viec), time.time() - t0,
             "tắt" if chromium_args() else "bật")
