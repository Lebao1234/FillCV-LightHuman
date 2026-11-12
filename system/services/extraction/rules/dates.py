"""Nhận khoảng thời gian trong CV: '03/2019 – Nay', 'T3/2019 - 12/2021', '2019 - 2021', 'Jan 2019 – Present'...

Tháng/năm trả dạng (năm, tháng). Chỉ có năm: mốc bắt đầu tính tháng 1, mốc kết thúc tính tháng 12.
Chữ khoảng thời gian giữ NGUYÊN VĂN như CV (chỉ chuẩn gạch nối thành " – ").
"""
import re
from dataclasses import dataclass
from datetime import date

_MON = (r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?")
_MON_INDEX = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct",
                                               "nov", "dec"])}
_YEAR = r"(?:19[5-9]\d|20[0-4]\d)"
# Một mốc: ngày/tháng/năm, tháng/năm, "Tháng 3 năm 2019", "T3/2019", "Jan 2019", hoặc chỉ năm
_POINT = (rf"(?:(?:ngày\s*)?\d{{1,2}}\s*[/.\-]\s*\d{{1,2}}\s*[/.\-]\s*{_YEAR}"
          rf"|(?:tháng|thg|th|t)\s*\.?\s*\d{{1,2}}\s*(?:[/.\-]|\s*năm\s*|\s+)\s*{_YEAR}"
          rf"|\d{{1,2}}\s*[/.\-]\s*{_YEAR}"
          rf"|(?:{_MON})\.?\s*,?\s*{_YEAR}"
          rf"|{_YEAR})")
_PRESENT = r"(?:đến\s+nay|tới\s+nay|hiện\s+tại|hiện\s+nay|nay|present|now|current|today|hiện\s+giờ)"
_SEP = r"\s*(?:-|–|—|~|->|→|đến|tới|to|until)\s*"
_RANGE = re.compile(rf"(?:từ\s+|from\s+)?(?P<a>{_POINT}){_SEP}(?P<b>{_POINT}|{_PRESENT})(?![\w/])",
                    re.IGNORECASE)
_SINGLE = re.compile(rf"(?<![\w/])(?P<a>{_POINT})(?![\w/])", re.IGNORECASE)
_PRESENT_RE = re.compile(rf"^{_PRESENT}$", re.IGNORECASE)


# Một khoảng thời gian tìm thấy trong dòng
@dataclass
class Period:
    text: str                       # chữ hiển thị, vd "03/2019 – Nay"
    start: tuple[int, int]          # (năm, tháng)
    end: tuple[int, int] | None     # None = đến nay
    span: tuple[int, int]           # vị trí trong dòng gốc
    is_range: bool = True
    present: bool = False


# Đổi một mốc thành (năm, tháng); is_end: chỉ có năm thì lấy tháng 12
def parse_point(text: str, is_end: bool = False) -> tuple[int, int] | None:
    """'03/2019' -> (2019, 3); 'Jan 2019' -> (2019, 1); '2019' -> (2019, 1|12)."""
    t = text.strip().lower()
    y = re.search(_YEAR, t)
    if not y:
        return None
    year = int(y.group(0))
    before = t[:y.start()]
    m = re.search(_MON, before, re.IGNORECASE)
    if m:
        return year, _MON_INDEX[m.group(0)[:3]]
    nums = [int(n) for n in re.findall(r"\d{1,2}", before)]
    if nums and 1 <= nums[-1] <= 12:
        return year, nums[-1]
    return year, 12 if is_end else 1


# Tìm khoảng thời gian (ưu tiên dạng "từ – đến") trong một dòng; không có -> None
def find_period(text: str, today: date | None = None) -> Period | None:
    """Khoảng có điểm đầu/cuối hợp lệ (đầu <= cuối). Không có khoảng thì nhận MỘT mốc đơn (vd năm tốt nghiệp)."""
    today = today or date.today()
    for m in _RANGE.finditer(text or ""):
        a = parse_point(m.group("a"))
        present = bool(_PRESENT_RE.match(m.group("b").strip()))
        b = None if present else parse_point(m.group("b"), is_end=True)
        if a is None or (b is None and not present) or (b is not None and b < a) or a > (today.year, today.month):
            continue
        shown = f"{m.group('a').strip()} – {m.group('b').strip()}"
        return Period(shown, a, b, m.span(), True, present)
    m = _SINGLE.search(text or "")
    if m:
        a = parse_point(m.group("a"))
        if a:
            return Period(m.group("a").strip(), a, a, m.span(), False, False)
    return None


# Số tháng giữa hai mốc (tính cả tháng đầu và tháng cuối)
def months(start: tuple[int, int], end: tuple[int, int] | None, today: date) -> int:
    """(2019, 3) -> (2019, 12) = 10 tháng; end None = đến tháng hiện tại."""
    e = end or (today.year, today.month)
    return max(0, (e[0] - start[0]) * 12 + e[1] - start[1] + 1)


# Gộp các khoảng chồng nhau, trả tổng số tháng không tính trùng
def total_months(ranges: list[tuple[tuple[int, int], tuple[int, int] | None]], today: date) -> int:
    """Dùng cho số năm kinh nghiệm: không cộng trùng những đoạn làm song song."""
    now = (today.year, today.month)
    iv = sorted((s[0] * 12 + s[1], (e or now)[0] * 12 + (e or now)[1]) for s, e in ranges)
    total, cur = 0, None
    for a, b in iv:
        if cur and a <= cur[1] + 1:
            cur = (cur[0], max(cur[1], b))
        else:
            if cur:
                total += cur[1] - cur[0] + 1
            cur = (a, b)
    if cur:
        total += cur[1] - cur[0] + 1
    return total
