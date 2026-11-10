"""Giai đoạn 5 (T1): test tích hợp đường chạy thật + các nhánh lỗi của extract.py.

- @pytest.mark.slow: dựng PDF bằng Chromium thật rồi quét checklist (không gọi OpenAI).
- Còn lại: _call_api với client OpenAI giả (mọi loại lỗi), _build_file_part, _docx_to_text.
"""
import copy
import io
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx
import openai
import pytest

from services.ai import extract

GOC = Path(__file__).resolve().parent.parent
GIA = json.loads((GOC / "tests" / "fixtures" / "fake_candidate.json").read_text(encoding="utf-8"))
REQ = httpx.Request("POST", "https://api.openai.com/v1/responses")


# ===================================================================== Tích hợp (Chromium thật)
@pytest.mark.slow
def test_tich_hop_dung_pdf_that_va_checklist(tmp_path):
    import pymupdf as fitz
    from infra import settings
    from services.privacy.checks import pdf_sach, scan_pdf
    from services.pdf.render import build_pdf
    p = build_pdf(extract.validate(copy.deepcopy(GIA)), "Dự án Mẫu", "Trưởng phòng Kế toán", None, tmp_path,
                  d=date(2026, 11, 9))
    assert p.name == "LH - CV Truong phong Ke toan - Lam Quynh Anh Thu - 09112026.pdf"
    ck = scan_pdf(p)
    assert all(r["ok"] for r in ck), [r for r in ck if not r["ok"]]
    assert pdf_sach(ck)
    with fitz.open(p) as d:
        chu = "\n".join(pg.get_text() for pg in d)
        assert d.metadata["title"] == p.stem
        assert settings.phien_ban_prompt() in d.metadata["keywords"]
    assert "LÂM QUỲNH ANH THƯ" in chu.upper() and "Dự án Mẫu" in chu
    assert settings.cong_ty()["cong_ty"]["dien_thoai"] in chu        # header công ty từ config
    assert "Light Human" in chu and "Trang 1/" in chu                  # footer


@pytest.mark.slow
def test_tich_hop_pdf_lot_sdt_thi_checklist_chan(tmp_path):
    """Lớp chặn cuối: dù dữ liệu lọt qua scan_pii, quét chính file PDF vẫn bắt được và pdf_sach() = False."""
    from services.privacy.checks import pdf_sach, scan_pdf
    from services.pdf.render import build_pdf
    cv = extract.validate(copy.deepcopy(GIA))
    cv["sections"][0]["paragraphs"].append("Liên hệ trực tiếp: 0912 345 678")
    p = build_pdf(cv, "", "Kế toán", None, tmp_path, d=date(2026, 11, 9))
    ck = scan_pdf(p)
    assert not pdf_sach(ck)
    assert "0912 345 678" in next(r["chi_tiet"] for r in ck if r["ma"] == "pii")


# ===================================================================== _call_api: mọi nhánh lỗi
def _goi_voi(monkeypatch, ket_qua):
    """extract_cv với client giả trả lần lượt `ket_qua` (chuỗi JSON, exception, hoặc response giả)."""
    cac_lan = []

    def create(**kw):
        cac_lan.append(kw)
        x = ket_qua.pop(0)
        if isinstance(x, BaseException):
            raise x
        if isinstance(x, SimpleNamespace):
            return x
        return SimpleNamespace(id=f"r{len(cac_lan)}", status="completed", output_text=x, incomplete_details=None)
    monkeypatch.setattr(extract, "_client", lambda: SimpleNamespace(responses=SimpleNamespace(create=create)))
    return lambda: extract.extract_cv(b"%PDF-gia", "cv.pdf", today=date(2026, 11, 9)), cac_lan


@pytest.mark.parametrize("loi,thong_bao", [
    (openai.APIConnectionError(request=REQ), "Không kết nối được tới OpenAI"),
    (openai.AuthenticationError("bad key", response=httpx.Response(401, request=REQ), body=None), "API key OpenAI không hợp lệ"),
    (openai.RateLimitError("insufficient_quota", response=httpx.Response(429, request=REQ), body=None), "hết hạn mức"),
    (openai.RateLimitError("slow down", response=httpx.Response(429, request=REQ), body=None), "quá tải"),
    (openai.BadRequestError("file quá lớn", response=httpx.Response(400, request=REQ), body=None), "OpenAI từ chối yêu cầu"),
    (openai.InternalServerError("lỗi máy chủ", response=httpx.Response(500, request=REQ), body=None), "Lỗi từ OpenAI"),
])
def test_call_api_doi_loi_thanh_tieng_viet(monkeypatch, loi, thong_bao):
    chay, _ = _goi_voi(monkeypatch, [loi])
    with pytest.raises(extract.ExtractError, match=thong_bao):
        chay()


def test_call_api_ket_qua_bi_cat_giua_chung(monkeypatch):
    cat = SimpleNamespace(id="r1", status="incomplete", output_text="{",
                          incomplete_details=SimpleNamespace(reason="max_output_tokens"))
    chay, _ = _goi_voi(monkeypatch, [cat])
    with pytest.raises(extract.ExtractError, match="CV quá dài"):
        chay()


def test_json_hong_ca_3_lan_thi_dung_lai(monkeypatch):
    chay, cac_lan = _goi_voi(monkeypatch, ["{hỏng", "vẫn hỏng", '{"language": "vi"}'])
    with pytest.raises(extract.ExtractError, match="sai cấu trúc sau 3 lần thử"):
        chay()
    assert len(cac_lan) == 3


def test_json_hong_roi_dung_o_lan_2(monkeypatch):
    chay, cac_lan = _goi_voi(monkeypatch, ["```json\n{hỏng\n```", json.dumps(GIA)])
    assert chay()["full_name"] == GIA["full_name"] and len(cac_lan) == 2


def test_thieu_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(extract.ExtractError, match="Chưa cấu hình OPENAI_API_KEY"):
        extract._client()


# ===================================================================== _build_file_part / _docx_to_text
def _docx(doan: list[str], bang=None, anh=False) -> bytes:
    import docx
    from PIL import Image
    d = docx.Document()
    for x in doan:
        d.add_paragraph(x)
    if bang:
        t = d.add_table(rows=len(bang), cols=len(bang[0]))
        for i, hang in enumerate(bang):
            for j, o in enumerate(hang):
                t.cell(i, j).text = o
        t.cell(0, 0).merge(t.cell(0, 1))                                # ô gộp -> không được lặp chữ
    if anh:
        b = io.BytesIO(); Image.new("RGB", (60, 80), "gray").save(b, "PNG"); b.seek(0)
        d.add_picture(b)
    out = io.BytesIO(); d.save(out)
    return out.getvalue()


def test_docx_to_text_doan_bang_va_anh():
    van_ban, co_anh = extract._docx_to_text(_docx(["Lâm Thư", "  ", "Kế toán"], [["Kỹ năng", "x"], ["Excel", "Power BI"]], anh=True))
    dong = van_ban.splitlines()
    assert dong[:2] == ["Lâm Thư", "Kế toán"]                           # bỏ đoạn trống
    assert "Excel | Power BI" in dong
    assert any(d.startswith("Kỹ năng") and d.count("Kỹ năng") == 1 for d in dong)
    assert co_anh is True
    assert extract._docx_to_text(_docx(["Chỉ có chữ"]))[1] is False


@pytest.mark.parametrize("ten,loai", [("cv.pdf", "input_file"), ("cv.PNG", "input_image"), ("cv.jpeg", "input_image")])
def test_build_file_part_theo_loai(ten, loai):
    part, ghi_chu = extract._build_file_part(b"du lieu", ten)
    assert part["type"] == loai and ghi_chu == []


def test_build_file_part_docx():
    part, ghi_chu = extract._build_file_part(_docx(["Lâm Thư"]), "cv.docx")
    assert part["type"] == "input_text" and "Lâm Thư" in part["text"]
    assert ghi_chu == ["DOCX không có ảnh chân dung"]
    with pytest.raises(extract.ExtractError, match="không có nội dung chữ"):
        extract._build_file_part(_docx([]), "cv.docx")
    with pytest.raises(extract.ExtractError, match="Chưa hỗ trợ loại file"):
        extract._build_file_part(b"x", "cv.txt")
