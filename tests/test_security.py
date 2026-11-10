"""Giai đoạn 1 — bảo mật & dữ liệu: S1, S7, S4, S5, S6, S2."""
import logging
import os
import subprocess
import time
import tomllib
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parent.parent


# ----- S1, S7: cấu hình server -----
def test_s1_s7_server_chi_nghe_localhost_va_gioi_han_upload():
    from services.ai import extract
    server = tomllib.loads((GOC / ".streamlit" / "config.toml").read_text(encoding="utf-8"))["server"]
    assert server["address"] == "localhost"
    assert server["maxUploadSize"] == extract.MAX_UPLOAD_MB == 20


def test_s7_doc_so_nguyen_tu_env(monkeypatch):
    from services.ai.extract import _so_nguyen_env
    for gia_tri, mong_doi in [("", 20), ("abc", 20), ("-5", 20), ("0", 20), ("35", 35)]:
        monkeypatch.setenv("X_TEST", gia_tri)
        assert _so_nguyen_env("X_TEST", 20) == mong_doi


def test_s7_chan_file_qua_lon_hoac_rong():
    from services.ai.extract import MAX_UPLOAD_MB, ExtractError, kiem_tra_file
    kiem_tra_file(b"x" * 1024, "cv.pdf")                                   # bình thường: không lỗi
    with pytest.raises(ExtractError, match="vượt giới hạn"):
        kiem_tra_file(b"x" * (MAX_UPLOAD_MB * 1024 * 1024 + 1), "cv.pdf")
    with pytest.raises(ExtractError, match="trống"):
        kiem_tra_file(b"", "cv.pdf")


def test_s7_extract_cv_chan_truoc_khi_goi_api(monkeypatch):
    from services.ai import extract
    monkeypatch.setattr(extract, "_client", lambda: pytest.fail("Không được gọi OpenAI với file quá lớn"))
    with pytest.raises(extract.ExtractError, match="vượt giới hạn"):
        extract.extract_cv(b"x" * (extract.MAX_UPLOAD_MB * 1024 * 1024 + 1), "cv.pdf")


# ----- S4: sandbox Chromium -----
def test_s4_chromium_giu_sandbox_mac_dinh(monkeypatch):
    from services.pdf.render_worker import chromium_args
    monkeypatch.delenv("CHROMIUM_NO_SANDBOX", raising=False)
    assert chromium_args() == []
    monkeypatch.setenv("CHROMIUM_NO_SANDBOX", "1")
    assert chromium_args() == ["--no-sandbox"]
    monkeypatch.setenv("CHROMIUM_NO_SANDBOX", "true")                      # chỉ đúng '1' mới tắt
    assert chromium_args() == []


# ----- S5: không đẩy stderr thô lên giao diện -----
def test_s5_loi_chromium_khong_lo_chi_tiet_len_ui(monkeypatch, tmp_path, caplog):
    from services.pdf import render
    bi_mat = r"C:\Users\nhan_vien\AppData\playwright\chrome.exe crashed"
    monkeypatch.setattr(render.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout="", stderr="Traceback...\n" + bi_mat))
    with caplog.at_level(logging.ERROR, logger="render"):
        with pytest.raises(RuntimeError) as loi:
            render.html_to_pdf("<html></html>", tmp_path / "x.pdf")
    assert bi_mat not in str(loi.value) and "log" in str(loi.value)       # UI: câu ngắn
    assert bi_mat in caplog.text                                          # log: đủ chi tiết


# ----- S6: log không chứa tên file CV -----
def test_s6_an_ten_file():
    from infra.logging_setup import an_ten_file
    ma = an_ten_file("Nguyễn Văn A - CV.pdf")
    assert ma.startswith("pdf#") and len(ma) == len("pdf#") + 8
    assert "Nguyễn" not in ma and "Van" not in ma
    assert an_ten_file("Nguyễn Văn A - CV.pdf") == ma                     # ổn định -> lần theo được
    assert an_ten_file("Trần Thị B.pdf") != ma
    assert an_ten_file("khong_duoi").startswith("khong-duoi#")


def test_s6_log_loi_doc_cv_khong_co_ten_file(monkeypatch, caplog):
    from services.ai import extract
    from streamlit.testing.v1 import AppTest
    from infra.logging_setup import an_ten_file

    def hong(*a, **k):
        raise ValueError("bất ngờ")
    monkeypatch.setattr(extract, "extract_cv", hong)
    at = AppTest.from_file(str(GOC / "app.py"), default_timeout=60)
    at.session_state["pending"] = {"data": b"x", "ten": "Nguyễn Văn A.docx", "project": "", "position": ""}
    with caplog.at_level(logging.ERROR):
        at.run()
    assert "Lỗi khi đọc CV" in caplog.text
    assert "Nguyễn Văn A" not in caplog.text and an_ten_file("Nguyễn Văn A.docx") in caplog.text


# ----- S2: tự xoá PDF hết hạn -----
def _tao(f: Path, so_ngay_truoc: float):
    f.write_bytes(b"%PDF")
    t = time.time() - so_ngay_truoc * 86400
    os.utime(f, (t, t))


def test_s2_xoa_dung_file_het_han(tmp_path):
    from infra.storage import don_file_het_han
    cu, moi, khac = tmp_path / "cu.pdf", tmp_path / "moi.pdf", tmp_path / "ghi_chu.txt"
    _tao(cu, 31); _tao(moi, 29); _tao(khac, 400)
    (tmp_path / "con").mkdir(); _tao(tmp_path / "con" / "cu_trong_thu_muc_con.pdf", 400)
    assert don_file_het_han(tmp_path, 30) == [cu]
    assert not cu.exists() and moi.exists() and khac.exists()            # .txt và thư mục con không bị đụng
    assert (tmp_path / "con" / "cu_trong_thu_muc_con.pdf").exists()


def test_s2_tat_tu_xoa_va_thu_muc_khong_ton_tai(tmp_path):
    from infra.storage import don_file_het_han
    _tao(tmp_path / "cu.pdf", 400)
    assert don_file_het_han(tmp_path, 0) == [] and (tmp_path / "cu.pdf").exists()
    assert don_file_het_han(tmp_path / "khong_co", 30) == []


def test_s2_doc_so_ngay_tu_env(monkeypatch):
    from infra.storage import so_ngay_luu
    for gia_tri, mong_doi in [("", 30), ("abc", 30), ("0", 0), ("-3", 0), ("7", 7)]:
        monkeypatch.setenv("OUTPUT_RETENTION_DAYS", gia_tri)
        assert so_ngay_luu() == mong_doi
    monkeypatch.delenv("OUTPUT_RETENTION_DAYS")
    assert so_ngay_luu() == 30


def test_s2_log_khong_ghi_ten_file(tmp_path, caplog):
    from infra.storage import don_file_het_han
    _tao(tmp_path / "LH - CV Ke toan - Nguyen Van A - 01012026.pdf", 400)
    with caplog.at_level(logging.INFO, logger="storage"):
        don_file_het_han(tmp_path, 30)
    assert "Đã xoá 1 hồ sơ" in caplog.text and "Nguyen Van A" not in caplog.text
