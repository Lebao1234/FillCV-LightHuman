"""Giai đoạn lọc thông tin nhạy cảm + khối nhận diện (thay cho lớp "prompt" khi còn dùng AI).

- Tên, chức danh mục tiêu: dòng chữ to nhất trang 1 và dòng ngay sau.
- Dòng "Nhãn: nội dung" thuộc nhóm nhạy cảm (SĐT, email, địa chỉ, quê quán, hôn nhân, quốc tịch, CCCD...) -> BỎ,
  ghi TÊN LOẠI vào model_notes.removed (không ghi nội dung). Ngày sinh -> chỉ giữ năm. Lương mong muốn ->
  expected_salary (nguyên văn); lương hiện tại -> bỏ. Mong muốn (vị trí/nơi làm/hình thức) -> facts.
- Mọi chuỗi còn lại: cắt SĐT/email/link/mạng xã hội/ngày sinh đầy đủ (dùng chung mẫu với services/privacy/checks.py).
- Địa chỉ viết tự do trong đoạn văn: không xoá được chắc chắn -> chỉ CẢNH BÁO để người duyệt xem.
"""
import re
from dataclasses import dataclass, field, replace

from services.extraction.rules import content, dates, rulebook
from services.extraction.rules.pdf_text import Line, Span
from services.privacy import checks

# Dòng trông như địa chỉ VN (số nhà/đường/phường/quận/thành phố) hoặc địa chỉ tiếng Anh
ADDRESS = re.compile(
    r"(?:\b(?:số|so)\s*\d+|\d+[a-z]?/\d+|\bkp\s*\d+|\bp\.\s*\d|\bq\.\s*\d|\b(?:phường|phuong|quận|quan|huyện|huyen|"
    r"xã|thị trấn|thị xã|đường|duong|ngõ|ngách|hẻm|kiệt|tổ dân phố|khu phố|ấp|thôn|tỉnh|tp\.?|thành phố|"
    r"ward|district|street|st\.|road|province|city)\b)", re.IGNORECASE)
GENDER_WORDS = {"nam": "Nam", "nu": "Nữ", "male": "Male", "female": "Female"}
_KIND_OF_CHECK = {"Số điện thoại": "phone", "Email": "email", "Đường link": "link", "Mạng xã hội": "social",
                  "Ngày sinh đầy đủ": "birth"}


# Kết quả khối nhận diện + những gì đã bỏ
@dataclass
class Identity:
    full_name: str | None = None
    name_conf: float = 0.0
    target_title: str | None = None
    title_conf: float = 0.0
    birth_year: int | None = None
    gender: str | None = None
    expected_salary: str | None = None
    facts: list[dict] = field(default_factory=list)
    removed: set[str] = field(default_factory=set)
    stats: list[dict] = field(default_factory=list)       # hàng ô số liệu có sẵn trong CV (source="original")
    intro: list[Line] = field(default_factory=list)       # đoạn văn dài ở đầu CV không có tiêu đề
    leftover: int = 0                                      # số dòng đầu CV chưa xếp được vào đâu
    used: set[int] = field(default_factory=set)            # id() các dòng đã dùng (tên, chức danh, nhãn)


# Loại nhãn: name | remove | birth | gender | salary | current_salary | wish | title | ignore | None
def label_kind(label: str) -> str | None:
    """Tra nhãn (bỏ dấu, hạ chữ) trong bảng [labels]. Nhãn song ngữ 'Giới tính/ Sex' -> thử từng phần."""
    lab = rulebook.rules()["labels"]
    kinds = ("name", "birth", "gender", "current_salary", "salary", "title", "wish", "remove", "ignore")
    for part in [label] + [p for p in re.split(r"\s*/\s*", label or "") if p.strip()]:
        for kind in kinds:
            if rulebook.in_list(part, lab[kind]):
                return kind
    return None


# Chữ viết HOA toàn bộ -> viết hoa chữ đầu ('KẾ TOÁN TRƯỞNG' -> 'Kế toán trưởng'); chữ khác giữ nguyên
def _sentence_case(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if len(letters) > 3 and all(c.isupper() for c in letters):
        return text[:1] + text[1:].lower()
    return text


# Họ tên trông hợp lệ: 2–6 từ, chỉ chữ cái
def _namelike(text: str) -> bool:
    words = text.split()
    return 2 <= len(words) <= 6 and all(re.fullmatch(r"[^\W\d_]+\.?", w) for w in words)


# Tìm họ tên (chữ to nhất trang 1) và chức danh mục tiêu (dòng ngắn ngay sau tên)
def find_name_and_title(lines: list[Line], body: float, ident: Identity) -> None:
    """Viết hoa toàn bộ -> đổi về dạng 'Nguyễn Văn A' (schema yêu cầu viết hoa đầu chữ). CV ghi họ tên bằng nhãn
    ('Họ và tên: ...') -> lấy theo nhãn, chức danh lấy từ nhãn 'Vị trí/Chức danh' ở giai đoạn lọc."""
    for l in lines:
        lab = content.label_of(l.text) if l.page == 0 else None
        value = re.sub(r"\s+", " ", lab[1]).strip() if lab else ""
        if lab and label_kind(lab[0]) == "name" and _namelike(value):
            ident.full_name = value.title() if value.isupper() else value
            ident.name_conf = 0.9
            ident.used.add(id(l))
            return
    cands = [(i, l) for i, l in enumerate(lines) if l.page == 0 and not l.bullet and _namelike(l.text.replace("\t", " "))
             and not rulebook.match_heading(l.text) and not content.label_of(l.text)]
    if not cands:
        return
    i, name = max(cands, key=lambda c: (c[1].size, c[1].bold, -c[1].y0))
    text = re.sub(r"\s+", " ", name.text.replace("\t", " ")).strip()
    ident.full_name = text.title() if name.upper else text
    ident.name_conf = 0.9 if name.size >= body * 1.3 else 0.6
    ident.used.add(id(name))
    for nxt in lines[i + 1:i + 3]:
        t = nxt.text.replace("\t", " ").strip()
        if (nxt.bullet or content.label_of(t) or rulebook.match_heading(t) or len(t.split()) > 10
                or checks.scan_text(t) or dates.find_period(t) or ADDRESS.search(t)):
            continue
        ident.target_title = t.title() if nxt.upper and len(t) > 3 else t
        ident.title_conf = 0.75
        ident.used.add(id(nxt))
        break


# Hàng ô số liệu có sẵn ở đầu CV: dòng >= 2 ô ngắn (đa số có số) + dòng ngay sau cùng số ô làm chú thích
def find_original_stats(pre: list[Line], ident: Identity) -> None:
    """'14 năm | 6+ năm | Thạc sĩ' + 'Kinh nghiệm | Quản lý | Học vấn' -> 3 ô source="original" (tối đa 4)."""
    for a, b in zip(pre, pre[1:]):
        va = [c.strip() for c in a.text.split("\t") if c.strip()]
        lb = [c.strip() for c in b.text.split("\t") if c.strip()]
        if (2 <= len(va) <= 6 and len(va) == len(lb) and all(len(v.split()) <= 3 for v in va)
                and sum(any(ch.isdigit() for ch in v) for v in va) * 2 >= len(va)
                and all(len(x.split()) <= 7 for x in lb) and b.size <= a.size and not checks.scan_text(a.text)):
            ident.stats = [{"value": v, "label": l, "source": "original"} for v, l in zip(va, lb)][:4]
            ident.used.update({id(a), id(b)})
            return


# Tách dòng có nhiều cặp "Nhãn: nội dung" cách nhau bằng khoảng trống lớn/gạch đứng thành từng phần
def _segments(line: Line) -> list[Line]:
    """'Năm sinh: 1987 <tab> Giới tính: Nữ' -> 2 dòng ảo; dòng không có nhãn nào thì giữ nguyên."""
    parts = [p.strip() for p in re.split(r"\t+|\s+\|\s+|\s*[✦◆♦]\s*", line.text) if p.strip()]
    if len(parts) < 2 or not any(content.label_of(p) or label_kind(p.rstrip(":")) for p in parts):
        return [line]
    return [replace(line, text=p, spans=[Span(p, line.bold, line.italic)]) for p in parts]


# Xử lý một dòng "Nhãn: nội dung" thuộc nhóm thông tin cá nhân; trả True nếu đã dùng/bỏ dòng
def _apply_label(label: str, value: str, kind: str, ident: Identity, wish: list[str], allow_wish: bool,
                 desired: bool = False) -> bool:
    r = rulebook.rules()
    if kind == "ignore":
        return allow_wish
    if kind == "name":
        if allow_wish and _namelike(value) and not ident.full_name:
            ident.full_name, ident.name_conf = (value.title() if value.isupper() else value), 0.9
        return allow_wish
    if kind == "remove":
        ident.removed.add(r["_removed_index"].get(rulebook.norm(label), "address"))
    elif kind == "birth":
        y = re.search(r"(19[4-9]\d|20[01]\d)", value)
        if y:
            ident.birth_year = int(y.group(1))
        if re.search(r"\d{1,2}\s*[/.\-]\s*\d{1,2}", value) or not y:
            ident.removed.add("birth")
    elif kind == "gender":
        ident.gender = GENDER_WORDS.get(rulebook.norm(value), value or None)
    elif kind == "salary":
        ident.expected_salary = value or ident.expected_salary
    elif kind == "current_salary":
        ident.removed.add("current_salary")
    elif kind == "title" and allow_wish:
        value = _sentence_case(value)
        ident.target_title = ident.target_title or value or None
        if desired and value:                                   # mục "Công việc mong muốn": vị trí cũng vào dòng Mong muốn
            wish.append(value)
    elif kind == "wish" and allow_wish:
        if value:
            wish.append(_sentence_case(value))
    else:
        return False
    return True


# Lọc khối thông tin cá nhân trên MỌI dòng: dòng nhạy cảm bị bỏ khỏi danh sách (trả danh sách dòng còn lại)
def strip_personal(lines: list[Line], personal_ids: set[int], ident: Identity,
                   desired_ids: frozenset[int] = frozenset()) -> list[Line]:
    """`personal_ids`: id() các dòng ở đầu CV / mục "Thông tin cá nhân" — ở đó còn nhận mong muốn, chức danh,
    giới tính viết trơn, địa chỉ không nhãn. Ở các mục khác chỉ bỏ dòng có nhãn nhạy cảm (an toàn trước).
    `desired_ids`: dòng của mục "Công việc mong muốn" (vị trí ở đó cũng đưa vào dòng Mong muốn)."""
    keep: list[Line] = []
    wish: list[str] = []
    pending: tuple[str, str] | None = None                       # (loại, nhãn) chờ nội dung ở dòng sau
    expanded = [(seg, id(l) in personal_ids, id(l) in desired_ids) for l in lines if id(l) not in ident.used
                for seg in _segments(l)]
    for i, (l, personal, desired) in enumerate(expanded):
        text = l.text.replace("\t", " ").strip()
        has_next = i + 1 < len(expanded)
        if pending:                                               # dòng này là nội dung của nhãn đứng ở dòng trước
            kind, label = pending
            pending = None
            if _apply_label(label, text, kind, ident, wish, personal, desired):
                continue
        lab = content.label_of(text)
        if lab:
            kind = label_kind(lab[0])
            if kind and (kind not in ("wish", "title", "name", "ignore") or personal):
                if not lab[1] and has_next:                       # nhãn một dòng, nội dung ở dòng sau
                    pending = (kind, lab[0])
                else:
                    _apply_label(lab[0], lab[1], kind, ident, wish, personal, desired)
                continue
        elif personal and label_kind(text) and len(text.split()) <= 5 and has_next and not l.bullet:
            pending = (label_kind(text), text)                    # nhãn không có dấu ':' đứng riêng một dòng
            continue
        if personal and id(l) not in ident.used:
            if rulebook.norm(text) in GENDER_WORDS and ident.gender is None:
                ident.gender = GENDER_WORDS[rulebook.norm(text)]
                continue
            found = _found(text)
            if found and len(re.sub(r"[\W\d_]", "", _scrub(text, set()))) < 3:
                ident.removed.update(_KIND_OF_CHECK.get(k, "phone") for k, _ in found)
                continue                                          # dòng chỉ có SĐT/email/link
            if ADDRESS.search(text) and (re.search(r"\d", text) or "," in text):
                ident.removed.add("address")
                continue
            if len(text.split()) >= 12:
                ident.intro.append(l)
            else:
                ident.leftover += 1
            continue
        keep.append(l)
    if wish:
        old = next((f for f in ident.facts if f["label"] == "Mong muốn"), None)
        values = (old["value"].split(" · ") if old else []) + wish
        if old:
            ident.facts.remove(old)
        ident.facts.append({"label": "Mong muốn", "value": " · ".join(dict.fromkeys(values))})
    return keep


# Thông tin liên hệ tìm thấy trong chuỗi (mẫu của checks.py), bỏ "đường link" chỉ là tên miền nằm trong email
def _found(text: str) -> list[tuple[str, str]]:
    found = checks.scan_text(text)
    emails = [v for k, v in found if k == "Email"]
    return [(k, v) for k, v in found if not (k == "Đường link" and any(v in e for e in emails))]


# Cắt SĐT/email/link/mạng xã hội/ngày sinh đầy đủ khỏi một chuỗi; ghi loại đã cắt vào `removed`
def _scrub(text: str, removed: set[str], allow_birth: bool = True) -> str:
    out = text
    for kind, value in _found(text):
        if kind == "Ngày sinh đầy đủ" and not allow_birth:
            continue
        removed.add(_KIND_OF_CHECK.get(kind, "phone"))
        out = out.replace(value, "")
    out = re.sub(r"\(\s*\)|\[\s*\]", "", out)
    out = re.sub(r"\s*([:,;|–-])\s*(?=[:,;|–-]|$)", "", out)
    return re.sub(r"\s{2,}", " ", out).strip(" ,;|–-")


# Cắt thông tin liên hệ khỏi MỌI chuỗi nội dung của hồ sơ (trừ lương và ghi chú); cảnh báo địa chỉ tự do
def scrub_cv(cv: dict, removed: set[str]) -> list[tuple[str, str]]:
    """Trả cảnh báo [(đường dẫn, câu)] cho chuỗi có dạng địa chỉ (không tự xoá vì dễ xoá nhầm)."""
    notes: list[tuple[str, str]] = []

    def walk(node, path: str, key: str = ""):
        if isinstance(node, dict):
            for k, v in list(node.items()):
                if path == "" and k in checks.SKIP_FIELDS:
                    continue
                node[k] = walk(v, f"{path}.{k}" if path else k, k)
            return node
        if isinstance(node, list):
            vals = [walk(v, f"{path}[{i}]", key) for i, v in enumerate(node)]
            return [v for v in vals if v not in ("", None)] if all(isinstance(v, (str, type(None))) for v in vals) \
                else vals
        if isinstance(node, str):
            s = _scrub(node, removed, allow_birth=key not in ("period",))
            if ADDRESS.search(s) and re.search(r"\d", s) and key not in ("period", "company", "title", "detail"):
                notes.append((path, "có thể chứa địa chỉ — kiểm tra và xoá nếu là địa chỉ nhà"))
            return s
        return node

    walk(cv, "")
    return notes


# Tên hiển thị của các loại thông tin đã bỏ (model_notes.removed)
def removed_names(kinds: set[str]) -> list[str]:
    """Theo thứ tự cố định, tên lấy từ bảng [removed_names]."""
    names = rulebook.rules()["removed_names"]
    order = ["phone", "email", "social", "link", "address", "hometown", "birth", "marital", "nationality", "id",
             "body", "current_salary"]
    return [names[k] for k in order if k in kinds]
