# Smoke test E2E cho quy trình API và dựng PDF bằng Playwright
"""Kiểm thử khói (smoke test) toàn diện từ nạp hồ sơ giả, thẩm định cấu trúc,
dựng PDF thật bằng Chromium Playwright, sinh ảnh xem trước và kiểm tra trạng thái tải.

Chỉ sử dụng fixture tests/fixtures/fake_candidate.json.
Được đánh dấu @pytest.mark.slow do khởi chạy Chromium Playwright.
"""
import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from api.server import app

FIXTURE = Path(__file__).parent / "fixtures" / "fake_candidate.json"


# Đọc hồ sơ giả lập từ file fixture
def get_fake_cv() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# Smoke test E2E: kiểm tra toàn bộ luồng từ thẩm định, dựng PDF bằng Chromium thật, sinh preview và tải về
@pytest.mark.slow
def test_full_pipeline_smoke_e2e():
    fake_cv = get_fake_cv()

    with TestClient(app) as client:
        # 1. Thẩm định cấu trúc hồ sơ
        val_res = client.post(
            "/api/cv/validate",
            json={"cv": fake_cv, "project": "Dự án Khói", "position": "Kế toán trưởng"},
        )
        assert val_res.status_code == 200
        val_data = val_res.json()
        assert val_data["valid"] is True
        assert val_data["structure_errors"] == []
        assert "normalized_cv" in val_data

        # 2. Dựng PDF bằng Playwright Chromium thật
        build_res = client.post(
            "/api/pdf/build",
            json={
                "run_id": "smoke_e2e_run",
                "cv": val_data["normalized_cv"],
                "project": "Dự án Khói",
                "position": "Kế toán trưởng",
                "lang": "vi",
            },
        )
        assert build_res.status_code == 200
        build_data = build_res.json()
        run_id = build_data["run_id"]
        assert run_id == "smoke_e2e_run"
        assert build_data["page_count"] >= 1
        assert build_data["filename"].startswith("LH - CV Ke toan truong -")
        assert build_data["filename"].endswith(".pdf")

        # Kiểm tra checklist chất lượng và PII
        checklist = build_data["checklist"]
        assert all(item["ok"] for item in checklist), f"Checklist thất bại: {checklist}"

        # 3. Xem trước trang 1
        prev_res = client.get(f"/api/preview/pdf/{run_id}/1")
        assert prev_res.status_code == 200
        assert prev_res.headers["content-type"] == "image/png"
        assert len(prev_res.content) > 1000

        # 4. Kiểm tra trạng thái PDF
        status_res = client.post(
            "/api/pdf/status",
            json={
                "has_pdf": True,
                "pdf_fingerprint": build_data["fingerprint"],
                "current_fingerprint": build_data["fingerprint"],
                "checklist": checklist,
                "has_violations": False,
                "has_structure_errors": False,
                "checked_generated": True,
                "reviewed": True,
            },
        )
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["can_download"] is True
        assert status_data["pill_kind"] == "ok"

        # 5. Tải file PDF về
        dl_res = client.get(f"/api/pdf/download/{run_id}?save_copy=false")
        assert dl_res.status_code == 200
        assert dl_res.headers["content-type"] == "application/pdf"
        assert len(dl_res.content) > 10000

