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
    targets = ("en",)            # như mô hình offline: chỉ dịch sang tiếng Anh (test hai chiều tự đổi thành ("en", "vi"))

    def __init__(self, table: dict[str, str] | None = None):
        self.table = table or {}
        self.calls: list[list[str]] = []
        self.targets_seen: list[str] = []

    def translate(self, texts: list[str], target: str = "en") -> list[str]:
        self.calls.append(list(texts))
        self.targets_seen.append(target)
        prefix = "EN: " if target == "en" else "VI: "
        return [self.table.get(t, f"{prefix}{t}") for t in texts]


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
    assert job["company"] == "Hoa Sen Company" and job["period"] == "03/2018 – Present"
    assert res.cv["full_name"] == "Nguyễn Văn A" and res.cv["sections"][0]["tags"] == ["Excel"]
    assert res.cv["sections"][1]["education"][0]["detail"] == "Đại học Kinh tế Quốc dân"
    assert res.engine == "fake-engine"
    # Đoạn đã là tiếng Anh không gửi cho mô hình
    sent = [t for call in engine.calls for t in call]
    assert "Managed the sales team" not in sent
    # Báo cáo không chứa nội dung CV
    assert all(set(i) == {"path", "status", "reason"} for i in res.items)
    assert "Hoa Sen" not in str(res.items)


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
    with pytest.raises(nmt.TranslatorUnavailable, match="Chưa bật dịch"):
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


# Hồ sơ mẫu tiếng Anh (CV gốc tiếng Anh) để thử chiều dịch en -> vi
def sample_cv_en() -> dict:
    cv = sample_cv()
    cv.update(language="en", target_title="Sales Director", gender="Male",
              facts=[{"label": "Desired", "value": "Accounting Manager · Full-time · Da Nang"}],
              stats=[{"value": "Master's degree", "label": "Years of experience", "source": "original"}])
    job = cv["sections"][0]["jobs"][0]
    cv["sections"][0]["title"] = "Work Experience"
    job.update(role="Sales Manager", period="Aug 2022 – Present", meta=[{"label": "Industry", "text": "Retail"}])
    job["groups"][0]["bullets"] = ["Managed a team of 12 staff", "Tăng doanh thu 25% mỗi năm", "KPI 2024"]
    cv["sections"][1]["title"] = "Education"
    cv["sections"][1]["education"][0].update(title="Bachelor of Economics", detail="National Economics University")
    return cv


# Chiều en -> vi: đoạn tiếng Anh được dịch, đoạn đã có dấu tiếng Việt bỏ qua, tên riêng giữ nguyên, bảng thuật ngữ tra ngược
def test_translate_to_vietnamese(engine):
    engine.targets = ("en", "vi")
    engine.table = {"Managed a team of 12 staff": "Quản lý đội ngũ 12 nhân viên", "KPI 2024": "KPI 2024"}
    cv = sample_cv_en()
    res = nmt.translate_cv(cv, "vi")
    out = res.cv
    job = out["sections"][0]["jobs"][0]
    assert set(engine.targets_seen) == {"vi"}
    assert job["groups"][0]["bullets"] == ["Quản lý đội ngũ 12 nhân viên", "Tăng doanh thu 25% mỗi năm", "KPI 2024"]
    assert job["role"] == "Trưởng phòng kinh doanh"                    # bảng thuật ngữ tra ngược, viết hoa chữ đầu
    assert job["period"] == "08/2022 – Nay"                          # ngày tiếng Anh đổi sang dạng số
    assert job["meta"][0]["label"] == "Lĩnh vực"
    assert out["target_title"] == "Giám đốc kinh doanh"
    assert out["gender"] == "Nam"
    assert out["facts"][0] == {"label": "Mong muốn", "value": "Trưởng phòng kế toán · Toàn thời gian · Đà Nẵng"}
    assert out["stats"][0]["value"] == "Thạc sĩ"
    assert out["sections"][0]["title"].upper() == "KINH NGHIỆM LÀM VIỆC"
    # Tên riêng không gửi cho bộ dịch và giữ nguyên
    assert job["company"] == "Công ty Hoa Sen" and out["full_name"] == "Nguyễn Văn A"   # đã là tiếng Việt: giữ nguyên
    assert out["sections"][1]["education"][0]["detail"] == "National Economics University"
    sent = {t for call in engine.calls for t in call}
    assert "Tăng doanh thu 25% mỗi năm" not in sent                     # đã là tiếng Việt
    assert not ({"Sales Manager", "Sales Director", "Industry", "National Economics University"} & sent)
    # Đoạn bộ dịch trả y nguyên (thuật ngữ) không bị coi là lỗi
    assert res.count("kept") == 0
    assert any("tiếng Anh sang tiếng Việt" in n for n in out["model_notes"]["self_created"])


# Bộ dịch chỉ có chiều vi -> en (mô hình offline) thì từ chối dịch sang tiếng Việt, không âm thầm trả bản lẫn lộn
def test_offline_engine_rejects_vietnamese_target(engine):
    assert nmt.supported_targets() == ("en",)
    with pytest.raises(nmt.TranslatorUnavailable, match="chưa dịch được sang tiếng Việt"):
        nmt.translate_cv(sample_cv_en(), "vi")


# Endpoint: nhận target, báo chiều dịch hỗ trợ trong /api/config, từ chối target lạ / chiều không hỗ trợ
def test_translate_endpoint_target(engine):
    from starlette.testclient import TestClient
    from api.server import app
    with TestClient(app) as client:
        assert client.get("/api/config").json()["translation"]["targets"] == ["en"]
        assert client.post("/api/cv/translate", json={"cv": sample_cv(), "target": "fr"}).status_code == 400
        assert client.post("/api/cv/translate", json={"cv": sample_cv_en(), "target": "vi"}).status_code == 503
        engine.targets = ("en", "vi")
        cfg = client.get("/api/config").json()["translation"]
        assert cfg["targets"] == ["en", "vi"] and cfg["online"] is False
        res = client.post("/api/cv/translate", json={"cv": sample_cv_en(), "target": "vi"})
        assert res.status_code == 200 and res.json()["target"] == "vi"
        assert res.json()["cv"]["sections"][0]["jobs"][0]["groups"][0]["bullets"][0].startswith("VI: ")


# Mô hình NLLB-200: nhận diện đúng loại "nllb", hỗ trợ cả 2 chiều ("en", "vi") và luôn offline
def test_nllb_model_detection_and_targets(tmp_path, monkeypatch):
    nllb_dir = tmp_path / "nllb-200-vi-en"
    nllb_dir.mkdir()
    (nllb_dir / "model.bin").write_bytes(b"x")
    (nllb_dir / "sentencepiece.bpe.model").write_bytes(b"x")
    (nllb_dir / "shared_vocabulary.json").write_text('["vie_Latn", "eng_Latn"]', encoding="utf-8")

    vinai_dir = tmp_path / "vinai-vi2en"
    vinai_dir.mkdir()
    (vinai_dir / "model.bin").write_bytes(b"x")
    (vinai_dir / "sentencepiece.bpe.model").write_bytes(b"x")

    assert nmt.model_kind(nllb_dir) == "nllb"
    assert nmt.model_kind(vinai_dir) == "mbart"

    monkeypatch.setenv("TRANSLATE_MODEL_DIR", str(nllb_dir))
    monkeypatch.setattr(nmt.importlib.util, "find_spec", lambda name: object())
    nmt.set_engine(None)
    assert nmt.is_available() is True
    assert nmt.supported_targets() == ("en", "vi")
    assert nmt.is_online() is False


# Cặp Opus-MT: có thêm mô hình en-vi thì hỗ trợ cả hai chiều; PairEngine chọn đúng mô hình theo ngôn ngữ đích
def test_opus_pair_supports_both_directions(tmp_path, monkeypatch):
    def marian(name):
        d = tmp_path / name
        d.mkdir()
        for f in ("model.bin", "source.spm", "target.spm"):
            (d / f).write_bytes(b"x")
        return d

    monkeypatch.setenv("TRANSLATE_MODEL_DIR", str(marian("opus-mt-vi-en")))
    monkeypatch.setenv("TRANSLATE_MODEL_DIR_EN_VI", str(tmp_path / "khong-co"))
    monkeypatch.setattr(nmt.importlib.util, "find_spec", lambda name: object())
    nmt.set_engine(None)
    assert nmt.supported_targets() == ("en",)                      # chưa có mô hình en-vi
    monkeypatch.setenv("TRANSLATE_MODEL_DIR_EN_VI", str(marian("opus-mt-en-vi")))
    assert nmt.supported_targets() == ("en", "vi")

    vi_en, en_vi = FakeEngine(), FakeEngine()
    vi_en.targets, en_vi.targets = ("en",), ("vi",)
    pair = nmt.PairEngine(vi_en, en_vi)
    assert pair.targets == ("en", "vi")
    pair.translate(["Xin chào"], "en")
    pair.translate(["Hello"], "vi")
    assert vi_en.calls == [["Xin chào"]] and en_vi.calls == [["Hello"]]
    nmt.set_engine(pair)
    try:
        res = nmt.translate_cv(sample_cv_en(), "vi")
        assert res.cv["sections"][0]["jobs"][0]["groups"][0]["bullets"][0].startswith("VI: ")
    finally:
        nmt.set_engine(None)


# Tên công ty: chỉ đổi loại hình doanh nghiệp theo luật cố định, tên riêng giữ nguyên, không gửi cho dịch máy
@pytest.mark.parametrize("vi, en", [
    ("CÔNG TY CỔ PHẦN MISA", "MISA JOINT STOCK COMPANY"),
    ("Công ty CP Gốm Sứ Bạch Mai", "Gốm Sứ Bạch Mai Joint Stock Company"),
    ("Công ty TNHH Nhựa Thanh Khê", "Nhựa Thanh Khê Co., Ltd."),
    ("Công ty Trách nhiệm hữu hạn Một thành viên ABC", "ABC One Member Co., Ltd."),
    ("Ngân hàng TMCP Á Châu", "Á Châu Joint Stock Commercial Bank"),
    ("Tập đoàn Vingroup", "Vingroup Group"),
    ("Tổng công ty Điện lực", "Điện lực Corporation"),
    ("Concentrix Malaysia", "Concentrix Malaysia"),       # không có loại hình tiếng Việt: giữ nguyên
])
def test_translate_company_vi_to_en(vi, en):
    assert nmt.translate_company(vi, "en") == en


# Chiều Anh -> Việt: hậu tố tiếng Anh thành tiền tố tiếng Việt; tên không có hậu tố giữ nguyên
@pytest.mark.parametrize("en, vi", [
    ("MISA Joint Stock Company", "Công ty Cổ phần MISA"),
    ("Sample Trading Co., Ltd.", "Công ty TNHH Sample Trading"),
    ("Acme JSC", "Công ty Cổ phần Acme"),
    ("SAMPLE TRADING COMPANY", "CÔNG TY SAMPLE TRADING"),
    ("Gốm Sứ Bạch Mai Joint Stock Company", "Công ty Cổ phần Gốm Sứ Bạch Mai"),   # tên riêng có dấu vẫn đổi được
    ("Concentrix Malaysia", "Concentrix Malaysia"),
])
def test_translate_company_en_to_vi(en, vi):
    assert nmt.translate_company(en, "vi") == vi


# Trong translate_cv: công ty ở công việc, lộ trình, người tham chiếu được đổi; không gửi cho dịch máy
def test_company_names_in_cv(engine):
    cv = sample_cv()
    cv["sections"][0]["jobs"][0]["company"] = "CÔNG TY CỔ PHẦN MISA"
    cv["sections"][0]["career_path"] = [{"period": "2020 – Nay", "title": "Kế toán", "company": "Công ty TNHH ABC"}]
    res = nmt.translate_cv(cv, "en").cv
    assert res["sections"][0]["jobs"][0]["company"] == "MISA JOINT STOCK COMPANY"
    assert res["sections"][0]["career_path"][0]["company"] == "ABC Co., Ltd."
    sent = {t for call in engine.calls for t in call}
    assert not ({"CÔNG TY CỔ PHẦN MISA", "Công ty TNHH ABC"} & sent)


# Sang tiếng Việt: ngày tiếng Anh trong khoảng thời gian đổi sang dạng số; "Present" -> "Nay"; không qua dịch máy
def test_english_dates_to_vietnamese(engine):
    engine.targets = ("en", "vi")
    cv = sample_cv_en()
    cv["sections"][0]["jobs"][0]["period"] = "Aug 2022 – Present"
    cv["sections"][1]["education"][0]["period"] = "June 16, 2021"
    out = nmt.translate_cv(cv, "vi").cv
    assert out["sections"][0]["jobs"][0]["period"] == "08/2022 – Nay"
    assert out["sections"][1]["education"][0]["period"] == "16/06/2021"
    sent = {t for call in engine.calls for t in call}
    assert "June 16, 2021" not in sent


# Tên văn bằng tiếng Anh -> tiếng Việt bằng luật cố định (loại bằng + ngành theo bảng), không gửi cho dịch máy
@pytest.mark.parametrize("en, vi", [
    ("Bachelor of Business Administration", "Cử nhân Quản trị kinh doanh"),
    ("Bachelor of Science in Accounting", "Cử nhân Kế toán"),
    ("Master of Business Administration (MBA)", "Thạc sĩ Quản trị kinh doanh (MBA)"),
    ("Certificate in Internal Communication Systems", "Chứng chỉ Internal Communication Systems"),
    ("PhD in Economics", "Tiến sĩ Kinh tế"),
    ("Bachelor of Engineering in Mechanical Engineering", "Kỹ sư Kỹ thuật cơ khí"),
])
def test_degree_to_vi(en, vi):
    assert nmt.degree_to_vi(en) == vi


# Trong translate_cv chiều en -> vi: tên văn bằng đi qua luật, không qua dịch máy
def test_degree_title_not_sent_to_engine(engine):
    engine.targets = ("en", "vi")
    cv = sample_cv_en()
    out = nmt.translate_cv(cv, "vi").cv
    assert out["sections"][1]["education"][0]["title"] == "Cử nhân Kinh tế"
    sent = {t for call in engine.calls for t in call}
    assert "Bachelor of Economics" not in sent


# Đoạn tiếng Anh chèn tên riêng có dấu không bị coi là tiếng Việt; đoạn tiếng Việt thật vẫn bị bỏ qua khi dịch sang vi
@pytest.mark.parametrize("text, expected", [
    ("Led team at Công ty ABC", False),
    ("Managed projects for Tập đoàn Hòa Phát in Hà Nội", False),
    ("Quản lý đội ngũ bán hàng tại chi nhánh", True),
    ("Nguyễn Văn A", True),
    ("2019 – 2021", True),
])
def test_already_in_vi_uses_word_ratio(text, expected):
    assert nmt._already_in(text, "vi") is expected
