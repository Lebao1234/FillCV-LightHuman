# Gói services/privacy/: lọc thông tin nhạy cảm của ứng viên + checklist PDF thành phẩm.
"""Bước 3: kiểm tra bảo mật và chất lượng (checklist mục 7 SKILL.md).

- scan_pii(cv)       : quét JSON trước khi xuất -> có vi phạm thì CHẶN xuất PDF.
- scan_pdf(pdf_path) : quét lại PDF thành phẩm.

Ghi chú: dùng PyMuPDF thay cho pdftotext/pdffonts để chạy được cả trên Windows
lẫn Docker mà không cần cài thêm poppler. Kết quả tương đương.
"""
import re
from pathlib import Path

from infra.settings import company, company_phone_digits


# A4: thông tin Light Human (được phép xuất hiện) đọc từ config/company.toml — cùng nguồn với header PDF,
# nên đổi SĐT/email/website công ty không làm mọi PDF bị chặn tải.
# SĐT được phép (của công ty)
def _allowed_phones() -> set[str]:
    return {company_phone_digits()}


# Email được phép (của công ty)
def _allowed_emails() -> set[str]:
    return {company()["company"]["email"].lower()}


# Tên miền được phép (của công ty)
def _allowed_domains() -> tuple[str, ...]:
    return (company()["company"]["domain"].lower(),)


# A8: một danh sách mạng xã hội dùng cho cả mẫu "Mạng xã hội" lẫn SOCIAL_LABEL bên dưới
SOCIAL_NETWORKS = ("linkedin", "facebook", "fb", "zalo", "behance", "github", "instagram", "tiktok", "skype", "telegram")
_SOCIAL_RE = "|".join(SOCIAL_NETWORKS)

PATTERNS = {
    # Đầu số: "(+84)", "(028)", "+84", "84", "0". Đầu số không nằm giữa một chuỗi khác
    # (chữ, số, '.', ',', '-', '/') -> không bắt nhầm số tiền "10.000.000.000" hay mã "CPA0123456789".
    "Số điện thoại": re.compile(
        r"(?:\(\s*(?:\+?84|0\d{1,3})\s*\)|(?<![\w/.,\-+])(?:\+84|84|0))"
        r"(?:[\s.\-]?\d){8,10}(?![\w/])"),
    "Email": re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"),
    "Đường link": re.compile(
        # Đuôi dài (.com.vn, .edu.vn) phải đứng TRƯỚC .com/.vn, không thì 'abc.com.vn' bị cắt thành 'abc.com'
        r"https?://\S+|www\.\S+|\b[\w\-]+\.(?:com\.vn|edu\.vn|com|net|org|io|me|vn)\b(?:/\S*)?",
        re.IGNORECASE),
    # Chỉ bắt khi có dạng tài khoản/liên hệ ("Facebook: abc", "Zalo - 09..."), không bắt tên kỹ năng
    # như "Facebook Ads", "GitHub Actions". Đường link dạng facebook.com/... đã do mẫu "Đường link" bắt.
    "Mạng xã hội": re.compile(
        rf"\b(?:{_SOCIAL_RE})(?:\s*[:：]|\s+[\-–]\s)\s*\S+",
        re.IGNORECASE),
    "Ngày sinh đầy đủ": re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](?P<year>(?:19|20)\d{2})\b"),
}

# Một ngày đầy đủ chỉ bị coi là NGÀY SINH khi: có chữ "sinh"/"DOB"/"birth" ngay trước,
# hoặc năm nằm trong khoảng năm sinh của người đi làm (ngày cấp chứng chỉ, mốc công việc gần đây -> bỏ qua).
BIRTH_CONTEXT = re.compile(r"(?:sinh|\bDOB\b|birth|\bNS\b)[^\d]{0,15}$", re.IGNORECASE)
# A6 (đã xác nhận là chủ ý): KHÁC khoảng 1940–2015 ở models.py. Ở đây dùng để ĐOÁN một ngày đầy đủ có phải
# ngày sinh không -> siết tới 2010 (người đi làm) để không chặn nhầm ngày cấp chứng chỉ / mốc công việc 2011+.
# models.py chỉ kiểm tra năm sinh nhập vào có hợp lý không -> nới rộng hơn.
BIRTH_YEAR_MIN, BIRTH_YEAR_MAX = 1940, 2010

SOCIAL_LABEL = re.compile(rf"(?:{_SOCIAL_RE})\s*:?", re.IGNORECASE)

# Các trường KHÔNG đưa vào PDF -> không cần quét
SKIP_FIELDS = {"model_notes", "expected_salary"}


# Tên công nghệ có dạng "xxx.net/.io/..." — không phải đường link
TECH_NAMES = {"asp.net", "vb.net", "ado.net", "f#.net", "c#.net", "socket.io", "node.io"}


# Tách link thành tên miền + phần còn lại
def _split_link(url: str) -> tuple[str, str]:
    """Tách link thành (tên miền, phần còn lại). Bỏ 'user:pass@' và ':cổng' khỏi tên miền.

    'https://lighthuman.vn:x@facebook.com/abc' -> ('facebook.com', '/abc')
    """
    g = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", url.lower())
    m = re.match(r"[^/?#]*", g)
    authority, rest = m.group(0), g[m.end():]
    host = authority.rsplit("@", 1)[-1]            # phần sau '@' cuối cùng mới là tên miền thật
    host = host.split(":", 1)[0].rstrip(".,;)")
    return host.removeprefix("www."), rest


# Lấy tên miền từ link
def _domain(url: str) -> str:
    """Lấy tên miền (host) từ chuỗi link: 'https://www.abc.vn/x' -> 'abc.vn'."""
    return _split_link(url)[0]


# Giá trị có thuộc danh sách được phép không
def _is_allowed(kind: str, value: str) -> bool:
    g = value.lower()
    if kind == "Số điện thoại":
        digits = re.sub(r"\D", "", g)
        allowed = _allowed_phones()
        return digits in allowed or digits.removeprefix("84") in {x[1:] for x in allowed}
    if kind == "Email":
        return g in _allowed_emails()
    if kind == "Đường link":
        if g.rstrip(".,;)") in TECH_NAMES:
            return True
        host, rest = _split_link(g)
        # So khớp đúng tên miền (hoặc tên miền con), không so chuỗi con
        if not any(host == domain or host.endswith("." + domain) for domain in _allowed_domains()):
            return False
        # Link Light Human nhưng nhúng link khác trong đường dẫn/query (?u=facebook.com/...) -> chặn
        return not any(not _is_allowed("Đường link", m.group(0)) for m in PATTERNS["Đường link"].finditer(rest))
    return False


# Ngày đầy đủ có phải ngày sinh không
def _is_birth_date(text: str, m: re.Match) -> bool:
    if BIRTH_CONTEXT.search(text[max(0, m.start() - 30):m.start()]):
        return True
    return BIRTH_YEAR_MIN <= int(m.group("year")) <= BIRTH_YEAR_MAX


# Tìm thông tin nhạy cảm trong một chuỗi
def scan_text(text: str) -> list[tuple[str, str]]:
    """Tìm thông tin nhạy cảm trong 1 chuỗi. Trả [(loại, giá trị)]."""
    result = []
    for kind, pattern in PATTERNS.items():
        for m in pattern.finditer(text or ""):
            if kind == "Ngày sinh đầy đủ" and not _is_birth_date(text, m):
                continue
            if not _is_allowed(kind, m.group(0)):
                result.append((kind, m.group(0)))
    return result


# Quét mọi chuỗi trong JSON hồ sơ
def scan_pii(data, path: str = "") -> list[dict]:
    """Duyệt TOÀN BỘ chuỗi trong JSON. Trả [{field, loai, value}]."""
    errors = []
    if isinstance(data, dict):
        for k, v in data.items():
            if not path and k in SKIP_FIELDS:
                continue
            # Nhãn dạng "Zalo" / "Facebook" + nội dung ở trường bên cạnh = thông tin liên hệ
            if k == "label" and isinstance(v, str) and SOCIAL_LABEL.fullmatch(v.strip()):
                errors.append({"field": f"{path}.{k}" if path else k,
                            "kind": "Mạng xã hội", "value": v.strip()})
            errors += scan_pii(v, f"{path}.{k}" if path else k)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            errors += scan_pii(v, f"{path}[{i}]")
    elif isinstance(data, str):
        for kind, found in scan_text(data):
            errors.append({"field": path, "kind": kind, "value": found})
    return errors


# Quét hồ sơ + dự án + vị trí trước khi xuất
def scan_pii_export(cv: dict, project: str, position: str) -> list[dict]:
    """Quét mọi chữ sẽ vào PDF: hồ sơ + tên dự án (header) + vị trí (header, tên file)."""
    errors = scan_pii(cv)
    for name, value in (("Tên dự án", project), ("Vị trí", position)):
        for kind, found in scan_text(value or ""):
            errors.append({"field": name, "kind": kind, "value": found})
    return errors


# PDF thành phẩm sạch thông tin liên hệ
def pdf_clean(checklist: list[dict] | None) -> bool:
    """PDF thành phẩm không còn thông tin liên hệ của ứng viên (mục 'pii' của scan_pdf)."""
    items = [r for r in (checklist or []) if r.get("code") == "pii"]
    return bool(items) and all(r["ok"] for r in items)


# A6 (đã xác nhận là chủ ý): checklist chỉ báo lỗi khi trang cuối dùng < 15% chiều cao. KHÁC ngưỡng 30% ở
# render.py: 30% là mức app CỐ thu nhỏ chữ để lấp đầy; thu nhỏ không phải lúc nào cũng đạt 30%, nên chỉ coi
# là lỗi thật khi trang cuối gần như trống (< 15%).
LAST_PAGE_ERROR_FILL = 0.15


# Mục checklist: font serif đã nhúng
def check_fonts(fonts: list[tuple]) -> dict:
    """Mục checklist 'font serif đã nhúng' từ danh sách `page.get_fonts()` của PyMuPDF.

    Mỗi phần tử: (xref, đuôi file font, loại, basefont, tên, encoding).
    N1: font Type3 (Chromium dùng cho ký tự không có trong Times New Roman, vd '▸') luôn được định nghĩa
    ngay trong PDF -> coi là ĐÃ nhúng, dù PyMuPDF báo đuôi 'n/a' và không có tên.
    """
    font_names = sorted({f[3] for f in fonts if f[3]})
    serif = [n for n in font_names if re.search(r"Times|Liberation.?Serif|Serif", n, re.I)]
    not_embedded = sorted({f[3] or "(không tên)" for f in fonts if f[1] in ("n/a", "") and f[2] != "Type3"})
    has_type3 = any(f[2] == "Type3" for f in fonts)
    detail = f"Font: {', '.join(font_names)}"
    if has_type3:
        detail += " (+ ký hiệu dạng Type3, đã nhúng)"
    if not_embedded:
        detail += f" — CHƯA nhúng: {not_embedded}"
    return {"code": "font", "item": "Font serif (Times New Roman / Liberation Serif) đã nhúng",
            "ok": bool(serif) and not not_embedded, "detail": detail}


# Checklist chất lượng cho PDF thành phẩm
def scan_pdf(pdf_path: Path) -> list[dict]:
    """Checklist cho PDF thành phẩm. Trả [{muc, ok, detail}]."""
    import pymupdf as fitz
    from services.pdf.pdf_utils import pdf_layout

    result = []
    with fitz.open(pdf_path) as doc:
        text = "\n".join(p.get_text() for p in doc)

        # 1. Font serif đã nhúng
        result.append(check_fonts([f for p in doc for f in p.get_fonts()]))

        # 2. Không còn thông tin liên hệ của ứng viên
        violations = scan_text(text)
        result.append({"code": "pii", "item": "Không còn SĐT, email, link, ngày sinh của ứng viên",
                   "ok": not violations,
                   "detail": "; ".join(f"{l}: {g}" for l, g in violations) or "Sạch"})

        # 3. Header đúng chuẩn
        result.append({"code": "header", "item": "Header: có 'HỒ SƠ ỨNG VIÊN', không có 'Candidate Profile'",
                   "ok": "HỒ SƠ ỨNG VIÊN" in text.upper() and "candidate profile" not in text.lower(),
                   "detail": ""})

        # 4. Tiêu đề PDF = tên file
        title = (doc.metadata or {}).get("title", "")
        result.append({"code": "title", "item": "Tiêu đề PDF trùng tên file",
                   "ok": title == Path(pdf_path).stem,
                   "detail": f"Tiêu đề: {title}"})

    # 5. Trang cuối không gần trống
    page_count, fill = pdf_layout(pdf_path)
    result.append({"code": "last_page", "item": "Trang cuối không gần trống",
               "ok": page_count == 1 or fill >= LAST_PAGE_ERROR_FILL,
               "detail": f"{page_count} trang, trang cuối dùng {fill:.0%}"})
    return result
