"""Giai đoạn a) — đọc chữ trong PDF bằng PyMuPDF: từng dòng kèm vị trí, cỡ chữ, in đậm/nghiêng, cột, ký hiệu đầu dòng.

Không OCR: PDF không có lớp chữ (bản scan) hoặc chữ lỗi mã hoá -> TextQualityError để chuyển sang nhập tay.
"""
import re
from dataclasses import dataclass, field

BULLET_CHARS = "•●▪■◦○◆◇►▶➢➤➣✓✔✗✦★☐❖·‣⁃−–—-+*"
_PUA = re.compile(r"[-]")                       # ký hiệu font Symbol/Wingdings của Word (vd )
_BULLET = re.compile(rf"^\s*(?:[{re.escape(BULLET_CHARS)}]|[-]|o(?=\s))\s*")
_NUMBERED = re.compile(r"^\s*(?:\d{1,2}|[a-z])[.)]\s+(?=\S)")
_PAGE_NO = re.compile(r"^\s*(?:trang|page)?\s*\d{1,2}\s*(?:/|of|trên)\s*\d{1,2}\s*$", re.IGNORECASE)
MIN_CHARS = 80                 # ít hơn số ký tự này trên cả file -> coi như không có lớp chữ
MAX_BAD_RATIO = 0.08           # tỉ lệ ký tự lỗi (�, ký tự điều khiển) vượt mức này -> chữ lỗi mã hoá


# PDF không đọc tự động được (không có lớp chữ / chữ lỗi)
class TextQualityError(Exception):
    """Thông điệp là câu tiếng Việt cho người dùng."""


# PDF dài quá số trang cho phép (không đọc tự động để khỏi giữ lượt đọc quá lâu)
class TooManyPagesError(TextQualityError):
    """Thông điệp là câu tiếng Việt cho người dùng."""


# Một đoạn chữ cùng định dạng trong dòng
@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False


# Một dòng chữ trên trang (đã gộp các mảnh cùng hàng)
@dataclass
class Line:
    text: str
    spans: list[Span] = field(default_factory=list)
    x0: float = 0.0
    y0: float = 0.0
    x1: float = 0.0
    y1: float = 0.0
    page: int = 0
    size: float = 11.0
    col: int = -1              # -1: toàn chiều ngang; 0/1: cột trái/phải
    bullet: bool = False       # dòng bắt đầu bằng ký hiệu đầu dòng (đã bỏ ký hiệu khỏi text)
    left: float = 0.0          # lề trái/phải của cột chứa dòng (tính trên cả trang) — để biết dòng có bị ngắt không
    right: float = 0.0
    cell: bool = False         # một ô tách ra từ bố cục dạng lưới (không bao giờ gộp với dòng khác)

    @property
    def bold(self) -> bool:
        """Cả dòng in đậm (bỏ qua khoảng trắng)."""
        parts = [s for s in self.spans if s.text.strip()]
        return bool(parts) and all(s.bold for s in parts)

    @property
    def italic(self) -> bool:
        """Cả dòng in nghiêng."""
        parts = [s for s in self.spans if s.text.strip()]
        return bool(parts) and all(s.italic for s in parts)

    @property
    def upper(self) -> bool:
        """Dòng viết HOA toàn bộ (có ít nhất 3 chữ cái)."""
        letters = [c for c in self.text if c.isalpha()]
        return len(letters) >= 3 and all(c.isupper() for c in letters)


# Mảnh chữ có in đậm/nghiêng không (theo cờ font và tên font)
def _style(span: dict) -> tuple[bool, bool]:
    font = (span.get("font") or "").lower()
    flags = span.get("flags", 0)
    bold = bool(flags & 16) or any(k in font for k in ("bold", "black", "heavy", "semibold", "demi"))
    italic = bool(flags & 2) or "italic" in font or "oblique" in font
    return bold, italic


# Các dòng thô của một trang (mỗi dòng PyMuPDF = 1 dòng, kèm mảnh chữ)
def _raw_lines(page, page_no: int) -> list[Line]:
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type", 0) != 0:
            continue
        for ln in block["lines"]:
            spans = [s for s in ln["spans"] if s["text"]]
            if not "".join(s["text"] for s in spans).strip():
                continue
            parts, text, last_x1 = [], "", None
            for s in spans:
                bold, italic = _style(s)
                gap = (s["bbox"][0] - last_x1) if last_x1 is not None else 0
                if last_x1 is not None and gap > max(s["size"] * 1.5, 12):
                    parts.append(Span("\t"))                      # khoảng cách lớn (cột ngày tháng canh phải)
                    text += "\t"
                parts.append(Span(s["text"], bold, italic))
                text += s["text"]
                last_x1 = s["bbox"][2]
            x0, y0, x1, y1 = ln["bbox"]
            size = max(s["size"] for s in spans)
            out.append(Line(text, parts, x0, y0, x1, y1, page_no, round(size, 1)))
    return out


# Gộp các dòng nằm cùng hàng TRONG CÙNG CỘT (PyMuPDF hay tách "Công ty ...   01/2019 - Nay" thành 2 khối)
def _merge_same_row(lines: list[Line]) -> list[Line]:
    lines = sorted(lines, key=lambda l: (l.col, round((l.y0 + l.y1) / 2), l.x0))
    out: list[Line] = []
    for ln in lines:
        prev = out[-1] if out else None
        same_row = (prev is not None and prev.col == ln.col
                    and abs((prev.y0 + prev.y1) / 2 - (ln.y0 + ln.y1) / 2) < min(prev.size, ln.size) * 0.45)
        if same_row and ln.x0 >= prev.x1 - 1:
            sep = "\t" if ln.x0 - prev.x1 > max(ln.size * 1.5, 12) else ("" if prev.text.endswith(" ") else " ")
            if prev.text.strip() and all(c in BULLET_CHARS or _PUA.match(c) or c.isspace() for c in prev.text):
                sep = " "                                          # "•" tách riêng một khối với nội dung
            prev.text += sep + ln.text
            prev.spans += ([Span(sep)] if sep else []) + ln.spans
            prev.x1, prev.y0, prev.y1 = ln.x1, min(prev.y0, ln.y0), max(prev.y1, ln.y1)
            prev.size = max(prev.size, ln.size)
        else:
            out.append(ln)
    return out


# Tìm khe dọc chia trang thành 2 cột (CV có sidebar); không có -> None
def _find_gutter(lines: list[Line], width: float) -> float | None:
    total = sum(len(l.text) for l in lines)
    if total < 200 or len(lines) < 12:
        return None
    best = None
    for x in range(int(width * 0.22), int(width * 0.78), 3):
        crossing = [l for l in lines if l.x0 < x - 2 and l.x1 > x + 2]
        left = sum(len(l.text) for l in lines if l.x1 <= x + 2)
        right = sum(len(l.text) for l in lines if l.x0 >= x - 2)
        if len(crossing) > max(2, len(lines) * 0.08) or min(left, right) < total * 0.15:
            continue
        score = min(left, right) - 50 * len(crossing)
        if best is None or score > best[0]:
            best = (score, x)
    return float(best[1]) if best else None


# Gán cột cho từng dòng theo khe dọc (không có khe -> mọi dòng là -1)
def _assign_cols(lines: list[Line], gutter: float | None) -> None:
    for l in lines:
        l.col = -1 if gutter is None else (0 if l.x1 <= gutter + 2 else (1 if l.x0 >= gutter - 2 else -1))


# Sắp thứ tự đọc: dòng toàn chiều ngang chia trang thành các đoạn; trong đoạn đọc hết cột trái rồi cột phải
def _reading_order(lines: list[Line]) -> list[Line]:
    lines = sorted(lines, key=lambda l: (l.y0, l.x0))
    if all(l.col == -1 for l in lines):
        return lines
    out, chunk = [], []
    for l in lines:
        if l.col == -1:
            out += sorted(chunk, key=lambda c: (c.col, c.y0, c.x0)) + [l]
            chunk = []
        else:
            chunk.append(l)
    return out + sorted(chunk, key=lambda c: (c.col, c.y0, c.x0))


# Bỏ ký hiệu đầu dòng / số thứ tự, đánh dấu dòng là gạch đầu dòng
def _strip_bullet(ln: Line) -> None:
    m = _BULLET.match(ln.text) or _NUMBERED.match(ln.text)
    if not m or not ln.text[m.end():].strip():
        return
    if m.group(0).strip() in ("-", "–", "—") and re.match(r"\s*[-–—]\s*\d", ln.text):
        return                                                     # "- 2019" không phải gạch đầu dòng
    ln.bullet = True
    cut = m.end()
    ln.text = ln.text[cut:]
    rest = []
    for s in ln.spans:                                             # cắt đúng số ký tự khỏi các mảnh đầu
        if cut <= 0:
            rest.append(s)
        elif len(s.text) <= cut:
            cut -= len(s.text)
        else:
            rest.append(Span(s.text[cut:], s.bold, s.italic))
            cut = 0
    ln.spans = rest


# Đọc toàn bộ PDF thành danh sách dòng theo thứ tự đọc; kiểm tra chất lượng lớp chữ
def read_lines(pdf_bytes: bytes, max_pages: int | None = None) -> tuple[list[Line], dict]:
    """Trả (dòng, thông tin: số trang, có 2 cột không, số ký tự). Lỗi lớp chữ -> TextQualityError.

    `max_pages`: PDF dài hơn số trang này -> TooManyPagesError ngay, chưa đọc trang nào (None = không giới hạn).
    """
    import pymupdf as fitz
    lines: list[Line] = []
    info = {"pages": 0, "two_columns": False, "chars": 0}
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        info["pages"] = doc.page_count
        if max_pages and doc.page_count > max_pages:
            raise TooManyPagesError(f"CV dài {doc.page_count} trang, vượt giới hạn {max_pages} trang của bộ đọc "
                                    "tự động — hãy nhập tay, đối chiếu tab CV gốc.")
        for i, page in enumerate(doc):
            raw = _raw_lines(page, i)
            gutter = _find_gutter(raw, page.rect.width)
            info["two_columns"] |= gutter is not None
            _assign_cols(raw, gutter)
            for l in _reading_order(_merge_same_row(raw)):
                l._edge = l.y0 < page.rect.height * 0.08 or l.y1 > page.rect.height * 0.92
                if not _PAGE_NO.match(l.text):
                    lines.append(l)
    lines = _drop_running_lines(lines)
    edges: dict[tuple, list[float]] = {}                 # lề trái/phải của từng cột trên từng trang (cả tài liệu)
    for l in lines:
        e = edges.setdefault((l.page, l.col), [l.x0, l.x1])
        e[0], e[1] = min(e[0], l.x0), max(e[1], l.x1)
    for l in lines:
        l.left, l.right = edges[(l.page, l.col)]
    text = "".join(l.text for l in lines)
    info["chars"] = len(text.strip())
    if info["chars"] < MIN_CHARS:
        raise TextQualityError("PDF không có lớp chữ (có thể là bản scan/ảnh) nên chưa đọc tự động được — "
                               "hãy nhập tay, đối chiếu tab CV gốc.")
    bad = sum(1 for c in text if c == "�" or (ord(c) < 32 and c not in "\t\n"))
    pua = len(_PUA.findall(text))
    if (bad + max(0, pua - len(lines))) / max(len(text), 1) > MAX_BAD_RATIO:
        raise TextQualityError("Chữ trong PDF bị lỗi mã hoá font nên đọc không chính xác — hãy nhập tay, "
                               "hoặc xuất lại CV thành PDF từ Word rồi gửi lại.")
    for l in lines:
        l.text = l.text.replace(" ", " ")
        _strip_bullet(l)
        l.text = re.sub(r"[ ]{2,}", " ", l.text).strip(" ")
    lines = _attach_lone_bullets(lines)
    return [l for l in lines if l.text.strip()], info


# Ký hiệu đầu dòng nằm thành dòng riêng (lệch hàng 1-2pt so với chữ) -> gắn cờ gạch đầu dòng cho dòng chữ bên phải
def _attach_lone_bullets(lines: list[Line]) -> list[Line]:
    out = []
    for g in lines:
        t = g.text.strip()
        if t and len(t) <= 2 and all(c in BULLET_CHARS or _PUA.match(c) for c in t):
            mid = (g.y0 + g.y1) / 2
            near = [l for l in lines if l is not g and l.page == g.page and l.col == g.col and 0 < l.x0 - g.x0 < 30
                    and abs((l.y0 + l.y1) / 2 - mid) < g.size * 0.6
                    and not all(c in BULLET_CHARS for c in l.text.strip())]
            if near:
                near[0].bullet = True
                continue
        out.append(g)
    return out


# Bỏ dòng đầu/chân trang lặp lại (cùng chữ, bỏ qua số trang) ở mép trên/dưới của từ 2 trang trở lên
def _drop_running_lines(lines: list[Line]) -> list[Line]:
    key = lambda l: re.sub(r"\d+", "#", re.sub(r"\s+", " ", l.text)).strip().lower()
    pages: dict[str, set[int]] = {}
    for l in lines:
        if getattr(l, "_edge", False):
            pages.setdefault(key(l), set()).add(l.page)
    repeated = {k for k, ps in pages.items() if len(ps) >= 2}
    sizes = sorted(l.size for l in lines)
    tiny = sizes[len(sizes) // 2] * 0.7 if sizes else 0          # chữ nhỏ hơn 70% cỡ chữ phổ biến
    # Bỏ: dòng lặp ở mép trang (header/footer) + dòng chữ rất nhỏ ở mép dưới trang (footer của CV một trang)
    return [l for l in lines if not (getattr(l, "_edge", False) and (key(l) in repeated or
                                                                      (l.size < tiny and l.y0 > 400)))]


# Chữ của dòng có giữ cụm in đậm dạng **...** (quy ước schema), dùng cho nội dung
def marked_text(ln: Line) -> str:
    """Chỉ đánh dấu khi dòng có CẢ chữ thường lẫn chữ đậm (cả dòng đậm thì không đánh dấu)."""
    parts = [s for s in ln.spans if s.text]
    if not any(s.bold and s.text.strip() for s in parts) or ln.bold:
        return ln.text
    out, buf, cur = [], "", None
    for s in parts:
        b = s.bold and bool(s.text.strip())
        if cur is None or b == cur or not s.text.strip():
            buf += s.text
            cur = b if cur is None or s.text.strip() else cur
        else:
            out.append((buf, cur))
            buf, cur = s.text, b
    out.append((buf, cur))
    text = ""
    for chunk, b in out:
        core = chunk.strip()
        if b and len(core) >= 2:
            lead, trail = chunk[:len(chunk) - len(chunk.lstrip())], chunk[len(chunk.rstrip()):]
            text += f"{lead}**{core}**{trail}"
        else:
            text += chunk
    return re.sub(r"[ ]{2,}", " ", text.replace("\t", " ")).strip()
