import { useEffect, useState } from 'react'
import { getOriginalInfo, getOriginalPageUrl } from '../api/client.js'

// Xem trước các trang của file CV gốc để đối chiếu nội dung
export default function OriginalCvPreview({ runId, originalName }) {
  const [info, setInfo] = useState(null)
  const [loading, setLoading] = useState(true)
  const [errorMsg, setErrorMsg] = useState(null)

  useEffect(() => {
    if (!runId) return
    let active = true

    getOriginalInfo(runId)
      .then((data) => {
        if (active) {
          setInfo(data)
          setLoading(false)
        }
      })
      .catch((err) => {
        if (active) {
          setErrorMsg(err.message || 'Không xem trước được file gốc.')
          setLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [runId])

  if (loading) {
    return (
      <div className="preview-container">
        <p className="text-muted">Đang tải bản xem trước CV gốc...</p>
      </div>
    )
  }

  if (errorMsg || (info && !info.can_preview)) {
    return (
      <div className="preview-container">
        <div className="lh-alert info max-w-[600px] w-full">
          <div className="t">Thông báo xem trước</div>
          <p className="m-0">
            {info?.message || errorMsg || 'File này không hỗ trợ xem trước trực tiếp. Hãy mở file gốc trên máy để đối chiếu.'}
          </p>
        </div>
      </div>
    )
  }

  const pageCount = info?.page_count || 1
  const pages = Array.from({ length: pageCount }, (_, i) => i + 1)

  return (
    <div className="preview-container">
      {pages.map((p) => (
        <img
          key={p}
          src={getOriginalPageUrl(runId, p)}
          alt={`Trang ${p} - ${originalName || 'CV gốc'}`}
          loading="lazy"
        />
      ))}
    </div>
  )
}
