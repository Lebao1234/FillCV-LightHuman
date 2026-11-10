"""Giai đoạn 2 — lỗi chức năng & độ tin cậy: Q1, R1, R3, R4, Q3, Q5, Q7, N1."""
import copy
import json
import logging
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

GOC = Path(__file__).resolve().parent.parent
APP = str(GOC / "app.py")
GIA = json.loads((GOC / "tests" / "fixtures" / "fake_candidate.json").read_text(encoding="utf-8"))


# ===================================================================== Q1
def _app_gia(monkeypatch, cv):
    """App đã có hồ sơ `cv`; build_pdf/scan_pdf giả cho nhanh."""
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
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in dict(cv0=cv, goc=b"", ten_goc="x.docx", project="Dự án Mẫu", position="Kế toán",
                     photo=None, auto_build=True, chat=[], run=0).items():
        at.session_state[k] = v
    at.run()
    return at


def test_q1_sua_duoc_sdt_trong_vi_tri_con_de_mo_khoa_tai(monkeypatch):
    cv = copy.deepcopy(GIA)
    cv["sections"][3]["jobs"][1]["sub_roles"][0]["meta"] = [{"label": "Liên hệ", "text": "0912 345 678"}]
    at = _app_gia(monkeypatch, cv)
    assert not at.exception
    for c in at.checkbox:
        c.check()
    at.run()
    assert [d.proto.disabled for d in at.get("download_button")] == [True]          # đang bị khoá vì SĐT
    o_meta = at.text_area(key="0-s3j1r0m")                                           # ô sửa mới (Q1)
    assert "0912 345 678" in o_meta.value
    o_meta.set_value("Báo cáo cho | Kế toán trưởng").run()
    next(b for b in at.button if b.label == "Cập nhật PDF").click().run()
    assert not at.exception
    assert [d.proto.disabled for d in at.get("download_button")] == [False]         # đã mở khoá


def test_q1_sua_duoc_tieu_de_nhom_vi_tri_con(monkeypatch):
    at = _app_gia(monkeypatch, copy.deepcopy(GIA))
    o = at.text_input(key="0-s3j1r0g0t")
    assert o.value == "Tổng hợp"


# ===================================================================== R1 (client OpenAI giả)
class _ClientGia:
    """Giả lập client.responses.create: trả lần lượt các văn bản trong `tra_ve`, ghi lại tham số mỗi lần gọi."""

    def __init__(self, tra_ve):
        self.tra_ve, self.cac_lan = list(tra_ve), []
        self.responses = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.cac_lan.append(kw)
        x = self.tra_ve.pop(0)
        if isinstance(x, BaseException):
            raise x
        return SimpleNamespace(id=f"resp_{len(self.cac_lan)}", status="completed", output_text=x,
                               incomplete_details=None)


def _extract_voi(monkeypatch, tra_ve, **env):
    from services.ai import extract
    for k, v in env.items():
        monkeypatch.setattr(extract, k, v)
    client = _ClientGia(tra_ve)
    monkeypatch.setattr(extract, "_client", lambda: client)
    return extract, client


def test_r1_mac_dinh_thoi_gian(monkeypatch):
    from services.ai.extract import _so_nguyen_env
    for ten, md, cho0 in [("OPENAI_TIMEOUT", 90, False), ("OPENAI_MAX_RETRIES", 1, True), ("OPENAI_TOTAL_DEADLINE", 180, False)]:
        monkeypatch.delenv(ten, raising=False)
        assert _so_nguyen_env(ten, md, cho0) == md
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "0")
    assert _so_nguyen_env("OPENAI_MAX_RETRIES", 1, cho_phep_0=True) == 0


def test_r1_sua_json_bang_previous_response_id_khong_gui_lai_file(monkeypatch):
    extract, client = _extract_voi(monkeypatch, ["{hỏng", json.dumps(GIA)], OPENAI_STORE=True)
    ra = extract.extract_cv(b"%PDF-1.4 gia", "cv.pdf", today=date(2026, 11, 9))
    assert ra["full_name"] == GIA["full_name"]
    lan1, lan2 = client.cac_lan
    assert lan1["store"] is True and "previous_response_id" not in lan1
    assert lan2["previous_response_id"] == "resp_1"
    assert "input_file" not in json.dumps(lan2["input"], ensure_ascii=False)        # không gửi lại file CV
    assert lan2["instructions"] == extract.SYSTEM_PROMPT                             # instructions luôn gửi lại


def test_r1_store_tat_thi_gui_lai_day_du(monkeypatch):
    extract, client = _extract_voi(monkeypatch, ["{hỏng", json.dumps(GIA)], OPENAI_STORE=False)
    extract.extract_cv(b"%PDF-1.4 gia", "cv.pdf", today=date(2026, 11, 9))
    lan2 = client.cac_lan[1]
    assert lan2["store"] is False and "previous_response_id" not in lan2
    assert "input_file" in json.dumps(lan2["input"], ensure_ascii=False)


def test_r1_timeout_moi_lan_khong_vuot_han_tong(monkeypatch):
    extract, client = _extract_voi(monkeypatch, [json.dumps(GIA)], OPENAI_TIMEOUT=90, OPENAI_MAX_RETRIES=1,
                                   OPENAI_TOTAL_DEADLINE=120)
    extract.extract_cv(b"%PDF-1.4 gia", "cv.pdf", today=date(2026, 11, 9))
    # (1 lần gọi + 1 lần SDK thử lại) x timeout phải <= hạn tổng 120 s
    assert client.cac_lan[0]["timeout"] <= 60 + 0.5


def test_r1_het_han_tong_bao_loi_ro_rang(monkeypatch):
    extract, client = _extract_voi(monkeypatch, ["{hỏng"] * 3, OPENAI_TOTAL_DEADLINE=180)
    dong_ho = iter([0, 0, 200, 200, 200, 200])                                       # lần thứ 2: đã qua 200 s
    monkeypatch.setattr(extract.time, "monotonic", lambda: next(dong_ho))
    with pytest.raises(extract.ExtractError, match="Quá 180 giây"):
        extract.extract_cv(b"%PDF-1.4 gia", "cv.pdf", today=date(2026, 11, 9))
    assert len(client.cac_lan) == 1


def test_r1_timeout_openai_thanh_thong_bao_tieng_viet(monkeypatch):
    import httpx
    import openai
    loi = openai.APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    extract, _ = _extract_voi(monkeypatch, [loi])
    with pytest.raises(extract.ExtractError, match="Hết thời gian chờ phản hồi từ OpenAI .*giây"):
        extract.extract_cv(b"%PDF-1.4 gia", "cv.pdf", today=date(2026, 11, 9))


# ===================================================================== Q7
def test_q7_ngay_mac_dinh_theo_gio_viet_nam(monkeypatch):
    from services.pdf import render
    monkeypatch.setattr(render, "hom_nay_vn", lambda: date(2030, 1, 2))
    extract, client = _extract_voi(monkeypatch, [json.dumps(GIA)])
    extract.extract_cv(b"%PDF-1.4 gia", "cv.pdf")
    assert "02/01/2030" in json.dumps(client.cac_lan[0]["input"], ensure_ascii=False)


# ===================================================================== R4
def test_r4_log_co_run_id_va_khong_trung_handler(tmp_path, monkeypatch):
    from infra import logging_setup as ls
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    f = ls.cau_hinh_logging("thu.log")
    ls.cau_hinh_logging("thu.log")
    goc = logging.getLogger()
    so = [h for h in goc.handlers if getattr(h, "baseFilename", "") == str(f.resolve())]
    assert len(so) == 1
    try:
        ls.dat_run_id("ab12cd34")
        logging.getLogger("thu").warning("xin chào")
        so[0].flush()
        dong = f.read_text(encoding="utf-8")
        assert "[ab12cd34] thu: xin chào" in dong and "WARNING" in dong
    finally:
        ls.dat_run_id(None)
        goc.removeHandler(so[0]); so[0].close()


def test_r4_run_id_truyen_sang_render_worker(monkeypatch, tmp_path):
    from infra import logging_setup as ls
    from services.pdf import render
    nhan = {}

    def run_gia(args, **kw):
        nhan["args"] = args
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(render.subprocess, "run", run_gia)
    ls.dat_run_id("ff00aa11")
    try:
        render.html_to_pdf("<html></html>", tmp_path / "x.pdf")
    finally:
        ls.dat_run_id(None)
    assert nhan["args"][-1] == "ff00aa11"


@pytest.mark.slow
def test_r4_render_worker_ghi_log_cung_run_id(tmp_path):
    """Chạy thật render_worker với file HTML không tồn tại -> lỗi được ghi vào render_worker.log kèm run_id."""
    env = {**__import__("os").environ, "LOG_DIR": str(tmp_path)}
    kq = subprocess.run([sys.executable, "-m", "services.pdf.render_worker", str(tmp_path / "khong_co.html"),
                         str(tmp_path / "x.pdf"), "c0ffee42"], capture_output=True, text=True, env=env, timeout=120, cwd=GOC)
    assert kq.returncode != 0
    log = (tmp_path / "render_worker.log").read_text(encoding="utf-8")
    assert "[c0ffee42]" in log and "Dựng PDF thất bại" in log


def test_r4_app_ghi_log_theo_run_id(monkeypatch):
    from services.ai import extract
    from infra import logging_setup as ls
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(extract, "extract_cv", lambda *a, **k: copy.deepcopy(GIA))
    monkeypatch.setattr(__import__("services.pdf.render", fromlist=["x"]), "build_pdf",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bỏ qua")))
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["pending"] = {"data": b"x", "ten": "Lâm Quỳnh Anh Thư.docx", "project": "", "position": ""}
    at.session_state["run_id"] = "5e5e5e5e"
    at.run()
    for h in logging.getLogger().handlers:
        h.flush()
    log = (ls.thu_muc_log() / "app.log").read_text(encoding="utf-8")
    assert "[5e5e5e5e] app: Đọc CV xong" in log
    assert "[5e5e5e5e] app: Dựng PDF thất bại" in log                                 # R3: lỗi có trong log
    assert "Lâm Quỳnh" not in log                                                     # không PII


# ===================================================================== R3
def test_r3_loi_lay_anh_duoc_ghi_log(caplog):
    from services.pdf.render import extract_photo
    with caplog.at_level(logging.WARNING, logger="render"):
        assert extract_photo(b"khong phai pdf", "cv.pdf") is None                    # vẫn fallback như cũ
    assert "Lấy ảnh chân dung thất bại" in caplog.text


# ===================================================================== Q5
def test_q5_ban_sao_khong_ghi_de(tmp_path):
    from infra.storage import duong_dan_khong_trung
    ten = "LH - CV Ke toan - Lam Thu - 09112026.pdf"
    p1 = duong_dan_khong_trung(tmp_path, ten)
    assert p1.name == ten                                                             # chưa trùng: giữ tên chuẩn
    p1.write_bytes(b"1")
    t = time.mktime((2026, 11, 9, 14, 30, 15, 0, 0, -1))
    p2 = duong_dan_khong_trung(tmp_path, ten, bay_gio=t)
    assert p2.name == "LH - CV Ke toan - Lam Thu - 09112026 (143015).pdf"
    p2.write_bytes(b"2")
    assert duong_dan_khong_trung(tmp_path, ten, bay_gio=t).name.endswith("(143015-2).pdf")


# ===================================================================== N1
def test_n1_font_type3_coi_la_da_nhung():
    from services.privacy.checks import kiem_tra_font
    tnr = (8, "ttf", "Type0", "BAAAAA+TimesNewRomanPSMT", "F8", "Identity-H")
    type3 = (10, "n/a", "Type3", "", "F10", "")
    kq = kiem_tra_font([tnr, type3])
    assert kq["ok"] and "Type3" in kq["chi_tiet"] and "CHƯA" not in kq["chi_tiet"]
    chua = (11, "n/a", "TrueType", "Arial", "F11", "")                               # font thường không nhúng
    kq = kiem_tra_font([tnr, chua])
    assert not kq["ok"] and "Arial" in kq["chi_tiet"]
    assert not kiem_tra_font([type3])["ok"]                                          # không có serif -> chưa đạt
