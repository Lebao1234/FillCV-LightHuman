"""Ngôn ngữ xuất PDF (Tiếng Việt / English) — dịch nhãn cố định trên máy chủ, không gọi dịch vụ ngoài.

- texts(lang): chữ cố định của mẫu PDF + footer/ghi chú tham chiếu của công ty.
- localize_cv(cv, lang): bản sao hồ sơ đã đổi tiêu đề mục chuẩn, nhãn dòng thông tin, ô số liệu, giới tính
  sang ngôn ngữ xuất. Chỉ đổi phần đang ở ngôn ngữ KIA -> xuất cùng ngôn ngữ với CV thì hồ sơ giữ nguyên.
Bảng chữ: config/pdf_labels.toml; chữ công ty: config/company.toml ([pdf] / [pdf_en]).
"""
import copy
import re
import tomllib
from functools import lru_cache

from infra.settings import PROJECT_ROOT, company
from services.extraction.rules import rulebook

LABELS_FILE = PROJECT_ROOT / "config" / "pdf_labels.toml"

# Ngôn ngữ xuất -> tên hiển thị trên nút chọn
PDF_LANGS = {"vi": "Tiếng Việt", "en": "English"}
_INDEX = {"vi": 0, "en": 1}                       # vị trí trong các cặp [tiếng Việt, tiếng Anh]
_COUNT_UNIT = re.compile(r"^(\d+\+?)\s+(\S+)$")   # "5 năm" / "6+ năm" / "18 months"


# Đọc bảng chữ (cache; đổi file thì phải khởi động lại app)
@lru_cache(maxsize=1)
def _labels() -> dict:
    return tomllib.loads(LABELS_FILE.read_text(encoding="utf-8"))


# Ngôn ngữ xuất mặc định theo ngôn ngữ của CV
def default_lang(cv: dict | None) -> str:
    """CV tiếng Anh -> 'en'; tiếng Việt / song ngữ / chưa có -> 'vi'."""
    return "en" if (cv or {}).get("language") == "en" else "vi"


# Chữ cố định của mẫu PDF theo ngôn ngữ
def texts(lang: str) -> dict:
    """{'doc_title', 'project', …, 'file_suffix', 'footer_intro', 'reference_note'} cho ngôn ngữ `lang`."""
    lang = lang if lang in PDF_LANGS else "vi"
    pdf = company()["pdf_en" if lang == "en" else "pdf"]
    return {**_labels()["text"][lang], "footer_intro": pdf["footer_intro"], "reference_note": pdf["reference_note"]}


# Khoá tra thuật ngữ: GIỮ dấu (bỏ dấu thì "Nam" trùng "năm"), bỏ hoa/thường, khoảng trắng thừa, dấu ":" cuối
def _term_key(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().rstrip(":").strip().lower()


# Bảng tra thuật ngữ: chữ ở ngôn ngữ kia -> chữ ở ngôn ngữ xuất
@lru_cache(maxsize=2)
def _term_map(lang: str) -> dict[str, str]:
    to, frm = _INDEX[lang], 1 - _INDEX[lang]
    degrees = [[vi, en] for vi, _, en in rulebook.rules()["education"]["degree_levels"]]
    table: dict[str, str] = {}
    for pair in _labels()["terms"]["pairs"] + degrees:
        table.setdefault(_term_key(pair[frm]), pair[to])
    return table


# Dịch một nhãn ngắn nếu nó là thuật ngữ ở ngôn ngữ kia
def translate_term(text: str | None, lang: str) -> str | None:
    """'Nữ' -> 'Female' (lang='en'); '5 năm' -> '5 years'; chữ không có trong bảng -> giữ nguyên."""
    if not text or lang not in PDF_LANGS:
        return text
    table = _term_map(lang)
    hit = table.get(_term_key(text))
    if hit:
        return hit
    m = _COUNT_UNIT.match(text.strip())
    if m and _term_key(m.group(2)) in table:
        return f"{m.group(1)} {table[_term_key(m.group(2))]}"
    return text


# Dịch tiêu đề mục chuẩn nếu đang ở ngôn ngữ kia
def translate_title(title: str, lang: str) -> str:
    """'KINH NGHIỆM LÀM VIỆC' -> 'WORK EXPERIENCE' (lang='en'). Giữ kiểu IN HOA của tiêu đề gốc."""
    hit = rulebook.match_heading(title)
    names = _labels()["section_titles"].get(hit[0]) if hit else None
    if not names or lang not in PDF_LANGS:
        return title
    # Nếu là summary (như Giới thiệu, About me), luôn trả về tiêu đề chuẩn của ngôn ngữ đích
    if hit[0] == "summary":
        name = names[_INDEX[lang]]
        return name.upper() if title.isupper() else name
    if hit[2] == lang:
        return title
    name = names[_INDEX[lang]]
    return name.upper() if title.isupper() else name


# Bản sao hồ sơ đã đổi nhãn sang ngôn ngữ xuất
def localize_cv(cv: dict, lang: str) -> dict:
    """Đổi tiêu đề mục, nhãn dòng thông tin, ô số liệu, giới tính, `language`. Không đổi nội dung tự do."""
    out = copy.deepcopy(cv)
    if lang not in PDF_LANGS:
        return out
    out["language"] = lang
    out["gender"] = translate_term(out.get("gender"), lang)
    for f in out.get("facts", []):
        f["label"] = translate_term(f.get("label"), lang)
    for s in out.get("stats", []):
        s["label"] = translate_term(s.get("label"), lang)
        s["value"] = translate_term(s.get("value"), lang)
    for sec in out.get("sections", []):
        sec["title"] = translate_title(sec.get("title") or "", lang)
    return out
