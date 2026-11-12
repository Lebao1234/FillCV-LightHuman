"""Giai đoạn b) — tách CV thành các mục theo tiêu đề.

Tiêu đề = dòng ngắn khớp bảng từ khoá (config/extraction_rules.toml), hoặc dòng có CÙNG KIỂU CHỮ với các tiêu đề
đã khớp (cỡ chữ, đậm, viết hoa) — để nhận cả tiêu đề viết lạ mà không nhầm tên công ty in hoa thành tiêu đề.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import median

from services.extraction.rules import rulebook
from services.extraction.rules.pdf_text import Line
from services.extraction.rules import dates

MAX_HEADING_WORDS = 8


# Một mục thô: tiêu đề + các dòng nội dung (chưa dựng theo schema)
@dataclass
class RawSection:
    title: str
    key: str | None            # khoá trong bảng từ khoá (None = tiêu đề lạ)
    type: str                  # loại theo bảng ("auto" = tự chọn theo nội dung, "personal" = thông tin cá nhân)
    lang: str                  # vi | en | ?
    lines: list[Line] = field(default_factory=list)
    confidence: float = 0.9
    reason: str = ""           # lý do khi không chắc (do code soạn)


# Cỡ chữ thân bài (trung vị theo số ký tự)
def body_size(lines: list[Line]) -> float:
    """Cỡ chữ phổ biến nhất của nội dung — để nhận tiêu đề/tên to hơn thân bài."""
    sizes = [l.size for l in lines for _ in range(max(1, len(l.text) // 10))]
    return median(sizes) if sizes else 11.0


# Thử khớp dòng với bảng tiêu đề; trả (khoá, loại, ngôn ngữ, phần nội dung cùng dòng nếu có)
def heading_of(line: Line) -> tuple[str, str, str, str] | None:
    """'KINH NGHIỆM LÀM VIỆC / WORK EXPERIENCE' -> experience; 'Ngoại ngữ: Tiếng Anh B1' -> languages + phần sau ':'.
    Dòng có ký hiệu đầu dòng ('◆ HỌC VẤN') chỉ là tiêu đề khi in đậm/viết hoa và khớp nguyên dòng."""
    if len(line.text.split()) > MAX_HEADING_WORDS + 6:
        return None
    text = line.text.replace("\t", " ").strip()
    hit = rulebook.match_heading(text)
    if line.bullet:
        return (*hit, "") if hit and (line.bold or line.upper) and len(text.split()) <= MAX_HEADING_WORDS else None
    if hit and len(text.split()) <= MAX_HEADING_WORDS:
        return (*hit, "")
    for part in re.split(r"\s+[/|–—-]\s+|\s*/\s*", text):           # tiêu đề song ngữ
        hit = rulebook.match_heading(part)
        if hit and len(text.split()) <= MAX_HEADING_WORDS * 2:
            return (*hit, "")
    if (line.bold or line.upper) and not dates.find_period(text):  # tiêu đề ghép 'KỸ NĂNG & HOẠT ĐỘNG' -> theo vế đầu
        first = re.split(r"\s*/\s*", text)[0]
        head = re.split(r"\s+(?:&|và|va|and)\s+|\s*&\s*", first, flags=re.IGNORECASE)[0]
        hit = rulebook.match_heading(head)
        if hit and head != first and len(first.split()) <= MAX_HEADING_WORDS:
            return (*hit, "")
    if ":" in text:                                                # "Kỹ năng: Excel, Word" (nội dung cùng dòng)
        label, rest = text.split(":", 1)
        hit = rulebook.match_heading(label)
        if hit and rest.strip() and hit[1] != "personal" and not _ambiguous(label):
            return (*hit, rest.strip())
    return None


# Chữ vừa có thể là tiêu đề mục vừa là nhãn bên trong công việc ("Thành tích", "Dự án"...)
def _ambiguous(text: str) -> bool:
    exp = rulebook.rules()["experience"]
    return rulebook.in_list(text, exp["meta_labels"] + exp["group_labels"])


# Kiểu chữ của một dòng để so với kiểu tiêu đề: (cỡ chữ làm tròn, đậm, viết hoa)
def _style(line: Line) -> tuple:
    return round(line.size), line.bold, line.upper


# Dòng có thể là tiêu đề lạ (không có trong bảng) nhưng cùng kiểu với các tiêu đề đã biết
def _looks_like_heading(line: Line, styles: set, nxt: Line | None) -> bool:
    words = line.text.split()
    if line.bullet or not words or len(words) > 6 or _style(line) not in styles or ":" in line.text.rstrip(":"):
        return False
    if any(c.isdigit() for c in line.text) or dates.find_period(line.text):
        return False
    r = rulebook.rules()
    if rulebook.contains_any(line.text, r["experience"]["company_words"]):
        return False
    return nxt is not None and not dates.find_period(nxt.text)


# Tách danh sách dòng thành (các dòng trước tiêu đề đầu tiên, các mục)
def split_sections(lines: list[Line]) -> tuple[list[Line], list[RawSection]]:
    """Dòng trước tiêu đề đầu tiên thường là khối tên + liên hệ (xử lý ở giai đoạn lọc thông tin cá nhân)."""
    hits = [heading_of(l) for l in lines]
    styles = {_style(l) for l, h in zip(lines, hits) if h and not h[3] and not _ambiguous(l.text)}
    # Tiêu đề "nhập nhằng" chỉ được nhận khi cùng kiểu chữ với các tiêu đề rõ ràng (không thì là nhãn trong công việc)
    hits = [None if h and styles and _ambiguous(l.text) and _style(l) not in styles else h
            for l, h in zip(lines, hits)]
    # Kiểu chữ phổ biến nhất của tiêu đề: tiêu đề cùng loại với mục đang mở nhưng KHÁC kiểu này là tiêu đề phụ
    # ("Quá trình học tập" in đậm thường nằm trong mục "HỌC VẤN") -> bỏ dòng, không mở mục mới
    main_style = Counter(_style(l) for l, h in zip(lines, hits) if h and not h[3]).most_common(1)
    main_style = main_style[0][0] if main_style else None
    pre: list[Line] = []
    out: list[RawSection] = []
    for i, (line, hit) in enumerate(zip(lines, hits)):
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if (hit and out and not hit[3] and _style(line) != main_style
                and (out[-1].key == hit[0] or (out[-1].type == hit[1] and hit[1] in ("education", "experience")))):
            continue
        if hit:
            key, typ, lang, inline = hit
            out.append(RawSection(line.text.split(":")[0].strip() if inline else _clean_title(line.text),
                                  key, typ, lang))
            if inline:
                out[-1].lines.append(Line(inline, [], line.x0, line.y0, line.x1, line.y1, line.page, line.size,
                                          line.col))
        elif styles and _looks_like_heading(line, styles, nxt):
            out.append(RawSection(_clean_title(line.text), None, "auto", "?", confidence=0.6,
                                  reason="tiêu đề mục không có trong bảng từ khoá — loại mục được đoán theo nội dung"))
        elif out:
            out[-1].lines.append(line)
        else:
            pre.append(line)
    return pre, out


# Tiêu đề hiển thị: bỏ dấu ':' cuối, số thứ tự đầu dòng, khoảng trắng thừa
def _clean_title(text: str) -> str:
    t = re.sub(r"^\s*(?:[0-9]{1,2}|[IVXivx]{1,4})[.)]\s+", "", text.replace("\t", " "))
    return re.sub(r"\s+", " ", t).strip(" :")
