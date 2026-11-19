import { useState } from 'react'
import StatusBar from './StatusBar.jsx'
import { getDownloadUrl, getPdfPageUrl } from '../api/client.js'

// Bảng điều khiển bản PDF: xem trước, checklist, tuỳ chọn ngôn ngữ và nút cập nhật/tải
export default function PdfPanel({
  pdfData,
  structureErrors = [],
  violations = [],
  status,
  isBuilding = false,
  onUpdatePdf,
  checkedGenerated,
  setCheckedGenerated,
  reviewed,
  setReviewed,
  pdfLang,
  onChangeLang,
}) {
  const [showChecklist, setShowChecklist] = useState(false)

  const hasPdf = Boolean(pdfData?.pdf_bytes_ready || pdfData?.filename)
  const filename = pdfData?.filename || 'Chưa có bản PDF'
  const pageCount = pdfData?.page_count || 0
  const aside = pageCount > 0 ? `A4 · ${pageCount} trang` : 'Bấm Cập nhật PDF để dựng'
  const checklist = pdfData?.checklist || []
  const okCount = checklist.filter((r) => r.ok).length

  const handleDownload = () => {
    if (!status?.can_download || !pdfData?.run_id) return
    window.location.href = getDownloadUrl(pdfData.run_id, true)
  }

  const piiViolationsInPdf = checklist.filter((r) => r.code === 'pii' && !r.ok)

  return (
    <div>
      <StatusBar
        filename={filename}
        aside={aside}
        pillKind={status?.pill_kind || 'idle'}
        pillText={status?.pill_text || 'Chưa dựng'}
      />

      {/* Các hộp cảnh báo */}
      {structureErrors.length > 0 && (
        <div className="lh-alert err">
          <div className="t">Hồ sơ chưa hợp lệ — sửa ở tab Chỉnh sửa nội dung</div>
          <ul>
            {structureErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {violations.length > 0 && (
        <div className="lh-alert err">
          <div className="t">Còn thông tin nhạy cảm — phải sửa trước khi tải PDF</div>
          <ul>
            {violations.map((v, i) => (
              <li key={i}>
                {v.kind} <code>{v.value}</code> tại <code>{v.field}</code>
              </li>
            ))}
          </ul>
        </div>
      )}

      {status?.outdated && structureErrors.length === 0 && (
        <div className="lh-alert warn">
          <div className="t">Nội dung đã thay đổi so với bản PDF đang hiển thị</div>
          <ul>
            <li>Bấm Cập nhật PDF để dựng lại trước khi tải.</li>
          </ul>
        </div>
      )}

      {status?.pdf_dirty && (
        <div className="lh-alert err">
          <div className="t">Bản PDF vẫn còn thông tin liên hệ của ứng viên — phải sửa trước khi tải</div>
          <ul>
            {piiViolationsInPdf.map((r, i) => (
              <li key={i}>{r.detail}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Checkbox xác nhận duyệt */}
      {hasPdf && (
        <div className="ack-row">
          <label className="ack-checkbox">
            <input
              type="checkbox"
              checked={checkedGenerated}
              onChange={(e) => setCheckedGenerated(e.target.checked)}
            />
            Đã kiểm tra các mục hệ thống tự lập
          </label>
          <label className="ack-checkbox">
            <input
              type="checkbox"
              checked={reviewed}
              onChange={(e) => setReviewed(e.target.checked)}
            />
            Đã đọc và duyệt toàn bộ hồ sơ
          </label>
        </div>
      )}

      {/* Hàng hành động */}
      <div className="action-row">
        <div className="lang-options">
          <span style={{ fontWeight: 500, color: 'var(--muted)' }}>Ngôn ngữ:</span>
          <label>
            <input
              type="radio"
              name="pdf_lang"
              value="vi"
              checked={pdfLang === 'vi'}
              onChange={() => onChangeLang('vi')}
            />
            Tiếng Việt
          </label>
          <label>
            <input
              type="radio"
              name="pdf_lang"
              value="en"
              checked={pdfLang === 'en'}
              onChange={() => onChangeLang('en')}
            />
            English
          </label>
        </div>

        <button
          type="button"
          className={`btn ${status?.outdated || !hasPdf ? 'btn-primary' : 'btn-secondary'}`}
          onClick={onUpdatePdf}
          disabled={structureErrors.length > 0 || isBuilding}
        >
          {isBuilding ? 'Đang dựng...' : 'Cập nhật PDF'}
        </button>

        <button
          type="button"
          className={`btn ${status?.can_download ? 'btn-primary' : 'btn-secondary'}`}
          onClick={handleDownload}
          disabled={!status?.can_download || isBuilding}
          title={
            status?.can_download
              ? 'Tải file PDF về máy'
              : 'Cần tick 2 ô xác nhận, PDF mới nhất và không còn thông tin nhạy cảm'
          }
        >
          Tải PDF
        </button>
      </div>

      {/* Checklist chất lượng */}
      {hasPdf && checklist.length > 0 && (
        <div style={{ marginBottom: 'var(--sp-4)' }}>
          <button
            type="button"
            className="btn btn-secondary btn-block"
            onClick={() => setShowChecklist(!showChecklist)}
            style={{ justifyContent: 'space-between', fontSize: 'var(--fs-sm)' }}
          >
            <span>
              Checklist chất lượng · {okCount}/{checklist.length} đạt
            </span>
            <span>{showChecklist ? '▲ Thu gọn' : '▼ Chi tiết'}</span>
          </button>
          {showChecklist && (
            <div style={{ border: '1px solid var(--line)', borderTop: 'none', padding: 'var(--sp-3)', background: 'var(--white)' }}>
              {checklist.map((r, i) => (
                <div key={i} className={`lh-check ${r.ok ? '' : 'no'}`}>
                  <span className="m" />
                  <span>{r.item}</span>
                  {r.detail && <small>{r.detail}</small>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Khung hiển thị PDF */}
      {hasPdf && pageCount > 0 && (
        <div className="preview-container">
          {Array.from({ length: pageCount }, (_, i) => i + 1).map((p) => (
            <img
              key={p}
              src={getPdfPageUrl(pdfData.run_id, p)}
              alt={`Trang ${p} - ${filename}`}
              loading="lazy"
            />
          ))}
        </div>
      )}
    </div>
  )
}
