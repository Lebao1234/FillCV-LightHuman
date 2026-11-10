"""Cấu hình dùng chung — một chỗ đọc cho các giá trị trước đây viết cứng rải rác nhiều file.

- Thông tin công ty:  config/company.toml (A4)        -> cong_ty(), so_dien_thoai_cong_ty()
- Đuôi file hỗ trợ:   DUOI_CV, DUOI_ANH (A5)
- Đường dẫn/timeout:  đọc từ .env, mặc định giữ nguyên hành vi cũ
- Phiên bản prompt:   prompts/version.txt + mã băm nội dung prompt -> phien_ban_prompt()

Không import Streamlit hay module nặng ở đây để mọi nơi (kể cả render_worker) dùng được.
"""
import hashlib
import os
import re
import tomllib
from functools import lru_cache
from pathlib import Path

THU_MUC = Path(__file__).resolve().parent.parent   # gốc dự án (file này nằm trong infra/)


def _duong_dan_env(ten: str, mac_dinh: Path) -> Path:
    """Đường dẫn từ .env (tương đối thì tính từ thư mục dự án); trống -> mặc định."""
    gia_tri = os.getenv(ten, "").strip()
    if not gia_tri:
        return mac_dinh
    p = Path(gia_tri)
    return p if p.is_absolute() else THU_MUC / p


def _so_nguyen_env(ten: str, mac_dinh: int) -> int:
    try:
        so = int(os.getenv(ten, ""))
        return so if so > 0 else mac_dinh
    except ValueError:
        return mac_dinh


# ---------------------------------------------------------------------------
# Đuôi file (A5) — trước đây lặp ở app.py, extract.py, render.py
# ---------------------------------------------------------------------------
DUOI_ANH = (".png", ".jpg", ".jpeg")              # ảnh chân dung / CV dạng ảnh
DUOI_CV = (".pdf", *DUOI_ANH, ".docx")            # CV gốc được chấp nhận


def loai_cho_uploader(duoi: tuple[str, ...]) -> list[str]:
    """('.pdf', '.png') -> ['pdf', 'png'] cho st.file_uploader(type=...)."""
    return [d.lstrip(".") for d in duoi]


# ---------------------------------------------------------------------------
# Đường dẫn & thời gian chờ (.env, mặc định = hành vi cũ)
# ---------------------------------------------------------------------------
def thu_muc_output() -> Path:
    """Nơi lưu bản sao PDF đã xuất. OUTPUT_DIR trong .env; mặc định data/output."""
    return _duong_dan_env("OUTPUT_DIR", THU_MUC / "data" / "output")


def logo_pdf() -> Path:
    """Logo in trong PDF (đã cắt sát viền). LOGO_PATH trong .env; mặc định assets/logo.png."""
    return _duong_dan_env("LOGO_PATH", THU_MUC / "assets" / "logo.png")


def logo_header() -> Path:
    """Logo gốc cho header web app. LOGO_HEADER_PATH; mặc định Logo.png, không có thì dùng logo PDF."""
    p = _duong_dan_env("LOGO_HEADER_PATH", THU_MUC / "Logo.png")
    return p if p.exists() else logo_pdf()


def render_timeout() -> int:
    """Số giây tối đa cho một lần Chromium dựng PDF. RENDER_TIMEOUT; mặc định 120."""
    return _so_nguyen_env("RENDER_TIMEOUT", 120)


def render_max_concurrent() -> int:
    """Số lượt dựng PDF được chạy CÙNG LÚC trên toàn app (mọi người dùng). RENDER_MAX_CONCURRENT; mặc định 2.

    Mỗi lượt là 1 tiến trình Python + Chromium (~300–400 MB). Kiểm thử tải cho thấy không giới hạn thì nhiều người
    dựng cùng lúc làm cạn RAM -> mọi lượt chậm 10–30 lần. Người thứ 3 trở đi xếp hàng chờ.
    """
    return _so_nguyen_env("RENDER_MAX_CONCURRENT", 2)


def render_queue_timeout() -> int:
    """Số giây tối đa một người chờ tới lượt dựng PDF. RENDER_QUEUE_TIMEOUT; mặc định 300."""
    return _so_nguyen_env("RENDER_QUEUE_TIMEOUT", 300)


# ---------------------------------------------------------------------------
# Thông tin công ty (A4)
# ---------------------------------------------------------------------------
def _file_cong_ty() -> Path:
    return _duong_dan_env("COMPANY_CONFIG", THU_MUC / "config" / "company.toml")


@lru_cache(maxsize=4)
def _doc_cong_ty(duong_dan: str) -> dict:
    return tomllib.loads(Path(duong_dan).read_text(encoding="utf-8"))


def cong_ty() -> dict:
    """{'cong_ty': {...}, 'pdf': {...}} từ config/company.toml (đọc 1 lần, có cache)."""
    return _doc_cong_ty(str(_file_cong_ty()))


def so_dien_thoai_cong_ty() -> str:
    """Chỉ chữ số: '028 3842 5188' -> '02838425188' (dùng cho danh sách được phép của bộ lọc PII)."""
    return re.sub(r"\D", "", cong_ty()["cong_ty"]["dien_thoai"])


# ---------------------------------------------------------------------------
# Prompt (bảng hardcode) — nội dung ở prompts/, có số phiên bản ghi vào metadata PDF
# ---------------------------------------------------------------------------
THU_MUC_PROMPT = THU_MUC / "prompts"
_FILE_PROMPT = ("system_prompt.txt", "schema.json", "user.txt", "fix_json.txt")


def doc_prompt(ten: str) -> str:
    """Đọc 1 file trong prompts/ (bỏ xuống dòng thừa ở cuối file)."""
    return (THU_MUC_PROMPT / ten).read_text(encoding="utf-8").rstrip("\n")


@lru_cache(maxsize=1)
def phien_ban_prompt() -> str:
    """'1.0+a1b2c3d4': số phiên bản đặt tay (prompts/version.txt) + 8 ký tự băm toàn bộ nội dung prompt.

    Phần băm đổi ngay khi ai đó sửa prompt mà quên tăng số phiên bản -> vẫn phân biệt được.
    """
    so = doc_prompt("version.txt").strip()
    h = hashlib.sha256()
    for ten in _FILE_PROMPT:
        h.update((THU_MUC_PROMPT / ten).read_bytes())
    return f"{so}+{h.hexdigest()[:8]}"
