# Gói infra/: hạ tầng dùng chung — cấu hình (settings), design tokens, log, lưu trữ file.
"""Cấu hình dùng chung — một chỗ đọc cho các giá trị trước đây viết cứng rải rác nhiều file.

- Thông tin công ty:  config/company.toml (A4)        -> company(), company_phone_digits()
- Đuôi file hỗ trợ:   CV_EXTENSIONS, IMAGE_EXTENSIONS (A5)
- Đường dẫn/timeout:  biến môi trường, mặc định giữ nguyên hành vi cũ
- Bộ trích xuất CV:   CV_EXTRACTOR -> extractor_name()
- Mọi giá trị có mặc định ở đây; ghi đè bằng BIẾN MÔI TRƯỜNG của hệ điều hành (dự án không dùng file .env).

Không import Streamlit hay module nặng ở đây để mọi nơi (kể cả render_worker) dùng được.
"""
import os
import re
import tomllib
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # gốc dự án (file này nằm trong infra/)


# Đọc đường dẫn từ biến môi trường
def _env_path(name: str, default: Path) -> Path:
    """Đường dẫn từ biến môi trường (tương đối thì tính từ thư mục dự án); trống -> mặc định."""
    value = os.getenv(name, "").strip()
    if not value:
        return default
    p = Path(value)
    return p if p.is_absolute() else PROJECT_ROOT / p


# Đọc số nguyên dương từ biến môi trường
def _env_int(name: str, default: int) -> int:
    try:
        num = int(os.getenv(name, ""))
        return num if num > 0 else default
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Đuôi file (A5) — trước đây lặp ở app.py, extract.py, render.py
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")              # ảnh chân dung / CV dạng ảnh
CV_EXTENSIONS = (".pdf", *IMAGE_EXTENSIONS, ".docx")            # CV gốc được chấp nhận


# Đuôi file cho st.file_uploader
def uploader_types(exts: tuple[str, ...]) -> list[str]:
    """('.pdf', '.png') -> ['pdf', 'png'] cho st.file_uploader(type=...)."""
    return [d.lstrip(".") for d in exts]


# ---------------------------------------------------------------------------
# Đường dẫn & thời gian chờ (biến môi trường, mặc định = hành vi cũ)
# ---------------------------------------------------------------------------
# Thư mục lưu PDF đã xuất
def output_dir() -> Path:
    """Nơi lưu bản sao PDF đã xuất. Biến môi trường OUTPUT_DIR; mặc định data/output."""
    return _env_path("OUTPUT_DIR", PROJECT_ROOT / "data" / "output")


# Logo dùng trong PDF
def logo_pdf() -> Path:
    """Logo in trong PDF (đã cắt sát viền). Biến môi trường LOGO_PATH; mặc định assets/logo.png."""
    return _env_path("LOGO_PATH", PROJECT_ROOT / "assets" / "logo.png")


# Logo cho header web app
def logo_header() -> Path:
    """Logo gốc cho header web app. LOGO_HEADER_PATH; mặc định Logo.png, không có thì dùng logo PDF."""
    p = _env_path("LOGO_HEADER_PATH", PROJECT_ROOT / "Logo.png")
    return p if p.exists() else logo_pdf()


# Hạn giây cho một lần Chromium dựng PDF
def render_timeout() -> int:
    """Số giây tối đa cho một lần Chromium dựng PDF. RENDER_TIMEOUT; mặc định 120."""
    return _env_int("RENDER_TIMEOUT", 120)


# Số lượt dựng PDF chạy cùng lúc
def render_max_concurrent() -> int:
    """Số lượt dựng PDF được chạy CÙNG LÚC trên toàn app (mọi người dùng). RENDER_MAX_CONCURRENT; mặc định 2.

    Mỗi lượt là 1 tiến trình Python + Chromium (~300–400 MB). Kiểm thử tải cho thấy không giới hạn thì nhiều người
    dựng cùng lúc làm cạn RAM -> mọi lượt chậm 10–30 lần. Người thứ 3 trở đi xếp hàng chờ.
    """
    return _env_int("RENDER_MAX_CONCURRENT", 2)


# Hạn giây chờ tới lượt dựng PDF
def render_queue_timeout() -> int:
    """Số giây tối đa một người chờ tới lượt dựng PDF. RENDER_QUEUE_TIMEOUT; mặc định 300."""
    return _env_int("RENDER_QUEUE_TIMEOUT", 300)


# Số lượt đọc CV chạy cùng lúc
def extract_max_concurrent() -> int:
    """Số lượt trích xuất CV chạy CÙNG LÚC trên toàn app. EXTRACT_MAX_CONCURRENT; mặc định 2.

    Đọc PDF theo luật nhẹ (< 1 giây), nhưng giới hạn sẵn để sau này thêm OCR (tốn CPU/RAM) không làm treo máy.
    """
    return _env_int("EXTRACT_MAX_CONCURRENT", 2)


# Hạn giây chờ tới lượt đọc CV
def extract_queue_timeout() -> int:
    """Số giây tối đa một người chờ tới lượt đọc CV. EXTRACT_QUEUE_TIMEOUT; mặc định 300."""
    return _env_int("EXTRACT_QUEUE_TIMEOUT", 300)


# Số trang PDF tối đa được đọc tự động / xem trước
def max_cv_pages() -> int:
    """Số trang tối đa của CV PDF được đọc tự động và xem trước. MAX_CV_PAGES; mặc định 20.

    CV dài hơn -> chuyển khung nhập tay, tab CV gốc chỉ vẽ các trang đầu (PDF hàng trăm trang giữ lượt đọc rất lâu).
    """
    return _env_int("MAX_CV_PAGES", 20)


# Bộ trích xuất CV đang dùng (services/extraction/base.BACKENDS)
def extractor_name() -> str:
    """Tên bộ trích xuất CV. CV_EXTRACTOR (biến môi trường); mặc định "rules" (đọc PDF theo luật).
    "manual" = luôn dựng khung trống để nhập tay."""
    return os.getenv("CV_EXTRACTOR", "").strip().lower() or "rules"


# S7: dung lượng tối đa của file tải lên (MB). Phải khớp server.maxUploadSize trong .streamlit/config.toml.
MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 20)


# ---------------------------------------------------------------------------
# Thông tin công ty (A4)
# ---------------------------------------------------------------------------
# Đường dẫn file cấu hình công ty
def _company_file() -> Path:
    return _env_path("COMPANY_CONFIG", PROJECT_ROOT / "config" / "company.toml")


# Đọc file TOML công ty (cache)
@lru_cache(maxsize=4)
def _read_company(path: str) -> dict:
    return tomllib.loads(Path(path).read_text(encoding="utf-8"))


# Thông tin công ty từ config/company.toml
def company() -> dict:
    """{'company': {...}, 'pdf': {...}} từ config/company.toml (đọc 1 lần, có cache)."""
    return _read_company(str(_company_file()))


# SĐT công ty chỉ gồm chữ số
def company_phone_digits() -> str:
    """Chỉ chữ số: '028 3842 5188' -> '02838425188' (dùng cho danh sách được phép của bộ lọc PII)."""
    return re.sub(r"\D", "", company()["company"]["phone"])
