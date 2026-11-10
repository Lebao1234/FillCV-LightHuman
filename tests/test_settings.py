"""Giai đoạn 3 — một nguồn sự thật: A4, A5, A6, A7, A8, prompt ra file + phiên bản, N2."""
import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from infra import settings
from services.privacy.checks import MAU, NHAN_MXH, MANG_XA_HOI, scan_text

GOC = Path(__file__).resolve().parent.parent
GIA = json.loads((GOC / "tests" / "fixtures" / "fake_candidate.json").read_text(encoding="utf-8"))


def _chu_hien_thi(html: str) -> str:
    """Bỏ thẻ HTML/CSS -> phần chữ người đọc thấy trong PDF (đủ để kiểm tra bộ lọc PII)."""
    html = re.sub(r"<(style|title)[^>]*>.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


@pytest.fixture
def cong_ty_khac(tmp_path, monkeypatch):
    """Config công ty với SĐT/email/website KHÁC mặc định."""
    toml = (GOC / "config" / "company.toml").read_text(encoding="utf-8")
    toml = (toml.replace("028 3842 5188", "028 7777 1234").replace("info@lighthuman.vn", "lienhe@lighthuman.com.vn")
                .replace("https://lighthuman.vn/", "https://lighthuman.com.vn/")
                .replace('ten_mien = "lighthuman.vn"', 'ten_mien = "lighthuman.com.vn"'))
    f = tmp_path / "company.toml"
    f.write_text(toml, encoding="utf-8")
    monkeypatch.setenv("COMPANY_CONFIG", str(f))
    settings._doc_cong_ty.cache_clear()
    yield
    settings._doc_cong_ty.cache_clear()


# ===================================================================== A4
def test_a4_template_va_bo_loc_khop_voi_config_mac_dinh():
    from services.pdf.render import render_html
    chu = _chu_hien_thi(render_html(copy.deepcopy(GIA), "Dự án Mẫu", "t"))
    assert "028 3842 5188" in chu and "info@lighthuman.vn" in chu
    assert scan_text(chu) == []                                          # header công ty không bị coi là PII


def test_a4_doi_sdt_trong_config_pdf_van_khong_bi_chan(cong_ty_khac):
    from services.pdf import render_worker
    from services.pdf.render import render_html
    chu = _chu_hien_thi(render_html(copy.deepcopy(GIA), "Dự án Mẫu", "t"))
    assert "028 7777 1234" in chu and "lienhe@lighthuman.com.vn" in chu  # header đổi theo config
    assert "028 3842 5188" not in chu
    assert scan_text(chu) == []                                          # bộ lọc cũng đổi theo -> không chặn
    assert scan_text("Gọi 028 3842 5188") != []                          # số cũ giờ không còn được phép
    assert "lighthuman.com.vn" in render_worker.footer_html()


def test_a4_khong_con_viet_cung_thong_tin_cong_ty():
    for f in ("services/pdf/template.html", "services/privacy/checks.py", "services/pdf/render_worker.py", "services/pdf/render.py"):
        noi_dung = (GOC / f).read_text(encoding="utf-8")
        for gt in ("028 3842 5188", "02838425188", "info@lighthuman.vn", "213 Chu Văn An"):
            assert gt not in noi_dung, f"{f} còn viết cứng '{gt}'"


# ===================================================================== A5
def test_a5_duoi_file_chi_khai_bao_mot_noi():
    assert settings.DUOI_CV == (".pdf", ".png", ".jpg", ".jpeg", ".docx")
    assert settings.loai_cho_uploader(settings.DUOI_ANH) == ["png", "jpg", "jpeg"]
    for f in ("app.py", "services/ai/extract.py", "services/pdf/render.py"):
        noi_dung = (GOC / f).read_text(encoding="utf-8")
        assert '(".png", ".jpg", ".jpeg")' not in noi_dung and '"jpg", "jpeg"' not in noi_dung, f


# ===================================================================== A6
def test_a6_nguong_co_ten_va_giu_gia_tri():
    from services.privacy import checks
    from services.ai import models
    from services.pdf import render
    assert render.TRANG_CUOI_GAN_TRONG == 0.30 and checks.NGUONG_TRANG_CUOI_BAO_LOI == 0.15
    assert (models.NAM_SINH_HOP_LE_TU, models.NAM_SINH_HOP_LE_DEN) == (1940, 2015)
    assert (checks.NAM_SINH_TU, checks.NAM_SINH_DEN) == (1940, 2010)


# ===================================================================== A7
def test_a7_le_trang_tu_token():
    from services.pdf.render import render_html
    from infra.tokens import PDF_LE_MM
    from services.pdf import render_worker
    html = render_html(copy.deepcopy(GIA), "", "t")
    le = PDF_LE_MM
    assert f"margin: {le['tren']}mm {le['phai']}mm {le['duoi']}mm {le['trai']}mm" in html
    assert f"margin:0 {le['phai']}mm 0 {le['trai']}mm" in render_worker.footer_html()
    assert "16 / 297" not in (GOC / "services/pdf/render.py").read_text(encoding="utf-8")


def test_a7_font_serif_tu_token():
    from services.pdf.render import render_html
    from infra.tokens import FONT
    assert f"font-family:{FONT['serif-pdf']};" in render_html(copy.deepcopy(GIA), "", "t")


# ===================================================================== A8
@pytest.mark.parametrize("mxh", MANG_XA_HOI)
def test_a8_mot_danh_sach_mang_xa_hoi(mxh):
    assert MAU["Mạng xã hội"].search(f"{mxh.title()}: nguyenvana")
    assert NHAN_MXH.fullmatch(mxh.title())


# ===================================================================== Prompt
def test_prompt_doc_tu_file_giong_ban_cu():
    from datetime import date
    from services.ai import extract
    assert extract._user_text("Message Coffee", "Kế toán", date(2026, 11, 9)) == (
        "Hôm nay: 09/11/2026\nDự án: Message Coffee\nVị trí: Kế toán\nHãy trích xuất CV này theo schema.")
    assert extract._user_text("", "", date(2026, 1, 5)) == (
        "Hôm nay: 05/01/2026\nDự án: (không có)\n"
        "Vị trí: (không có — lấy theo chức danh mục tiêu trên CV)\nHãy trích xuất CV này theo schema.")
    assert settings.doc_prompt("fix_json.txt").format(loi="E") == \
        "JSON trên bị lỗi, hãy trả lại toàn bộ JSON đã sửa.\nLỗi: E"


def test_prompt_phien_ban_doi_khi_sua_prompt(tmp_path, monkeypatch):
    v = settings.phien_ban_prompt()
    assert re.fullmatch(r"\d+(\.\d+)*\+[0-9a-f]{8}", v)
    ban_sao = tmp_path / "prompts"
    shutil.copytree(GOC / "prompts", ban_sao)
    (ban_sao / "user.txt").write_text("đã sửa", encoding="utf-8")
    monkeypatch.setattr(settings, "THU_MUC_PROMPT", ban_sao)
    settings.phien_ban_prompt.cache_clear()
    try:
        v2 = settings.phien_ban_prompt()
        assert v2.split("+")[0] == v.split("+")[0] and v2 != v            # cùng số phiên bản, khác mã băm
    finally:
        monkeypatch.undo()
        settings.phien_ban_prompt.cache_clear()


def test_prompt_phien_ban_ghi_vao_metadata_pdf():
    import pymupdf as fitz
    from services.pdf.render import ghi_metadata
    doc = fitz.open(); doc.new_page(); doc.set_metadata({"title": "LH - CV Test"}); goc = doc.tobytes(); doc.close()
    with fitz.open(stream=ghi_metadata(goc), filetype="pdf") as d:
        assert d.metadata["title"] == "LH - CV Test"                     # checklist "tiêu đề = tên file" vẫn đạt
        assert settings.phien_ban_prompt() in d.metadata["keywords"]


# ===================================================================== .env: đường dẫn / timeout
def test_duong_dan_va_timeout_tu_env(monkeypatch, tmp_path):
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    assert settings.thu_muc_output() == GOC / "data" / "output"
    monkeypatch.setenv("OUTPUT_DIR", "du_lieu/xuat")
    assert settings.thu_muc_output() == GOC / "du_lieu" / "xuat"
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    assert settings.thu_muc_output() == tmp_path
    monkeypatch.delenv("RENDER_TIMEOUT", raising=False)
    assert settings.render_timeout() == 120
    monkeypatch.delenv("LOGO_PATH", raising=False)
    assert settings.logo_pdf() == GOC / "assets" / "logo.png"


# ===================================================================== N2
def test_n2_file_goc_khong_xem_duoc_khong_lam_hong_app(monkeypatch):
    from services.privacy import checks
    import pymupdf as fitz
    from services.pdf import render
    from streamlit.testing.v1 import AppTest

    def build_gia(cv, project, position, photo, out_dir, d=None):
        p = Path(out_dir) / "LH - CV Test.pdf"
        doc = fitz.open(); doc.new_page(); doc.save(p); doc.close()
        return p
    monkeypatch.setattr(render, "build_pdf", build_gia)
    monkeypatch.setattr(checks, "scan_pdf", lambda p: [{"ma": "pii", "muc": "x", "ok": True, "chi_tiet": "Sạch"}])
    at = AppTest.from_file(str(GOC / "app.py"), default_timeout=60)
    for k, v in dict(cv0=copy.deepcopy(GIA), goc=b"%PDF-hong-co-mat-khau", ten_goc="cv.pdf", project="",
                     position="", photo=None, auto_build=True, chat=[]).items():
        at.session_state[k] = v
    at.run()
    assert not at.exception
    assert any("Không xem trước được file gốc" in i.value for i in at.info)
