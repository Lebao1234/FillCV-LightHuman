"""Cấu hình log cho app + render_worker, và tiện ích log an toàn (KHÔNG để PII của ứng viên lọt vào log).

- File log xoay vòng: data/logs/app.log (app) và data/logs/render_worker.log (tiến trình dựng PDF).
  Hai tiến trình ghi hai file riêng để không tranh nhau khi xoay vòng file trên Windows.
- Mỗi lần xử lý một CV có một `run_id` (8 ký tự). app.py truyền run_id sang render_worker.py qua argv
  -> tìm `[a1b2c3d4]` trong cả hai file là thấy toàn bộ một lượt xử lý.
- Thư mục log đổi bằng LOG_DIR trong .env (mặc định data/logs, đã nằm trong .gitignore).
"""
import contextvars
import hashlib
import logging
import os
import threading
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

THU_MUC_LOG_MAC_DINH = Path(__file__).resolve().parent.parent / "data" / "logs"   # gốc dự án / data / logs
DUNG_LUONG_FILE_LOG = 1_000_000   # ~1 MB mỗi file
SO_FILE_LOG_CU = 5                # giữ app.log.1 … app.log.5
DINH_DANG = "%(asctime)s %(levelname)-7s [%(run_id)s] %(name)s: %(message)s"

_run_id: contextvars.ContextVar[str] = contextvars.ContextVar("run_id", default="-")


# ---------------------------------------------------------------------------
# run_id
# ---------------------------------------------------------------------------

def tao_run_id() -> str:
    """Mã ngắn cho một lượt xử lý CV."""
    return uuid.uuid4().hex[:8]


def dat_run_id(run_id: str | None) -> None:
    """Gắn run_id cho mọi dòng log tiếp theo trong luồng/lượt chạy hiện tại."""
    _run_id.set(run_id or "-")


def lay_run_id() -> str:
    return _run_id.get()


class _GanRunId(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = _run_id.get()
        return True


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

def thu_muc_log() -> Path:
    return Path(os.getenv("LOG_DIR") or THU_MUC_LOG_MAC_DINH)


_khoa_cau_hinh = threading.Lock()


def cau_hinh_logging(ten_file: str = "app.log", muc: int = logging.INFO) -> Path:
    """Gắn handler ghi file xoay vòng vào root logger. Gọi nhiều lần vẫn chỉ gắn 1 handler cho mỗi file.

    Có khoá: nhiều phiên Streamlit (nhiều luồng) mở cùng lúc đều gọi hàm này — không khoá thì cả hai cùng thấy
    "chưa có handler" và cùng thêm, làm mỗi dòng log bị ghi 2 lần (phát hiện khi kiểm thử tải).
    """
    duong_dan = thu_muc_log() / ten_file
    goc = logging.getLogger()
    with _khoa_cau_hinh:
        for h in goc.handlers:
            if isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == duong_dan.resolve():
                return duong_dan
        duong_dan.parent.mkdir(parents=True, exist_ok=True)
        h = RotatingFileHandler(duong_dan, maxBytes=DUNG_LUONG_FILE_LOG, backupCount=SO_FILE_LOG_CU, encoding="utf-8")
        h.setFormatter(logging.Formatter(DINH_DANG))
        h.addFilter(_GanRunId())
        goc.addHandler(h)
        if goc.level == logging.NOTSET or goc.level > muc:
            goc.setLevel(muc)
    return duong_dan


# ---------------------------------------------------------------------------
# Log an toàn
# ---------------------------------------------------------------------------

def an_ten_file(ten_file: str) -> str:
    """Mô tả file trong log mà không lộ tên (S6). Tên file CV thường chính là họ tên ứng viên.

    'Nguyễn Văn A.pdf' -> 'pdf#1a2b3c4d' (đuôi file + 8 ký tự đầu sha256 của tên).
    Cùng một tên luôn ra cùng mã -> vẫn lần theo được một file qua nhiều dòng log.
    """
    duoi = Path(ten_file or "").suffix.lower().lstrip(".") or "khong-duoi"
    ma = hashlib.sha256((ten_file or "").encode("utf-8")).hexdigest()[:8]
    return f"{duoi}#{ma}"
