"""Test phần đọc/kiểm tra JSON (không gọi API)."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from services.ai.extract import SCHEMA, parse_json_text, validate

MAU_TOI_THIEU = {
    "language": "vi", "full_name": "Đặng Thị Lan", "target_title": "Kế toán trưởng",
    "birth_year": 1988, "gender": "Nữ", "facts": [], "expected_salary": None,
    "stats": [], "sections": [],
    "model_notes": {"removed": [], "self_created": [], "recruiting_flags": [], "other": []},
}


def test_parse_json_thuong():
    assert parse_json_text('{"a": 1}') == {"a": 1}


def test_parse_json_co_markdown():
    assert parse_json_text('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_text('Đây là kết quả:\n```\n{"a": 2}\n```') == {"a": 2}


def test_parse_json_hong():
    with pytest.raises(json.JSONDecodeError):
        parse_json_text('{"a": ')


def test_validate_hop_le():
    assert validate(MAU_TOI_THIEU)["full_name"] == "Đặng Thị Lan"


def test_validate_truong_la_bi_chan():
    with pytest.raises(ValidationError):
        validate({**MAU_TOI_THIEU, "phone": "0909123456"})


def test_validate_qua_4_o_so_lieu():
    o = {"value": "1", "label": "x", "source": "original"}
    with pytest.raises(ValidationError):
        validate({**MAU_TOI_THIEU, "stats": [o] * 5})


def test_schema_khop_models():
    """Mọi trường trong schema.json phải có trong models.py và ngược lại."""
    from services.ai.models import CVData
    assert set(SCHEMA["required"]) == set(CVData.model_fields)
    assert set(SCHEMA["properties"]) == set(CVData.model_fields)
