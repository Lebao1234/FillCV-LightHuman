import { useState } from 'react'
import PortraitEditor from './PortraitEditor.jsx'
import GeneralInfoEditor from './GeneralInfoEditor.jsx'
import StatsEditor from './StatsEditor.jsx'
import ReviewBadge from './ReviewBadge.jsx'
import {
  TextSection,
  BulletsSection,
  TagsSection,
  CardsSection,
  CareerPathSection,
  EducationSection,
  ReferencesSection,
  ExperienceSection,
} from './SectionEditors.jsx'

import Field from '../Field.jsx'
const EDITORS_MAP = {
  text: TextSection,
  bullets: BulletsSection,
  tags: TagsSection,
  cards: CardsSection,
  career_path: CareerPathSection,
  education: EducationSection,
  references: ReferencesSection,
  experience: ExperienceSection,
}

const SECTION_TYPE_LABELS = {
  experience: 'Kinh nghiệm làm việc',
  education: 'Học vấn & bằng cấp',
  career_path: 'Lộ trình nghề nghiệp',
  cards: 'Thẻ năng lực',
  bullets: 'Gạch đầu dòng',
  text: 'Đoạn văn tự do',
  tags: 'Thẻ kỹ năng',
  references: 'Người tham chiếu',
}

// Form chỉnh sửa toàn bộ nội dung hồ sơ ứng viên (Tab "Chỉnh sửa nội dung")
export default function ProfileForm({
  cv,
  onChangeCv,
  project,
  onChangeProject,
  position,
  onChangePosition,
  runId,
  photoUrl,
  onChangePhoto,
  review,
}) {
  const [openSections, setOpenSections] = useState({})
  const [newType, setNewType] = useState('experience')

  const toggleSection = (idx) => {
    setOpenSections((prev) => ({ ...prev, [idx]: !prev[idx] }))
  }

  const sections = cv?.sections || []

  const updateSection = (idx, updatedSec) => {
    const newSections = [...sections]
    newSections[idx] = updatedSec
    onChangeCv({ ...cv, sections: newSections })
  }

  const removeSection = (idx) => {
    const newSections = sections.filter((_, i) => i !== idx)
    onChangeCv({ ...cv, sections: newSections })
  }

  const moveSection = (idx, direction) => {
    const targetIdx = idx + direction
    if (targetIdx < 0 || targetIdx >= sections.length) return
    const newSections = [...sections]
    const [moved] = newSections.splice(idx, 1)
    newSections.splice(targetIdx, 0, moved)
    onChangeCv({ ...cv, sections: newSections })
  }

  const addSection = () => {
    const baseSec = {
      type: newType,
      title: SECTION_TYPE_LABELS[newType] || 'Mục mới',
      paragraphs: [],
      bullets: [],
      cards: [],
      tags: [],
      career_path: [],
      education: [],
      references: [],
      jobs: [],
    }
    onChangeCv({ ...cv, sections: [...sections, baseSec] })
    setOpenSections((prev) => ({ ...prev, [sections.length]: true }))
  }

  return (
    <div className="bg-white p-4 border border-line rounded-md">
      {/* Dự án và Vị trí */}
      <div className="form-row mb-4">
        <Field label="Tên dự án">
          <input
            type="text"
            className="form-input"
            placeholder="Message Coffee"
            value={project || ''}
            onChange={(e) => onChangeProject(e.target.value)}
          />
        </Field>
        <Field label="Vị trí (dùng cho tên file PDF)">
          <input
            type="text"
            className="form-input"
            placeholder="Kế toán trưởng"
            value={position || ''}
            onChange={(e) => onChangePosition(e.target.value)}
          />
        </Field>
      </div>

      {/* Ảnh chân dung */}
      <PortraitEditor runId={runId} photoUrl={photoUrl} onPhotoChange={onChangePhoto} />

      {/* Thông tin chung */}
      <GeneralInfoEditor cv={cv} onChange={onChangeCv} review={review} />

      {/* Hàng ô số liệu */}
      <StatsEditor cv={cv} onChange={onChangeCv} review={review} />

      {/* Danh sách các mục nội dung */}
      <div className="mt-6">
        <div className="flex justify-between items-center mb-3">
          <h4 className="m-0">Các mục nội dung ({sections.length})</h4>
          <div className="flex gap-2 items-center">
            <select
              className="form-input text-sm py-1 px-2"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
            >
              {Object.entries(SECTION_TYPE_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
            <button type="button" className="btn btn-primary text-sm" onClick={addSection}>
              + Thêm mục
            </button>
          </div>
        </div>

        {sections.map((sec, idx) => {
          const isOpen = openSections[idx] !== false // Mặc định mở
          const EditorComponent = EDITORS_MAP[sec.type] || TextSection
          return (
            <div
              key={idx} className="border border-line rounded-md mb-3 bg-white overflow-hidden"
            >
              {/* Header của mục */}
              <div
                className={`flex cursor-pointer items-center justify-between bg-soft px-3 py-2 ${isOpen ? 'border-b border-line' : ''}`}
                onClick={() => toggleSection(idx)}
              >
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-ink">
                    {idx + 1}. {sec.title || '(Chưa có tiêu đề)'}
                  </span>
                  <span className="text-xs text-faint">({sec.type})</span>
                  <ReviewBadge review={review} paths={`sections[${idx}]`} />
                </div>

                <div className="flex gap-1 items-center"
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    type="button"
                    className="btn btn-tertiary py-0.5 px-1.5"
                    onClick={() => moveSection(idx, -1)}
                    disabled={idx === 0}
                    title="Di chuyển lên"
                    aria-label="Di chuyển lên"
                  >
                    ▲
                  </button>
                  <button
                    type="button"
                    className="btn btn-tertiary py-0.5 px-1.5"
                    onClick={() => moveSection(idx, 1)}
                    disabled={idx === sections.length - 1}
                    title="Di chuyển xuống"
                    aria-label="Di chuyển xuống"
                  >
                    ▼
                  </button>
                  <button
                    type="button"
                    className="btn btn-tertiary text-err py-0.5 px-1.5"
                    onClick={() => removeSection(idx)}
                    title="Xoá mục này"
                    aria-label="Xoá mục này"
                  >
                    ✕
                  </button>
                  <span className="text-xs text-faint ml-1">
                    {isOpen ? '▲' : '▼'}
                  </span>
                </div>
              </div>

              {/* Nội dung bên trong mục khi mở */}
              {isOpen && (
                <div className="p-3">
                  <Field label="Tiêu đề mục" small className="mb-3">
                    <input
                      type="text"
                      className="form-input"
                      value={sec.title || ''}
                      onChange={(e) => updateSection(idx, { ...sec, title: e.target.value })}
                    />
                  </Field>

                  <EditorComponent section={sec} onChange={(updated) => updateSection(idx, updated)} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

