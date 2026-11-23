
import Field from '../Field.jsx'
const MAX_STATS = 4
const STAT_LABEL_MAX_LEN = 35

// Thành phần chỉnh sửa hàng ô số liệu (tối đa 4 ô)
export default function StatsEditor({ cv, onChange }) {
  const stats = cv.stats || []

  const handleStatChange = (index, field, value) => {
    const newStats = [...stats]
    newStats[index] = { ...newStats[index], [field]: value }
    onChange({ ...cv, stats: newStats })
  }

  const addStat = () => {
    if (stats.length >= MAX_STATS) return
    onChange({ ...cv, stats: [...stats, { value: '', label: '', source: 'original' }] })
  }

  const removeStat = (index) => {
    onChange({ ...cv, stats: stats.filter((_, i) => i !== index) })
  }

  return (
    <div className="mb-6">
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center">
          <h4 className="m-0">Hàng ô số liệu (tối đa 4)</h4>
        </div>
        {stats.length < MAX_STATS && (
          <button type="button" className="btn btn-tertiary text-xs" onClick={addStat}>
            + Thêm ô số liệu
          </button>
        )}
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3">
        {stats.map((s, idx) => {
          const isTooLong = (s.label || '').length > STAT_LABEL_MAX_LEN
          return (
            <div
              key={idx}
              className="relative rounded-md border border-line bg-soft p-3"
            >
              <button
                type="button"
                onClick={() => removeStat(idx)}
              className="absolute top-1 right-1.5 cursor-pointer border-0 bg-transparent text-faint text-sm hover:text-err"
                title="Xoá ô"
                aria-label="Xoá ô"
              >
                ✕
              </button>
              <Field label="Số liệu (vd: 10+)" small className="mb-2">
                <input
                  type="text"
                  className="form-input"
                  value={s.value || ''}
                  onChange={(e) => handleStatChange(idx, 'value', e.target.value)}
                />
              </Field>
              <Field label="Chú thích" small>
                <input
                  type="text"
                  className="form-input"
                  value={s.label || ''}
                  onChange={(e) => handleStatChange(idx, 'label', e.target.value)}
                />
              </Field>
              {isTooLong && (
                <span className="mt-0.5 block text-xs text-warn" role="status">
                  Dài hơn {STAT_LABEL_MAX_LEN} ký tự, có thể tràn ô.
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

