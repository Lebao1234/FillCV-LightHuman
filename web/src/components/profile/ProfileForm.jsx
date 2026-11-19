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
    <div style={{ background: 'var(--white)', padding: 'var(--sp-4)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)' }}>
      {/* Dự án và Vị trí */}
      <div className="form-row" style={{ marginBottom: 'var(--sp-4)' }}>
        <div className="form-group">
          <label className="form-label">Tên dự án</label>
          <input
            type="text"
            className="form-input"
            placeholder="Message Coffee"
            value={project || ''}
            onChange={(e) => onChangeProject(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Vị trí (dùng cho tên file PDF)</label>
          <input
            type="text"
            className="form-input"
            placeholder="Kế toán trưởng"
            value={position || ''}
            onChange={(e) => onChangePosition(e.target.value)}
          />
        </div>
      </div>

      {/* Ảnh chân dung */}
      <PortraitEditor runId={runId} photoUrl={photoUrl} onPhotoChange={onChangePhoto} />

      {/* Thông tin chung */}
      <GeneralInfoEditor cv={cv} onChange={onChangeCv} review={review} />

      {/* Hàng ô số liệu */}
      <StatsEditor cv={cv} onChange={onChangeCv} review={review} />

      {/* Danh sách các mục nội dung */}
      <div style={{ marginTop: 'var(--sp-5)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-3)' }}>
          <h4 style={{ margin: 0 }}>Các mục nội dung ({sections.length})</h4>
          <div style={{ display: 'flex', gap: 'var(--sp-2)', alignItems: 'center' }}>
            <select
              className="form-input"
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              style={{ fontSize: 'var(--fs-sm)', padding: '4px 8px' }}
            >
              {Object.entries(SECTION_TYPE_LABELS).map(([k, label]) => (
                <option key={k} value={k}>
                  {label}
                </option>
              ))}
            </select>
            <button type="button" className="btn btn-primary" onClick={addSection} style={{ fontSize: 'var(--fs-sm)' }}>
              + Thêm mục
            </button>
          </div>
        </div>

        {sections.map((sec, idx) => {
          const isOpen = openSections[idx] !== false // Mặc định mở
          const EditorComponent = EDITORS_MAP[sec.type] || TextSection
          return (
            <div
              key={idx}
              style={{
                border: '1px solid var(--line)',
                borderRadius: 'var(--r-md)',
                marginBottom: 'var(--sp-3)',
                background: 'var(--white)',
                overflow: 'hidden',
              }}
            >
              {/* Header của mục */}
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: 'var(--sp-2) var(--sp-3)',
                  background: 'var(--soft)',
                  borderBottom: isOpen ? '1px solid var(--line)' : 'none',
                  cursor: 'pointer',
                }}
                onClick={() => toggleSection(idx)}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--sp-2)' }}>
                  <span style={{ fontWeight: 600, fontSize: 'var(--fs-sm)', color: 'var(--ink)' }}>
                    {idx + 1}. {sec.title || '(Chưa có tiêu đề)'}
                  </span>
                  <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--faint)' }}>({sec.type})</span>
                  <ReviewBadge review={review} paths={`sections[${idx}]`} />
                </div>

                <div
                  style={{ display: 'flex', gap: '4px', alignItems: 'center' }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    type="button"
                    className="btn btn-tertiary"
                    onClick={() => moveSection(idx, -1)}
                    disabled={idx === 0}
                    style={{ padding: '2px 6px' }}
                    title="Di chuyển lên"
                  >
                    ▲
                  </button>
                  <button
                    type="button"
                    className="btn btn-tertiary"
                    onClick={() => moveSection(idx, 1)}
                    disabled={idx === sections.length - 1}
                    style={{ padding: '2px 6px' }}
                    title="Di chuyển xuống"
                  >
                    ▼
                  </button>
                  <button
                    type="button"
                    className="btn btn-tertiary"
                    onClick={() => removeSection(idx)}
                    style={{ color: 'var(--err)', padding: '2px 6px' }}
                    title="Xoá mục này"
                  >
                    ✕
                  </button>
                  <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--faint)', marginLeft: '4px' }}>
                    {isOpen ? '▲' : '▼'}
                  </span>
                </div>
              </div>

              {/* Nội dung bên trong mục khi mở */}
              {isOpen && (
                <div style={{ padding: 'var(--sp-3)' }}>
                  <div className="form-group" style={{ marginBottom: 'var(--sp-3)' }}>
                    <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                      Tiêu đề mục
                    </label>
                    <input
                      type="text"
                      className="form-input"
                      value={sec.title || ''}
                      onChange={(e) => updateSection(idx, { ...sec, title: e.target.value })}
                    />
                  </div>

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

