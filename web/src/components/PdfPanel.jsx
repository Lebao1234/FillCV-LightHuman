import { useId, useState } from 'react'
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
  isTranslating = false,
  translateError = null,
  langNote = '',
  keepContact = false,
  contactMissing = false,
  onChangeKeepContact,
}) {
  const [showChecklist, setShowChecklist] = useState(false)
  const checklistId = useId()
  const downloadHintId = useId()

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

      {/* Tuỳ chọn ngôn ngữ & liên hệ chia 2 cột Tailwind, nút hành động xếp gọn một hàng */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3 bg-surface border border-line rounded-md mb-3">
        <div className="lang-options min-w-0">
          <span className="font-medium text-muted">Ngôn ngữ:</span>
          <label>
            <input
              type="radio"
              name="pdf_lang"
              value="vi"
              checked={pdfLang === 'vi'}
              disabled={isTranslating || isBuilding}
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
              disabled={isTranslating || isBuilding}
              onChange={() => onChangeLang('en')}
            />
            English
          </label>
          {/* Trạng thái dịch nội dung khi đổi ngôn ngữ: đang dịch / lỗi / chỉ đổi được nhãn */}
          {isTranslating && (
            <p className="m-0 mt-1 w-full text-xs text-muted" role="status" aria-live="polite">
              Đang dịch nội dung hồ sơ, vui lòng chờ...
            </p>
          )}
          {!isTranslating && translateError && (
            <p className="m-0 mt-1 w-full text-xs text-err" role="alert">
              Chưa dịch được: {translateError}
            </p>
          )}
          {!isTranslating && !translateError && langNote && (
            <p className="m-0 mt-1 w-full text-xs text-warn" role="note">
              {langNote}
            </p>
          )}
        </div>

        <div className="contact-options min-w-0">
          <label className="inline-flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              name="keep_contact"
              checked={keepContact}
              onChange={(e) => onChangeKeepContact && onChangeKeepContact(e.target.checked)}
            />
            <span>{keepContact ? 'Giữ nguyên liên hệ (không cắt contact)' : 'Cắt bỏ toàn bộ contact'}</span>
          </label>
          {keepContact && contactMissing && (
            <p className="m-0 mt-1 text-xs text-warn" role="note">
              Hồ sơ này đã được đọc ở chế độ cắt liên hệ nên chưa có SĐT/email để giữ. Hãy nạp lại CV và chọn &quot;Giữ nguyên liên hệ&quot; ở form tải lên.
            </p>
          )}
        </div>
      </div>

      {/* Hàng nút hành động */}
      <div className="action-row flex flex-wrap items-center gap-2.5">
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
          aria-describedby={status?.can_download ? undefined : downloadHintId}
        >
          Tải PDF
        </button>
      </div>

      {hasPdf && !status?.can_download && !isBuilding && (
        <p id={downloadHintId} className="mb-3 text-sm text-muted">
          Chưa tải được PDF: cần tick 2 ô xác nhận, PDF phải là bản mới nhất và không còn thông tin nhạy cảm.
        </p>
      )}

      {/* Checklist chất lượng */}
      {hasPdf && checklist.length > 0 && (
        <div className="mb-4">
          <button
            type="button"
            className="btn btn-secondary btn-block justify-between text-sm"
            onClick={() => setShowChecklist(!showChecklist)}
            aria-expanded={showChecklist}
            aria-controls={checklistId}
          >
            <span>
              Checklist chất lượng · {okCount}/{checklist.length} đạt
            </span>
            <span className="inline-flex items-center gap-1">
              {showChecklist ? 'Thu gọn' : 'Chi tiết'}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={showChecklist ? 'rotate-180' : ''}>
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </span>
          </button>
          {showChecklist && (
            <div id={checklistId} className="border border-line border-t-0 p-3 bg-white">
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
              key={`${pdfData.fingerprint || ''}-${p}`}
              src={getPdfPageUrl(pdfData.run_id, p, pdfData.fingerprint || pdfData.filename)}
              alt={`Trang ${p} - ${filename}`}
              loading="lazy"
            />
          ))}
        </div>
      )}
    </div>
  )
}
