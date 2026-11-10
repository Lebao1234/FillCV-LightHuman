"""Hệ thống giao diện: token là nguồn duy nhất, đạt tương phản, web app và PDF không lệch nhau."""
import re
import tomllib
from pathlib import Path

import pytest

from infra import tokens

GOC = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("chu,nen", tokens.CAP_CHU_NEN)
def test_tuong_phan_dat_wcag_aa(chu, nen):
    assert tokens.tuong_phan(chu, nen) >= 4.5, f"{chu}/{nen}: {tokens.tuong_phan(chu, nen):.2f}:1"


def test_config_toml_khop_token():
    theme = tomllib.loads((GOC / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["theme"]
    m = tokens.MAU
    assert theme["primaryColor"].lower() == m["navy"]
    assert theme["backgroundColor"].lower() == m["white"]
    assert theme["secondaryBackgroundColor"].lower() == m["soft"]
    assert theme["textColor"].lower() == m["ink"]
    assert theme["borderColor"].lower() == m["line"]
    assert theme["baseRadius"] == tokens.BO_GOC["md"]


def _css_app():
    # GĐ4 (A1): CSS của web app chuyển từ app.py sang ui/styles.css
    return (GOC / "ui" / "styles.css").read_text(encoding="utf-8")


def test_css_app_chi_dung_token():
    css = _css_app()
    assert re.findall(r"#[0-9a-fA-F]{3,6}\b", css) == []                 # không mã màu cứng
    assert re.findall(r"font-size:\s*[\d.]", css) == []                   # cỡ chữ theo thang --fs-*
    assert re.findall(r"border-radius:\s*\d+px", css) == []               # bo góc theo thang --r-*
    for gt in re.findall(r"(?:padding|margin|gap)[a-z-]*:([^;}]+)", css):  # khoảng cách theo thang --sp-*
        for so in re.findall(r"(?<![\w-])(\d+(?:\.\d+)?)px", gt):
            assert so == "0", f"khoảng cách cứng {so}px trong '{gt}'"


def test_css_app_dung_token_ton_tai():
    co = set(re.findall(r"--([\w-]+):", tokens.css_vars("web")))
    dung = set(re.findall(r"var\(--([\w-]+)\)", _css_app()))
    assert dung <= co, f"dùng token chưa định nghĩa: {dung - co}"


def test_pdf_dung_dung_mau_skill_md():
    """Token PDF phải trùng CSS mẫu mục 5 SKILL.md -> mẫu PDF không đổi."""
    skill = (GOC / "SKILL.md").read_text(encoding="utf-8")
    goc = dict(re.findall(r"--(navy|gold|yellow|ink|muted|line):(#[0-9a-fA-F]{6})", skill))
    assert goc and all(tokens.MAU[k] == v.lower() for k, v in goc.items())
    tpl = (GOC / "services/pdf/template.html").read_text(encoding="utf-8")
    style = tpl[tpl.index("<style>"):tpl.index("</style>")]
    assert re.findall(r"#[0-9a-fA-F]{3,6}\b", style) == []


def test_footer_pdf_dung_token():
    from services.pdf import render_worker
    footer = render_worker.footer_html()
    assert tokens.MAU["line"] in footer and tokens.MAU["navy"] in footer


def test_docs_bang_token_cap_nhat():
    docs = (GOC / "docs" / "design-system.md").read_text(encoding="utf-8")
    assert tokens.bang_markdown() in docs, "Chạy `python -m infra.tokens` rồi dán lại bảng vào docs/design-system.md"
