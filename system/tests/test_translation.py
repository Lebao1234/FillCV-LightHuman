# Test dịch máy offline vi -> en: chọn đoạn nào được dịch, kiểm tra bản dịch, endpoint /api/cv/translate
"""Dùng bộ dịch giả (không cần tải mô hình): kiểm logic chọn đoạn, bảng thuật ngữ, kiểm tra số liệu, ghi chú và endpoint."""
import copy

import pytest
from starlette.testclient import TestClient

from api.server import app
from services.translation import nmt


# Bộ dịch giả: bản dịch tra theo bảng, câu lạ thì thêm tiền tố "EN: "
class FakeEngine:
    name = "fake-engine"

    def __init__(self, table: dict[str, str] | None = None):
        self.table = table or {}
        self.calls: list[list[str]] = []

    def translate(self, texts: list[str]) -> list[str]:
        self.calls.append(list(texts))
        return [self.table.get(t, f"EN: {t}") for t in texts]


# Gắn bộ dịch giả cho mỗi test và gỡ sau khi xong
@pytest.fixture
def engine():
    eng = FakeEngine()
    nmt.set_engine(eng)
    yield eng
    nmt.set_engine(None)


# Hồ sơ mẫu có đủ loại đoạn chữ
def sample_cv() -> dict:
    return {
        "language": "vi", "full_name": "Nguyễn Văn A", "target_title": "Giám đốc kinh doanh", "birth_year": 1990,
        "gender": "Nam", "facts": [], "expected_salary": None,
        "stats": [{"value": "10+", "label": "năm kinh nghiệm", "source": "original"}],
        "sections": [{
            "type": "experience", "title": "Kinh nghiệm", "paragraphs": [], "bullets": [], "cards": [], "tags": ["Excel"],
            "career_path": [], "education": [], "references": [],
            "jobs": [{
                "company": "Công ty Hoa Sen", "period": "03/2018 – Nay", "role": "Trưởng phòng kinh doanh",
                "meta": [{"label": "Lĩnh vực", "text": "Bán lẻ"}],
                "groups": [{"title": None, "bullets": [
                    "Quản lý đội ngũ **12** nhân viên", "Tăng doanh thu 25% mỗi năm", "Managed the sales team"]}],
                "sub_roles": [],
            }],
        }, {
            "type": "education", "title": "Học vấn", "paragraphs": [], "bullets": [], "cards": [], "tags": [],
            "career_path": [], "jobs": [], "references": [],
            "education": [{"title": "Cử nhân Kinh tế", "detail": "Đại học Kinh tế Quốc dân", "period": "2008 – 2012"}],
        }],
        "model_notes": {"removed": [], "self_created": [], "recruiting_flags": [], "other": []},
    }


# Chỉ các trường chữ tự do được đưa vào dịch; tên riêng, công ty, trường, thẻ, thời gian thì không
def test_collect_slots_excludes_proper_nouns():
    # Chỉ xét đoạn được phép đưa vào dịch máy (kind="text"); đoạn "term"/"title" chỉ tra bảng
    paths = {s.path for s in nmt.collect_slots(sample_cv()) if s.kind == "text"}
    assert "target_title" in paths
    assert "sections[0].jobs[0].role" in paths
    assert "sections[0].jobs[0].groups[0].bullets[0]" in paths
    assert "sections[1].education[0].title" in paths
    for banned in ("full_name", "tags", "company", "period", "detail"):
        assert not any(banned in p for p in paths), banned


# Dịch: đoạn tiếng Việt được dịch, đoạn tiếng Anh bỏ qua, tên riêng giữ nguyên, hồ sơ gốc không bị sửa
def test_translate_cv_translates_only_vietnamese_free_text(engine):
    cv = sample_cv()
    original = copy.deepcopy(cv)
    engine.table = {
        "Quản lý đội ngũ 12 nhân viên": "Managed a team of 12 staff",
        "Tăng doanh thu 25% mỗi năm": "Increased revenue by 25% every year",
        "Trưởng phòng kinh doanh": "Sales Manager",
    }
    res = nmt.translate_cv(cv)
    assert cv == original  # không sửa đầu vào
    job = res.cv["sections"][0]["jobs"][0]
    assert job["role"] == "Sales Manager"
    assert job["groups"][0]["bullets"] == ["Managed a team of 12 staff", "Increased revenue by 25% every year", "Managed the sales team"]
    assert job["company"] == "Công ty Hoa Sen" and job["period"] == "03/2018 – Present"
    assert res.cv["full_name"] == "Nguyễn Văn A" and res.cv["sections"][0]["tags"] == ["Excel"]
    assert res.cv["sections"][1]["education"][0]["detail"] == "Đại học Kinh tế Quốc dân"
    assert res.engine == "fake-engine"
    # Đoạn đã là tiếng Anh không gửi cho mô hình
    sent = [t for call in engine.calls for t in call]
    assert "Managed the sales team" not in sent
    # Báo cáo không chứa nội dung CV
    assert all(set(i) == {"path", "status", "reason"} for i in res.items)
    assert "Công ty Hoa Sen" not in str(res.items)


# Bảng thuật ngữ được áp trước, đoạn đó không gửi cho dịch máy
def test_glossary_term_skips_engine(engine):
    cv = sample_cv()
    cv["sections"][0]["jobs"][0]["meta"][0]["text"] = "Nữ"
    res = nmt.translate_cv(cv)
    assert res.cv["sections"][0]["jobs"][0]["meta"][0]["text"] == "Female"
    assert "Nữ" not in [t for call in engine.calls for t in call]
    assert res.count("glossary") >= 1


# Bản dịch làm đổi số liệu thì giữ tiếng Việt và báo lại
def test_translation_changing_numbers_is_rejected(engine):
    engine.table = {"Tăng doanh thu 25% mỗi năm": "Increased revenue by 52% every year"}
    res = nmt.translate_cv(sample_cv())
    bullets = res.cv["sections"][0]["jobs"][0]["groups"][0]["bullets"]
    assert bullets[1] == "Tăng doanh thu 25% mỗi năm"
    kept = [i for i in res.items if i["status"] == "kept"]
    assert any("số liệu" in i["reason"] for i in kept)
    # Ghi chú để nhân viên biết còn đoạn phải tự dịch
    assert any("giữ nguyên tiếng Việt" in n for n in res.cv["model_notes"]["other"])


# check_translation: các trường hợp không đạt
def test_check_translation_rules():
    assert nmt.check_translation("Tăng 1.000 đơn", "Increased 1,000 orders") == (True, "")
    assert nmt.check_translation("Tăng 10 đơn", "Increased orders")[0] is False      # mất số
    assert nmt.check_translation("Tăng đơn", "")[0] is False                           # rỗng
    assert nmt.check_translation("Tăng đơn", "Tăng đơn")[0] is False                  # chép nguyên bản gốc
    assert nmt.check_translation("Tăng đơn", "x" * 200)[0] is False                    # dài bất thường
    ok, reason = nmt.check_translation("Doanh thu 800 tỷ đồng mỗi năm", "Revenue of $800 billion a year")
    assert ok is False and "tiền tệ" in reason                                         # đồng bị đổi thành đô la
    assert nmt.check_translation("Doanh thu 800 tỷ đồng", "Revenue of VND 800 billion")[0] is True


# Có đoạn được dịch thì ghi vào model_notes.self_created (bắt buộc nhân viên tick "đã kiểm tra")
def test_notes_mark_machine_translation(engine):
    res = nmt.translate_cv(sample_cv())
    notes = res.cv["model_notes"]["self_created"]
    assert any("Dịch máy" in n and "đọc lại" in n for n in notes)
    # Dịch lần hai trên kết quả không nhân đôi ghi chú
    res2 = nmt.translate_cv(res.cv)
    assert sum("Dịch máy" in n for n in res2.cv["model_notes"]["self_created"]) == 1


# Đoạn dài được tách theo câu rồi ghép lại, bộ nhớ tạm không gọi lại mô hình cho đoạn đã dịch
def test_long_segment_split_and_cache(engine):
    long_text = " ".join(f"Phụ trách mảng số {i} của phòng." for i in range(30))
    assert len(long_text) > nmt.MAX_SEGMENT_CHARS
    cv = sample_cv()
    cv["sections"][0]["jobs"][0]["groups"][0]["bullets"] = [long_text, long_text]
    nmt.translate_cv(cv)
    assert all(len(t) <= nmt.MAX_SEGMENT_CHARS + 60 for call in engine.calls for t in call)
    n_calls = len(engine.calls)
    nmt.translate_cv(cv)
    assert len(engine.calls) == n_calls  # lần hai: toàn bộ từ bộ nhớ tạm


# Không có bộ dịch và không có mô hình -> ném lỗi rõ ràng (tiếng Việt)
def test_unavailable_without_model(monkeypatch, tmp_path):
    nmt.set_engine(None)
    monkeypatch.setenv("TRANSLATE_MODEL_DIR", str(tmp_path / "khong-co"))
    assert nmt.is_available() is False
    with pytest.raises(nmt.TranslatorUnavailable, match="dịch máy"):
        nmt.translate_cv(sample_cv())


# CV_TRANSLATOR=none tắt hẳn tính năng dù đã có bộ dịch
def test_translator_none_disables(engine, monkeypatch):
    monkeypatch.setenv("CV_TRANSLATOR", "none")
    assert nmt.is_available() is False


# Endpoint: trả hồ sơ đã dịch + tóm tắt, và /api/config báo khả dụng
def test_translate_endpoint_and_config(engine):
    with TestClient(app) as client:
        cfg = client.get("/api/config").json()
        assert cfg["translation"]["available"] is True and cfg["translation"]["target"] == "en"

        res = client.post("/api/cv/translate", json={"cv": sample_cv()})
        assert res.status_code == 200
        data = res.json()
        assert {"cv", "engine", "summary", "items"} <= data.keys()
        assert data["summary"]["translated"] >= 1
        assert data["cv"]["sections"][0]["jobs"][0]["role"] == "Sales Manager"            # bảng thuật ngữ
        assert data["cv"]["sections"][0]["jobs"][0]["groups"][0]["bullets"][1].startswith("EN: ")   # dịch máy


# Endpoint: sai cấu trúc -> 400, chưa bật -> 503, thiếu cv -> 400
def test_translate_endpoint_errors(monkeypatch, tmp_path):
    nmt.set_engine(None)
    monkeypatch.setenv("TRANSLATE_MODEL_DIR", str(tmp_path / "khong-co"))
    with TestClient(app) as client:
        assert client.get("/api/config").json()["translation"]["available"] is False
        assert client.post("/api/cv/translate", json={"cv": sample_cv()}).status_code == 503
        assert client.post("/api/cv/translate", json={}).status_code == 400
    eng = FakeEngine()
    nmt.set_engine(eng)
    try:
        with TestClient(app) as client:
            bad = sample_cv()
            bad["full_name"] = "  "
            res = client.post("/api/cv/translate", json={"cv": bad})
            assert res.status_code == 400 and "chưa hợp lệ" in res.json()["error"]
            assert eng.calls == []
    finally:
        nmt.set_engine(None)


# Chức danh trong bảng thuật ngữ cố định được tra trước, không gửi cho dịch máy; IN HOA giữ kiểu IN HOA
def test_job_title_glossary_before_engine(engine):
    cv = sample_cv()
    cv["target_title"] = "Kế toán trưởng"
    cv["sections"][0]["jobs"][0]["role"] = "TRƯỞNG PHÒNG KINH DOANH"
    cv["sections"][0]["jobs"][0]["meta"][0]["label"] = "Lĩnh vực:"
    res = nmt.translate_cv(cv)
    assert res.cv["target_title"] == "Chief Accountant"
    assert res.cv["sections"][0]["jobs"][0]["role"] == "SALES MANAGER"
    assert res.cv["sections"][0]["jobs"][0]["meta"][0]["label"] == "Industry"
    sent = [t for call in engine.calls for t in call]
    assert not {"Kế toán trưởng", "TRƯỞNG PHÒNG KINH DOANH", "Lĩnh vực:"} & set(sent)


# Bảng thuật ngữ hợp lệ: khoá không trùng sau khi chuẩn hoá, giá trị không rỗng
def test_glossary_file_is_valid():
    import tomllib
    raw = tomllib.loads(nmt.GLOSSARY_FILE.read_text(encoding="utf-8"))["phrases"]
    assert len(nmt._glossary()) == len(raw)          # không có hai khoá trùng nhau sau khi chuẩn hoá
    assert all(v.strip() for v in raw.values())


# Nhận diện loại mô hình theo file trong thư mục: Opus-MT (marian), VinAI (mbart), thiếu file thì None
def test_model_kind_detection(tmp_path):
    assert nmt.model_kind(tmp_path) is None
    (tmp_path / "model.bin").write_bytes(b"x")
    assert nmt.model_kind(tmp_path) is None            # có model nhưng thiếu file tách từ
    (tmp_path / "sentencepiece.bpe.model").write_bytes(b"x")
    assert nmt.model_kind(tmp_path) == "mbart"
    (tmp_path / "source.spm").write_bytes(b"x")
    assert nmt.model_kind(tmp_path) == "mbart"         # marian cần đủ cả source.spm và target.spm
    (tmp_path / "target.spm").write_bytes(b"x")
    assert nmt.model_kind(tmp_path) == "marian"


# Nạp mô hình lỗi (thư viện bị chặn, mô hình hỏng) -> báo TranslatorUnavailable rõ ràng và không giữ bộ dịch hỏng
def test_engine_load_failure_is_reported(monkeypatch, tmp_path):
    (tmp_path / "model.bin").write_bytes(b"x")
    (tmp_path / "source.spm").write_bytes(b"x")
    (tmp_path / "target.spm").write_bytes(b"x")
    monkeypatch.setenv("TRANSLATE_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(nmt.importlib.util, "find_spec", lambda name: object())   # coi như đã cài thư viện

    class Boom:
        def __init__(self, *args, **kwargs):
            raise OSError("An Application Control policy has blocked this file")

    monkeypatch.setattr(nmt, "Ct2Engine", Boom)
    nmt.set_engine(None)
    assert nmt.is_available() is True
    with pytest.raises(nmt.TranslatorUnavailable, match="Không nạp được mô hình"):
        nmt.translate_cv(sample_cv())
    assert nmt._engine is None


# Thẻ kỹ năng, họ tên, giới tính, giá trị ô số liệu và dòng "Mong muốn" chỉ tra bảng thuật ngữ, KHÔNG gửi cho dịch máy
def test_term_only_fields_use_glossary_not_engine(engine):
    cv = sample_cv()
    cv["gender"] = "Nữ"
    cv["facts"] = [{"label": "Mong muốn", "value": "Trưởng phòng kế toán · Toàn thời gian · Đà Nẵng"}]
    cv["stats"] = [{"value": "Thạc sĩ", "label": "Quản lý đội 9 người", "source": "original"},
                   {"value": "14 năm", "label": "Kinh nghiệm", "source": "original"}]
    cv["sections"][0]["tags"] = ["Excel nâng cao", "ERP sản xuất"]
    cv["sections"][0]["title"] = "Kinh nghiệm làm việc"
    res = nmt.translate_cv(cv).cv
    assert res["gender"] == "Female"
    assert res["facts"][0]["label"] == "Desired"
    assert res["facts"][0]["value"] == "Accounting Manager · Full-time · Da Nang"
    assert res["stats"][0]["value"] == "Master's degree"
    assert res["stats"][1]["value"] == "14 years"
    assert res["sections"][0]["tags"] == ["Advanced Excel", "ERP sản xuất"]     # thẻ lạ giữ nguyên, không dịch máy
    assert res["sections"][0]["title"].upper() == "WORK EXPERIENCE"
    sent = {t for call in engine.calls for t in call}
    assert "Quản lý đội 9 người" in sent                                          # nhãn ô số liệu được dịch máy
    assert not ({"Excel nâng cao", "ERP sản xuất", "Nữ", "Thạc sĩ", "Đà Nẵng"} & sent)


# Nạp sẵn mô hình: không có mô hình thì trả False, không ném lỗi; có thì nạp bộ dịch
def test_preload(monkeypatch, tmp_path, engine):
    assert nmt.preload() is True                  # fixture engine đã gắn
    monkeypatch.setenv("TRANSLATE_MODEL_DIR", str(tmp_path))
    nmt.set_engine(None)
    assert nmt.preload() is False                 # thư mục không có mô hình


# Chữ "Nay" ở khoảng thời gian đổi thành "Present"; ngày tháng giữ nguyên, thời gian không gửi cho dịch máy
def test_period_now_becomes_present(engine):
    cv = sample_cv()
    cv["sections"][0]["jobs"][0]["period"] = "03/2018 – Nay"
    cv["sections"][1]["education"][0]["period"] = "2008 – 2012"
    res = nmt.translate_cv(cv).cv
    assert res["sections"][0]["jobs"][0]["period"] == "03/2018 – Present"
    assert res["sections"][1]["education"][0]["period"] == "2008 – 2012"
    sent = {t for call in engine.calls for t in call}
    assert "03/2018 – Nay" not in sent
