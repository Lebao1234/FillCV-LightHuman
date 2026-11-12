"""Cấu hình log cho app + render_worker, và tiện ích log an toàn (KHÔNG để PII của ứng viên lọt vào log).

- File log xoay vòng: data/logs/app.log (app) và data/logs/render_worker.log (tiến trình dựng PDF).
  Hai tiến trình ghi hai file riêng để không tranh nhau khi xoay vòng file trên Windows.
- Mỗi lần xử lý một CV có một `run_id` (8 ký tự). app.py truyền run_id sang render_worker.py qua argv
  -> tìm `[a1b2c3d4]` trong cả hai file là thấy toàn bộ một lượt xử lý.
- Thư mục log đổi bằng biến môi trường LOG_DIR (mặc định data/logs, đã nằm trong .gitignore).
"""
import contextvars
import hashlib
import logging
import os
import threading
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"   # gốc dự án / data / logs
LOG_FILE_MAX_BYTES = 1_000_000   # ~1 MB mỗi file
LOG_BACKUP_COUNT = 5                # giữ app.log.1 … app.log.5
LOG_FORMAT = "%(asctime)s %(levelname)-7s [%(run_id)s] %(name)s: %(message)s"

_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="-")


# ---------------------------------------------------------------------------
# run_id
# ---------------------------------------------------------------------------

# Tạo mã cho một lượt xử lý CV
def new_run_id() -> str:
    """Mã ngắn cho một lượt xử lý CV."""
    return uuid.uuid4().hex[:8]


# Gắn run_id cho các dòng log tiếp theo
def set_run_id(run_id: str | None) -> None:
    """Gắn run_id cho mọi dòng log tiếp theo trong luồng/lượt chạy hiện tại."""
    _run_id.set(run_id or "-")


# Lấy run_id hiện tại
def get_run_id() -> str:
    return _run_id.get()


# Filter gắn run_id vào từng dòng log
class _RunIdFilter(logging.Filter):
    # Gắn run_id vào bản ghi log
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get()
        return True


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

# Thư mục log (LOG_DIR hoặc mặc định)
def log_dir() -> Path:
    return Path(os.getenv("LOG_DIR") or DEFAULT_LOG_DIR)


_config_lock = threading.Lock()


# Gắn handler file log xoay vòng (chỉ 1 lần mỗi file)
def setup_logging(filename: str = "app.log", level: int = logging.INFO) -> Path:
    """Gắn handler ghi file xoay vòng vào root logger. Gọi nhiều lần vẫn chỉ gắn 1 handler cho mỗi file.

    Có khoá: nhiều phiên Streamlit (nhiều luồng) mở cùng lúc đều gọi hàm này — không khoá thì cả hai cùng thấy
    "chưa có handler" và cùng thêm, làm mỗi dòng log bị ghi 2 lần (phát hiện khi kiểm thử tải).
    """
    path = log_dir() / filename
    root = logging.getLogger()
    with _config_lock:
        for h in root.handlers:
            if isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == path.resolve():
                return path
        path.parent.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(path, maxBytes=LOG_FILE_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
        h.setFormatter(logging.Formatter(LOG_FORMAT))
        h.addFilter(_RunIdFilter())
        root.addHandler(h)
        if root.level == logging.NOTSET or root.level > level:
            root.setLevel(level)
    return path


# ---------------------------------------------------------------------------
# Log an toàn
# ---------------------------------------------------------------------------

# Che tên file khi ghi log
def mask_filename(filename: str) -> str:
    """Mô tả file trong log mà không lộ tên (S6). Tên file CV thường chính là họ tên ứng viên.

    'Nguyễn Văn A.pdf' -> 'pdf#1a2b3c4d' (đuôi file + 8 ký tự đầu sha256 của tên).
    Cùng một tên luôn ra cùng mã -> vẫn lần theo được một file qua nhiều dòng log.
    """
    ext = Path(filename or "").suffix.lower().lstrip(".") or "khong-duoi"
    digest = hashlib.sha256((filename or "").encode("utf-8")).hexdigest()[:8]
    return f"{ext}#{digest}"
