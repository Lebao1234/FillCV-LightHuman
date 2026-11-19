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
      ⚠ Cần xem: {matchedNotes.join(' · ')}
    </span>
  )
}

