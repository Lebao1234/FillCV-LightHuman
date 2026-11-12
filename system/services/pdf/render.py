# Gói services/pdf/: dựng PDF — template.html -> HTML -> Chromium (render_worker, tiến trình riêng).
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

from infra.settings import PROJECT_ROOT, IMAGE_EXTENSIONS, company, logo_pdf, render_timeout
from infra.logging_setup import get_run_id
from services.extraction import base as extraction
from services.pdf.pdf_utils import pdf_layout  # A3: hàm đo bố cục PDF nằm ở module riêng
from infra.tokens import FONT, PDF_MARGIN_MM, css_vars

log = logging.getLogger("render")   # giữ tên cũ cho log

TEMPLATE_DIR = Path(__file__).parent          # services/pdf/ — chứa template.html
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Các mức cỡ chữ thử lần lượt (mục 4.5 SKILL.md): (cỡ chữ pt, line-height, thu gọn khoảng cách)
FONT_SIZE_ATTEMPTS = [(11.5, 1.42, False), (11.0, 1.38, True), (10.8, 1.34, True)]
# A6 (đã xác nhận là chủ ý): trang cuối dùng < 30% chiều cao -> thử cỡ chữ nhỏ hơn để lấp đầy.
# KHÁC ngưỡng 15% của checklist (checks.LAST_PAGE_ERROR_FILL): 30% là mức CỐ đạt, 15% mới là lỗi thật.
LAST_PAGE_MIN_FILL = 0.30


# ---------------------------------------------------------------------------
# Tên file (mục 3.6)
# ---------------------------------------------------------------------------

# Bỏ dấu tiếng Việt
def strip_accents(s: str) -> str:
    """Bỏ dấu tiếng Việt: 'Đặng Thị Lan' -> 'Dang Thi Lan'."""
    s = (s or "").replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Ngày hôm nay theo giờ Việt Nam
def today_vn() -> date:
    return datetime.now(VN_TZ).date()


# Tên file PDF chuẩn
def build_filename(position: str, full_name: str, d: date | None = None) -> str:
    """'LH - CV <Vị trí> - <Họ tên> - <ddmmyyyy>.pdf', không dấu."""
    d = d or today_vn()

    # Làm sạch một phần tên file
    def clean(x: str) -> str:
        x = strip_accents(x)
        x = re.sub(r'[\\/:*?"<>|]', " ", x)       # ký tự cấm trong tên file
        return re.sub(r"\s+", " ", x).strip()

    return f"LH - CV {clean(position)} - {clean(full_name)} - {d:%d%m%Y}.pdf"


# ---------------------------------------------------------------------------
# Ảnh: logo + chân dung
# ---------------------------------------------------------------------------

# Đổi bytes thành data URI
def _data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


# Cắt sát viền logo và đổi cỡ
def crop_logo(src: Path, width: int) -> Image.Image:
    """Cắt sát viền trong suốt của logo và đưa về chiều rộng `width` px (giữ tỉ lệ).

    Dùng chung cho logo trong PDF (prepare_logo) và logo trên header web app.
    """
    with Image.open(src) as orig_img:                      # Q3: đóng file logo sau khi đọc
        im = orig_img.convert("RGBA")
    im = im.crop(im.getbbox())
    return im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)


# Chuẩn bị file logo PDF
def prepare_logo(src: Path, dst: Path | None = None) -> None:
    """Cắt sát viền trong suốt và thu về ~1200px rộng (chạy 1 lần khi đổi logo). Mặc định ghi vào logo PDF."""
    crop_logo(src, 1200).save(dst or logo_pdf(), optimize=True)


PHOTO_ASPECT = 29 / 38               # khung ảnh chân dung 29x38 mm (mục 4.3 SKILL.md)

# ----- Tham số ảnh chân dung (bảng hardcode). Giá trị đã kiểm chứng bằng ảnh thật khi làm tính năng lấy ảnh;
# đổi giá trị nào thì chạy lại test ảnh và thử với vài CV thật. -----
FACE_DETECT_MAX_PX = 1600          # ảnh lớn hơn được thu nhỏ trước khi tìm mặt (cho nhanh)
FACE_SCALE_FACTOR = 1.1            # bước phóng của bộ dò Haar
FACE_MIN_NEIGHBORS = 6             # cao hơn = ít nhận nhầm chữ/hoa văn là mặt, nhưng dễ bỏ sót
FACE_MIN_SIZE_PX = 28        # bỏ qua "mặt" nhỏ hơn 28px
CROP_WIDTH_PER_FACE = 2.4          # khung cắt rộng ~2.4 lần khuôn mặt (lấy đầu + vai)
CROP_FACE_CENTER_Y = 0.40          # tâm khuôn mặt nằm ở 40% chiều cao khung
ROUND_AVATAR_MIN_PX = 40           # vùng không trong suốt nhỏ hơn -> không coi là avatar tròn
ROUND_AVATAR_CORNER_INSET = 0.04        # lùi vào 4% khi xét góc (tránh viền răng cưa)
ROUND_AVATAR_TRANSPARENT_ALPHA = 32      # alpha <= 32 coi là trong suốt
ROUND_AVATAR_SHRINK = 0.98          # thu khung trong elip thêm 2% cho chắc không chạm viền
PHOTO_MAX_WIDTH_PX = 600          # ảnh chân dung lưu tối đa 600px rộng
PHOTO_JPEG_QUALITY = 90
PORTRAIT_ASPECT = (1.05, 1.9)           # cao/rộng của ảnh "dọc" — chỉ nhận ảnh dọc khi KHÔNG tìm thấy mặt
ACCEPTED_ASPECT = (0.7, 1.9)      # cao/rộng chấp nhận (vuông, tròn, dọc)
BACKGROUND_IMAGE_PAGE_RATIO = 0.35        # ảnh hiển thị > 35% diện tích trang = ảnh nền / trang scan
EMBEDDED_IMAGE_MIN_PX = 80             # ảnh nhúng nhỏ hơn 80px -> icon
PHOTO_DISPLAY_MIN_PT = 40          # ảnh hiển thị nhỏ hơn 40pt -> icon
SCANNED_PAGE_DPI = 200              # độ phân giải dựng trang PDF scan để tìm mặt
PHOTO_SEARCH_PAGES = 2              # ảnh chân dung thường ở 1–2 trang đầu


# Bộ nhận diện khuôn mặt OpenCV (cache)
@lru_cache(maxsize=1)
def _face_detector():
    """Bộ nhận diện khuôn mặt Haar của OpenCV. Không cài OpenCV -> None (bỏ qua bước tìm mặt)."""
    try:
        import cv2
    except ImportError:
        return None
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return None if detector.empty() else detector


# Tìm khuôn mặt lớn nhất
def _find_face(im: Image.Image) -> tuple[int, int, int, int] | None:
    """Tìm khuôn mặt lớn nhất trong ảnh. Trả (x, y, w, h) theo pixel của ảnh gốc, hoặc None."""
    detector = _face_detector()
    if detector is None:
        return None
    import cv2
    import numpy as np

    gray = np.array(im.convert("L"))
    scale = min(1.0, FACE_DETECT_MAX_PX / max(gray.shape))            # ảnh quá lớn -> thu nhỏ cho nhanh
    if scale < 1:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    face = detector.detectMultiScale(gray, scaleFactor=FACE_SCALE_FACTOR, minNeighbors=FACE_MIN_NEIGHBORS,
                               minSize=(FACE_MIN_SIZE_PX, FACE_MIN_SIZE_PX))
    if len(face) == 0:
        return None
    x, y, w, h = max(face, key=lambda m: m[2] * m[3])
    return tuple(int(round(v / scale)) for v in (x, y, w, h))


# Khung 29:38 quanh khuôn mặt
def box_around_face(size: tuple[int, int], face: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Khung 29:38 lấy đầu + vai quanh khuôn mặt (mục 4.3 SKILL.md: selfie cắt quanh khuôn mặt).

    Rộng ~2.4 lần khuôn mặt, tâm mặt ở ~40% chiều cao khung; không vượt ra ngoài ảnh.
    """
    W, H = size
    x, y, w, h = face
    bw = w * CROP_WIDTH_PER_FACE
    bh = bw / PHOTO_ASPECT
    k = min(1.0, W / bw, H / bh)                      # khung lớn hơn ảnh -> thu nhỏ, giữ tỉ lệ
    bw, bh = bw * k, bh * k
    cx, cy = x + w / 2, y + h / 2
    left = min(max(cx - bw / 2, 0), W - bw)
    top = min(max(cy - bh * CROP_FACE_CENTER_Y, 0), H - bh)
    return round(left), round(top), round(left + bw), round(top + bh)


# Khung 29:38 nằm trong avatar tròn
def _box_inside_round_avatar(alpha: Image.Image) -> tuple[int, int, int, int] | None:
    """Avatar tròn/bo góc (4 góc trong suốt): trả khung 29:38 lớn nhất nằm gọn trong hình elip.

    Ảnh không trong suốt ở góc (ảnh tách nền bình thường...) -> None.
    """
    bbox = alpha.getbbox()
    if not bbox:
        return None
    l, t, r, b = bbox
    bw, bh = r - l, b - t
    if bw < ROUND_AVATAR_MIN_PX or bh < ROUND_AVATAR_MIN_PX:
        return None
    inset = ROUND_AVATAR_CORNER_INSET
    corners = [(l + bw * inset, t + bh * inset), (r - 1 - bw * inset, t + bh * inset),
           (l + bw * inset, b - 1 - bh * inset), (r - 1 - bw * inset, b - 1 - bh * inset)]
    if any(alpha.getpixel((round(x), round(y))) > ROUND_AVATAR_TRANSPARENT_ALPHA for x, y in corners):
        return None
    A, B, k = bw / 2, bh / 2, PHOTO_ASPECT                # elip bán trục A, B; khung rộng/cao = k
    h = 2 * A * B / (k * k * B * B + A * A) ** 0.5 * ROUND_AVATAR_SHRINK
    w = h * k
    cx, cy = l + A, t + B
    return round(cx - w / 2), round(cy - h / 2), round(cx + w / 2), round(cy + h / 2)


# Cắt ảnh chân dung 29:38
def crop_portrait(img_bytes: bytes) -> bytes:
    """Cắt theo tỉ lệ 29:38 (quanh khuôn mặt nếu tìm thấy, không thì cắt giữa), KHÔNG mặt nạ tròn. Trả JPEG."""
    im = Image.open(io.BytesIO(img_bytes))
    im = ImageOps.exif_transpose(im)                  # xoay đúng chiều ảnh chụp từ điện thoại
    round_box = None
    if im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")                       # ảnh đã tách nền -> đặt lên nền trắng
        round_box = _box_inside_round_avatar(im.getchannel("A"))
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.getchannel("A"))
        im = bg
    else:
        im = im.convert("RGB")
    w, h = im.size
    ratio = PHOTO_ASPECT
    face = None if round_box else _find_face(im)
    if round_box:             # avatar tròn/bo góc -> khung 29:38 nằm gọn bên trong, không lộ góc
        box = round_box
    elif face:                  # có khuôn mặt -> cắt đầu + vai quanh mặt
        box = box_around_face((w, h), face)
    elif w / h > ratio:        # ảnh quá rộng -> cắt bớt hai bên
        nw = round(h * ratio)
        box = ((w - nw) // 2, 0, (w - nw) // 2 + nw, h)
    else:                      # ảnh quá cao -> cắt bớt, ưu tiên giữ phần trên (khuôn mặt)
        nh = round(w / ratio)
        top = min((h - nh) // 4, h - nh)
        box = (0, top, w, top + nh)
    im = im.crop(box)
    if im.width > PHOTO_MAX_WIDTH_PX:
        im = im.resize((PHOTO_MAX_WIDTH_PX, round(PHOTO_MAX_WIDTH_PX / ratio)), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=PHOTO_JPEG_QUALITY)
    return out.getvalue()


# Chọn ảnh chân dung tốt nhất
def _pick_photo(candidates: list[tuple[bytes, float, int]]) -> bytes | None:
    """Chọn ảnh chân dung từ danh sách (ảnh, tỉ lệ cao/rộng khi hiển thị, độ ưu tiên vị trí).

    Có khuôn mặt -> ưu tiên. Không tìm được mặt -> chỉ nhận ảnh dọc (tránh lấy nhầm logo, mã QR vuông).
    """
    best = None
    for data, ratio, priority in candidates:
        try:
            with Image.open(io.BytesIO(data)) as orig_img:  # Q3
                im = orig_img.copy()
        except Exception:
            # R3: ảnh nhúng không đọc được (EMF, hỏng...) là chuyện thường gặp -> WARNING, bỏ qua ảnh đó
            log.warning("Bỏ qua một ảnh ứng viên không đọc được", exc_info=True)
            continue
        has_face = _find_face(im) is not None
        if not has_face and not (PORTRAIT_ASPECT[0] <= ratio <= PORTRAIT_ASPECT[1]):
            continue
        score = (has_face, priority, im.width * im.height)
        if best is None or score > best[0]:
            best = (score, data)
    return crop_portrait(best[1]) if best else None


# Lấy ảnh chân dung từ PDF
def extract_photo_from_pdf(pdf_bytes: bytes) -> bytes | None:
    """Tìm ảnh chân dung trong PDF gốc. Không có -> None.

    - Ảnh nhúng: nhận cả ảnh dọc, vuông, bo tròn; lọc theo kích thước HIỂN THỊ trên trang
      (bỏ icon nhỏ, bỏ ảnh nền/ảnh scan chiếm cả trang).
    - PDF scan (cả trang là 1 ảnh): dựng ảnh trang 1 rồi tìm khuôn mặt.
    """
    import pymupdf as fitz  # PyMuPDF

    candidates, has_scanned_page = [], False
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for page_no, page in enumerate(doc[:PHOTO_SEARCH_PAGES]):
            page_area = page.rect.width * page.rect.height
            for info in page.get_images(full=True):
                xref, w, h = info[0], info[2], info[3]
                rects = page.get_image_rects(xref)
                r = max(rects, key=lambda r: r.width * r.height) if rects else None
                if r is not None and r.width * r.height > BACKGROUND_IMAGE_PAGE_RATIO * page_area:
                    has_scanned_page = has_scanned_page or page_no == 0
                    continue
                if w < EMBEDDED_IMAGE_MIN_PX or h < EMBEDDED_IMAGE_MIN_PX or (r is not None and min(r.width, r.height) < PHOTO_DISPLAY_MIN_PT):
                    continue                          # icon / ảnh quá nhỏ
                ratio = r.height / r.width if r is not None else h / w
                if not (ACCEPTED_ASPECT[0] <= ratio <= ACCEPTED_ASPECT[1]):
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
                candidates.append((pix.tobytes("png"), ratio, -page_no))
        photo = _pick_photo(candidates)
        if photo is None and has_scanned_page:
            page_png = doc[0].get_pixmap(dpi=SCANNED_PAGE_DPI).tobytes("png")
            photo = extract_photo_from_image(page_png)
    return photo


# Lấy ảnh chân dung từ CV dạng ảnh
def extract_photo_from_image(img_bytes: bytes) -> bytes | None:
    """CV dạng ảnh (hoặc ảnh 1 trang PDF scan): tìm khuôn mặt rồi cắt quanh mặt. Không có mặt -> None."""
    with Image.open(io.BytesIO(img_bytes)) as orig_img:   # Q3
        im = ImageOps.exif_transpose(orig_img)
    if _find_face(im) is None:
        return None
    return crop_portrait(img_bytes)


# Lấy ảnh chân dung từ DOCX
def extract_photo_from_docx(docx_bytes: bytes) -> bytes | None:
    """Lấy ảnh chân dung trong DOCX (ảnh nằm trong word/media/)."""
    candidates = []
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        for filename in z.namelist():
            if not re.match(r"word/media/.+\.(png|jpe?g|bmp|gif|tiff?)$", filename, re.IGNORECASE):
                continue
            data = z.read(filename)
            try:
                with Image.open(io.BytesIO(data)) as im:
                    w, h = im.size
            except Exception:
                log.warning("Bỏ qua một ảnh trong DOCX không đọc được", exc_info=True)
                continue
            if w >= EMBEDDED_IMAGE_MIN_PX and h >= EMBEDDED_IMAGE_MIN_PX and ACCEPTED_ASPECT[0] <= h / w <= ACCEPTED_ASPECT[1]:
                candidates.append((data, h / w, 0))
    return _pick_photo(candidates)


# Lấy ảnh chân dung theo loại file
def extract_photo(file_bytes: bytes, filename: str) -> bytes | None:
    """Lấy ảnh chân dung từ CV gốc theo loại file. Lỗi bất kỳ -> None (không chặn luồng làm hồ sơ)."""
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            return extract_photo_from_pdf(file_bytes)
        if ext == ".docx":
            return extract_photo_from_docx(file_bytes)
        if ext in IMAGE_EXTENSIONS:
            return extract_photo_from_image(file_bytes)
    except Exception:
        log.exception("Lấy ảnh chân dung thất bại (file .%s) — hồ sơ tiếp tục không có ảnh", ext.lstrip("."))
        return None
    return None


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

# Filter Jinja: **chữ** -> in đậm
def bold_filter(text) -> Markup:
    """Đổi **cụm từ** thành <span class="k">cụm từ</span>. Escape trước để an toàn."""
    safe = str(escape(text or ""))
    return Markup(re.sub(r"\*\*(.+?)\*\*", r'<span class="k">\1</span>', safe))


_env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=select_autoescape(["html"]))
_env.filters["bold"] = bold_filter


# CSS của PDF: phần đổi theo lần dựng + template.css tĩnh
def pdf_css(font_size: float, line_height: float) -> Markup:
    """Toàn bộ CSS của hồ sơ PDF, ghép bằng Python để template.html không còn biểu thức Jinja trong <style>.

    Thứ tự giữ như bản cũ: lề @page (A7) -> biến màu (tokens.py) -> font/cỡ chữ của body -> template.css (tĩnh).
    template.css được đọc như file thường (Jinja không phân tích) nên viết gì trong đó cũng không làm vỡ template.
    """
    m = PDF_MARGIN_MM
    return Markup("\n".join([
        f"@page {{ size: A4; margin: {m['top']}mm {m['right']}mm {m['bottom']}mm {m['left']}mm; }}",
        css_vars("pdf"),
        f"body {{ font-family:{FONT['serif-pdf']}; font-size:{font_size}pt; line-height:{line_height}; }}",
        (TEMPLATE_DIR / "template.css").read_text(encoding="utf-8"),
    ]))


# Dựng HTML hồ sơ từ template
def render_html(cv: dict, project: str, title: str, photo_bytes: bytes | None = None,
                font_size: float = 11.5, line_height: float = 1.42, compact: bool = False) -> str:
    return _env.get_template("template.html").render(
        cv=cv,
        project=(project or "").strip(),
        title=title,
        logo=_data_uri(logo_pdf().read_bytes(), "image/png"),
        photo=_data_uri(photo_bytes, "image/jpeg") if photo_bytes else None,
        compact=compact,
        css=pdf_css(font_size, line_height),                       # A7: lề, màu, font từ tokens.py
        company_info=company()["company"],                          # A4: header công ty
        ref_note=company()["pdf"]["reference_note"],  # A4
    )


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

# Dựng một PDF
def html_to_pdf(html: str, pdf_path: Path) -> None:
    """Dựng 1 bản PDF (xem html_to_pdf_batch)."""
    html_to_pdf_batch([html], [pdf_path])


# Dựng nhiều PDF trong một tiến trình render_worker
def html_to_pdf_batch(htmls: list[str], pdfs: list[Path]) -> None:
    """Dựng nhiều bản PDF trong MỘT lần gọi render_worker.py (1 tiến trình Python + 1 Chromium).

    Tiến trình riêng: xem giải thích trong render_worker.py.
    """
    with tempfile.TemporaryDirectory() as tmp:
        jobs = []
        for i, (html, pdf) in enumerate(zip(htmls, pdfs, strict=True)):
            f = Path(tmp) / f"cv_{i}.html"
            f.write_text(html, encoding="utf-8")
            jobs.append([str(f), str(pdf)])
        job_list = Path(tmp) / "jobs.json"
        job_list.write_text(json.dumps(jobs), encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "services.pdf.render_worker", str(job_list), get_run_id()],
                cwd=PROJECT_ROOT,                  # chạy module trong package -> thư mục làm việc phải là gốc dự án
                capture_output=True, text=True, timeout=render_timeout(),
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Trình dựng PDF (Chromium) không phản hồi sau {render_timeout()} giây. "
                               "Kiểm tra đã cài 'playwright install chromium' rồi thử lại.")
    if result.returncode != 0:
        # S5: chi tiết kỹ thuật (đường dẫn máy, traceback) chỉ vào log, giao diện chỉ hiện câu ngắn
        log.error("render_worker lỗi (mã %s):\n%s", result.returncode, result.stderr[-4000:])
        raise RuntimeError("Trình dựng PDF (Chromium) gặp lỗi. Chi tiết đã ghi vào log; "
                           "hãy thử lại, nếu vẫn lỗi hãy báo người quản trị.")


# Dựng PDF hoàn chỉnh, tự chọn cỡ chữ
def build_pdf(cv: dict, project: str, position: str, photo_bytes: bytes | None,
              out_dir: Path, d: date | None = None) -> Path:
    """Dựng PDF, tự chọn cỡ chữ để không có trang cuối gần trống."""
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(position or cv.get("target_title") or "", cv["full_name"], d)
    title = filename[:-4]
    target = out_dir / filename

    with tempfile.TemporaryDirectory() as tmp:
        # Dựng sẵn cả 3 cỡ chữ trong 1 lần mở Chromium (rẻ hơn nhiều so với mở lại cho mỗi cỡ chữ)
        variants = [Path(tmp) / f"variant_{i}.pdf" for i in range(len(FONT_SIZE_ATTEMPTS))]
        html_to_pdf_batch([render_html(cv, project, title, photo_bytes, fs, lh, compact) for fs, lh, compact in FONT_SIZE_ATTEMPTS],
                          variants)
        chosen = pick_font_size([pdf_layout(p) for p in variants])
        target.write_bytes(write_metadata(variants[chosen].read_bytes()))
    return target


# Chọn bản cỡ chữ phù hợp
def pick_font_size(layouts: list[tuple[int, float]]) -> int:
    """Chọn bản dùng trong các bản thử cỡ chữ [(số trang, độ đầy trang cuối), ...] — đúng luật cũ:

    bản đầu (cỡ chuẩn) ổn (trang cuối đủ đầy hoặc chỉ 1 trang) -> dùng; không thì lấy bản chữ nhỏ ĐẦU TIÊN
    giúp bớt được 1 trang so với bản đầu; không bản nào bớt được trang -> vẫn dùng bản đầu.
    """
    first_page_count, first_fill = layouts[0]
    if first_fill >= LAST_PAGE_MIN_FILL or first_page_count == 1:
        return 0
    for i, (page_count, _) in enumerate(layouts[1:], start=1):
        if page_count < first_page_count:
            return i
    return 0


# Ghi phiên bản bộ trích xuất vào metadata PDF
def write_metadata(pdf_bytes: bytes) -> bytes:
    """Ghi phiên bản bộ trích xuất vào metadata PDF (trường keywords) — biết hồ sơ do bộ đọc nào tạo.

    Giữ nguyên tiêu đề (= tên file, checklist kiểm tra) và mọi metadata khác; nội dung trang không đổi.
    """
    import pymupdf as fitz
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        meta = dict(doc.metadata or {})
        meta["keywords"] = f"FillCV-LightHuman; extractor {extraction.extractor_version()}"
        doc.set_metadata(meta)
        return doc.tobytes()
