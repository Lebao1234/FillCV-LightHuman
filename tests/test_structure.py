"""Giai đoạn 4 — tái cấu trúc: A1, A2, A3, Q2, Q4."""
import copy
import inspect
import json
import logging
import typing
from pathlib import Path

import pytest

from core import pipeline, pdf_status
from ui import components as ui

GOC = Path(__file__).resolve().parent.parent
GIA = json.loads((GOC / "tests" / "fixtures" / "fake_candidate.json").read_text(encoding="utf-8"))
SACH = [{"ma": "pii", "muc": "x", "ok": True, "chi_tiet": "Sạch"}]
BAN = [{"ma": "pii", "muc": "x", "ok": False, "chi_tiet": "Số điện thoại: 0909123456"}]
XSS = '<script>alert("x")</script><img src=x onerror=alert(1)>'


# ===================================================================== A2: luật trạng thái (thuần Python)
def _tt(**kw):
    mac_dinh = dict(co_pdf=True, dau_pdf="a", dau_hien_tai="a", checklist=SACH, co_vi_pham=False,
                    co_loi_cau_truc=False, da_kiem_tu_lap=True, da_duyet=True)
    return pdf_status.tinh_trang_thai(**{**mac_dinh, **kw})


@pytest.mark.parametrize("kw,cho_tai,pill", [
    ({}, True, ("ok", "Sẵn sàng tải")),
    ({"da_duyet": False}, False, ("idle", "Chờ duyệt")),
    ({"da_kiem_tu_lap": False}, False, ("idle", "Chờ duyệt")),
    ({"dau_hien_tai": "b"}, False, ("warn", "Cần cập nhật")),
    ({"co_vi_pham": True}, False, ("err", "Cần sửa")),
    ({"co_loi_cau_truc": True}, False, ("err", "Cần sửa")),
    ({"checklist": BAN}, False, ("err", "Cần sửa")),
    ({"checklist": None}, False, ("err", "Cần sửa")),          # chưa có checklist -> không coi là sạch
    ({"co_pdf": False, "dau_pdf": None}, False, ("idle", "Chưa dựng")),
])
def test_a2_luat_khoa_tai(kw, cho_tai, pill):
    tt = _tt(**kw)
    assert tt.cho_tai is cho_tai and (tt.pill_loai, tt.pill_chu) == pill


def test_a2_pdf_cu_thi_khong_xet_checklist_cu():
    tt = _tt(dau_hien_tai="b", checklist=BAN)
    assert tt.cu and not tt.pdf_ban                                 # checklist thuộc bản PDF cũ -> bỏ qua


# ===================================================================== A1/A2: pipeline
def test_a2_doc_cv_doi_loi_thanh_loidoccv(monkeypatch, caplog):
    from services.ai import extract
    monkeypatch.setattr(extract, "extract_cv", lambda *a, **k: (_ for _ in ()).throw(extract.ExtractError("Hết hạn mức.")))
    with pytest.raises(pipeline.LoiDocCV, match="Hết hạn mức."):
        pipeline.doc_cv(b"x", "cv.pdf", "", "")
    monkeypatch.setattr(extract, "extract_cv", lambda *a, **k: (_ for _ in ()).throw(ValueError("bất ngờ")))
    with caplog.at_level(logging.ERROR, logger="app"):
        with pytest.raises(pipeline.LoiDocCV, match="Có lỗi không mong muốn"):
            pipeline.doc_cv(b"x", "Nguyễn Văn A.pdf", "", "")
    assert "Nguyễn Văn A" not in caplog.text and "Lỗi khi đọc CV" in caplog.text


def test_a2_doc_cv_tra_ho_so_va_anh(monkeypatch):
    from services.ai import extract
    from services.pdf import render
    monkeypatch.setattr(extract, "extract_cv", lambda *a, **k: copy.deepcopy(GIA))
    monkeypatch.setattr(render, "extract_photo", lambda d, t: b"ANH")
    kq = pipeline.doc_cv(b"x", "cv.pdf", "Dự án", "")
    assert kq.cv["full_name"] == GIA["full_name"] and kq.photo == b"ANH"


def test_a2_dung_pdf_goi_qua_module(monkeypatch, tmp_path):
    from services.privacy import checks
    from services.pdf import render
    def build_gia(cv, project, position, photo, out_dir, d=None):
        p = Path(out_dir) / "LH - CV X.pdf"; p.write_bytes(b"%PDF-gia"); return p
    monkeypatch.setattr(render, "build_pdf", build_gia)
    monkeypatch.setattr(checks, "scan_pdf", lambda p: SACH)
    kq = pipeline.dung_pdf(copy.deepcopy(GIA), "Dự án Mẫu", "Kế toán", None)
    assert (kq.pdf_bytes, kq.ten, kq.checklist) == (b"%PDF-gia", "LH - CV X.pdf", SACH)
    assert kq.tin_nhan.startswith(f"Hồ sơ ứng viên: {GIA['full_name']} – Kế toán")


def test_a2_luu_ban_sao_khong_ghi_de(tmp_path):
    a = pipeline.luu_ban_sao(tmp_path / "out", "LH - CV.pdf", b"1")
    b = pipeline.luu_ban_sao(tmp_path / "out", "LH - CV.pdf", b"2")
    assert a.name == "LH - CV.pdf" and b != a and a.read_bytes() == b"1" and b.read_bytes() == b"2"


# ===================================================================== A1: app.py chỉ còn điều phối
def test_a1_app_gon_va_khong_chua_nghiep_vu():
    code = (GOC / "app.py").read_text(encoding="utf-8")
    assert len(code.splitlines()) < 250
    for khong_nen in ("import tempfile", "import hashlib", "import json", "def sua_ho_so", "def kiem_tra_cau_truc",
                      "<style>", 'class="lh-'):
        assert khong_nen not in code, khong_nen


# ===================================================================== A3
def test_a3_checks_khong_phu_thuoc_render():
    code = (GOC / "services/privacy/checks.py").read_text(encoding="utf-8")
    assert "from render" not in code and "import render" not in code
    from services.pdf import pdf_utils
    from services.pdf import render
    assert render.pdf_layout is pdf_utils.pdf_layout                # render vẫn dùng chung 1 hàm


# ===================================================================== Q4: chống XSS
def test_q4_tin_text_luon_duoc_escape():
    html = ui.ve_tin({"role": "assistant", "kind": "error", "text": XSS})
    assert "<script>" not in html and "<img" not in html and "&lt;script&gt;" in html


def test_q4_tin_html_dung_san_giu_nguyen():
    html = ui.ve_tin({"role": "assistant", "kind": "text", "html": ui.tin_loi("Lỗi.", XSS)})
    assert "<b>Lỗi.</b>" in html and "<script>" not in html and "<img" not in html


@pytest.mark.parametrize("tin", [
    {"role": "user", "kind": "file", "ten": XSS, "project": XSS, "position": XSS},
    {"role": "assistant", "kind": "notes", "name": XSS, "salary": XSS, "co_anh": False,
     "notes": {"removed": [XSS], "self_created": [XSS], "recruiting_flags": [XSS], "other": [XSS]}},
])
def test_q4_du_lieu_cv_trong_tin_nhan_khong_chen_duoc_the(tin):
    html = ui.ve_tin(tin)
    assert "<script>" not in html and "<img" not in html


def test_q4_khung_pdf_khong_chen_duoc_the():
    vp = [{"loai": "Email", "gia_tri": XSS, "field": XSS}]
    ck = [{"ma": "pii", "muc": XSS, "ok": False, "chi_tiet": XSS}]
    for html in (ui.canh_bao_html([XSS], vp, True, True, ck), ui.checklist_html(ck),
                 ui.thanh_trang_thai(XSS, XSS, "err", XSS), ui.alert("err", XSS), ui.tin_da_xuat(XSS),
                 ui.tieu_de_panel(XSS)):
        assert "<script>" not in html and "<img" not in html, html


def test_q4_loi_doc_cv_co_the_html_hien_thi_an_toan(monkeypatch):
    from services.ai import extract
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(extract, "extract_cv", lambda *a, **k: (_ for _ in ()).throw(extract.ExtractError(XSS)))
    at = AppTest.from_file(str(GOC / "app.py"), default_timeout=60)
    at.session_state["pending"] = {"data": b"x", "ten": "cv.docx", "project": "", "position": ""}
    at.run()
    assert not at.exception
    tat_ca = " ".join(m.value for m in at.markdown)
    assert "<script>" not in tat_ca and "<img src=x" not in tat_ca and "&lt;script&gt;" in tat_ca


# ===================================================================== Q2
def test_q2_form_co_ham_cho_moi_loai_muc():
    from services.ai.models import SectionType
    from ui.profile_form import SUA_THEO_LOAI
    assert set(SUA_THEO_LOAI) == set(typing.get_args(SectionType))


def test_q2_sua_ho_so_gon():
    from ui.profile_form import sua_ho_so
    assert len(inspect.getsource(sua_ho_so).splitlines()) <= 15


@pytest.mark.parametrize("module", [pipeline, pdf_status, ui])
def test_q2_ham_cong_khai_co_type_hint_va_docstring(module):
    for ten, ham in inspect.getmembers(module, inspect.isfunction):
        if ten.startswith("_") or ham.__module__ != module.__name__:
            continue
        chu_ky = inspect.signature(ham)
        assert chu_ky.return_annotation is not inspect.Signature.empty, f"{ten}: thiếu kiểu trả về"
        if module is not ui:            # ui.* là hàm dựng HTML ngắn, tên đã tự giải thích
            assert ham.__doc__, f"{ten}: thiếu docstring"
