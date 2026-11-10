"""Nghiệp vụ xử lý hồ sơ (A1/A2) — thuần Python, không Streamlit, import được trong test.

Gọi các module khác qua TÊN MODULE (render.build_pdf, extract.extract_cv...) chứ không import thẳng tên hàm,
để test thay được bằng bản giả (monkeypatch) và để app.py chỉ còn lo giao diện + state.
"""
import hashlib
import json
import logging
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pydantic import ValidationError

from services.privacy import checks
from services.ai import extract
from services.pdf import render
from infra.logging_setup import an_ten_file, dat_run_id
from infra.settings import render_max_concurrent, render_queue_timeout
from infra.storage import duong_dan_khong_trung
from services.ai.models import CVData

# Giữ tên logger "app" như trước khi tách file -> dòng log vẫn dạng "[run_id] app: ..."
log = logging.getLogger("app")


class LoiDocCV(Exception):
    """Đọc CV thất bại; thông điệp là câu tiếng Việt hiển thị thẳng cho người dùng."""


@dataclass
class KetQuaDoc:
    cv: dict
    photo: bytes | None


@dataclass
class KetQuaPdf:
    pdf_bytes: bytes
    ten: str
    checklist: list[dict]
    tin_nhan: str


def doc_cv(data: bytes, ten: str, project: str, position: str) -> KetQuaDoc:
    """AI đọc CV + lấy ảnh chân dung. Mọi lỗi -> LoiDocCV có câu thông báo dễ hiểu (không để traceback lọt ra)."""
    try:
        cv = extract.extract_cv(data, ten, project, position, render.hom_nay_vn())
    except extract.ExtractError as e:
        raise LoiDocCV(str(e)) from e
    except Exception as e:   # file hỏng, lỗi mạng, lỗi bất ngờ...
        log.exception("Lỗi khi đọc CV %s", an_ten_file(ten))   # S6: không ghi tên file
        raise LoiDocCV(thong_bao_loi_doc(e)) from e
    photo = render.extract_photo(data, ten)                     # PDF / DOCX / ảnh; lỗi -> None
    log.info("Đọc CV xong: %d mục, ảnh chân dung: %s", len(cv["sections"]), "có" if photo else "không")
    return KetQuaDoc(cv, photo)


# ----- Hàng đợi dựng PDF (dùng chung cho MỌI phiên Streamlit — chúng chạy chung 1 tiến trình) -----
_luot_dung = threading.BoundedSemaphore(render_max_concurrent())
_dem_cho = 0
_khoa_dem = threading.Lock()


class HangChoQuaLau(RuntimeError):
    """Chờ tới lượt dựng PDF quá RENDER_QUEUE_TIMEOUT giây."""


def so_nguoi_dang_cho() -> int:
    """Số người đang xếp hàng chờ dựng PDF (để hiển thị)."""
    return _dem_cho


def dung_pdf(cv: dict, project: str, position: str, photo: bytes | None,
             khi_cho: Callable[[int], None] | None = None) -> KetQuaPdf:
    """Dựng PDF vào thư mục tạm + checklist + tin nhắn tóm tắt. Lỗi -> ném ra (app ghi log và báo).

    Tối đa RENDER_MAX_CONCURRENT lượt dựng chạy cùng lúc trên toàn app; người tới sau xếp hàng.
    Phải chờ thì gọi `khi_cho(vi_tri_trong_hang)` trước để giao diện báo "đang xếp hàng".
    """
    global _dem_cho
    if not _luot_dung.acquire(blocking=False):
        with _khoa_dem:
            _dem_cho += 1
            vi_tri = _dem_cho
        try:
            log.info("Chờ tới lượt dựng PDF (vị trí %d trong hàng)", vi_tri)
            if khi_cho:
                khi_cho(vi_tri)
            if not _luot_dung.acquire(timeout=render_queue_timeout()):
                raise HangChoQuaLau(f"Đang có nhiều hồ sơ dựng cùng lúc, đã chờ quá {render_queue_timeout()} giây. "
                                    "Vui lòng bấm Cập nhật PDF lại sau ít phút.")
        finally:
            with _khoa_dem:
                _dem_cho -= 1
    try:
        with tempfile.TemporaryDirectory() as tmp:
            p = render.build_pdf(cv, project, position, photo, Path(tmp))
            checklist = checks.scan_pdf(p)
            kq = KetQuaPdf(p.read_bytes(), p.name, checklist, tin_nhan_tom_tat(cv, project, position))
    finally:
        _luot_dung.release()
    log.info("Đã dựng PDF, checklist %d/%d đạt", sum(r["ok"] for r in checklist), len(checklist))
    return kq


def luu_ban_sao(thu_muc: Path, ten: str, pdf_bytes: bytes, run_id: str | None = None) -> Path:
    """Lưu bản sao PDF đã xuất; trùng tên thì thêm hậu tố giờ (Q5), không ghi đè.

    `run_id`: hàm này chạy trong callback của nút Tải — chạy TRƯỚC khi script kịp gắn run_id cho lượt chạy,
    nên phải gắn lại ở đây để dòng log mang đúng mã của hồ sơ.
    """
    if run_id:
        dat_run_id(run_id)
    thu_muc.mkdir(parents=True, exist_ok=True)
    dich = duong_dan_khong_trung(thu_muc, ten)
    dich.write_bytes(pdf_bytes)
    log.info("Đã lưu bản xuất vào thư mục output (%s)", "tên chuẩn" if dich.name == ten else "thêm hậu tố giờ")
    return dich


def la_dung(v) -> bool:
    """Ô đúng/sai trong bảng chữ: chỉ 'x' (hoặc có/yes/true/1) mới là đúng."""
    return v is True or str(v or "").strip().lower() in {"x", "có", "co", "yes", "true", "1"}


def kiem_tra_cau_truc(cv: dict) -> tuple[dict | None, list[str]]:
    """Kiểm tra lại hồ sơ đã sửa bằng CVData. Trả (hồ sơ chuẩn hoá | None, danh sách lỗi)."""
    try:
        return CVData.model_validate(cv).model_dump(), []
    except ValidationError as e:
        loi = []
        for err in e.errors():
            vi_tri = ".".join(str(x) for x in err["loc"]) or "hồ sơ"
            loi.append(f"{vi_tri}: {err['msg'].removeprefix('Value error, ')}")
        return None, loi


def dau_van_tay(cv: dict, project: str, position: str, photo: bytes | None) -> str:
    """Mã nhận diện nội dung đầu vào của PDF -> biết PDF đã xuất còn khớp màn hình không."""
    goi = json.dumps([cv, project, position], ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(goi + (photo or b"")).hexdigest()


def tin_nhan_tom_tat(cv: dict, project: str, position: str) -> str:
    """Khung tin nhắn mục 8 SKILL.md, giọng trung tính."""
    n = cv["model_notes"]
    vi_tri = position or cv.get("target_title") or ""
    dau_dong = lambda xs: "\n".join(f"  - {x}" for x in xs) if xs else "  - (không có)"
    return (
        f"Hồ sơ ứng viên: {cv['full_name']} – {vi_tri}\n\n"
        f"• Dự án đã gắn: {project or '(để trống)'}\n"
        f"• Thông tin đã bỏ khỏi CV:\n{dau_dong(n['removed'])}\n"
        f"• Lương mong muốn: {cv.get('expected_salary') or 'CV không ghi'} (đã bỏ khỏi CV)\n"
        f"• Hệ thống tự lập/điều chỉnh:\n{dau_dong(n['self_created'])}\n\n"
        f"Lưu ý cần xác minh trước khi gửi khách:\n{dau_dong(n['recruiting_flags'] + n['other'])}\n"
    )


def thong_bao_loi_doc(e: Exception) -> str:
    """Đổi lỗi kỹ thuật (không phải ExtractError) thành câu thông báo dễ hiểu."""
    ten = type(e).__name__
    if ten in ("BadZipFile", "PackageNotFoundError", "UnidentifiedImageError") or "zip" in str(e).lower():
        return ("File CV bị hỏng hoặc không đúng định dạng. Hãy mở file, lưu lại thành PDF hoặc DOCX "
                "rồi gửi lại.")
    if isinstance(e, (ConnectionError, TimeoutError, OSError)):
        return "Mất kết nối khi gửi CV cho AI. Kiểm tra mạng rồi gửi lại."
    return "Có lỗi không mong muốn khi đọc CV. Vui lòng gửi lại, nếu vẫn lỗi hãy thử file khác."
