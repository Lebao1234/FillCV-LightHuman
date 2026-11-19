import ReviewBadge from './ReviewBadge.jsx'

const MAX_STATS = 4
const STAT_LABEL_MAX_LEN = 35

// Thành phần chỉnh sửa hàng ô số liệu (tối đa 4 ô)
export default function StatsEditor({ cv, onChange, review }) {
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
    <div style={{ marginBottom: 'var(--sp-5)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--sp-2)' }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h4 style={{ margin: 0 }}>Hàng ô số liệu (tối đa 4)</h4>
          <ReviewBadge review={review} paths="stats" />
        </div>
        {stats.length < MAX_STATS && (
          <button type="button" className="btn btn-tertiary" onClick={addStat} style={{ fontSize: 'var(--fs-xs)' }}>
            + Thêm ô số liệu
          </button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--sp-3)' }}>
        {stats.map((s, idx) => {
          const isTooLong = (s.label || '').length > STAT_LABEL_MAX_LEN
          return (
            <div
              key={idx}
              style={{
                border: '1px solid var(--line)',
                borderRadius: 'var(--r-md)',
                padding: 'var(--sp-3)',
                background: 'var(--soft)',
                position: 'relative',
              }}
            >
              <button
                type="button"
                onClick={() => removeStat(idx)}
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '6px',
                  background: 'none',
                  border: 'none',
                  color: 'var(--faint)',
                  cursor: 'pointer',
                  fontSize: 'var(--fs-sm)',
                }}
                title="Xoá ô"
              >
                ✕
              </button>
              <div className="form-group" style={{ marginBottom: 'var(--sp-2)' }}>
                <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                  Số liệu (vd: 10+)
                </label>
                <input
                  type="text"
                  className="form-input"
                  value={s.value || ''}
                  onChange={(e) => handleStatChange(idx, 'value', e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label" style={{ fontSize: 'var(--fs-xs)' }}>
                  Chú thích
                </label>
                <input
                  type="text"
                  className="form-input"
                  value={s.label || ''}
                  onChange={(e) => handleStatChange(idx, 'label', e.target.value)}
                />
                {isTooLong && (
                  <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--warn)', marginTop: '2px' }}>
                    Dài hơn {STAT_LABEL_MAX_LEN} ký tự, có thể tràn ô.
                  </span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
