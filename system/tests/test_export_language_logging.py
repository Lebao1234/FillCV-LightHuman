"""Test: lưu bản xuất (PDF + JSON) an toàn, ngôn ngữ xuất PDF, log giờ Việt Nam + cảnh báo dựng chậm.

Chỉ dùng hồ sơ giả tests/fixtures/fake_candidate.json. Test đánh dấu `slow` dựng PDF bằng Chromium thật.
"""
import itertools
import json
import logging
import subprocess
from datetime import date
from pathlib import Path

import pytest

from core import pipeline
from infra import logging_setup
from services.pdf import labels, render
from services.privacy import checks

FIXTURE = Path(__file__).parent / "fixtures" / "fake_candidate.json"
SECRET_NAME = "LH - CV Ke toan - Nguyen Van Bimat - 13112026.pdf"   # tên file = họ tên ứng viên -> không được vào log


# Hồ sơ giả dùng chung
@pytest.fixture
def cv() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ lưu bản xuất

# Lưu được: có cặp PDF + JSON, JSON ghi ngôn ngữ xuất và hồ sơ đọc lại đúng
def test_store_export_saves_pdf_and_json(tmp_path, cv):
    assert pipeline.store_export(tmp_path, SECRET_NAME, b"%PDF-fake", cv=cv, project="P", position="Q", lang="en") is None
    record = json.loads((tmp_path / SECRET_NAME).with_suffix(".json").read_text(encoding="utf-8"))
    assert (tmp_path / SECRET_NAME).read_bytes() == b"%PDF-fake"
    assert record["pdf_language"] == "en" and record["project"] == "P" and record["cv"] == cv


# Không lưu được: trả câu báo, log chỉ có loại lỗi — không lộ đường dẫn / họ tên ứng viên
def test_store_export_error_is_reported_without_leaking_name(tmp_path, cv, caplog):
    blocker = tmp_path / "output"
    blocker.write_text("not a folder", encoding="utf-8")
    with caplog.at_level(logging.ERROR):
        message = pipeline.store_export(blocker, SECRET_NAME, b"%PDF-fake", cv=cv)
    assert message and "báo người quản trị" in message
    assert "Bimat" not in message and "Bimat" not in caplog.text
    assert "Không lưu được bản sao" in caplog.text


# PermissionError: câu báo nói rõ thiếu quyền ghi (trường hợp data/ thuộc root trong Docker)
def test_store_export_permission_hint(tmp_path, monkeypatch, caplog):
    def deny(*args, **kwargs):
        raise PermissionError(13, "Permission denied", f"/app/data/output/{SECRET_NAME}")
    monkeypatch.setattr(pipeline, "save_copy", deny)
    with caplog.at_level(logging.ERROR):
        message = pipeline.store_export(tmp_path, SECRET_NAME, b"%PDF-fake")
    assert "không có quyền ghi" in message
    assert "Bimat" not in caplog.text and "PermissionError" in caplog.text


# ------------------------------------------------------------------ log

# Giờ trong log luôn là giờ Việt Nam, bất kể múi giờ hệ điều hành (container Docker = UTC)
def test_log_time_is_vietnam_time():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "x", None, None)
    record.created, record.msecs = 1767225600.0, 5.0          # 2026-01-01 00:00:00 UTC
    assert logging_setup._LocalTimeFormatter().formatTime(record) == "2026-01-01 07:00:00,005"


# Lượt dựng PDF quá nửa RENDER_TIMEOUT -> WARNING (không cần Chromium: giả tiến trình con và đồng hồ)
def test_slow_render_logs_warning(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    clock = itertools.count(0, 70)
    monkeypatch.setattr(render.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(render, "render_timeout", lambda: 120)
    with caplog.at_level(logging.WARNING):
        render.html_to_pdf_batch(["<p>x</p>"], [tmp_path / "a.pdf"])
    assert "Dựng PDF chậm" in caplog.text


# Lượt dựng nhanh -> không cảnh báo
def test_fast_render_no_warning(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(render.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""))
    with caplog.at_level(logging.WARNING):
        render.html_to_pdf_batch(["<p>x</p>"], [tmp_path / "a.pdf"])
    assert "Dựng PDF chậm" not in caplog.text


# ------------------------------------------------------------------ ngôn ngữ xuất PDF

# Thuật ngữ so khớp GIỮ dấu: "Nam" (giới tính) khác "năm" (đơn vị)
@pytest.mark.parametrize("text, lang, expected", [
    ("Nam", "en", "Male"), ("Nữ", "en", "Female"), ("5 năm", "en", "5 years"), ("6+ năm", "en", "6+ years"),
    ("18 tháng", "en", "18 months"), ("Thạc sĩ", "en", "Master"), ("Kế toán", "en", "Kế toán"),
    ("3 years", "vi", "3 năm"), ("Male", "vi", "Nam"), ("Nam", "vi", "Nam"),
])
def test_translate_term(text, lang, expected):
    assert labels.translate_term(text, lang) == expected


# Tiêu đề mục chuẩn đổi ngôn ngữ, giữ IN HOA; tiêu đề đã đúng ngôn ngữ giữ nguyên
def test_translate_title():
    assert labels.translate_title("KINH NGHIỆM LÀM VIỆC", "en") == "WORK EXPERIENCE"
    assert labels.translate_title("Work Experience", "vi") == "Kinh nghiệm làm việc"
    assert labels.translate_title("Quá trình công tác", "vi") == "Quá trình công tác"
    assert labels.translate_title("Một mục tự đặt", "en") == "Một mục tự đặt"


# Xuất tiếng Việt từ CV tiếng Việt: hồ sơ không đổi gì (giữ PDF giống từng điểm ảnh); không sửa hồ sơ gốc
def test_localize_vi_keeps_vietnamese_cv(cv):
    before = json.dumps(cv, sort_keys=True)
    assert labels.localize_cv(cv, "vi") == {**cv, "language": "vi"}
    english = labels.localize_cv(cv, "en")
    assert json.dumps(cv, sort_keys=True) == before
    assert english["language"] == "en" and english["gender"] == "Female"


# Tên file bản tiếng Anh có hậu tố " - EN"; mã nhận diện nội dung đổi theo ngôn ngữ
def test_filename_and_fingerprint_depend_on_language(cv):
    d = date(2026, 11, 13)
    assert render.build_filename("Ke toan", "Lam Thu", d, "vi") == "LH - CV Ke toan - Lam Thu - 13112026.pdf"
    assert render.build_filename("Ke toan", "Lam Thu", d, "en") == "LH - CV Ke toan - Lam Thu - 13112026 - EN.pdf"
    fp = [pipeline.content_fingerprint(cv, "P", "Q", None, lang) for lang in ("vi", "en")]
    assert fp[0] != fp[1]


# Ngôn ngữ mặc định theo CV
def test_default_lang():
    assert labels.default_lang({"language": "en"}) == "en"
    assert labels.default_lang({"language": "bilingual_vi_en"}) == "vi"
    assert labels.default_lang(None) == "vi"


# Dựng thật cả hai ngôn ngữ: checklist đạt hết, header đúng ngôn ngữ
@pytest.mark.slow
@pytest.mark.parametrize("lang, title", [("vi", "HỒ SƠ ỨNG VIÊN"), ("en", "CANDIDATE PROFILE")])
def test_build_pdf_checklist_passes(tmp_path, cv, lang, title):
    pdf = render.build_pdf(cv, "Du an", "Ke toan", None, tmp_path, d=date(2026, 11, 13), lang=lang)
    result = checks.scan_pdf(pdf, lang=lang)
    assert all(r["ok"] for r in result), [r for r in result if not r["ok"]]
    assert title in next(r["item"] for r in result if r["code"] == "header")
    assert pdf.name.endswith(" - EN.pdf") == (lang == "en")
