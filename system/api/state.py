# Quản lý trạng thái phiên làm việc (in-memory run cache) cho server API
"""Lưu trữ tạm thời các phiên xử lý CV (RunData) trong bộ nhớ của tiến trình đơn.

Mỗi phiên được định danh bằng `run_id`, lưu giữ dữ liệu file gốc, ảnh chân dung,
và bản PDF vừa dựng để phục vụ các endpoint xem trước và tải về.
"""
from dataclasses import dataclass, field
import threading
from typing import Any


# Dữ liệu của một phiên xử lý CV
@dataclass
class RunData:
    run_id: str
    original_bytes: bytes | None = None
    original_name: str = ""
    photo: bytes | None = None
    pdf_bytes: bytes | None = None
    pdf_name: str = ""
    pdf_cv: dict[str, Any] | None = None
    pdf_lang: str = "vi"
    pdf_fingerprint: str = ""
    checklist: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    project: str = ""
    position: str = ""


# Kho lưu trữ các phiên xử lý CV trong bộ nhớ
class RunStore:
    def __init__(self, max_runs: int = 100) -> None:
        self._runs: dict[str, RunData] = {}
        self._lock = threading.Lock()
        self._max_runs = max_runs

    # Lấy thông tin một phiên theo run_id
    def get(self, run_id: str) -> RunData | None:
        with self._lock:
            return self._runs.get(run_id)

    # Lưu hoặc cập nhật thông tin phiên
    def set(self, data: RunData) -> None:
        with self._lock:
            # Nếu vượt quá số lượng tối đa, xoá bớt phiên cũ nhất
            if len(self._runs) >= self._max_runs and data.run_id not in self._runs:
                oldest_key = next(iter(self._runs))
                del self._runs[oldest_key]
            self._runs[data.run_id] = data

    # Lấy phiên hiện có hoặc tạo mới nếu chưa tồn tại
    def get_or_create(self, run_id: str) -> RunData:
        with self._lock:
            if run_id not in self._runs:
                if len(self._runs) >= self._max_runs:
                    oldest_key = next(iter(self._runs))
                    del self._runs[oldest_key]
                self._runs[run_id] = RunData(run_id=run_id)
            return self._runs[run_id]

    # Xoá ảnh chân dung của phiên
    def clear_photo(self, run_id: str) -> bool:
        with self._lock:
            run = self._runs.get(run_id)
            if run and run.photo is not None:
                run.photo = None
                return True
            return False

    # Xoá hoàn toàn một phiên
    def remove(self, run_id: str) -> None:
        with self._lock:
            self._runs.pop(run_id, None)


# Đối tượng RunStore duy nhất dùng chung cho toàn bộ server
run_store = RunStore()

