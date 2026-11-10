"""Bước 3: kiểm tra bảo mật và chất lượng (checklist mục 7 SKILL.md).

- scan_pii(cv)       : quét JSON trước khi xuất -> có vi phạm thì CHẶN xuất PDF.
- scan_pdf(pdf_path) : quét lại PDF thành phẩm.

Ghi chú: dùng PyMuPDF thay cho pdftotext/pdffonts để chạy được cả trên Windows
lẫn Docker mà không cần cài thêm poppler. Kết quả tương đương.
"""
import re
from pathlib import Path

from infra.settings import cong_ty, so_dien_thoai_cong_ty


# A4: thông tin Light Human (được phép xuất hiện) đọc từ config/company.toml — cùng nguồn với header PDF,
# nên đổi SĐT/email/website công ty không làm mọi PDF bị chặn tải.
def _sdt_duoc_phep() -> set[str]:
    return {so_dien_thoai_cong_ty()}


def _email_duoc_phep() -> set[str]:
    return {cong_ty()["cong_ty"]["email"].lower()}


def _ten_mien_duoc_phep() -> tuple[str, ...]:
    return (cong_ty()["cong_ty"]["ten_mien"].lower(),)


# A8: một danh sách mạng xã hội dùng cho cả mẫu "Mạng xã hội" lẫn NHAN_MXH bên dưới
MANG_XA_HOI = ("linkedin", "facebook", "fb", "zalo", "behance", "github", "instagram", "tiktok", "skype", "telegram")
_MXH = "|".join(MANG_XA_HOI)

MAU = {
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
        rf"\b(?:{_MXH})(?:\s*[:：]|\s+[\-–]\s)\s*\S+",
        re.IGNORECASE),
    "Ngày sinh đầy đủ": re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](?P<nam>(?:19|20)\d{2})\b"),
}

# Một ngày đầy đủ chỉ bị coi là NGÀY SINH khi: có chữ "sinh"/"DOB"/"birth" ngay trước,
# hoặc năm nằm trong khoảng năm sinh của người đi làm (ngày cấp chứng chỉ, mốc công việc gần đây -> bỏ qua).
NGU_CANH_SINH = re.compile(r"(?:sinh|\bDOB\b|birth|\bNS\b)[^\d]{0,15}$", re.IGNORECASE)
# A6 (đã xác nhận là chủ ý): KHÁC khoảng 1940–2015 ở models.py. Ở đây dùng để ĐOÁN một ngày đầy đủ có phải
# ngày sinh không -> siết tới 2010 (người đi làm) để không chặn nhầm ngày cấp chứng chỉ / mốc công việc 2011+.
# models.py chỉ kiểm tra năm sinh nhập vào có hợp lý không -> nới rộng hơn.
NAM_SINH_TU, NAM_SINH_DEN = 1940, 2010

NHAN_MXH = re.compile(rf"(?:{_MXH})\s*:?", re.IGNORECASE)

# Các trường KHÔNG đưa vào PDF -> không cần quét
BO_QUA = {"model_notes", "expected_salary"}


# Tên công nghệ có dạng "xxx.net/.io/..." — không phải đường link
TEN_CONG_NGHE = {"asp.net", "vb.net", "ado.net", "f#.net", "c#.net", "socket.io", "node.io"}


def _tach_link(url: str) -> tuple[str, str]:
    """Tách link thành (tên miền, phần còn lại). Bỏ 'user:pass@' và ':cổng' khỏi tên miền.

    'https://lighthuman.vn:x@facebook.com/abc' -> ('facebook.com', '/abc')
    """
    g = re.sub(r"^[a-z][a-z0-9+.\-]*://", "", url.lower())
    m = re.match(r"[^/?#]*", g)
    authority, con_lai = m.group(0), g[m.end():]
    host = authority.rsplit("@", 1)[-1]            # phần sau '@' cuối cùng mới là tên miền thật
    host = host.split(":", 1)[0].rstrip(".,;)")
    return host.removeprefix("www."), con_lai


def _ten_mien(url: str) -> str:
    """Lấy tên miền (host) từ chuỗi link: 'https://www.abc.vn/x' -> 'abc.vn'."""
    return _tach_link(url)[0]


def _duoc_phep(loai: str, gia_tri: str) -> bool:
    g = gia_tri.lower()
    if loai == "Số điện thoại":
        so = re.sub(r"\D", "", g)
        duoc = _sdt_duoc_phep()
        return so in duoc or so.removeprefix("84") in {x[1:] for x in duoc}
    if loai == "Email":
        return g in _email_duoc_phep()
    if loai == "Đường link":
        if g.rstrip(".,;)") in TEN_CONG_NGHE:
            return True
        host, con_lai = _tach_link(g)
        # So khớp đúng tên miền (hoặc tên miền con), không so chuỗi con
        if not any(host == dm or host.endswith("." + dm) for dm in _ten_mien_duoc_phep()):
            return False
        # Link Light Human nhưng nhúng link khác trong đường dẫn/query (?u=facebook.com/...) -> chặn
        return not any(not _duoc_phep("Đường link", m.group(0)) for m in MAU["Đường link"].finditer(con_lai))
    return False


def _la_ngay_sinh(text: str, m: re.Match) -> bool:
    if NGU_CANH_SINH.search(text[max(0, m.start() - 30):m.start()]):
        return True
    return NAM_SINH_TU <= int(m.group("nam")) <= NAM_SINH_DEN


def scan_text(text: str) -> list[tuple[str, str]]:
    """Tìm thông tin nhạy cảm trong 1 chuỗi. Trả [(loại, giá trị)]."""
    kq = []
    for loai, mau in MAU.items():
        for m in mau.finditer(text or ""):
            if loai == "Ngày sinh đầy đủ" and not _la_ngay_sinh(text, m):
                continue
            if not _duoc_phep(loai, m.group(0)):
                kq.append((loai, m.group(0)))
    return kq


def scan_pii(data, duong_dan: str = "") -> list[dict]:
    """Duyệt TOÀN BỘ chuỗi trong JSON. Trả [{field, loai, gia_tri}]."""
    loi = []
    if isinstance(data, dict):
        for k, v in data.items():
            if not duong_dan and k in BO_QUA:
                continue
            # Nhãn dạng "Zalo" / "Facebook" + nội dung ở trường bên cạnh = thông tin liên hệ
            if k == "label" and isinstance(v, str) and NHAN_MXH.fullmatch(v.strip()):
                loi.append({"field": f"{duong_dan}.{k}" if duong_dan else k,
                            "loai": "Mạng xã hội", "gia_tri": v.strip()})
            loi += scan_pii(v, f"{duong_dan}.{k}" if duong_dan else k)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            loi += scan_pii(v, f"{duong_dan}[{i}]")
    elif isinstance(data, str):
        for loai, gt in scan_text(data):
            loi.append({"field": duong_dan, "loai": loai, "gia_tri": gt})
    return loi


def scan_pii_xuat(cv: dict, project: str, position: str) -> list[dict]:
    """Quét mọi chữ sẽ vào PDF: hồ sơ + tên dự án (header) + vị trí (header, tên file)."""
    loi = scan_pii(cv)
    for ten, gia_tri in (("Tên dự án", project), ("Vị trí", position)):
        for loai, gt in scan_text(gia_tri or ""):
            loi.append({"field": ten, "loai": loai, "gia_tri": gt})
    return loi


def pdf_sach(checklist: list[dict] | None) -> bool:
    """PDF thành phẩm không còn thông tin liên hệ của ứng viên (mục 'pii' của scan_pdf)."""
    muc = [r for r in (checklist or []) if r.get("ma") == "pii"]
    return bool(muc) and all(r["ok"] for r in muc)


# A6 (đã xác nhận là chủ ý): checklist chỉ báo lỗi khi trang cuối dùng < 15% chiều cao. KHÁC ngưỡng 30% ở
# render.py: 30% là mức app CỐ thu nhỏ chữ để lấp đầy; thu nhỏ không phải lúc nào cũng đạt 30%, nên chỉ coi
# là lỗi thật khi trang cuối gần như trống (< 15%).
NGUONG_TRANG_CUOI_BAO_LOI = 0.15


def kiem_tra_font(fonts: list[tuple]) -> dict:
    """Mục checklist 'font serif đã nhúng' từ danh sách `page.get_fonts()` của PyMuPDF.

    Mỗi phần tử: (xref, đuôi file font, loại, basefont, tên, encoding).
    N1: font Type3 (Chromium dùng cho ký tự không có trong Times New Roman, vd '▸') luôn được định nghĩa
    ngay trong PDF -> coi là ĐÃ nhúng, dù PyMuPDF báo đuôi 'n/a' và không có tên.
    """
    ten_font = sorted({f[3] for f in fonts if f[3]})
    serif = [n for n in ten_font if re.search(r"Times|Liberation.?Serif|Serif", n, re.I)]
    chua_nhung = sorted({f[3] or "(không tên)" for f in fonts if f[1] in ("n/a", "") and f[2] != "Type3"})
    co_type3 = any(f[2] == "Type3" for f in fonts)
    chi_tiet = f"Font: {', '.join(ten_font)}"
    if co_type3:
        chi_tiet += " (+ ký hiệu dạng Type3, đã nhúng)"
    if chua_nhung:
        chi_tiet += f" — CHƯA nhúng: {chua_nhung}"
    return {"ma": "font", "muc": "Font serif (Times New Roman / Liberation Serif) đã nhúng",
            "ok": bool(serif) and not chua_nhung, "chi_tiet": chi_tiet}


def scan_pdf(pdf_path: Path) -> list[dict]:
    """Checklist cho PDF thành phẩm. Trả [{muc, ok, chi_tiet}]."""
    import pymupdf as fitz
    from services.pdf.pdf_utils import pdf_layout

    kq = []
    with fitz.open(pdf_path) as doc:
        text = "\n".join(p.get_text() for p in doc)

        # 1. Font serif đã nhúng
        kq.append(kiem_tra_font([f for p in doc for f in p.get_fonts()]))

        # 2. Không còn thông tin liên hệ của ứng viên
        vi_pham = scan_text(text)
        kq.append({"ma": "pii", "muc": "Không còn SĐT, email, link, ngày sinh của ứng viên",
                   "ok": not vi_pham,
                   "chi_tiet": "; ".join(f"{l}: {g}" for l, g in vi_pham) or "Sạch"})

        # 3. Header đúng chuẩn
        kq.append({"ma": "header", "muc": "Header: có 'HỒ SƠ ỨNG VIÊN', không có 'Candidate Profile'",
                   "ok": "HỒ SƠ ỨNG VIÊN" in text.upper() and "candidate profile" not in text.lower(),
                   "chi_tiet": ""})

        # 4. Tiêu đề PDF = tên file
        title = (doc.metadata or {}).get("title", "")
        kq.append({"ma": "tieu_de", "muc": "Tiêu đề PDF trùng tên file",
                   "ok": title == Path(pdf_path).stem,
                   "chi_tiet": f"Tiêu đề: {title}"})

    # 5. Trang cuối không gần trống
    so_trang, do_day = pdf_layout(pdf_path)
    kq.append({"ma": "trang_cuoi", "muc": "Trang cuối không gần trống",
               "ok": so_trang == 1 or do_day >= NGUONG_TRANG_CUOI_BAO_LOI,
               "chi_tiet": f"{so_trang} trang, trang cuối dùng {do_day:.0%}"})
    return kq
