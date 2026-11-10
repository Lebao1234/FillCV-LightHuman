"""Thời hạn lưu hồ sơ PDF đã xuất (S2).

File PDF trong data/output chứa họ tên + quá trình làm việc của ứng viên -> không giữ vô thời hạn.
Mặc định xoá file quá 30 ngày; đổi bằng OUTPUT_RETENTION_DAYS trong .env (0 = tắt tự xoá).
"""
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("storage")   # giữ tên cũ cho log

SO_NGAY_LUU_MAC_DINH = 30


def so_ngay_luu() -> int:
    """Số ngày giữ PDF đã xuất. Trống/sai -> 30; '0' -> tắt tự xoá."""
    try:
        so = int(os.getenv("OUTPUT_RETENTION_DAYS", ""))
    except ValueError:
        return SO_NGAY_LUU_MAC_DINH
    return max(so, 0)


def don_file_het_han(thu_muc: Path, so_ngay: int, bay_gio: float | None = None) -> list[Path]:
    """Xoá file .pdf trong `thu_muc` (KHÔNG đi vào thư mục con) có lần sửa cuối quá `so_ngay` ngày.

    Trả danh sách file đã xoá. so_ngay <= 0 hoặc thư mục không tồn tại -> không làm gì.
    Lỗi xoá một file (đang mở, không có quyền) chỉ ghi log, không chặn các file khác.
    """
    if so_ngay <= 0 or not thu_muc.is_dir():
        return []
    han = (bay_gio if bay_gio is not None else time.time()) - so_ngay * 86400
    da_xoa = []
    for f in thu_muc.iterdir():
        if f.is_file() and f.suffix.lower() == ".pdf" and f.stat().st_mtime < han:
            try:
                f.unlink()
                da_xoa.append(f)
            except OSError:
                log.exception("Không xoá được một file hết hạn trong %s", thu_muc)
    if da_xoa:
        # Chỉ ghi số lượng — tên file là họ tên ứng viên (S6)
        log.info("Đã xoá %d hồ sơ PDF quá %d ngày trong %s", len(da_xoa), so_ngay, thu_muc)
    return da_xoa


def duong_dan_khong_trung(thu_muc: Path, ten: str, bay_gio: float | None = None) -> Path:
    """Đường dẫn lưu bản sao không ghi đè file cũ (Q5).

    Chưa có file trùng -> giữ nguyên tên (đúng chuẩn đặt tên mục 3.6 SKILL.md).
    Đã có -> thêm hậu tố giờ: 'LH - CV … - 09112026 (143015).pdf'; trùng cả giờ -> thêm số đếm.
    """
    dich = thu_muc / ten
    if not dich.exists():
        return dich
    goc, duoi = dich.stem, dich.suffix
    gio = time.strftime("%H%M%S", time.localtime(bay_gio if bay_gio is not None else time.time()))
    dich = thu_muc / f"{goc} ({gio}){duoi}"
    dem = 2
    while dich.exists():
        dich = thu_muc / f"{goc} ({gio}-{dem}){duoi}"
        dem += 1
    return dich
