
import Field from '../Field.jsx'
// Thành phần chỉnh sửa thông tin chung của ứng viên (họ tên, chức danh, năm sinh, giới tính, thông tin nhanh)
export default function GeneralInfoEditor({ cv, onChange }) {
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
    <div className="mb-6">
      <div className="flex items-center mb-3">
        <h4 className="m-0">Thông tin chung</h4>
      </div>

      <div className="form-row mb-3">
        <Field label={<>Họ và tên <span className="text-err">*</span></>}>
<input
            type="text"
            className="form-input"
            value={cv.full_name || ''}
            onChange={(e) => updateField('full_name', e.target.value)}
          />
        </Field>

        <Field label={<>Chức danh</>}>
<input
            type="text"
            className="form-input"
            value={cv.target_title || ''}
            onChange={(e) => updateField('target_title', e.target.value)}
          />
        </Field>
      </div>

      <div className="form-row mb-3">
        <Field label={<>Năm sinh</>}>
<input
            type="number"
            className="form-input"
            value={cv.birth_year || ''}
            onChange={(e) => updateField('birth_year', e.target.value ? parseInt(e.target.value, 10) : null)}
          />
        </Field>

        <Field label={<>Giới tính</>}>
<input
            type="text"
            className="form-input"
            value={cv.gender || ''}
            onChange={(e) => updateField('gender', e.target.value)}
            placeholder="Nam / Nữ"
            aria-label="Nam / Nữ"
          />
        </Field>
      </div>

      {/* Thông tin nhanh khác (facts) */}
      <div className="mt-3">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm font-medium text-muted">
            Thông tin nhanh khác (vd: Mong muốn)
          </span>
          <button type="button" className="btn btn-tertiary text-xs" onClick={addFact}>
            + Thêm dòng
          </button>
        </div>

        {(cv.facts || []).map((fact, idx) => (
          <div key={idx} className="grid grid-cols-[1fr_2fr_auto] gap-2 mb-2 items-center">
            <input
              type="text"
              className="form-input"
              placeholder="Nhãn (vd: Mong muốn)"
              aria-label="Nhãn (vd: Mong muốn)"
              value={fact.label || ''}
              onChange={(e) => handleFactsChange(idx, 'label', e.target.value)}
            />
            <input
              type="text"
              className="form-input"
              placeholder="Nội dung"
              aria-label="Nội dung"
              value={fact.value || ''}
              onChange={(e) => handleFactsChange(idx, 'value', e.target.value)}
            />
            <button
              type="button"
              className="btn btn-tertiary text-err p-1"
              onClick={() => removeFact(idx)}
              title="Xoá dòng"
              aria-label="Xoá dòng"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

