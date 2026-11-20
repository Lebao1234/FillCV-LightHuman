import Field from '../Field.jsx'

// Các component chỉnh sửa tương ứng từng loại mục (EDITORS_BY_TYPE)

// 1. Mục dạng đoạn văn (text)
export function TextSection({ section, onChange }) {
  const text = (section.paragraphs || []).join('\n')
  const handleChange = (e) => {
    const lines = e.target.value.split('\n')
    onChange({ ...section, paragraphs: lines })
  }
  return (
    <Field label="Đoạn văn (mỗi dòng 1 đoạn)" small>
      <textarea
        className="form-textarea"
        rows={5}
        value={text}
        onChange={handleChange}
        placeholder="Nhập nội dung các đoạn văn..."
      />
    </Field>
  )
}

// 2. Mục dạng gạch đầu dòng (bullets)
export function BulletsSection({ section, onChange }) {
  const text = (section.bullets || []).join('\n')
  const handleChange = (e) => {
    const lines = e.target.value.split('\n')
    onChange({ ...section, bullets: lines })
  }
  return (
    <Field label="Gạch đầu dòng (mỗi dòng 1 ý)" small>
      <textarea
        className="form-textarea"
        rows={6}
        value={text}
        onChange={handleChange}
        placeholder="Mỗi dòng là một gạch đầu dòng..."
      />
    </Field>
  )
}

// 3. Mục dạng thẻ (tags)
export function TagsSection({ section, onChange }) {
  const text = (section.tags || []).join('\n')
  const handleChange = (e) => {
    const lines = e.target.value.split('\n')
    onChange({ ...section, tags: lines })
  }
  return (
    <Field label="Thẻ (mỗi dòng 1 thẻ)" small>
      <textarea
        className="form-textarea"
        rows={4}
        value={text}
        onChange={handleChange}
        placeholder="Mỗi dòng là một thẻ kỹ năng/ngôn ngữ..."
      />
    </Field>
  )
}

// 4. Mục dạng thẻ năng lực (cards)
export function CardsSection({ section, onChange }) {
  const cards = section.cards || []

  const updateCard = (idx, field, value) => {
    const newCards = [...cards]
    newCards[idx] = { ...newCards[idx], [field]: value }
    onChange({ ...section, cards: newCards })
  }

  const addCard = () => {
    onChange({
      ...section,
      cards: [...cards, { title: `Thẻ ${cards.length + 1}`, items: [] }],
    })
  }

  const removeCard = (idx) => {
    onChange({ ...section, cards: cards.filter((_, i) => i !== idx) })
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button type="button" className="btn btn-tertiary text-xs" onClick={addCard}>
          + Thêm thẻ năng lực
        </button>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-3">
        {cards.map((c, idx) => (
          <div
            key={idx}
            className="relative rounded-md border border-line bg-white p-3"
          >
            <button
              type="button"
              onClick={() => removeCard(idx)}
              className="absolute top-1 right-1.5 cursor-pointer border-0 bg-transparent text-faint hover:text-err"
              title="Xoá thẻ"
              aria-label="Xoá thẻ"
            >
              ✕
            </button>
            <Field label="Tên thẻ" small className="mb-2">
              <input
                type="text"
                className="form-input"
                value={c.title || ''}
                onChange={(e) => updateCard(idx, 'title', e.target.value)}
              />
            </Field>
            <Field label="Nội dung (mỗi dòng 1 ý)" small>
              <textarea
                className="form-textarea"
                rows={4}
                value={(c.items || []).join('\n')}
                onChange={(e) => updateCard(idx, 'items', e.target.value.split('\n'))}
              />
            </Field>
          </div>
        ))}
      </div>
    </div>
  )
}

// 5. Mục lộ trình nghề nghiệp (career_path)
export function CareerPathSection({ section, onChange }) {
  const items = section.career_path || []

  const updateRow = (idx, field, value) => {
    const newItems = [...items]
    newItems[idx] = { ...newItems[idx], [field]: value }
    onChange({ ...section, career_path: newItems })
  }

  const addRow = () => {
    onChange({
      ...section,
      career_path: [...items, { period: '', title: '', company: '', current: false }],
    })
  }

  const removeRow = (idx) => {
    onChange({ ...section, career_path: items.filter((_, i) => i !== idx) })
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button type="button" className="btn btn-tertiary text-xs" onClick={addRow}>
          + Thêm mốc lộ trình
        </button>
      </div>
      {items.map((row, idx) => (
        <div
          key={idx} className="grid grid-cols-[1.5fr_2fr_2fr_auto_auto] gap-2 items-center mb-2"
        >
          <input
            type="text"
            className="form-input"
            placeholder="Thời gian"
            aria-label="Thời gian"
            value={row.period || ''}
            onChange={(e) => updateRow(idx, 'period', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Chức danh"
            aria-label="Chức danh"
            value={row.title || ''}
            onChange={(e) => updateRow(idx, 'title', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Công ty"
            aria-label="Công ty"
            value={row.company || ''}
            onChange={(e) => updateRow(idx, 'company', e.target.value)}
          />
          <label className="flex items-center gap-1 text-xs cursor-pointer">
            <input
              type="checkbox"
              checked={Boolean(row.current)}
              onChange={(e) => updateRow(idx, 'current', e.target.checked)}
            />
            Hiện tại
          </label>
          <button
            type="button"
            className="btn btn-tertiary text-err p-1"
            onClick={() => removeRow(idx)}
            title="Xoá dòng"
            aria-label="Xoá dòng"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

// 6. Mục học vấn (education)
export function EducationSection({ section, onChange }) {
  const items = section.education || []

  const updateRow = (idx, field, value) => {
    const newItems = [...items]
    newItems[idx] = { ...newItems[idx], [field]: value }
    onChange({ ...section, education: newItems })
  }

  const addRow = () => {
    onChange({
      ...section,
      education: [...items, { title: '', detail: '', period: '' }],
    })
  }

  const removeRow = (idx) => {
    onChange({ ...section, education: items.filter((_, i) => i !== idx) })
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button type="button" className="btn btn-tertiary text-xs" onClick={addRow}>
          + Thêm học vấn
        </button>
      </div>
      {items.map((row, idx) => (
        <div
          key={idx} className="grid grid-cols-[2fr_3fr_1.5fr_auto] gap-2 items-center mb-2"
        >
          <input
            type="text"
            className="form-input"
            placeholder="Văn bằng / Chứng chỉ"
            aria-label="Văn bằng / Chứng chỉ"
            value={row.title || ''}
            onChange={(e) => updateRow(idx, 'title', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Trường / Nơi cấp"
            aria-label="Trường / Nơi cấp"
            value={row.detail || ''}
            onChange={(e) => updateRow(idx, 'detail', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Năm / Thời gian"
            aria-label="Năm / Thời gian"
            value={row.period || ''}
            onChange={(e) => updateRow(idx, 'period', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-tertiary text-err p-1"
            onClick={() => removeRow(idx)}
            title="Xoá dòng"
            aria-label="Xoá dòng"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

// 7. Mục người tham chiếu (references)
export function ReferencesSection({ section, onChange }) {
  const items = section.references || []

  const updateRow = (idx, field, value) => {
    const newItems = [...items]
    newItems[idx] = { ...newItems[idx], [field]: value }
    onChange({ ...section, references: newItems })
  }

  const addRow = () => {
    onChange({
      ...section,
      references: [...items, { name: '', title: '', company: '' }],
    })
  }

  const removeRow = (idx) => {
    onChange({ ...section, references: items.filter((_, i) => i !== idx) })
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button type="button" className="btn btn-tertiary text-xs" onClick={addRow}>
          + Thêm người tham chiếu
        </button>
      </div>
      {items.map((row, idx) => (
        <div
          key={idx} className="grid grid-cols-[2fr_2fr_2fr_auto] gap-2 items-center mb-2"
        >
          <input
            type="text"
            className="form-input"
            placeholder="Họ tên"
            aria-label="Họ tên"
            value={row.name || ''}
            onChange={(e) => updateRow(idx, 'name', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Chức danh"
            aria-label="Chức danh"
            value={row.title || ''}
            onChange={(e) => updateRow(idx, 'title', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Công ty"
            aria-label="Công ty"
            value={row.company || ''}
            onChange={(e) => updateRow(idx, 'company', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-tertiary text-err p-1"
            onClick={() => removeRow(idx)}
            title="Xoá dòng"
            aria-label="Xoá dòng"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

// Bảng sửa dòng phụ (meta): label + text
function MetaEditor({ meta = [], onChange }) {
  const addMeta = () => {
    onChange([...meta, { label: '', text: '' }])
  }

  const updateMeta = (idx, field, val) => {
    const newMeta = [...meta]
    newMeta[idx] = { ...newMeta[idx], [field]: val }
    onChange(newMeta)
  }

  const removeMeta = (idx) => {
    onChange(meta.filter((_, i) => i !== idx))
  }

  return (
    <div className="mt-2 mb-2">
      <div className="flex justify-between items-center">
        <span className="text-xs text-faint">
          Dòng phụ (nhãn để trống = dòng nghiêng)
        </span>
        <button type="button" className="btn btn-tertiary text-xs py-0.5 px-1" onClick={addMeta}>
          + Thêm dòng phụ
        </button>
      </div>
      {meta.map((m, idx) => (
        <div key={idx} className="grid grid-cols-[1fr_2fr_auto] gap-2 mt-1 items-center">
          <input
            type="text"
            className="form-input text-sm py-1 px-2"
            placeholder="Nhãn (vd: Quy mô)"
            aria-label="Nhãn (vd: Quy mô)"
            value={m.label || ''}
            onChange={(e) => updateMeta(idx, 'label', e.target.value)}
          />
          <input
            type="text"
            className="form-input text-sm py-1 px-2"
            placeholder="Nội dung dòng phụ"
            aria-label="Nội dung dòng phụ"
            value={m.text || ''}
            onChange={(e) => updateMeta(idx, 'text', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-tertiary text-err py-0.5 px-1.5"
            onClick={() => removeMeta(idx)}
          >
            ✕
          </button>
        </div>
      ))}
    </div>
  )
}

// Sửa nhóm việc (groups): title + bullets
function GroupsEditor({ groups = [], onChange, bulletLabel = 'Gạch đầu dòng (mỗi dòng 1 ý)' }) {
  const addGroup = () => {
    onChange([...groups, { title: null, bullets: [] }])
  }

  const updateGroup = (idx, field, val) => {
    const newGroups = [...groups]
    newGroups[idx] = { ...newGroups[idx], [field]: val }
    onChange(newGroups)
  }

  const removeGroup = (idx) => {
    onChange(groups.filter((_, i) => i !== idx))
  }

  return (
    <div className="mt-2">
      <div className="flex justify-between items-center">
        <span className="text-xs font-medium text-muted">
          {bulletLabel}
        </span>
        <button type="button" className="btn btn-tertiary text-xs py-0.5 px-1" onClick={addGroup}>
          + Thêm nhóm việc
        </button>
      </div>
      {groups.map((g, idx) => (
        <div key={idx} className="my-2 border-l-2 border-line pl-2">
          <div className="flex gap-2 mb-1 items-center">
            <input
              type="text"
              className="form-input text-sm py-1 px-2"
              placeholder="Tiêu đề nhóm việc (không bắt buộc)"
              aria-label="Tiêu đề nhóm việc (không bắt buộc)"
              value={g.title || ''}
              onChange={(e) => updateGroup(idx, 'title', e.target.value || null)}
            />
            {groups.length > 1 && (
              <button
                type="button"
                className="btn btn-tertiary text-err"
                onClick={() => removeGroup(idx)}
              >
                ✕
              </button>
            )}
          </div>
          <textarea
            className="form-textarea text-sm"
            rows={3}
            value={(g.bullets || []).join('\n')}
            onChange={(e) => updateGroup(idx, 'bullets', e.target.value.split('\n'))}
            placeholder="Mỗi dòng là một ý..."
            aria-label="Mỗi dòng là một ý..."
          />
        </div>
      ))}
    </div>
  )
}

// 8. Mục kinh nghiệm làm việc (experience)
export function ExperienceSection({ section, onChange }) {
  const jobs = section.jobs || []

  const updateJob = (idx, newJob) => {
    const newJobs = [...jobs]
    newJobs[idx] = newJob
    onChange({ ...section, jobs: newJobs })
  }

  const addJob = () => {
    onChange({
      ...section,
      jobs: [
        ...jobs,
        {
          company: '',
          period: null,
          role: null,
          meta: [],
          groups: [{ title: null, bullets: [] }],
          sub_roles: [],
        },
      ],
    })
  }

  const removeJob = (idx) => {
    onChange({ ...section, jobs: jobs.filter((_, i) => i !== idx) })
  }

  const moveJob = (idx, direction) => {
    const targetIdx = idx + direction
    if (targetIdx < 0 || targetIdx >= jobs.length) return
    const newJobs = [...jobs]
    const [moved] = newJobs.splice(idx, 1)
    newJobs.splice(targetIdx, 0, moved)
    onChange({ ...section, jobs: newJobs })
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button type="button" className="btn btn-tertiary text-xs" onClick={addJob}>
          + Thêm công việc
        </button>
      </div>

      {jobs.map((job, idx) => (
        <div
          key={idx} className="border border-line rounded-md p-3 mb-4 bg-soft"
        >
          {/* Header công việc */}
          <div className="flex justify-between items-center mb-2">
            <span className="font-semibold text-sm text-ink">
              Công việc {idx + 1}
            </span>
            <div className="flex gap-1">
              <button
                type="button"
                className="btn btn-tertiary py-0.5 px-1.5"
                onClick={() => moveJob(idx, -1)}
                disabled={idx === 0}
                title="Di chuyển lên"
                aria-label="Di chuyển lên"
              >
                ▲
              </button>
              <button
                type="button"
                className="btn btn-tertiary py-0.5 px-1.5"
                onClick={() => moveJob(idx, 1)}
                disabled={idx === jobs.length - 1}
                title="Di chuyển xuống"
                aria-label="Di chuyển xuống"
              >
                ▼
              </button>
              <button
                type="button"
                className="btn btn-tertiary text-err py-0.5 px-1.5"
                onClick={() => removeJob(idx)}
                title="Xoá công việc này"
                aria-label="Xoá công việc này"
              >
                ✕ Xoá
              </button>
            </div>
          </div>

          <div className="form-row mb-2">
            <Field label="Công ty" small>
              <input
                type="text"
                className="form-input"
                value={job.company || ''}
                onChange={(e) => updateJob(idx, { ...job, company: e.target.value })}
              />
            </Field>
            <Field label="Thời gian" small>
              <input
                type="text"
                className="form-input"
                placeholder="03/2020 – Nay"
                value={job.period || ''}
                onChange={(e) => updateJob(idx, { ...job, period: e.target.value || null })}
              />
            </Field>
          </div>

          <Field label="Chức danh" small className="mb-2">
            <input
              type="text"
              className="form-input"
              value={job.role || ''}
              onChange={(e) => updateJob(idx, { ...job, role: e.target.value || null })}
            />
          </Field>

          {/* Dòng phụ (meta) */}
          <MetaEditor
            meta={job.meta || []}
            onChange={(newMeta) => updateJob(idx, { ...job, meta: newMeta })}
          />

          {/* Các nhóm gạch đầu dòng */}
          <GroupsEditor
            groups={job.groups || []}
            onChange={(newGroups) => updateJob(idx, { ...job, groups: newGroups })}
          />

          {/* Vị trí con (sub_roles) */}
          <div className="mt-3 border-t border-dashed border-line-strong pt-2">
            <div className="flex justify-between items-center">
              <span className="text-xs font-semibold text-muted">
                Vị trí con ({ (job.sub_roles || []).length })
              </span>
              <button
                type="button"
                className="btn btn-tertiary text-xs py-0.5 px-1"
                onClick={() =>
                  updateJob(idx, {
                    ...job,
                    sub_roles: [
                      ...(job.sub_roles || []),
                      { name: '', period: null, meta: [], groups: [{ title: null, bullets: [] }] },
                    ],
                  })
                }
              >
                + Thêm vị trí con
              </button>
            </div>

            {(job.sub_roles || []).map((sub, sIdx) => (
              <div
                key={sIdx} className="border border-line rounded-sm p-2 mt-2 bg-white"
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="text-xs font-medium">Vị trí con {sIdx + 1}</span>
                  <button
                    type="button"
                    className="btn btn-tertiary text-err p-0.5"
                    onClick={() => {
                      const newSubs = job.sub_roles.filter((_, i) => i !== sIdx)
                      updateJob(idx, { ...job, sub_roles: newSubs })
                    }}
                  >
                    ✕
                  </button>
                </div>
                <div className="form-row">
                  <input
                    type="text"
                    className="form-input text-sm"
                    placeholder="Tên vị trí con"
                    aria-label="Tên vị trí con"
                    value={sub.name || ''}
                    onChange={(e) => {
                      const newSubs = [...job.sub_roles]
                      newSubs[sIdx] = { ...newSubs[sIdx], name: e.target.value }
                      updateJob(idx, { ...job, sub_roles: newSubs })
                    }}
                  />
                  <input
                    type="text"
                    className="form-input text-sm"
                    placeholder="Thời gian vị trí con"
                    aria-label="Thời gian vị trí con"
                    value={sub.period || ''}
                    onChange={(e) => {
                      const newSubs = [...job.sub_roles]
                      newSubs[sIdx] = { ...newSubs[sIdx], period: e.target.value || null }
                      updateJob(idx, { ...job, sub_roles: newSubs })
                    }}
                  />
                </div>
                <MetaEditor
                  meta={sub.meta || []}
                  onChange={(newMeta) => {
                    const newSubs = [...job.sub_roles]
                    newSubs[sIdx] = { ...newSubs[sIdx], meta: newMeta }
                    updateJob(idx, { ...job, sub_roles: newSubs })
                  }}
                />
                <GroupsEditor
                  groups={sub.groups || []}
                  onChange={(newGroups) => {
                    const newSubs = [...job.sub_roles]
                    newSubs[sIdx] = { ...newSubs[sIdx], groups: newGroups }
                    updateJob(idx, { ...job, sub_roles: newSubs })
                  }}
                />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

