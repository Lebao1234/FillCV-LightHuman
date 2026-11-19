"""Chương trình phụ: đổi 1 file HTML thành PDF bằng Playwright (Chromium).

Vì sao tách riêng? Streamlit tự chạy một "event loop" bên trong, còn Playwright
bản đồng bộ (sync) cũng cần event loop riêng -> chạy chung dễ treo/lỗi.
Chạy Playwright trong một tiến trình (process) riêng là cách ổn định nhất.

Cách gọi (từ gốc dự án):  python -m services.pdf.render_worker <file.html> <file.pdf> [run_id] [lang]
                          python -m services.pdf.render_worker <job_list.json> [run_id] [lang]   (nhiều bản)
(run_id do app truyền sang để log của hai tiến trình cùng mã — xem logging_setup.py;
 lang = ngôn ngữ xuất 'vi' | 'en' cho chữ ở footer, mặc định 'vi')
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from html import escape

from infra.settings import company
from services.pdf import labels
from infra.logging_setup import setup_logging, set_run_id
from infra.tokens import FONT, COLORS, PDF_MARGIN_MM

log = logging.getLogger("render_worker")

# HTML footer của PDF
def footer_html(lang: str = "vi") -> str:
    """Footer theo mục 4.6 + mục 6 SKILL.md. Chữ từ config/company.toml (A4), lề từ tokens (A7).

    Footer của Chromium không đọc được CSS của trang -> màu/font phải ghi thẳng vào style.
    """
    company_info = company()["company"]
    name = f'<b style="color:{COLORS["navy"]}">{escape(company_info["name"])}</b>'
    t = labels.texts(lang)                       # footer_intro từ company.toml [pdf] / [pdf_en]
    intro = escape(t["footer_intro"]).replace("{name}", name)
    return f"""
<div style="width:100%; margin:0 {PDF_MARGIN_MM['right']}mm 0 {PDF_MARGIN_MM['left']}mm; padding-top:1.5mm; border-top:0.5pt solid {COLORS['line']};
            font-family:{FONT['serif-pdf'].replace('"', "'")}; font-size:8px; color:{COLORS['muted']};
            display:flex; justify-content:space-between; -webkit-print-color-adjust:exact;">
  <span>{intro}</span>
  <span>{escape(company_info["domain"])} · {escape(t["page"])} <span class="pageNumber"></span>/<span class="totalPages"></span></span>
</div>"""


# Tham số khởi động Chromium
def chromium_args() -> list[str]:
    """Tham số khởi động Chromium (S4).

    Mặc định GIỮ sandbox — lớp bảo vệ khi dựng HTML có nội dung từ CV.
    Chỉ tắt khi đặt CHROMIUM_NO_SANDBOX=1 (Docker / chạy bằng root, nơi sandbox không khởi động được).
    """
    return ["--no-sandbox"] if os.getenv("CHROMIUM_NO_SANDBOX") == "1" else []


# Dựng nhiều PDF trong một lần mở Chromium
def html_to_pdf_batch(jobs: list[tuple[str, str]], lang: str = "vi") -> None:
    """Dựng nhiều cặp (file HTML -> file PDF) trong MỘT lần khởi động Chromium.

    Khởi động Python + Chromium là phần tốn nhất (~2 s, ~300 MB). Trước đây mỗi cỡ chữ cần thử là một tiến trình
    riêng (tới 3 lần); giờ cả 3 cỡ chữ dựng chung một lần — mỗi bản in thêm chỉ mất ~0.1 s.
    """
    footer = footer_html(lang)
    with sync_playwright() as p:
        browser = p.chromium.launch(args=chromium_args())
        try:
            for html_path, pdf_path in jobs:
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


# Dựng một PDF
def html_to_pdf(html_path: str, pdf_path: str) -> None:
    html_to_pdf_batch([(html_path, pdf_path)])


# Đọc danh sách việc từ argv
def _read_jobs(argv: list[str]) -> tuple[list[tuple[str, str]], str | None, str]:
    """2 cách gọi: '<job_list.json> [run_id] [lang]' (nhiều bản) hoặc '<file.html> <file.pdf> [run_id] [lang]'."""
    if argv[1].lower().endswith(".json"):
        jobs, rest = [tuple(x) for x in json.loads(Path(argv[1]).read_text(encoding="utf-8"))], argv[2:]
    else:
        jobs, rest = [(argv[1], argv[2])], argv[3:]
    return jobs, (rest[0] if rest else None), (rest[1] if len(rest) > 1 else "vi")


if __name__ == "__main__":
    setup_logging("render_worker.log")
    jobs, run_id, lang = _read_jobs(sys.argv)
    set_run_id(run_id)
    t0 = time.time()
    try:
        html_to_pdf_batch(jobs, lang)
    except Exception:
        log.exception("Dựng PDF thất bại")
        raise
    log.info("Dựng %d bản PDF xong trong %.1f giây (sandbox: %s)", len(jobs), time.time() - t0,
             "tắt" if chromium_args() else "bật")
