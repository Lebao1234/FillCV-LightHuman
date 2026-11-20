// Nhãn "Cần xem" cho trường hoặc mục có độ tin cậy thấp hoặc có cảnh báo
export default function ReviewBadge({ review, paths = [] }) {
  if (!review) return null

  const { confidence = {}, notes = [] } = review
  const pathList = Array.isArray(paths) ? paths : [paths]
  const matchedNotes = []

  // Kiểm tra độ tin cậy (< 0.7)
  for (const p of pathList) {
    if (p in confidence && confidence[p] < 0.7) {
      const pct = Math.round(confidence[p] * 100)
      matchedNotes.push(`độ tin cậy ${pct}%`)
    }
  }

  // Kiểm tra cảnh báo ghi chú (notes)
  for (const [np, msg] of notes) {
    if (pathList.some((p) => p === np || np.startsWith(`${p}.`) || np.startsWith(`${p}[`))) {
      matchedNotes.push(msg)
    }
  }

  if (matchedNotes.length === 0) return null

  return (
    <span className="badge-review" title={matchedNotes.join(' · ')}>
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 9v4M12 17h.01" />
        <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
      </svg>
      Cần xem: {matchedNotes.join(' · ')}
    </span>
  )
}

