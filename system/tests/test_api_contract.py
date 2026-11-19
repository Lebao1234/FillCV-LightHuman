# Test hợp đồng API và các endpoint backend theo docs/api.md
"""Kiểm thử tính đúng đắn của các endpoint Starlette API và kiểm tra response
khớp các khoá quy định trong hợp đồng docs/api.md.

Sử dụng monkeypatch cho base.get_extractor, render.build_pdf, checks.scan_pdf, render.extract_photo
theo đúng quy tắc CLAUDE.md.
"""
import io
import json
from pathlib import Path

from starlette.testclient import TestClient

from api.server import app
from api.state import run_store, RunData
from services.extraction import base as extraction


# Đọc hồ sơ giả để làm fixture
def load_fake_cv() -> dict:
    p = Path(__file__).parent / "fixtures" / "fake_candidate.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# Test endpoint /health
def test_health_endpoint():
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data == {"status": "ok"}


# Test endpoint /api/config khớp hợp đồng docs/api.md
def test_config_contract():
    with TestClient(app) as client:
        res = client.get("/api/config")
        assert res.status_code == 200
        data = res.json()
        required_keys = {
            "max_upload_mb",
            "allowed_extensions",
            "image_extensions",
            "pdf_languages",
            "logo_header_b64",
            "default_stage_labels",
        }
        assert required_keys.issubset(data.keys())
        assert isinstance(data["max_upload_mb"], int)
        assert isinstance(data["allowed_extensions"], list)
        assert ".pdf" in data["allowed_extensions"]
        assert isinstance(data["pdf_languages"], dict)
        assert "vi" in data["pdf_languages"]


# Test endpoint /api/cv/validate với hồ sơ hợp lệ và không hợp lệ
def test_validate_cv_contract():
    fake_cv = load_fake_cv()
    with TestClient(app) as client:
        # 1. Hồ sơ hợp lệ
        res = client.post("/api/cv/validate", json={"cv": fake_cv, "project": "TestPrj", "position": "Pos"})
        assert res.status_code == 200
        data = res.json()
        assert {"valid", "structure_errors", "violations", "normalized_cv"}.issubset(data.keys())
        assert data["valid"] is True
        assert data["structure_errors"] == []

        # 2. Hồ sơ thiếu trường bắt buộc
        invalid_cv = dict(fake_cv)
        invalid_cv.pop("full_name")
        res2 = client.post("/api/cv/validate", json={"cv": invalid_cv})
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["valid"] is False
        assert len(data2["structure_errors"]) > 0


# Test endpoint /api/pdf/status khớp hợp đồng docs/api.md
def test_pdf_status_contract():
    with TestClient(app) as client:
        payload = {
            "has_pdf": True,
            "pdf_fingerprint": "fp1",
            "current_fingerprint": "fp1",
            "checklist": [{"code": "pii", "ok": True, "item": "PII", "detail": "Sạch"}],
            "has_violations": False,
            "has_structure_errors": False,
            "checked_generated": True,
            "reviewed": True,
        }
        res = client.post("/api/pdf/status", json=payload)
        assert res.status_code == 200
        data = res.json()
        required_keys = {"outdated", "pdf_dirty", "can_download", "pill_kind", "pill_text"}
        assert required_keys.issubset(data.keys())
        assert data["can_download"] is True
        assert data["pill_kind"] == "ok"


# Test endpoint /api/cv/extract luồng SSE và các sự kiện trả về
def test_extract_cv_sse(monkeypatch):
    fake_cv = load_fake_cv()

    # Tạo extractor giả
    class DummyExtractor:
        stages = [extraction.Stage("s1", "Bước 1")]
        def extract(self, doc, report=None):
            if report:
                report("s1")
            return extraction.ExtractionResult(
                cv=fake_cv,
                warnings=[extraction.ReviewNote("sections[0]", "Lưu ý")],
                confidence={"full_name": 0.9},
                stages=[extraction.StageRun(key="s1", label="Bước 1", seconds=0.1, status="ok", detail="Xong")],
                backend="dummy",
            )

    from services.extraction import base
    from services.pdf import render
    monkeypatch.setattr(base, "get_extractor", lambda: DummyExtractor())
    monkeypatch.setattr(render, "extract_photo", lambda data, name: b"fake_photo_png")

    with TestClient(app) as client:
        file_content = b"%PDF-1.4 dummy pdf bytes"
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"project": "Dự án A", "position": "Kế toán"}
        res = client.post("/api/cv/extract", files=files, data=data)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        # Đọc các sự kiện SSE từ body
        lines = res.text.strip().split("\n\n")
        events = []
        for block in lines:
            if not block.strip():
                continue
            ev_type, ev_data = None, None
            for line in block.split("\n"):
                if line.startswith("event: "):
                    ev_type = line[7:]
                elif line.startswith("data: "):
                    ev_data = json.loads(line[6:])
            if ev_type and ev_data:
                events.append((ev_type, ev_data))

        event_names = [e[0] for e in events]
        assert "progress" in event_names
        assert "done" in event_names

        done_event = next(e[1] for e in events if e[0] == "done")
        required_keys = {"run_id", "cv", "has_photo", "warnings", "confidence", "original_filename"}
        assert required_keys.issubset(done_event.keys())
        assert done_event["has_photo"] is True
        assert done_event["cv"]["full_name"] == fake_cv["full_name"]


# Test endpoint /api/pdf/build với monkeypatch
def test_build_pdf_contract(monkeypatch, tmp_path):
    fake_cv = load_fake_cv()

    # Giả lập render.build_pdf trả về file PDF tạm hợp lệ
    dummy_pdf = tmp_path / "dummy.pdf"
    import pymupdf as fitz
    doc = fitz.open()
    doc.new_page()
    doc.save(str(dummy_pdf))
    doc.close()

    from services.pdf import render
    from services.privacy import checks
    monkeypatch.setattr(render, "build_pdf", lambda cv, prj, pos, photo, folder, lang="vi": dummy_pdf)
    monkeypatch.setattr(checks, "scan_pdf", lambda p, lang="vi": [
        {"code": "pii", "item": "PII", "ok": True, "detail": "Sạch"}
    ])

    run_id = "test_build_run_123"
    run_store.set(RunData(run_id=run_id, photo=b"photo_bytes"))

    with TestClient(app) as client:
        payload = {
            "run_id": run_id,
            "cv": fake_cv,
            "project": "Dự án Test",
            "position": "Kế toán",
            "lang": "vi",
        }
        res = client.post("/api/pdf/build", json=payload)
        assert res.status_code == 200
        data = res.json()
        required_keys = {
            "run_id", "filename", "fingerprint", "lang", "page_count",
            "summary", "checklist", "status"
        }
        assert required_keys.issubset(data.keys())
        assert data["run_id"] == run_id
        assert data["lang"] == "vi"
        assert "outdated" in data["status"]


# Test endpoint tải PDF và xem trước info
def test_download_and_preview_pdf():
    run_id = "test_dl_run_456"
    import pymupdf as fitz
    # Tạo PDF hợp lệ có 1 trang
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello FillCV")
    pdf_bytes = doc.tobytes()
    doc.close()

    run = RunData(
        run_id=run_id,
        pdf_bytes=pdf_bytes,
        pdf_name="LH - CV Test - 19112026.pdf",
        pdf_cv={"full_name": "Test"},
        project="Prj",
        position="Pos",
        original_bytes=pdf_bytes,
        original_name="test.pdf",
    )
    run_store.set(run)

    with TestClient(app) as client:
        # 1. Info bản PDF đã dựng
        res_info = client.get(f"/api/preview/pdf/{run_id}/info")
        assert res_info.status_code == 200
        assert res_info.json()["page_count"] == 1

        # 2. Xem trước trang 1
        res_prev = client.get(f"/api/preview/pdf/{run_id}/1")
        assert res_prev.status_code == 200
        assert res_prev.headers["content-type"] == "image/png"

        # 3. Info file gốc
        res_orig_info = client.get(f"/api/preview/original/{run_id}/info")
        assert res_orig_info.status_code == 200
        assert res_orig_info.json()["file_type"] == "pdf"

        # 4. Tải file PDF
        res_dl = client.get(f"/api/pdf/download/{run_id}?save_copy=false")
        assert res_dl.status_code == 200
        assert res_dl.headers["content-type"] == "application/pdf"
        assert 'attachment; filename="LH - CV Test - 19112026.pdf"' in res_dl.headers["content-disposition"]


# Test endpoint ảnh chân dung: crop, preview, delete
def test_photo_endpoints(monkeypatch):
    run_id = "test_photo_run_789"
    run_store.set(RunData(run_id=run_id, photo=b"fake_initial_photo"))

    from services.pdf import render
    monkeypatch.setattr(render, "crop_portrait", lambda b: b"cropped_png_bytes")

    with TestClient(app) as client:
        # 1. Preview ảnh hiện tại
        res_p = client.get(f"/api/photo/preview/{run_id}")
        assert res_p.status_code == 200
        assert res_p.content == b"fake_initial_photo"

        # 2. Xoá ảnh
        res_del = client.delete(f"/api/photo/{run_id}")
        assert res_del.status_code == 200
        assert res_del.json() == {"ok": True}
        assert run_store.get(run_id).photo is None

        # 3. Crop ảnh mới
        files = {"file": ("avatar.png", io.BytesIO(b"raw_avatar_bytes"), "image/png")}
        res_crop = client.post("/api/photo/crop", files=files)
        assert res_crop.status_code == 200
        data = res_crop.json()
        assert "photo_b64" in data
        assert "photo_id" in data
