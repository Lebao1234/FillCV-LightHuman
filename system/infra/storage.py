"""Thời hạn lưu hồ sơ PDF đã xuất (S2).

File PDF + JSON trong data/output chứa họ tên + quá trình làm việc của ứng viên -> không giữ vô thời hạn.
Mặc định xoá file quá 30 ngày; đổi bằng biến môi trường OUTPUT_RETENTION_DAYS (0 = tắt tự xoá).
"""
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("storage")   # giữ tên cũ cho log

DEFAULT_RETENTION_DAYS = 30
# Loại file xuất được dọn theo hạn: PDF + JSON hồ sơ lưu kèm
EXPIRING_SUFFIXES = {".pdf", ".json"}


# Số ngày giữ PDF đã xuất
def retention_days() -> int:
    """Số ngày giữ PDF đã xuất. Trống/sai -> 30; '0' -> tắt tự xoá."""
    try:
        days = int(os.getenv("OUTPUT_RETENTION_DAYS", ""))
    except ValueError:
        return DEFAULT_RETENTION_DAYS
    return max(days, 0)


# Xoá PDF quá hạn trong thư mục output
def delete_expired_files(folder: Path, days: int, now: float | None = None) -> list[Path]:
    """Xoá file .pdf/.json trong `folder` (KHÔNG đi vào thư mục con) có lần sửa cuối quá `days` ngày.

    Trả danh sách file đã xoá. days <= 0 hoặc thư mục không tồn tại -> không làm gì.
    Lỗi xoá một file (đang mở, không có quyền) chỉ ghi log, không chặn các file khác.
    """
    if days <= 0 or not folder.is_dir():
        return []
    cutoff = (now if now is not None else time.time()) - days * 86400
    deleted = []
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in EXPIRING_SUFFIXES and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                deleted.append(f)
            except OSError:
                log.exception("Không xoá được một file hết hạn trong %s", folder)
    if deleted:
        # Chỉ ghi số lượng — tên file là họ tên ứng viên (S6)
        log.info("Đã xoá %d file hồ sơ (PDF/JSON) quá %d ngày trong %s", len(deleted), days, folder)
    return deleted


# Đường dẫn lưu không ghi đè file cũ
def unique_path(folder: Path, name: str, now: float | None = None) -> Path:
    """Đường dẫn lưu bản sao không ghi đè file cũ (Q5).

    Chưa có file trùng -> giữ nguyên tên (đúng chuẩn đặt tên mục 3.6 SKILL.md).
    Đã có -> thêm hậu tố giờ: 'LH - CV … - 09112026 (143015).pdf'; trùng cả giờ -> thêm số đếm.
    """
    target = folder / name
    if not target.exists():
        return target
    stem, ext = target.stem, target.suffix
    clock = time.strftime("%H%M%S", time.localtime(now if now is not None else time.time()))
    target = folder / f"{stem} ({clock}){ext}"
    counter = 2
    while target.exists():
        target = folder / f"{stem} ({clock}-{counter}){ext}"
        counter += 1
    return target
