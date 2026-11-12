# Gói services/ai/: cấu trúc hồ sơ ứng viên (models). Tên thư mục giữ từ thời dùng AI, hiện KHÔNG còn gọi AI.
"""Mô hình dữ liệu (pydantic) cho JSON hồ sơ ứng viên.

Cấu trúc ở đây PHẢI khớp với prompts/schema.json.
Nếu sửa schema thì sửa luôn file này (và ngược lại).
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# A6 (đã xác nhận là chủ ý): năm sinh hợp lệ khi nhập/trích xuất — nới rộng tới 2015 chỉ để chặn năm
# sai rõ ràng. KHÁC khoảng 1940–2010 của checks.py (dùng để đoán một ngày đầy đủ có phải ngày sinh không).
VALID_BIRTH_YEAR_MIN, VALID_BIRTH_YEAR_MAX = 1940, 2015


# Lớp gốc: cấm trường lạ
class _Base(BaseModel):
    # Không cho phép trường lạ -> phát hiện sớm khi bộ trích xuất trả sai cấu trúc
    model_config = ConfigDict(extra="forbid")


# Thông tin nhanh (nhãn: giá trị)
class Fact(_Base):
    label: str
    value: str


# Ô số liệu
class Stat(_Base):
    value: str
    label: str
    source: Literal["original", "generated"]


# Dòng phụ của công việc
class MetaLine(_Base):
    label: Optional[str] = None
    text: str


# Nhóm gạch đầu dòng
class Group(_Base):
    title: Optional[str] = None
    bullets: list[str] = []


# Vị trí con trong một công việc
class SubRole(_Base):
    name: str
    period: Optional[str] = None
    meta: list[MetaLine] = []
    groups: list[Group] = []


# Một công việc
class Job(_Base):
    company: str
    period: Optional[str] = None
    role: Optional[str] = None
    meta: list[MetaLine] = []
    groups: list[Group] = []
    sub_roles: list[SubRole] = []


# Thẻ năng lực
class Card(_Base):
    title: str
    items: list[str] = []


# Một bước lộ trình nghề nghiệp
class CareerStep(_Base):
    period: str
    title: str
    company: str
    current: bool = False


# Một mục học vấn
class EducationItem(_Base):
    title: str
    detail: Optional[str] = None
    period: Optional[str] = None


# Người tham chiếu
class Reference(_Base):
    name: str
    title: Optional[str] = None
    company: Optional[str] = None


SectionType = Literal[
    "text", "bullets", "cards", "tags", "career_path", "experience", "education", "references"
]


# Một mục nội dung của hồ sơ
class Section(_Base):
    type: SectionType
    title: str
    paragraphs: list[str] = []
    bullets: list[str] = []
    cards: list[Card] = []
    tags: list[str] = []
    career_path: list[CareerStep] = []
    jobs: list[Job] = []
    education: list[EducationItem] = []
    references: list[Reference] = []


# Ghi chú của bộ trích xuất cho người làm hồ sơ
class ModelNotes(_Base):
    removed: list[str] = []
    self_created: list[str] = []
    recruiting_flags: list[str] = []
    other: list[str] = []


# Toàn bộ hồ sơ ứng viên
class CVData(_Base):
    language: Literal["vi", "en", "bilingual_vi_en"]
    full_name: str
    target_title: Optional[str] = None
    birth_year: Optional[int] = None
    gender: Optional[str] = None
    facts: list[Fact] = []
    expected_salary: Optional[str] = None
    stats: list[Stat] = Field(default_factory=list, max_length=4)
    sections: list[Section] = []
    model_notes: ModelNotes = ModelNotes()

    # Họ tên không được trống
    @field_validator("full_name")
    @classmethod
    def _name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Họ tên ứng viên đang trống")
        return v.strip()

    # Năm sinh phải hợp lý
    @field_validator("birth_year")
    @classmethod
    def _birth_year_valid(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (VALID_BIRTH_YEAR_MIN <= v <= VALID_BIRTH_YEAR_MAX):
            raise ValueError(f"Năm sinh {v} không hợp lý")
        return v
