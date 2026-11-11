"""Giai đoạn a') — làm sạch dòng trước khi tách mục.

1. Nhãn cột thời gian lặp lại ở đầu dòng ("From time – To time CÔNG TY ...") -> bỏ phần nhãn.
2. Phần sau dấu "/" chỉ là bản không dấu của phần trước ("Nguyễn Văn A / Nguyen Van A") -> bỏ.
3. CV "dịch theo từng dòng" (mỗi dòng tiếng Việt có dòng tiếng Anh dịch lại, hoặc "tiếng Việt / tiếng Anh" trên cùng
   dòng): nhận ra theo số cặp Việt–Anh, rồi bỏ dòng / ô / phần "/ ..." tiếng Anh. Hồ sơ chỉ giữ tiếng Việt.

Tiếng Anh = không có dấu tiếng Việt + có từ tiếng Anh thông dụng (bảng [translation] trong file luật).
"""
import re
import unicodedata
from dataclasses import replace

from services.extraction.rules import dates, rulebook
from services.extraction.rules.pdf_text import Line, Span, _strip_bullet

_VI = re.compile(r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]", re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z]+")
_SLASH = re.compile(r"\s*/\s*")
MIN_PAIRS = 6                 # ít hơn số cặp Việt–Anh này -> không phải CV dịch theo dòng
MIN_PAIR_RATIO = 0.1          # ... hoặc số cặp < 10% số dòng


# Có chữ cái mang dấu tiếng Việt không
def has_vi(text: str) -> bool:
    """'Kế toán' -> True; 'Accountant' / 'Ke toan' -> False."""
    return bool(_VI.search(text or ""))


# Đoạn chữ có phải tiếng Anh không (không dấu tiếng Việt + đủ từ tiếng Anh thông dụng)
def is_english(text: str) -> bool:
    """'Main job: manage the team' -> True; 'Ke toan tong hop' -> False; '07/2019' -> False."""
    if has_vi(text):
        return False
    words = [w.lower() for w in _WORD.findall(text or "")]
    if not words:
        return False
    tr = rulebook.rules()["translation"]
    strong, weak = set(tr["en_words"]), set(tr["weak_words"])
    score = sum(1 for w in words if w in strong) + 0.5 * sum(1 for w in words if w in weak)
    return score >= 1 and (score >= 2 or len(words) <= 3 or score * 4 >= len(words))


# Bỏ dấu từng ký tự (giữ nguyên độ dài chuỗi để cắt theo vị trí)
def _plain(text: str) -> str:
    out = []
    for c in text:
        c = "d" if c in "đĐ" else c
        base = "".join(x for x in unicodedata.normalize("NFD", c) if unicodedata.category(x) != "Mn")
        out.append((base or c)[:1].lower())
    return "".join(out)


# Mẫu regex (trên chữ đã bỏ dấu) của một nhãn cột thời gian: "from time - to time" -> from\s+time\s*[-–—]\s*to\s+time
def _range_pattern(label: str) -> str:
    halves = [r"\s+".join(re.escape(w) for w in re.findall(r"\w+", h)) for h in label.split("-")]
    return r"\s*" + r"\s*[-–—]\s*".join(halves) + r"\b[\s:]*"


# Bỏ nhãn cột thời gian ở đầu dòng ("From time – To time ...")
def strip_range_label(text: str) -> str:
    """'From time – To time  CÔNG TY ABC' -> 'CÔNG TY ABC'; dòng khác giữ nguyên."""
    plain = _plain(text)
    for lab in rulebook.rules()["translation"]["range_labels"]:
        m = re.match(_range_pattern(lab), plain)
        if m:
            return text[m.end():].lstrip()
    return text


# Phần sau "/" là bản không dấu của phần trước không ("Đoàn Văn A / Doan Van A", "Hồ Chí Minh / Ho Chi Minh City")
def _unaccented_copy(left: str, right: str) -> bool:
    seg = re.split(r"[:\t,;(]", left)[-1].strip()
    a, b = rulebook.norm(seg), rulebook.norm(right)
    return len(a) >= 3 and has_vi(seg) and not has_vi(right) and (b == a or b.startswith(a + " "))


# Cắt phần "/ bản dịch" khỏi một đoạn chữ (nhãn hoặc nội dung)
def cut_slash(text: str, translated: bool) -> str:
    """'Giới tính/ Sex' -> 'Giới tính'; 'Kế toán trưởng / Chief Accountant' -> 'Kế toán trưởng' (chỉ khi CV dịch theo
    dòng); 'Kế toán thanh toán / nội bộ' giữ nguyên (cả hai phía đều tiếng Việt)."""
    for m in _SLASH.finditer(text or ""):
        left, right = text[:m.start()], text[m.end():]
        if not right.strip() or not has_vi(left) or has_vi(right):
            continue
        if _unaccented_copy(left, right):
            return left.rstrip()
        if translated and (is_english(right) or len(_WORD.findall(right)) >= 2):
            return left.rstrip()
    return text


# Làm sạch một ô (giữa hai dấu tab): nhãn và nội dung cắt riêng
def _clean_cell(cell: str, translated: bool) -> str:
    if "/" not in cell:
        return cell
    m = re.match(r"^([^:：]{1,60}?)\s*[:：]\s*(.*)$", cell)
    if m and len(m.group(1).split()) <= 8 and not re.search(r"https?$|\d$", m.group(1)):
        label, value = cut_slash(m.group(1), translated), cut_slash(m.group(2), translated)
        if (label, value) == (m.group(1), m.group(2)):
            return cell
        return f"{label}: {value}".rstrip() if value else f"{label}:"
    return cut_slash(cell, translated)


# Ô tiếng Anh: bỏ cả ô, nhưng giữ khoảng thời gian nếu phần chữ còn lại không chỉ là "year/from/to"
def _english_cell(cell: str) -> str | None:
    """None = ô không phải tiếng Anh. '' = bỏ cả ô. Chuỗi khác = phần thời gian được giữ lại."""
    p = dates.find_period(cell)
    rest = (cell[:p.span[0]] + " " + cell[p.span[1]:]) if p else cell
    if not is_english(rest):
        return None
    words = {w.lower() for w in _WORD.findall(rest)}
    if p and not words <= set(rulebook.rules()["translation"]["date_words"]):
        return p.text
    return ""


# Đếm số dấu hiệu "dịch theo dòng": dòng tiếng Anh ngay sau dòng tiếng Việt + phần "/ tiếng Anh" trong dòng
def _pair_count(lines: list[Line]) -> int:
    pairs = 0
    for i, l in enumerate(lines):
        cells = [strip_range_label(c) for c in l.text.split("\t")]
        if i and has_vi(lines[i - 1].text) and all(_english_cell(c) is not None or not c.strip() for c in cells) \
                and any(c.strip() for c in cells):
            pairs += 1
        elif has_vi(l.text) and any(_SLASH.search(c) and _clean_cell(c, True) != c for c in cells):
            pairs += 1
    return pairs


# Dựng lại các mảnh chữ (giữ đậm/nghiêng theo từng ô) sau khi đổi chữ của dòng
def _respan(line: Line, cells: list[str]) -> list[Span]:
    groups: list[list[Span]] = [[]]
    for s in line.spans:
        if s.text == "\t":
            groups.append([])
        else:
            groups[-1].append(s)
    out: list[Span] = []
    for k, text in enumerate(cells):
        if out:
            out.append(Span("\t"))
        src = groups[k] if k < len(groups) else []
        if "".join(s.text for s in src).strip() == text.strip() and src:
            out += src
        else:
            parts = [s for s in src if s.text.strip()] or [Span(text, line.bold, line.italic)]
            out.append(Span(text, all(s.bold for s in parts), all(s.italic for s in parts)))
    return out


# Dòng đang xét có phải phần tiếp của đoạn tiếng Anh ngay trên không (không dấu, cùng cột, sát, không thụt ra)
def _continues(l: Line, prev: Line | None) -> bool:
    return (prev is not None and not has_vi(l.text) and not l.bullet and l.page == prev.page and l.col == prev.col
            and 0 <= l.y0 - prev.y1 < l.size * 1.2 and l.x0 >= prev.x0 - 3 and bool(_WORD.search(l.text)))


# Làm sạch toàn bộ dòng; trả (dòng còn lại, có phải CV dịch theo dòng không, số dòng/ô tiếng Anh đã bỏ)
def clean_lines(lines: list[Line]) -> tuple[list[Line], bool, int]:
    """Tiêu đề mục không bị bỏ (chỉ cắt phần "/ tiếng Anh"). Dòng tiếp nối của một đoạn tiếng Anh (không dấu, cùng
    cột, sát dòng trước, không thụt ra) cũng bị bỏ dù không có từ tiếng Anh nào."""
    translated = _pair_count(lines) >= max(MIN_PAIRS, MIN_PAIR_RATIO * len(lines))
    out: list[Line] = []
    dropped = 0
    prev_en: Line | None = None                    # dòng vừa bỏ / vừa cắt đuôi tiếng Anh
    for l in lines:
        cells = [c for c in (strip_range_label(c) for c in l.text.split("\t")) if c.strip()]
        if translated and rulebook.match_heading(l.text) is None:
            if _continues(l, prev_en):
                prev_en, dropped = l, dropped + 1
                continue
            judged = [(c, _english_cell(c)) for c in cells]
            p = dates.find_period(l.text)
            rest = (l.text[:p.span[0]] + " " + l.text[p.span[1]:]) if p else ""
            if p and out and has_vi(out[-1].text) and not has_vi(rest) and len(_WORD.findall(rest)) >= 2:
                judged = [(p.text, None)]                         # "07/2025 – Nay  ABC JOINT STOCK COMPANY"
                dropped += 1
            if judged and all(en is not None for _, en in judged):
                cells = [en for _, en in judged if en]           # chỉ còn khoảng thời gian (nếu có)
                if not cells:
                    prev_en, dropped = l, dropped + 1
                    continue
            else:
                dropped += sum(1 for _, en in judged if en is not None)
                cells = [c if en is None else en for c, en in judged]
                cells = [c for c in cells if c]
        new = [c for c in (_clean_cell(c, translated).strip() for c in cells) if c]
        prev_en = l if translated and new and cells and new[-1] != cells[-1].strip() else None
        text = "\t".join(new)
        if not text.strip():
            continue
        if text == l.text:
            out.append(l)
            continue
        # chữ ngắn lại -> lề phải ước theo tỉ lệ ký tự (để bước gộp dòng không tưởng dòng này chạm lề phải)
        x1 = l.x0 + (l.x1 - l.x0) * min(1.0, len(text) / max(len(l.text), 1))
        nl = replace(l, text=text, spans=_respan(l, new), x1=x1)
        if not nl.bullet:
            _strip_bullet(nl)                                     # "2012 year:\t9. Chứng chỉ" -> "9." là số thứ tự
        out.append(nl)
    return out, translated, dropped
