"""Sửa sau kiểm thử tải: hàng đợi dựng PDF, dựng nhiều cỡ chữ trong 1 tiến trình, log an toàn đa luồng."""
import copy
import json
import logging
import random
import subprocess
import threading
import time
from pathlib import Path

import pytest

from core import pipeline

GOC = Path(__file__).resolve().parent.parent
GIA = json.loads((GOC / "tests" / "fixtures" / "fake_candidate.json").read_text(encoding="utf-8"))
SACH = [{"ma": "pii", "muc": "x", "ok": True, "chi_tiet": "Sạch"}]


@pytest.fixture
def dung_gia(monkeypatch):
    """build_pdf giả mất 0.3 s; ghi lại số lượt chạy cùng lúc nhiều nhất."""
    from services.privacy import checks
    from services.pdf import render
    dem = {"dang": 0, "max": 0}
    khoa = threading.Lock()

    def build_gia(cv, project, position, photo, out_dir, d=None):
        with khoa:
            dem["dang"] += 1
            dem["max"] = max(dem["max"], dem["dang"])
        time.sleep(0.3)
        with khoa:
            dem["dang"] -= 1
        p = Path(out_dir) / "LH - CV X.pdf"
        p.write_bytes(b"%PDF")
        return p
    monkeypatch.setattr(render, "build_pdf", build_gia)
    monkeypatch.setattr(checks, "scan_pdf", lambda p: SACH)
    monkeypatch.setattr(pipeline, "_luot_dung", threading.BoundedSemaphore(2))
    return dem


# ===================================================================== 1. Hàng đợi dựng PDF
def test_toi_da_2_luot_dung_cung_luc(dung_gia):
    vi_tri, loi = [], []

    def nguoi():
        try:
            pipeline.dung_pdf(copy.deepcopy(GIA), "", "", None, khi_cho=vi_tri.append)
        except Exception as e:      # pragma: no cover
            loi.append(e)
    luong = [threading.Thread(target=nguoi) for _ in range(6)]
    for t in luong:
        t.start()
    for t in luong:
        t.join()
    assert not loi
    assert dung_gia["max"] == 2                         # 6 người nhưng chỉ 2 lượt chạy cùng lúc
    assert len(vi_tri) >= 4 and min(vi_tri) >= 1        # người phải chờ được báo vị trí trong hàng
    assert pipeline.so_nguoi_dang_cho() == 0


def test_cho_qua_lau_bao_loi_ro_rang(dung_gia, monkeypatch):
    monkeypatch.setattr(pipeline, "_luot_dung", threading.BoundedSemaphore(1))
    monkeypatch.setattr(pipeline, "render_queue_timeout", lambda: 0.2)
    pipeline._luot_dung.acquire()                       # có người khác đang dựng mãi không xong
    try:
        with pytest.raises(pipeline.HangChoQuaLau, match="Cập nhật PDF lại sau ít phút"):
            pipeline.dung_pdf(copy.deepcopy(GIA), "", "", None)
    finally:
        pipeline._luot_dung.release()
    assert pipeline.so_nguoi_dang_cho() == 0


def test_dung_loi_van_tra_luot(dung_gia, monkeypatch):
    from services.pdf import render
    monkeypatch.setattr(render, "build_pdf", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("Chromium hỏng")))
    for _ in range(3):                                  # nếu lỗi mà không trả lượt, lần thứ 3 sẽ kẹt
        with pytest.raises(RuntimeError):
            pipeline.dung_pdf(copy.deepcopy(GIA), "", "", None)
    assert pipeline._luot_dung.acquire(blocking=False)
    pipeline._luot_dung.release()


def test_mac_dinh_hang_doi(monkeypatch):
    from infra import settings
    monkeypatch.delenv("RENDER_MAX_CONCURRENT", raising=False)
    monkeypatch.delenv("RENDER_QUEUE_TIMEOUT", raising=False)
    assert settings.render_max_concurrent() == 2 and settings.render_queue_timeout() == 300


def test_giao_dien_bao_dang_xep_hang():
    from ui import components as ui
    html = ui.stage(True, 2, so_cho=3)
    assert "Đang xếp hàng dựng PDF" in html and "<b>3</b>" in html
    assert "Đang xếp hàng" not in ui.stage(True, 2)


# ===================================================================== 1b. Dựng 3 cỡ chữ trong 1 tiến trình
def _chon_cu(bo_cuc):
    """Đúng vòng lặp chọn cỡ chữ của build_pdf TRƯỚC khi sửa — để so sánh."""
    from services.pdf.render import TRANG_CUOI_GAN_TRONG
    lan_dau = None
    for i, (so_trang, do_day) in enumerate(bo_cuc):
        if lan_dau is None:
            lan_dau = (i, so_trang)
            if do_day >= TRANG_CUOI_GAN_TRONG or so_trang == 1:
                break
        elif so_trang < lan_dau[1]:
            lan_dau = (i, so_trang)
            break
    return lan_dau[0]


def test_chon_co_chu_giong_het_luat_cu():
    from services.pdf.render import chon_co_chu
    rnd = random.Random(7)
    for _ in range(2000):
        bo_cuc = [(rnd.randint(1, 4), rnd.random()) for _ in range(3)]
        assert chon_co_chu(bo_cuc) == _chon_cu(bo_cuc), bo_cuc


def test_build_pdf_chi_mo_chromium_1_lan(monkeypatch, tmp_path):
    import pymupdf as fitz
    from services.pdf import render
    goi = []

    def run_gia(args, **kw):
        goi.append(args)
        viec = json.loads(Path(args[-2]).read_text(encoding="utf-8"))
        for i, (_, pdf) in enumerate(viec):                 # cỡ 11.5: 3 trang, 11.0: 2 trang, 10.8: 2 trang
            doc = fitz.open()
            for _ in range(3 if i == 0 else 2):
                doc.new_page()
            doc.save(pdf); doc.close()
        return subprocess.CompletedProcess(args, 0, "", "")
    monkeypatch.setattr(render.subprocess, "run", run_gia)
    p = render.build_pdf(copy.deepcopy(GIA), "", "Kế toán", None, tmp_path)
    assert len(goi) == 1                                    # 1 tiến trình cho cả 3 cỡ chữ
    with fitz.open(p) as d:
        assert d.page_count == 2                            # chọn bản bớt được 1 trang (cỡ 11.0)


def test_worker_doc_ca_2_cach_goi(tmp_path):
    from services.pdf.render_worker import _doc_viec
    f = tmp_path / "viec.json"
    f.write_text(json.dumps([["a.html", "a.pdf"], ["b.html", "b.pdf"]]), encoding="utf-8")
    assert _doc_viec(["w", str(f), "ab12cd34"]) == ([("a.html", "a.pdf"), ("b.html", "b.pdf")], "ab12cd34")
    assert _doc_viec(["w", "x.html", "x.pdf"]) == ([("x.html", "x.pdf")], None)


# ===================================================================== 2. Log an toàn đa luồng
def test_cau_hinh_log_dong_thoi_chi_1_handler(tmp_path, monkeypatch):
    from infra import logging_setup as ls
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    rao = threading.Barrier(20)

    def goi():
        rao.wait()                                          # 20 phiên mở cùng một lúc
        ls.cau_hinh_logging("dong_thoi.log")
    luong = [threading.Thread(target=goi) for _ in range(20)]
    for t in luong:
        t.start()
    for t in luong:
        t.join()
    duong_dan = str((tmp_path / "dong_thoi.log").resolve())
    handlers = [h for h in logging.getLogger().handlers if getattr(h, "baseFilename", "") == duong_dan]
    try:
        assert len(handlers) == 1
    finally:
        for h in handlers:
            logging.getLogger().removeHandler(h); h.close()


# ===================================================================== 3. run_id khi lưu bản xuất
def test_luu_ban_sao_ghi_dung_run_id(tmp_path, monkeypatch):
    from infra import logging_setup as ls
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    f = ls.cau_hinh_logging("luu.log")
    h = next(x for x in logging.getLogger().handlers if getattr(x, "baseFilename", "") == str(f.resolve()))
    try:
        ls.dat_run_id(None)                                 # như lúc callback nút Tải chạy: chưa có run_id
        pipeline.luu_ban_sao(tmp_path / "out", "LH - CV.pdf", b"%PDF", run_id="abcd1234")
        h.flush()
        assert "[abcd1234] app: Đã lưu bản xuất" in f.read_text(encoding="utf-8")
    finally:
        ls.dat_run_id(None)
        logging.getLogger().removeHandler(h); h.close()
