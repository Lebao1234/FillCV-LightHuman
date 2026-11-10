"""Mô hình dữ liệu (pydantic) cho JSON hồ sơ ứng viên.

Cấu trúc ở đây PHẢI khớp với prompts/schema.json.
Nếu sửa schema thì sửa luôn file này (và ngược lại).
"""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# A6 (đã xác nhận là chủ ý): năm sinh hợp lệ khi nhập/AI trích xuất — nới rộng tới 2015 chỉ để chặn năm
# sai rõ ràng. KHÁC khoảng 1940–2010 của checks.py (dùng để đoán một ngày đầy đủ có phải ngày sinh không).
NAM_SINH_HOP_LE_TU, NAM_SINH_HOP_LE_DEN = 1940, 2015


class _Base(BaseModel):
    # Không cho phép trường lạ -> phát hiện sớm khi AI trả sai cấu trúc
    model_config = ConfigDict(extra="forbid")


class Fact(_Base):
    label: str
    value: str


class Stat(_Base):
    value: str
    label: str
    source: Literal["original", "generated"]


class MetaLine(_Base):
    label: Optional[str] = None
    text: str


class Group(_Base):
    title: Optional[str] = None
    bullets: list[str] = []


class SubRole(_Base):
    name: str
    period: Optional[str] = None
    meta: list[MetaLine] = []
    groups: list[Group] = []


class Job(_Base):
    company: str
    period: Optional[str] = None
    role: Optional[str] = None
    meta: list[MetaLine] = []
    groups: list[Group] = []
    sub_roles: list[SubRole] = []


class Card(_Base):
    title: str
    items: list[str] = []


class CareerStep(_Base):
    period: str
    title: str
    company: str
    current: bool = False


class EducationItem(_Base):
    title: str
    detail: Optional[str] = None
    period: Optional[str] = None


class Reference(_Base):
    name: str
    title: Optional[str] = None
    company: Optional[str] = None


SectionType = Literal[
    "text", "bullets", "cards", "tags", "career_path", "experience", "education", "references"
]


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


class ModelNotes(_Base):
    removed: list[str] = []
    self_created: list[str] = []
    recruiting_flags: list[str] = []
    other: list[str] = []


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

    @field_validator("full_name")
    @classmethod
    def _ten_khong_rong(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Họ tên ứng viên đang trống")
        return v.strip()

    @field_validator("birth_year")
    @classmethod
    def _nam_sinh_hop_ly(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (NAM_SINH_HOP_LE_TU <= v <= NAM_SINH_HOP_LE_DEN):
            raise ValueError(f"Năm sinh {v} không hợp lý")
        return v
