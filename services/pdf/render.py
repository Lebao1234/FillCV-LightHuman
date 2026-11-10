"""Bước 2: dựng JSON hồ sơ thành HTML rồi xuất PDF chuẩn Light Human.

Hàm chính: build_pdf(cv, project, position, photo_bytes, out_dir) -> Path
"""
import base64
import io
import json
import logging
import re
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape
from PIL import Image, ImageOps

from infra.settings import THU_MUC as GOC_DU_AN, DUOI_ANH, cong_ty, logo_pdf, phien_ban_prompt, render_timeout
from infra.logging_setup import lay_run_id
from services.pdf.pdf_utils import pdf_layout  # A3: hàm đo bố cục PDF nằm ở module riêng
from infra.tokens import FONT, PDF_LE_MM, css_vars

log = logging.getLogger("render")   # giữ tên cũ cho log

THU_MUC = Path(__file__).parent          # services/pdf/ — chứa template.html
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Các mức cỡ chữ thử lần lượt (mục 4.5 SKILL.md): (cỡ chữ pt, line-height, thu gọn khoảng cách)
CO_CHU = [(11.5, 1.42, False), (11.0, 1.38, True), (10.8, 1.34, True)]
# A6 (đã xác nhận là chủ ý): trang cuối dùng < 30% chiều cao -> thử cỡ chữ nhỏ hơn để lấp đầy.
# KHÁC ngưỡng 15% của checklist (checks.NGUONG_TRANG_CUOI_BAO_LOI): 30% là mức CỐ đạt, 15% mới là lỗi thật.
TRANG_CUOI_GAN_TRONG = 0.30


# ---------------------------------------------------------------------------
# Tên file (mục 3.6)
# ---------------------------------------------------------------------------

def khong_dau(s: str) -> str:
    """Bỏ dấu tiếng Việt: 'Đặng Thị Lan' -> 'Dang Thi Lan'."""
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def hom_nay_vn() -> date:
    return datetime.now(VN_TZ).date()


def build_filename(position: str, full_name: str, d: date | None = None) -> str:
    """'LH - CV <Vị trí> - <Họ tên> - <ddmmyyyy>.pdf', không dấu."""
    d = d or hom_nay_vn()

    def sach(x: str) -> str:
        x = khong_dau(x)
        x = re.sub(r'[\\/:*?"<>|]', " ", x)       # ký tự cấm trong tên file
        return re.sub(r"\s+", " ", x).strip()

    return f"LH - CV {sach(position)} - {sach(full_name)} - {d:%d%m%Y}.pdf"


# ---------------------------------------------------------------------------
# Ảnh: logo + chân dung
# ---------------------------------------------------------------------------

def _data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def cat_logo(src: Path, rong: int) -> Image.Image:
    """Cắt sát viền trong suốt của logo và đưa về chiều rộng `rong` px (giữ tỉ lệ).

    Dùng chung cho logo trong PDF (prepare_logo) và logo trên header web app.
    """
    with Image.open(src) as goc:                      # Q3: đóng file logo sau khi đọc
        im = goc.convert("RGBA")
    im = im.crop(im.getbbox())
    return im.resize((rong, round(im.height * rong / im.width)), Image.LANCZOS)


def prepare_logo(src: Path, dst: Path | None = None) -> None:
    """Cắt sát viền trong suốt và thu về ~1200px rộng (chạy 1 lần khi đổi logo). Mặc định ghi vào logo PDF."""
    cat_logo(src, 1200).save(dst or logo_pdf(), optimize=True)


TI_LE_ANH = 29 / 38               # khung ảnh chân dung 29x38 mm (mục 4.3 SKILL.md)

# ----- Tham số ảnh chân dung (bảng hardcode). Giá trị đã kiểm chứng bằng ảnh thật khi làm tính năng lấy ảnh;
# đổi giá trị nào thì chạy lại test ảnh và thử với vài CV thật. -----
MAT_ANH_TOI_DA_PX = 1600          # ảnh lớn hơn được thu nhỏ trước khi tìm mặt (cho nhanh)
MAT_SCALE_FACTOR = 1.1            # bước phóng của bộ dò Haar
MAT_MIN_NEIGHBORS = 6             # cao hơn = ít nhận nhầm chữ/hoa văn là mặt, nhưng dễ bỏ sót
MAT_KICH_THUOC_MIN_PX = 28        # bỏ qua "mặt" nhỏ hơn 28px
KHUNG_RONG_GAP_MAT = 2.4          # khung cắt rộng ~2.4 lần khuôn mặt (lấy đầu + vai)
KHUNG_TAM_MAT_DOC = 0.40          # tâm khuôn mặt nằm ở 40% chiều cao khung
AVATAR_TRON_MIN_PX = 40           # vùng không trong suốt nhỏ hơn -> không coi là avatar tròn
AVATAR_TRON_LUI_GOC = 0.04        # lùi vào 4% khi xét góc (tránh viền răng cưa)
AVATAR_TRON_ALPHA_TRONG = 32      # alpha <= 32 coi là trong suốt
AVATAR_TRON_HE_SO = 0.98          # thu khung trong elip thêm 2% cho chắc không chạm viền
ANH_RONG_TOI_DA_PX = 600          # ảnh chân dung lưu tối đa 600px rộng
ANH_JPEG_QUALITY = 90
TI_LE_DOC = (1.05, 1.9)           # cao/rộng của ảnh "dọc" — chỉ nhận ảnh dọc khi KHÔNG tìm thấy mặt
TI_LE_CHAP_NHAN = (0.7, 1.9)      # cao/rộng chấp nhận (vuông, tròn, dọc)
ANH_NEN_TY_LE_TRANG = 0.35        # ảnh hiển thị > 35% diện tích trang = ảnh nền / trang scan
ANH_NHUNG_MIN_PX = 80             # ảnh nhúng nhỏ hơn 80px -> icon
ANH_HIEN_THI_MIN_PT = 40          # ảnh hiển thị nhỏ hơn 40pt -> icon
DPI_TRANG_SCAN = 200              # độ phân giải dựng trang PDF scan để tìm mặt
SO_TRANG_TIM_ANH = 2              # ảnh chân dung thường ở 1–2 trang đầu


@lru_cache(maxsize=1)
def _bo_nhan_dien_mat():
    """Bộ nhận diện khuôn mặt Haar của OpenCV. Không cài OpenCV -> None (bỏ qua bước tìm mặt)."""
    try:
        import cv2
    except ImportError:
        return None
    bo = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return None if bo.empty() else bo


def _tim_mat(im: Image.Image) -> tuple[int, int, int, int] | None:
    """Tìm khuôn mặt lớn nhất trong ảnh. Trả (x, y, w, h) theo pixel của ảnh gốc, hoặc None."""
    bo = _bo_nhan_dien_mat()
    if bo is None:
        return None
    import cv2
    import numpy as np

    xam = np.array(im.convert("L"))
    ty_le = min(1.0, MAT_ANH_TOI_DA_PX / max(xam.shape))            # ảnh quá lớn -> thu nhỏ cho nhanh
    if ty_le < 1:
        xam = cv2.resize(xam, None, fx=ty_le, fy=ty_le, interpolation=cv2.INTER_AREA)
    mat = bo.detectMultiScale(xam, scaleFactor=MAT_SCALE_FACTOR, minNeighbors=MAT_MIN_NEIGHBORS,
                               minSize=(MAT_KICH_THUOC_MIN_PX, MAT_KICH_THUOC_MIN_PX))
    if len(mat) == 0:
        return None
    x, y, w, h = max(mat, key=lambda m: m[2] * m[3])
    return tuple(int(round(v / ty_le)) for v in (x, y, w, h))


def khung_quanh_mat(kich_thuoc: tuple[int, int], mat: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Khung 29:38 lấy đầu + vai quanh khuôn mặt (mục 4.3 SKILL.md: selfie cắt quanh khuôn mặt).

    Rộng ~2.4 lần khuôn mặt, tâm mặt ở ~40% chiều cao khung; không vượt ra ngoài ảnh.
    """
    W, H = kich_thuoc
    x, y, w, h = mat
    bw = w * KHUNG_RONG_GAP_MAT
    bh = bw / TI_LE_ANH
    k = min(1.0, W / bw, H / bh)                      # khung lớn hơn ảnh -> thu nhỏ, giữ tỉ lệ
    bw, bh = bw * k, bh * k
    cx, cy = x + w / 2, y + h / 2
    left = min(max(cx - bw / 2, 0), W - bw)
    top = min(max(cy - bh * KHUNG_TAM_MAT_DOC, 0), H - bh)
    return round(left), round(top), round(left + bw), round(top + bh)


def _khung_trong_avatar_tron(alpha: Image.Image) -> tuple[int, int, int, int] | None:
    """Avatar tròn/bo góc (4 góc trong suốt): trả khung 29:38 lớn nhất nằm gọn trong hình elip.

    Ảnh không trong suốt ở góc (ảnh tách nền bình thường...) -> None.
    """
    bbox = alpha.getbbox()
    if not bbox:
        return None
    l, t, r, b = bbox
    bw, bh = r - l, b - t
    if bw < AVATAR_TRON_MIN_PX or bh < AVATAR_TRON_MIN_PX:
        return None
    lui = AVATAR_TRON_LUI_GOC
    goc = [(l + bw * lui, t + bh * lui), (r - 1 - bw * lui, t + bh * lui),
           (l + bw * lui, b - 1 - bh * lui), (r - 1 - bw * lui, b - 1 - bh * lui)]
    if any(alpha.getpixel((round(x), round(y))) > AVATAR_TRON_ALPHA_TRONG for x, y in goc):
        return None
    A, B, k = bw / 2, bh / 2, TI_LE_ANH                # elip bán trục A, B; khung rộng/cao = k
    h = 2 * A * B / (k * k * B * B + A * A) ** 0.5 * AVATAR_TRON_HE_SO
    w = h * k
    cx, cy = l + A, t + B
    return round(cx - w / 2), round(cy - h / 2), round(cx + w / 2), round(cy + h / 2)


def crop_portrait(img_bytes: bytes) -> bytes:
    """Cắt theo tỉ lệ 29:38 (quanh khuôn mặt nếu tìm thấy, không thì cắt giữa), KHÔNG mặt nạ tròn. Trả JPEG."""
    im = Image.open(io.BytesIO(img_bytes))
    im = ImageOps.exif_transpose(im)                  # xoay đúng chiều ảnh chụp từ điện thoại
    khung_tron = None
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")                       # ảnh đã tách nền -> đặt lên nền trắng
        khung_tron = _khung_trong_avatar_tron(im.getchannel("A"))
        nen = Image.new("RGB", im.size, "white")
        nen.paste(im, mask=im.getchannel("A"))
        im = nen
    else:
        im = im.convert("RGB")
    w, h = im.size
    ti_le = TI_LE_ANH
    mat = None if khung_tron else _tim_mat(im)
    if khung_tron:             # avatar tròn/bo góc -> khung 29:38 nằm gọn bên trong, không lộ góc
        box = khung_tron
    elif mat:                  # có khuôn mặt -> cắt đầu + vai quanh mặt
        box = khung_quanh_mat((w, h), mat)
    elif w / h > ti_le:        # ảnh quá rộng -> cắt bớt hai bên
        nw = round(h * ti_le)
        box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    else:                      # ảnh quá cao -> cắt bớt, ưu tiên giữ phần trên (khuôn mặt)
        nh = round(w / ti_le)
        top = min((h - nh) // 4, h - nh)
        box = (0, top, w, top + nh)
    im = im.crop(box)
    if im.width > ANH_RONG_TOI_DA_PX:
        im = im.resize((ANH_RONG_TOI_DA_PX, round(ANH_RONG_TOI_DA_PX / ti_le)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=ANH_JPEG_QUALITY)
    return out.getvalue()


def _chon_anh(ung_vien: list[tuple[bytes, float, int]]) -> bytes | None:
    """Chọn ảnh chân dung từ danh sách (ảnh, tỉ lệ cao/rộng khi hiển thị, độ ưu tiên vị trí).

    Có khuôn mặt -> ưu tiên. Không tìm được mặt -> chỉ nhận ảnh dọc (tránh lấy nhầm logo, mã QR vuông).
    """
    tot = None
    for data, ti_le, uu_tien in ung_vien:
        try:
            with Image.open(io.BytesIO(data)) as goc:  # Q3
                im = goc.copy()
        except Exception:
            # R3: ảnh nhúng không đọc được (EMF, hỏng...) là chuyện thường gặp -> WARNING, bỏ qua ảnh đó
            log.warning("Bỏ qua một ảnh ứng viên không đọc được", exc_info=True)
            continue
        co_mat = _tim_mat(im) is not None
        if not co_mat and not (TI_LE_DOC[0] <= ti_le <= TI_LE_DOC[1]):
            continue
        diem = (co_mat, uu_tien, im.width * im.height)
        if tot is None or diem > tot[0]:
            tot = (diem, data)
    return crop_portrait(tot[1]) if tot else None


def extract_photo_from_pdf(pdf_bytes: bytes) -> bytes | None:
    """Tìm ảnh chân dung trong PDF gốc. Không có -> None.

    - Ảnh nhúng: nhận cả ảnh dọc, vuông, bo tròn; lọc theo kích thước HIỂN THỊ trên trang
      (bỏ icon nhỏ, bỏ ảnh nền/ảnh scan chiếm cả trang).
    - PDF scan (cả trang là 1 ảnh): dựng ảnh trang 1 rồi tìm khuôn mặt.
    """
    import pymupdf as fitz  # PyMuPDF

    ung_vien, co_anh_scan = [], False
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for so, page in enumerate(doc[:SO_TRANG_TIM_ANH]):
            dien_tich_trang = page.rect.width * page.rect.height
            for info in page.get_images(full=True):
                xref, w, h = info[0], info[2], info[3]
                rects = page.get_image_rects(xref)
                r = max(rects, key=lambda r: r.width * r.height) if rects else None
                if r is not None and r.width * r.height > ANH_NEN_TY_LE_TRANG * dien_tich_trang:
                    co_anh_scan = co_anh_scan or so == 0
                    continue
                if w < ANH_NHUNG_MIN_PX or h < ANH_NHUNG_MIN_PX or (r is not None and min(r.width, r.height) < ANH_HIEN_THI_MIN_PT):
                    continue                          # icon / ảnh quá nhỏ
                ti_le = r.height / r.width if r is not None else h / w
                if not (TI_LE_CHAP_NHAN[0] <= ti_le <= TI_LE_CHAP_NHAN[1]):
                    continue
                pix = fitz.Pixmap(doc, xref)
                if pix.n - pix.alpha >= 4:            # CMYK -> RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                smask = info[1]                       # lớp trong suốt (avatar tròn) nằm ở ảnh riêng
                if smask and not pix.alpha:
                    try:
                        pix = fitz.Pixmap(pix, fitz.Pixmap(doc, smask))
                    except Exception:
                        log.warning("Không ghép được lớp trong suốt của ảnh, dùng ảnh gốc", exc_info=True)
                ung_vien.append((pix.tobytes("png"), ti_le, -so))
        anh = _chon_anh(ung_vien)
        if anh is None and co_anh_scan:
            trang = doc[0].get_pixmap(dpi=DPI_TRANG_SCAN).tobytes("png")
            anh = extract_photo_from_image(trang)
    return anh


def extract_photo_from_image(img_bytes: bytes) -> bytes | None:
    """CV dạng ảnh (hoặc ảnh 1 trang PDF scan): tìm khuôn mặt rồi cắt quanh mặt. Không có mặt -> None."""
    with Image.open(io.BytesIO(img_bytes)) as goc:   # Q3
        im = ImageOps.exif_transpose(goc)
    if _tim_mat(im) is None:
        return None
    return crop_portrait(img_bytes)


def extract_photo_from_docx(docx_bytes: bytes) -> bytes | None:
    """Lấy ảnh chân dung trong DOCX (ảnh nằm trong word/media/)."""
    ung_vien = []
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        for ten in z.namelist():
            if not re.match(r"word/media/.+\.(png|jpe?g|bmp|gif|tiff?)$", ten, re.IGNORECASE):
                continue
            data = z.read(ten)
            try:
                with Image.open(io.BytesIO(data)) as im:
                    w, h = im.size
            except Exception:
                log.warning("Bỏ qua một ảnh trong DOCX không đọc được", exc_info=True)
                continue
            if w >= ANH_NHUNG_MIN_PX and h >= ANH_NHUNG_MIN_PX and TI_LE_CHAP_NHAN[0] <= h / w <= TI_LE_CHAP_NHAN[1]:
                ung_vien.append((data, h / w, 0))
    return _chon_anh(ung_vien)


def extract_photo(file_bytes: bytes, filename: str) -> bytes | None:
    """Lấy ảnh chân dung từ CV gốc theo loại file. Lỗi bất kỳ -> None (không chặn luồng làm hồ sơ)."""
    duoi = Path(filename).suffix.lower()
    try:
        if duoi == ".pdf":
            return extract_photo_from_pdf(file_bytes)
        if duoi == ".docx":
            return extract_photo_from_docx(file_bytes)
        if duoi in DUOI_ANH:
            return extract_photo_from_image(file_bytes)
    except Exception:
        log.exception("Lấy ảnh chân dung thất bại (file .%s) — hồ sơ tiếp tục không có ảnh", duoi.lstrip("."))
        return None
    return None


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def bold_filter(text) -> Markup:
    """Đổi **cụm từ** thành <span class="k">cụm từ</span>. Escape trước để an toàn."""
    safe = str(escape(text or ""))
    return Markup(re.sub(r"\*\*(.+?)\*\*", r'<span class="k">\1</span>', safe))


_env = Environment(loader=FileSystemLoader(str(THU_MUC)), autoescape=select_autoescape(["html"]))
_env.filters["bold"] = bold_filter


def render_html(cv: dict, project: str, title: str, photo_bytes: bytes | None = None,
                font_size: float = 11.5, line_height: float = 1.42, compact: bool = False) -> str:
    return _env.get_template("template.html").render(
        cv=cv,
        project=(project or "").strip(),
        title=title,
        logo=_data_uri(logo_pdf().read_bytes(), "image/png"),
        photo=_data_uri(photo_bytes, "image/jpeg") if photo_bytes else None,
        font_size=font_size, line_height=line_height, compact=compact,
        ct=cong_ty()["cong_ty"],                          # A4: header công ty
        ref_note=cong_ty()["pdf"]["ghi_chu_tham_chieu"],  # A4
        tokens_pdf=css_vars("pdf"),
        le=PDF_LE_MM,                                     # A7
        font_serif=FONT["serif-pdf"],
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def html_to_pdf(html: str, pdf_path: Path) -> None:
    """Dựng 1 bản PDF (xem html_to_pdf_nhieu)."""
    html_to_pdf_nhieu([html], [pdf_path])


def html_to_pdf_nhieu(cac_html: list[str], cac_pdf: list[Path]) -> None:
    """Dựng nhiều bản PDF trong MỘT lần gọi render_worker.py (1 tiến trình Python + 1 Chromium).

    Tiến trình riêng: xem giải thích trong render_worker.py.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cac_viec = []
        for i, (html, pdf) in enumerate(zip(cac_html, cac_pdf, strict=True)):
            f = Path(tmp) / f"cv_{i}.html"
            f.write_text(html, encoding="utf-8")
            cac_viec.append([str(f), str(pdf)])
        danh_sach = Path(tmp) / "viec.json"
        danh_sach.write_text(json.dumps(cac_viec), encoding="utf-8")
        try:
            kq = subprocess.run(
                [sys.executable, "-m", "services.pdf.render_worker", str(danh_sach), lay_run_id()],
                cwd=GOC_DU_AN,                  # chạy module trong package -> thư mục làm việc phải là gốc dự án
                capture_output=True, text=True, timeout=render_timeout(),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Trình dựng PDF (Chromium) không phản hồi sau {render_timeout()} giây. "
                               "Kiểm tra đã cài 'playwright install chromium' rồi thử lại.")
    if kq.returncode != 0:
        # S5: chi tiết kỹ thuật (đường dẫn máy, traceback) chỉ vào log, giao diện chỉ hiện câu ngắn
        log.error("render_worker lỗi (mã %s):\n%s", kq.returncode, kq.stderr[-4000:])
        raise RuntimeError("Trình dựng PDF (Chromium) gặp lỗi. Chi tiết đã ghi vào log; "
                           "hãy thử lại, nếu vẫn lỗi hãy báo người quản trị.")


def build_pdf(cv: dict, project: str, position: str, photo_bytes: bytes | None,
              out_dir: Path, d: date | None = None) -> Path:
    """Dựng PDF, tự chọn cỡ chữ để không có trang cuối gần trống."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ten = build_filename(position or cv.get("target_title") or "", cv["full_name"], d)
    title = ten[:-4]
    dich = out_dir / ten

    with tempfile.TemporaryDirectory() as tmp:
        # Dựng sẵn cả 3 cỡ chữ trong 1 lần mở Chromium (rẻ hơn nhiều so với mở lại cho mỗi cỡ chữ)
        cac_ban = [Path(tmp) / f"thu_{i}.pdf" for i in range(len(CO_CHU))]
        html_to_pdf_nhieu([render_html(cv, project, title, photo_bytes, fs, lh, compact) for fs, lh, compact in CO_CHU],
                          cac_ban)
        chon = chon_co_chu([pdf_layout(p) for p in cac_ban])
        dich.write_bytes(ghi_metadata(cac_ban[chon].read_bytes()))
    return dich


def chon_co_chu(bo_cuc: list[tuple[int, float]]) -> int:
    """Chọn bản dùng trong các bản thử cỡ chữ [(số trang, độ đầy trang cuối), ...] — đúng luật cũ:

    bản đầu (cỡ chuẩn) ổn (trang cuối đủ đầy hoặc chỉ 1 trang) -> dùng; không thì lấy bản chữ nhỏ ĐẦU TIÊN
    giúp bớt được 1 trang so với bản đầu; không bản nào bớt được trang -> vẫn dùng bản đầu.
    """
    so_trang_dau, do_day_dau = bo_cuc[0]
    if do_day_dau >= TRANG_CUOI_GAN_TRONG or so_trang_dau == 1:
        return 0
    for i, (so_trang, _) in enumerate(bo_cuc[1:], start=1):
        if so_trang < so_trang_dau:
            return i
    return 0


def ghi_metadata(pdf_bytes: bytes) -> bytes:
    """Ghi phiên bản prompt vào metadata PDF (trường keywords) — biết hồ sơ được tạo từ prompt nào.

    Giữ nguyên tiêu đề (= tên file, checklist kiểm tra) và mọi metadata khác; nội dung trang không đổi.
    """
    import pymupdf as fitz
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        meta = dict(doc.metadata or {})
        meta["keywords"] = f"FillCV-LightHuman; prompt {phien_ban_prompt()}"
        doc.set_metadata(meta)
        return doc.tobytes()
