import ReviewBadge from './ReviewBadge.jsx'

// Thành phần chỉnh sửa thông tin chung của ứng viên (họ tên, chức danh, năm sinh, giới tính, thông tin nhanh)
export default function GeneralInfoEditor({ cv, onChange, review }) {
  const updateField = (field, value) => {
    onChange({ ...cv, [field]: value })
  }

  const handleFactsChange = (index, key, val) => {
    const newFacts = [...(cv.facts || [])]
    newFacts[index] = { ...newFacts[index], [key]: val }
    onChange({ ...cv, facts: newFacts })
  }

  const addFact = () => {
    onChange({ ...cv, facts: [...(cv.facts || []), { label: '', value: '' }] })
  }

  const removeFact = (index) => {
    const newFacts = (cv.facts || []).filter((_, i) => i !== index)
    onChange({ ...cv, facts: newFacts })
  }

  return (
    <div style={{ marginBottom: 'var(--sp-5)' }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 'var(--sp-3)' }}>
        <h4 style={{ margin: 0 }}>Thông tin chung</h4>
        <ReviewBadge
          review={review}
          paths={['full_name', 'target_title', 'birth_year', 'gender', 'facts', 'expected_salary']}
        />
      </div>

      <div className="form-row" style={{ marginBottom: 'var(--sp-3)' }}>
        <div className="form-group">
          <label className="form-label">
            Họ và tên <span style={{ color: 'var(--err)' }}>*</span>
            <ReviewBadge review={review} paths="full_name" />
          </label>
          <input
            type="text"
            className="form-input"
            value={cv.full_name || ''}
            onChange={(e) => updateField('full_name', e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            Chức danh
            <ReviewBadge review={review} paths="target_title" />
          </label>
          <input
            type="text"
            className="form-input"
            value={cv.target_title || ''}
            onChange={(e) => updateField('target_title', e.target.value)}
          />
        </div>
      </div>

      <div className="form-row" style={{ marginBottom: 'var(--sp-3)' }}>
        <div className="form-group">
          <label className="form-label">
            Năm sinh
            <ReviewBadge review={review} paths="birth_year" />
          </label>
          <input
            type="number"
            className="form-input"
            value={cv.birth_year || ''}
            onChange={(e) => updateField('birth_year', e.target.value ? parseInt(e.target.value, 10) : null)}
          />
        </div>

        <div className="form-group">
          <label className="form-label">
            Giới tính
            <ReviewBadge review={review} paths="gender" />
          </label>
          <input
            type="text"
            className="form-input"
            value={cv.gender || ''}
            onChange={(e) => updateField('gender', e.target.value)}
            placeholder="Nam / Nữ"
          />
        </div>
      </div>

      {/* Thông tin nhanh khác (facts) */}
      <div style={{ marginTop: 'var(--sp-3)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-2)' }}>
          <span style={{ fontSize: 'var(--fs-sm)', fontWeight: 500, color: 'var(--muted)' }}>
            Thông tin nhanh khác (vd: Mong muốn)
          </span>
          <button type="button" className="btn btn-tertiary" onClick={addFact} style={{ fontSize: 'var(--fs-xs)' }}>
            + Thêm dòng
          </button>
        </div>

        {(cv.facts || []).map((fact, idx) => (
          <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 'var(--sp-2)', marginBottom: 'var(--sp-2)', alignItems: 'center' }}>
            <input
              type="text"
              className="form-input"
              placeholder="Nhãn (vd: Mong muốn)"
              value={fact.label || ''}
              onChange={(e) => handleFactsChange(idx, 'label', e.target.value)}
            />
            <input
              type="text"
              className="form-input"
              placeholder="Nội dung"
              value={fact.value || ''}
              onChange={(e) => handleFactsChange(idx, 'value', e.target.value)}
            />
            <button
              type="button"
              className="btn btn-tertiary"
              onClick={() => removeFact(idx)}
              style={{ color: 'var(--err)', padding: 'var(--sp-1)' }}
              title="Xoá dòng"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
