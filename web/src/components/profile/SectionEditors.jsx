// Các component chỉnh sửa tương ứng từng loại mục (EDITORS_BY_TYPE)

// 1. Mục dạng đoạn văn (text)
export function TextSection({ section, onChange }) {
  const text = (section.paragraphs || []).join('\n')
  const handleChange = (e) => {
    const lines = e.target.value.split('\n')
    onChange({ ...section, paragraphs: lines })
  }
  return (
    <div className="form-group">
      <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
        Đoạn văn (mỗi dòng 1 đoạn)
      </label>
      <textarea
        className="form-textarea"
        rows={5}
        value={text}
        onChange={handleChange}
        placeholder="Nhập nội dung các đoạn văn..."
      />
    </div>
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
    <div className="form-group">
      <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
        Gạch đầu dòng (mỗi dòng 1 ý)
      </label>
      <textarea
        className="form-textarea"
        rows={6}
        value={text}
        onChange={handleChange}
        placeholder="Mỗi dòng là một gạch đầu dòng..."
      />
    </div>
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
    <div className="form-group">
      <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
        Thẻ (mỗi dòng 1 thẻ)
      </label>
      <textarea
        className="form-textarea"
        rows={4}
        value={text}
        onChange={handleChange}
        placeholder="Mỗi dòng là một thẻ kỹ năng/ngôn ngữ..."
      />
    </div>
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--sp-2)' }}>
        <button type="button" className="btn btn-tertiary" onClick={addCard} style={{ fontSize: 'var(--fs-xs)' }}>
          + Thêm thẻ năng lực
        </button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 'var(--sp-3)' }}>
        {cards.map((c, idx) => (
          <div
            key={idx}
            style={{
              border: '1px solid var(--line)',
              borderRadius: 'var(--r-md)',
              padding: 'var(--sp-3)',
              background: 'var(--white)',
              position: 'relative',
            }}
          >
            <button
              type="button"
              onClick={() => removeCard(idx)}
              style={{
                position: 'absolute',
                top: '4px',
                right: '6px',
                background: 'none',
                border: 'none',
                color: 'var(--faint)',
                cursor: 'pointer',
              }}
              title="Xoá thẻ"
            >
              ✕
            </button>
            <div className="form-group" style={{ marginBottom: 'var(--sp-2)' }}>
              <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                Tên thẻ
              </label>
              <input
                type="text"
                className="form-input"
                value={c.title || ''}
                onChange={(e) => updateCard(idx, 'title', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                Nội dung (mỗi dòng 1 ý)
              </label>
              <textarea
                className="form-textarea"
                rows={4}
                value={(c.items || []).join('\n')}
                onChange={(e) => updateCard(idx, 'items', e.target.value.split('\n'))}
              />
            </div>
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--sp-2)' }}>
        <button type="button" className="btn btn-tertiary" onClick={addRow} style={{ fontSize: 'var(--fs-xs)' }}>
          + Thêm mốc lộ trình
        </button>
      </div>
      {items.map((row, idx) => (
        <div
          key={idx}
          style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 2fr 2fr auto auto',
            gap: 'var(--sp-2)',
            alignItems: 'center',
            marginBottom: 'var(--sp-2)',
          }}
        >
          <input
            type="text"
            className="form-input"
            placeholder="Thời gian"
            value={row.period || ''}
            onChange={(e) => updateRow(idx, 'period', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Chức danh"
            value={row.title || ''}
            onChange={(e) => updateRow(idx, 'title', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Công ty"
            value={row.company || ''}
            onChange={(e) => updateRow(idx, 'company', e.target.value)}
          />
          <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 'var(--fs-xs)', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={Boolean(row.current)}
              onChange={(e) => updateRow(idx, 'current', e.target.checked)}
            />
            Hiện tại
          </label>
          <button
            type="button"
            className="btn btn-tertiary"
            onClick={() => removeRow(idx)}
            style={{ color: 'var(--err)', padding: 'var(--sp-1)' }}
            title="Xoá dòng"
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--sp-2)' }}>
        <button type="button" className="btn btn-tertiary" onClick={addRow} style={{ fontSize: 'var(--fs-xs)' }}>
          + Thêm học vấn
        </button>
      </div>
      {items.map((row, idx) => (
        <div
          key={idx}
          style={{
            display: 'grid',
            gridTemplateColumns: '2fr 3fr 1.5fr auto',
            gap: 'var(--sp-2)',
            alignItems: 'center',
            marginBottom: 'var(--sp-2)',
          }}
        >
          <input
            type="text"
            className="form-input"
            placeholder="Văn bằng / Chứng chỉ"
            value={row.title || ''}
            onChange={(e) => updateRow(idx, 'title', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Trường / Nơi cấp"
            value={row.detail || ''}
            onChange={(e) => updateRow(idx, 'detail', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Năm / Thời gian"
            value={row.period || ''}
            onChange={(e) => updateRow(idx, 'period', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-tertiary"
            onClick={() => removeRow(idx)}
            style={{ color: 'var(--err)', padding: 'var(--sp-1)' }}
            title="Xoá dòng"
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--sp-2)' }}>
        <button type="button" className="btn btn-tertiary" onClick={addRow} style={{ fontSize: 'var(--fs-xs)' }}>
          + Thêm người tham chiếu
        </button>
      </div>
      {items.map((row, idx) => (
        <div
          key={idx}
          style={{
            display: 'grid',
            gridTemplateColumns: '2fr 2fr 2fr auto',
            gap: 'var(--sp-2)',
            alignItems: 'center',
            marginBottom: 'var(--sp-2)',
          }}
        >
          <input
            type="text"
            className="form-input"
            placeholder="Họ tên"
            value={row.name || ''}
            onChange={(e) => updateRow(idx, 'name', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Chức danh"
            value={row.title || ''}
            onChange={(e) => updateRow(idx, 'title', e.target.value)}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Công ty"
            value={row.company || ''}
            onChange={(e) => updateRow(idx, 'company', e.target.value)}
          />
          <button
            type="button"
            className="btn btn-tertiary"
            onClick={() => removeRow(idx)}
            style={{ color: 'var(--err)', padding: 'var(--sp-1)' }}
            title="Xoá dòng"
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
    <div style={{ marginTop: 'var(--sp-2)', marginBottom: 'var(--sp-2)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--faint)' }}>
          Dòng phụ (nhãn để trống = dòng nghiêng)
        </span>
        <button type="button" className="btn btn-tertiary" onClick={addMeta} style={{ fontSize: 'var(--fs-xs)', padding: '2px 4px' }}>
          + Thêm dòng phụ
        </button>
      </div>
      {meta.map((m, idx) => (
        <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 'var(--sp-2)', marginTop: '4px', alignItems: 'center' }}>
          <input
            type="text"
            className="form-input"
            placeholder="Nhãn (vd: Quy mô)"
            value={m.label || ''}
            onChange={(e) => updateMeta(idx, 'label', e.target.value)}
            style={{ fontSize: 'var(--fs-sm)', padding: '4px 8px' }}
          />
          <input
            type="text"
            className="form-input"
            placeholder="Nội dung dòng phụ"
            value={m.text || ''}
            onChange={(e) => updateMeta(idx, 'text', e.target.value)}
            style={{ fontSize: 'var(--fs-sm)', padding: '4px 8px' }}
          />
          <button
            type="button"
            className="btn btn-tertiary"
            onClick={() => removeMeta(idx)}
            style={{ color: 'var(--err)', padding: '2px 6px' }}
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
    <div style={{ marginTop: 'var(--sp-2)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 500, color: 'var(--muted)' }}>
          {bulletLabel}
        </span>
        <button type="button" className="btn btn-tertiary" onClick={addGroup} style={{ fontSize: 'var(--fs-xs)', padding: '2px 4px' }}>
          + Thêm nhóm việc
        </button>
      </div>
      {groups.map((g, idx) => (
        <div key={idx} style={{ borderLeft: '2px solid var(--line)', paddingLeft: 'var(--sp-2)', margin: 'var(--sp-2) 0' }}>
          <div style={{ display: 'flex', gap: 'var(--sp-2)', marginBottom: '4px', alignItems: 'center' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Tiêu đề nhóm việc (không bắt buộc)"
              value={g.title || ''}
              onChange={(e) => updateGroup(idx, 'title', e.target.value || null)}
              style={{ fontSize: 'var(--fs-sm)', padding: '4px 8px' }}
            />
            {groups.length > 1 && (
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={() => removeGroup(idx)}
                style={{ color: 'var(--err)' }}
              >
                ✕
              </button>
            )}
          </div>
          <textarea
            className="form-textarea"
            rows={3}
            value={(g.bullets || []).join('\n')}
            onChange={(e) => updateGroup(idx, 'bullets', e.target.value.split('\n'))}
            placeholder="Mỗi dòng là một ý..."
            style={{ fontSize: 'var(--fs-sm)' }}
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
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--sp-2)' }}>
        <button type="button" className="btn btn-tertiary" onClick={addJob} style={{ fontSize: 'var(--fs-xs)' }}>
          + Thêm công việc
        </button>
      </div>

      {jobs.map((job, idx) => (
        <div
          key={idx}
          style={{
            border: '1px solid var(--line)',
            borderRadius: 'var(--r-md)',
            padding: 'var(--sp-3)',
            marginBottom: 'var(--sp-4)',
            background: 'var(--soft)',
          }}
        >
          {/* Header công việc */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-2)' }}>
            <span style={{ fontWeight: 600, fontSize: 'var(--fs-sm)', color: 'var(--ink)' }}>
              Công việc {idx + 1}
            </span>
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={() => moveJob(idx, -1)}
                disabled={idx === 0}
                style={{ padding: '2px 6px' }}
                title="Di chuyển lên"
              >
                ▲
              </button>
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={() => moveJob(idx, 1)}
                disabled={idx === jobs.length - 1}
                style={{ padding: '2px 6px' }}
                title="Di chuyển xuống"
              >
                ▼
              </button>
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={() => removeJob(idx)}
                style={{ color: 'var(--err)', padding: '2px 6px' }}
                title="Xoá công việc này"
              >
                ✕ Xoá
              </button>
            </div>
          </div>

          <div className="form-row" style={{ marginBottom: 'var(--sp-2)' }}>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                Công ty
              </label>
              <input
                type="text"
                className="form-input"
                value={job.company || ''}
                onChange={(e) => updateJob(idx, { ...job, company: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                Thời gian
              </label>
              <input
                type="text"
                className="form-input"
                placeholder="03/2020 – Nay"
                value={job.period || ''}
                onChange={(e) => updateJob(idx, { ...job, period: e.target.value || null })}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: 'var(--sp-2)' }}>
            <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
              Chức danh
            </label>
            <input
              type="text"
              className="form-input"
              value={job.role || ''}
              onChange={(e) => updateJob(idx, { ...job, role: e.target.value || null })}
            />
          </div>

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
          <div style={{ marginTop: 'var(--sp-3)', borderTop: '1px dashed var(--line-strong)', paddingTop: 'var(--sp-2)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 600, color: 'var(--muted)' }}>
                Vị trí con ({ (job.sub_roles || []).length })
              </span>
              <button
                type="button"
                className="btn btn-tertiary"
                onClick={() =>
                  updateJob(idx, {
                    ...job,
                    sub_roles: [
                      ...(job.sub_roles || []),
                      { name: '', period: null, meta: [], groups: [{ title: null, bullets: [] }] },
                    ],
                  })
                }
                style={{ fontSize: 'var(--fs-xs)', padding: '2px 4px' }}
              >
                + Thêm vị trí con
              </button>
            </div>

            {(job.sub_roles || []).map((sub, sIdx) => (
              <div
                key={sIdx}
                style={{
                  border: '1px solid var(--line)',
                  borderRadius: 'var(--r-sm)',
                  padding: 'var(--sp-2)',
                  marginTop: 'var(--sp-2)',
                  background: 'var(--white)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <span style={{ fontSize: 'var(--fs-xs)', fontWeight: 500 }}>Vị trí con {sIdx + 1}</span>
                  <button
                    type="button"
                    className="btn btn-tertiary"
                    onClick={() => {
                      const newSubs = job.sub_roles.filter((_, i) => i !== sIdx)
                      updateJob(idx, { ...job, sub_roles: newSubs })
                    }}
                    style={{ color: 'var(--err)', padding: '2px' }}
                  >
                    ✕
                  </button>
                </div>
                <div className="form-row">
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Tên vị trí con"
                    value={sub.name || ''}
                    onChange={(e) => {
                      const newSubs = [...job.sub_roles]
                      newSubs[sIdx] = { ...newSubs[sIdx], name: e.target.value }
                      updateJob(idx, { ...job, sub_roles: newSubs })
                    }}
                    style={{ fontSize: 'var(--fs-sm)' }}
                  />
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Thời gian vị trí con"
                    value={sub.period || ''}
                    onChange={(e) => {
                      const newSubs = [...job.sub_roles]
                      newSubs[sIdx] = { ...newSubs[sIdx], period: e.target.value || null }
                      updateJob(idx, { ...job, sub_roles: newSubs })
                    }}
                    style={{ fontSize: 'var(--fs-sm)' }}
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

