"""Bộ trích xuất "nhập tay": không đọc nội dung CV, chỉ kiểm tra file mở được rồi dựng khung hồ sơ trống đúng schema.

Dùng khi chưa có/không dùng được bộ đọc tự động (vd PDF không có lớp chữ). Không bịa dữ liệu: mọi trường để trống,
riêng họ tên (schema bắt buộc khác rỗng) để chữ tạm và ghi vào `model_notes.self_created` để người duyệt phải sửa.
Mọi phần đều có độ tin cậy 0 -> form duyệt gắn nhãn "Cần xem".
"""
import io
import zipfile
from pathlib import Path

from infra.settings import IMAGE_EXTENSIONS
from services.extraction import base

PLACEHOLDER_NAME = "Chưa nhập họ tên"
NOTE_MANUAL = "Hồ sơ đang là khung trống để nhập tay — chưa có nội dung nào được đọc tự động từ CV gốc."


# Khung hồ sơ trống đúng schema: các mục thường gặp, chưa có nội dung
def blank_cv(note: str = NOTE_MANUAL) -> dict:
    """Họ tên để chữ tạm (schema không cho rỗng); mục kinh nghiệm có sẵn 1 công việc trống để form có ô nhập."""
    job = {"company": "", "period": None, "role": None, "meta": [], "groups": [{"title": None, "bullets": []}],
           "sub_roles": []}
    return {
        "language": "vi", "full_name": PLACEHOLDER_NAME, "target_title": None, "birth_year": None, "gender": None,
        "facts": [], "expected_salary": None, "stats": [],
        "sections": [
            {"type": "text", "title": "Mục tiêu nghề nghiệp", "paragraphs": []},
            {"type": "experience", "title": "Kinh nghiệm làm việc", "jobs": [job]},
            {"type": "education", "title": "Học vấn", "education": []},
            {"type": "bullets", "title": "Kỹ năng", "bullets": []},
        ],
        "model_notes": {"removed": [], "recruiting_flags": [], "other": [note],
                        "self_created": [f"Họ tên đang để chữ tạm '{PLACEHOLDER_NAME}' — phải nhập họ tên thật"]},
    }


# Mở thử file để chắc file không hỏng; trả mô tả ngắn (không chứa nội dung CV)
def probe_file(data: bytes, filename: str) -> str:
    """Lỗi file hỏng -> base.ExtractionError có câu dễ hiểu."""
    ext = Path(filename).suffix.lower()
    try:
        if ext == ".pdf":
            import pymupdf as fitz
            with fitz.open(stream=data, filetype="pdf") as doc:
                has_text = any(page.get_text().strip() for page in doc)
                return f"PDF {doc.page_count} trang, {'có' if has_text else 'không có'} lớp chữ"
        if ext == ".docx":
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                z.getinfo("word/document.xml")
            return "DOCX"
        if ext in IMAGE_EXTENSIONS:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                return f"ảnh {im.width}x{im.height}"
    except Exception as e:
        raise base.ExtractionError("File CV bị hỏng hoặc không đúng định dạng. Hãy mở file, lưu lại thành PDF "
                                   "rồi gửi lại.") from e
    raise base.ExtractionError(f"Chưa hỗ trợ loại file '{ext}'. Hãy dùng PDF, PNG, JPG hoặc DOCX.")


# Độ tin cậy 0 và cảnh báo cho mọi phần của khung trống
def blank_review(cv: dict, reason: str) -> tuple[list[base.ReviewNote], dict[str, float]]:
    """Mọi phần của khung đều cần người nhập/duyệt."""
    notes = [base.ReviewNote(None, reason), base.ReviewNote("full_name", "chưa có họ tên — đang để chữ tạm")]
    conf = {"full_name": 0.0, **{f"sections[{i}]": 0.0 for i in range(len(cv["sections"]))}}
    return notes, conf


# Bộ trích xuất nhập tay: kiểm tra file + dựng khung trống
class ManualExtractor:
    name = "manual"
    version = "1"
    stages = (base.Stage("open", "Mở và kiểm tra file CV gốc"),
              base.Stage("form", "Tạo khung hồ sơ để nhập tay"))

    # Trích xuất (thực chất là dựng khung): không đọc nội dung CV
    def extract(self, doc: base.SourceDoc, progress: base.Progress) -> base.ExtractionResult:
        runs: list[base.StageRun] = []
        with base.stage_run(runs, self.stages[0], progress) as run:
            run.detail = probe_file(doc.data, doc.filename)
        with base.stage_run(runs, self.stages[1], progress):
            cv = blank_cv()
            notes, conf = blank_review(cv, "Chưa có bộ đọc tự động cho CV này: hãy nhập tay toàn bộ nội dung, "
                                           "đối chiếu với tab CV gốc.")
        return base.ExtractionResult(cv=cv, warnings=notes, confidence=conf, stages=runs,
                                     backend=f"{self.name}-{self.version}")
