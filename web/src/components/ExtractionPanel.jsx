import { useRef, useState } from 'react'

const ICON_FILE = (
  <svg
    width="20"
    height="20"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 17h4" />
  </svg>
)

const ICON_CHECK = (
  <svg
    width="16"
    height="16"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <polyline points="20 6 9 17 4 12" />
  </svg>
)

const ICON_COPY = (
  <svg
    width="15"
    height="15"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
  </svg>
)

const ICON_UPLOAD = (
  <svg
    width="28"
    height="28"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
)

// Khung trạng thái bóc tách CV dạng stateful pipeline theo dõi quy trình xử lý
export default function ExtractionPanel({
  isExtracting = false,
  isBuildingPdf = false,
  queuePos = 0,
  queueWhat = 'đọc CV',
  activeStep = 0,
  stageLabels = [],
  cvData = null,
  originalName = '',
  project = '',
  position = '',
  summary = '',
  review = null,
  error = null,
  structureErrors = [],
  violations = [],
  onSubmitCv,
  onReset,
}) {
  const [file, setFile] = useState(null)
  const [inputProject, setInputProject] = useState(project || '')
  const [inputPosition, setInputPosition] = useState(position || '')
  const [copied, setCopied] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)

  const hasData = Boolean(cvData)
  const isBusy = isExtracting || isBuildingPdf

  // Xử lý gửi form nạp file CV
  const handleSubmit = (e) => {
    e.preventDefault()
    if (!file || isBusy) return
    onSubmitCv({
      file,
      project: inputProject,
      position: inputPosition,
    })
    setFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Xử lý kéo thả file
  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0])
    }
  }

  // Xử lý chọn file qua input
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  // Sao chép nội dung tin nhắn tóm tắt
  const handleCopySummary = () => {
    if (!summary) return
    navigator.clipboard.writeText(summary)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Danh sách các bước bóc tách mặc định nếu chưa nhận từ SSE
  const defaultSteps = [
    'Tiếp nhận file CV & kiểm tra định dạng',
    'Đọc lớp chữ & bố cục đa cột',
    'Nhận diện tiêu đề & phân tách các mục',
    'Lọc bỏ thông tin liên hệ (PII) & trích xuất nhân thân',
    'Bóc tách kinh nghiệm, học vấn & số liệu',
    'Cắt ảnh chân dung tự động (OpenCV)',
    'Dựng PDF & kiểm tra chất lượng bản xuất',
  ]

  const steps = stageLabels && stageLabels.length > 0 ? stageLabels : defaultSteps

  // Trích xuất các ghi chú từ model_notes của CV
  const modelNotes = cvData?.model_notes || {}
  const removedFields = modelNotes.removed || []
  const selfCreated = [...(modelNotes.self_created || []), ...(modelNotes.other || [])]
  const recruitingFlags = modelNotes.recruiting_flags || []
  const reviewNotes = review?.notes || []
  const totalErrors = structureErrors.length + violations.length

  return (
    <div className="stateful-panel">
      {/* Tiêu đề panel và nút làm mới */}
      <div className="lh-ph">
        <div className="h">Trạng thái bóc tách CV</div>
        {(hasData || isBusy || error) && (
          <button
            type="button"
            className="btn btn-tertiary"
            onClick={onReset}
            disabled={isBusy}
          >
            Làm mới / Nạp CV khác
          </button>
        )}
      </div>

      <div className="stateful-body">
        {/* THẺ NẠP FILE CV: Hiển thị form nạp khi chưa có CV, hoặc hiển thị thẻ thông tin file đã nạp */}
        {!hasData && !isBusy ? (
          <form className="upload-stateful-card" onSubmit={handleSubmit}>
            <div
              className={`dropzone-stateful ${isDragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
            >
              <div className="dropzone-icon">{ICON_UPLOAD}</div>
              <div className="dropzone-content">
                {file ? (
                  <>
                    <div className="dropzone-filename">{file.name}</div>
                    <div className="dropzone-hint">
                      {(file.size / 1024 / 1024).toFixed(2)} MB · Bấm để đổi file khác
                    </div>
                  </>
                ) : (
                  <>
                    <div className="dropzone-title">Kéo thả file CV vào đây hoặc bấm để chọn</div>
                    <div className="dropzone-hint">Hỗ trợ định dạng PDF, DOCX, PNG, JPG (tối đa 20 MB)</div>
                  </>
                )}
              </div>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                style={{ display: 'none' }}
                accept=".pdf,.docx,.png,.jpg,.jpeg"
              />
            </div>

            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Tên dự án</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Ví dụ: Message Coffee"
                  value={inputProject}
                  onChange={(e) => setInputProject(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label className="form-label">Vị trí ứng tuyển</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Ví dụ: Kế toán trưởng (hoặc theo CV)"
                  value={inputPosition}
                  onChange={(e) => setInputPosition(e.target.value)}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={!file || isBusy}
            >
              Bắt đầu bóc tách CV
            </button>
          </form>
        ) : (
          /* THẺ NGUỒN FILE ĐÃ NẠP */
          <div className="source-file-badge">
            <div className="sf-left">
              <div className="sf-icon">{ICON_FILE}</div>
              <div className="sf-info">
                <div className="sf-name">{originalName || file?.name || 'File CV'}</div>
                <div className="sf-meta">
                  Dự án: <strong>{project || '—'}</strong> · Vị trí: <strong>{position || 'Theo CV'}</strong>
                </div>
              </div>
            </div>
            <span className={`sf-status-tag ${hasData ? 'success' : isBusy ? 'processing' : 'idle'}`}>
              {hasData ? 'Đã bóc tách' : isBusy ? 'Đang xử lý' : 'Chờ xử lý'}
            </span>
          </div>
        )}

        {/* CẢNH BÁO LỖI NẾU CÓ */}
        {error && (
          <div className="lh-alert err" style={{ marginTop: 'var(--sp-3)' }}>
            <div className="t">Không thể hoàn tất bóc tách CV</div>
            <div className="m">{error}</div>
          </div>
        )}

        {/* HÀNG CHỜ XỬ LÝ NẾU CÓ */}
        {isBusy && queuePos > 0 && (
          <div className="queue-banner">
            <div className="q-spinner" />
            <div className="q-text">
              Đang trong hàng đợi ({queueWhat}): <strong>Vị trí thứ #{queuePos}</strong>. Hệ thống sẽ tự động bắt đầu khi tới lượt.
            </div>
          </div>
        )}

        {/* STATEFUL PIPELINE STEPPER: Bảng theo dõi các bước bóc tách */}
        <div className="pipeline-card">
          <div className="pipeline-header">
            <div className="ph-title">Tiến trình các bước bóc tách</div>
            <div className="ph-badge">
              {hasData
                ? 'Hoàn tất 100%'
                : isBusy
                ? `Đang chạy bước ${Math.min(activeStep + 1, steps.length)}/${steps.length}`
                : 'Chưa khởi chạy'}
            </div>
          </div>

          <div className="pipeline-steps">
            {steps.map((label, idx) => {
              let stepState = 'pending'
              if (hasData) {
                stepState = 'completed'
              } else if (isBusy) {
                if (idx < activeStep) stepState = 'completed'
                else if (idx === activeStep) stepState = 'active'
                else stepState = 'pending'
              }

              return (
                <div key={idx} className={`pipe-step ${stepState}`}>
                  <div className="step-indicator">
                    {stepState === 'completed' ? (
                      <span className="dot-done">{ICON_CHECK}</span>
                    ) : stepState === 'active' ? (
                      <span className="dot-active" />
                    ) : (
                      <span className="dot-pending">{idx + 1}</span>
                    )}
                    {idx < steps.length - 1 && <span className="step-line" />}
                  </div>
                  <div className="step-body">
                    <div className="step-label">{label}</div>
                    {stepState === 'active' && (
                      <div className="step-subtext">Đang thực thi xử lý chuyên sâu...</div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* THẺ KẾT QUẢ BÓC TÁCH & PHÂN TÍCH THÔNG MINH */}
        {hasData && (
          <div className="insights-container">
            {/* 1. Tổng quan ứng viên */}
            <div className="insight-card highlight">
              <div className="ic-header">
                <span className="ic-title">Ứng viên đã nhận diện</span>
                <span className="ic-badge ok">Khớp cấu trúc</span>
              </div>
              <div className="ic-candidate">
                <div className="c-name">{cvData.full_name || 'Chưa nhận diện tên'}</div>
                <div className="c-role">{cvData.target_title || position || 'Chưa có chức danh'}</div>
                <div className="c-specs">
                  {cvData.birth_year && <span>Năm sinh: <strong>{cvData.birth_year}</strong></span>}
                  {cvData.gender && <span>Giới tính: <strong>{cvData.gender}</strong></span>}
                  <span>Ảnh chân dung: <strong>{cvData.has_photo ? 'Đã lấy từ CV gốc' : 'Không có trong CV'}</strong></span>
                </div>
              </div>
            </div>

            {/* 2. Dữ liệu nhạy cảm PII đã được loại bỏ */}
            {removedFields.length > 0 && (
              <div className="insight-card">
                <div className="ic-header">
                  <span className="ic-title">Đã loại bỏ khỏi CV (Bảo mật PII)</span>
                  <span className="ic-pill">{removedFields.length} trường</span>
                </div>
                <ul className="ic-list">
                  {removedFields.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 3. Lương mong muốn */}
            <div className="insight-card">
              <div className="ic-header">
                <span className="ic-title">Lương mong muốn</span>
                <span className="ic-sub">Ghi chú nội bộ</span>
              </div>
              <div className="ic-salary">{cvData.expected_salary || 'CV gốc không ghi mức lương'}</div>
              <div className="ic-hint">Không đưa vào bản PDF xuất ra — chỉ lưu nội bộ để trao đổi với khách.</div>
            </div>

            {/* 4. Hệ thống tự lập hoặc điều chỉnh */}
            {selfCreated.length > 0 && (
              <div className="insight-card">
                <div className="ic-header">
                  <span className="ic-title">Hệ thống tự lập / Điều chỉnh</span>
                  <span className="ic-pill">{selfCreated.length}</span>
                </div>
                <ul className="ic-list">
                  {selfCreated.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 5. Cờ tuyển dụng & Cảnh báo */}
            {recruitingFlags.length > 0 && (
              <div className="insight-card warn">
                <div className="ic-header">
                  <span className="ic-title">Lưu ý tuyển dụng</span>
                  <span className="ic-pill warn">{recruitingFlags.length}</span>
                </div>
                <ul className="ic-list">
                  {recruitingFlags.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* 6. Mục cần xem lại */}
            {reviewNotes.length > 0 && (
              <div className="insight-card warn">
                <div className="ic-header">
                  <span className="ic-title">Cần xem lại khi duyệt</span>
                  <span className="ic-pill warn">{reviewNotes.length}</span>
                </div>
                <ul className="ic-list">
                  {reviewNotes.map(([p, msg], i) => (
                    <li key={i}>
                      <strong>{p}:</strong> {msg}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 7. Thông báo lỗi hồ sơ nếu có */}
            {totalErrors > 0 && (
              <div className="lh-alert err">
                <div className="t">Còn {totalErrors} lỗi cần xử lý</div>
                <div className="m">Vui lòng kiểm tra và sửa đổi ở tab &quot;Chỉnh sửa nội dung&quot; trước khi tải PDF.</div>
              </div>
            )}

            {/* 8. Hộp tin nhắn tóm tắt để sao chép */}
            {summary && (
              <div className="summary-wrapper">
                <div className="summary-bar">
                  <span className="summary-label">Tin nhắn tóm tắt hồ sơ</span>
                  <button
                    type="button"
                    className="btn-copy-summary"
                    onClick={handleCopySummary}
                    title="Sao chép toàn bộ tóm tắt"
                  >
                    {ICON_COPY}
                    {copied ? 'Đã sao chép!' : 'Sao chép'}
                  </button>
                </div>
                <pre className="summary-box">{summary}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
