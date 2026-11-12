# Gói services/: xử lý chuyên môn — trích xuất CV (extraction/), cấu trúc hồ sơ (ai/models.py), dựng PDF (pdf/),
# lọc thông tin nhạy cảm (privacy/).
# Gói services/extraction/: ranh giới trích xuất CV — mọi bộ trích xuất (theo luật, nhập tay...) cắm vào đây.
"""Interface bộ trích xuất CV. Trích xuất chạy hoàn toàn trên máy chủ, KHÔNG gọi dịch vụ ngoài.

core/pipeline.py chỉ gọi `get_extractor().extract(...)` (qua tên module) và không biết bên dưới là bộ nào.
Kết quả LUÔN gồm:
  - cv          : dict đúng schema (prompts/schema.json ↔ services/ai/models.py) — schema KHÔNG chứa độ tin cậy;
  - warnings    : cảnh báo cho người duyệt (kênh riêng, gắn với đường dẫn trường nếu có);
  - confidence  : độ tin cậy 0..1 theo đường dẫn trường/mục, vd "full_name", "sections[2].jobs[0].period";
  - stages      : các giai đoạn đã chạy thật (tên, thời gian, trạng thái) — để log và màn hình "đang xử lý".
Thông điệp trong warnings phải do code soạn (không chép nguyên văn nội dung CV) vì được hiển thị dạng markdown và
không được ghi nội dung CV vào log.
"""
import importlib
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Iterator, Protocol

from infra import settings
from services.ai.models import CVData

# Trường/mục có độ tin cậy dưới ngưỡng này được đánh dấu "Cần xem" trong form duyệt
REVIEW_THRESHOLD = 0.7

# Tên bộ trích xuất -> (module, lớp). Module chỉ được import khi dùng tới (không kéo thư viện của backend khác)
BACKENDS = {
    "rules": ("services.extraction.rules.extractor", "RulesExtractor"),
    "manual": ("services.extraction.manual", "ManualExtractor"),
}


# Lỗi trích xuất có câu thông báo tiếng Việt hiển thị thẳng cho người dùng
class ExtractionError(Exception):
    """Đọc CV thất bại; thông điệp là câu tiếng Việt dễ hiểu (không có traceback/chi tiết kỹ thuật)."""


# Đầu vào chung cho mọi bộ trích xuất
@dataclass(frozen=True)
class SourceDoc:
    data: bytes
    filename: str
    project: str = ""
    position: str = ""
    today: date | None = None


# Một giai đoạn bộ trích xuất khai báo (hiển thị trên màn hình "đang xử lý")
@dataclass(frozen=True)
class Stage:
    key: str
    label: str


# Một giai đoạn đã chạy xong: thời gian + trạng thái (để log theo run_id)
@dataclass
class StageRun:
    key: str
    label: str
    seconds: float
    status: str = "ok"          # ok | warn | skip
    detail: str = ""            # mô tả ngắn do code soạn, KHÔNG chứa nội dung CV


# Cảnh báo cho người duyệt; path = đường dẫn trường (None = cảnh báo chung cho cả hồ sơ)
@dataclass(frozen=True)
class ReviewNote:
    path: str | None
    message: str


# Kết quả trích xuất: dữ liệu đúng schema + các kênh riêng (cảnh báo, độ tin cậy, giai đoạn)
@dataclass
class ExtractionResult:
    cv: dict
    warnings: list[ReviewNote] = field(default_factory=list)
    confidence: dict[str, float] = field(default_factory=dict)
    stages: list[StageRun] = field(default_factory=list)
    backend: str = ""


# Hàm báo tiến độ: gọi với `Stage.key` ngay khi BẮT ĐẦU một giai đoạn
Progress = Callable[[str], None]


# Giao diện mà mọi bộ trích xuất phải có (Protocol: không cần kế thừa)
class Extractor(Protocol):
    name: str
    version: str                 # đổi khi đổi luật -> ghi vào metadata PDF (biết hồ sơ do phiên bản nào đọc)
    stages: tuple[Stage, ...]

    def extract(self, doc: SourceDoc, progress: Progress) -> ExtractionResult: ...


# Chạy một giai đoạn: báo tiến độ lúc bắt đầu, đo thời gian, ghi vào danh sách giai đoạn đã chạy
@contextmanager
def stage_run(runs: list[StageRun], stage: Stage, progress: Progress | None) -> Iterator[StageRun]:
    if progress:
        progress(stage.key)
    run = StageRun(stage.key, stage.label, 0.0)
    t0 = time.monotonic()
    try:
        yield run
    finally:
        run.seconds = time.monotonic() - t0
        runs.append(run)


# Chặn file rỗng hoặc quá lớn trước khi xử lý (S7)
def check_file(file_bytes: bytes, filename: str) -> None:
    """Lỗi -> ExtractionError có câu thông báo dễ hiểu. Giới hạn: settings.MAX_UPLOAD_MB."""
    if not file_bytes:
        raise ExtractionError(f"File '{Path(filename).name}' trống.")
    size_mb = len(file_bytes) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise ExtractionError(f"File nặng {size_mb:.1f} MB, vượt giới hạn {settings.MAX_UPLOAD_MB} MB. "
                              "Hãy nén hoặc xuất lại file nhẹ hơn rồi gửi lại.")


# Kiểm tra hồ sơ theo schema, trả dict đã chuẩn hoá (lỗi -> pydantic.ValidationError)
def validate(cv: dict) -> dict:
    """Kiểm tra bằng CVData (khớp prompts/schema.json), trả dict đã chuẩn hoá."""
    return CVData.model_validate(cv).model_dump()


# Chọn bộ trích xuất theo tên (mặc định: settings.extractor_name(), biến môi trường CV_EXTRACTOR)
def get_extractor(name: str | None = None) -> Extractor:
    key = (name or settings.extractor_name()).strip().lower()
    if key not in BACKENDS:
        raise ExtractionError(f"Chưa có bộ trích xuất '{key}'. Báo người quản trị kiểm tra cấu hình CV_EXTRACTOR.")
    module, cls = BACKENDS[key]
    return getattr(importlib.import_module(module), cls)()


# Phiên bản bộ trích xuất đang cấu hình — ghi vào metadata PDF (thay cho phiên bản prompt trước đây)
def extractor_version() -> str:
    """'manual-1': tên + phiên bản của bộ trích xuất đang cấu hình; cấu hình sai -> 'unknown'."""
    try:
        ex = get_extractor()
    except ExtractionError:
        return "unknown"
    return f"{ex.name}-{ex.version}"


# Đường dẫn trường `path` có nằm trong một trong các mục `prefixes` không ("sections[1]" chứa "sections[1].jobs[0]")
def _under(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == p or path.startswith(p + ".") or path.startswith(p + "[") for p in prefixes)


# Các câu "cần xem" cho một nhóm trường: cảnh báo gắn với trường + trường có độ tin cậy dưới ngưỡng
def review_messages(review: dict | None, prefixes: tuple[str, ...]) -> list[str]:
    """`review` = {"confidence": {path: điểm}, "notes": [(path, câu)]} như app lưu trong session."""
    if not review:
        return []
    msgs = [m for p, m in review.get("notes", []) if p and _under(p, prefixes)]
    low = sorted((p, v) for p, v in (review.get("confidence") or {}).items()
                 if v < REVIEW_THRESHOLD and _under(p, prefixes))
    msgs += [f"độ tin cậy thấp ở `{p}` ({v:.0%})" for p, v in low]
    return msgs
