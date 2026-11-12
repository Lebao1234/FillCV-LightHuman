# Gói services/extraction/rules/: bộ đọc CV dạng PDF theo luật (không AI, không mạng) — mỗi giai đoạn một module.
"""Bảng từ khoá (config/extraction_rules.toml) + hàm chuẩn hoá chữ để so khớp.

So khớp luôn trên chữ đã bỏ dấu, hạ chữ, gọn khoảng trắng -> "KINH NGHIỆM LÀM VIỆC:" == "kinh nghiem lam viec".
"""
import hashlib
import re
import tomllib
import unicodedata
from functools import lru_cache

from infra.settings import PROJECT_ROOT

RULES_FILE = PROJECT_ROOT / "config" / "extraction_rules.toml"


# Bỏ dấu tiếng Việt, hạ chữ, gộp khoảng trắng, bỏ dấu câu ở hai đầu
def norm(text: str) -> str:
    """'  KINH NGHIỆM LÀM VIỆC: ' -> 'kinh nghiem lam viec'."""
    s = (text or "").replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return s.strip(" :;,.-–—|•*#/\\()[]")


# Đọc bảng từ khoá (cache; đổi file thì phải khởi động lại app)
@lru_cache(maxsize=1)
def rules() -> dict:
    """Nội dung config/extraction_rules.toml, đã dựng sẵn các bảng tra theo chữ chuẩn hoá."""
    data = tomllib.loads(RULES_FILE.read_text(encoding="utf-8"))
    heading_index = {}
    for key, h in data["headings"].items():
        for lang in ("vi", "en"):
            for w in h.get(lang, []):
                heading_index[norm(w)] = (key, h["type"], lang)
    data["_heading_index"] = heading_index
    data["_removed_index"] = {norm(w): kind for kind, ws in data["removed_kind"].items() for w in ws}
    return data


# Mã băm của bảng từ khoá -> ghép vào phiên bản bộ đọc (đổi luật là đổi phiên bản)
@lru_cache(maxsize=1)
def rules_hash() -> str:
    """8 ký tự đầu sha256 của file luật."""
    return hashlib.sha256(RULES_FILE.read_bytes()).hexdigest()[:8]


# Tra một tiêu đề mục: (khoá, loại, ngôn ngữ) hoặc None
def match_heading(text: str) -> tuple[str, str, str] | None:
    """Khớp nguyên dòng (sau chuẩn hoá); bỏ số thứ tự đầu dòng ('1.', 'II.', 'A)')."""
    key = norm(re.sub(r"^\s*(?:[0-9]{1,2}|[ivxIVX]{1,4}|[a-zA-Z])[.)]\s+", "", text or ""))
    index = rules()["_heading_index"]
    return index.get(key) or index.get(key.replace("&", "va").replace("  ", " ")) \
        or index.get(key.replace("&", "and").replace("  ", " "))


# Chữ chuẩn hoá có nằm trong danh sách từ khoá không (khớp nguyên cụm)
def in_list(text: str, words: list[str]) -> bool:
    """norm(text) trùng hẳn một từ khoá trong `words`."""
    t = norm(text)
    return any(t == norm(w) for w in words)


# Tách chữ chuẩn hoá thành các từ (chữ/số)
def tokens(text: str) -> list[str]:
    """'Sr. Accountant (ABC)' -> ['sr', 'accountant', 'abc']."""
    return re.findall(r"[a-z0-9]+", norm(text))


# Chữ có CHỨA một từ khoá nào không (khớp theo nguyên từ, không khớp giữa từ)
def contains_any(text: str, words: list[str]) -> bool:
    """'Công ty CP ABC' chứa 'cong ty'; 'Có kinh nghiệm' KHÔNG chứa 'co phan'."""
    t = tokens(text)
    for w in words:
        k = tokens(w)
        if k and any(t[i:i + len(k)] == k for i in range(len(t) - len(k) + 1)):
            return True
    return False
