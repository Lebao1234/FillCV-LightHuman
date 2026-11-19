import { useRef, useState } from 'react'

const ICON_FILE = (
  <svg
    width="18"
    height="18"
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

// Khung chat trao đổi và form gửi file CV
export default function ChatPanel({
  chatMessages = [],
  isExtracting = false,
  onReset,
  onSubmitCv,
  structureErrors = [],
  violations = [],
  summary = '',
}) {
  const [file, setFile] = useState(null)
  const [project, setProject] = useState('')
  const [position, setPosition] = useState('')
  const fileInputRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!file) return
    onSubmitCv({ file, project, position })
    setFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const totalErrors = structureErrors.length + violations.length

  return (
    <div>
      <div className="lh-ph">
        <div className="h">Trợ lý hồ sơ</div>
        <button
          type="button"
          className="btn btn-tertiary"
          onClick={onReset}
          disabled={chatMessages.length === 0}
        >
          Làm mới
        </button>
      </div>

      <div className="chat-container">
        {/* Lời chào mặc định */}
        <div className="lh-msg bot">
          <div className="who">Trợ lý Light Human</div>
          <div className="bub">
            Chào chị. Gửi giúp em <b>CV gốc</b> (PDF, ảnh hoặc DOCX) kèm <b>tên dự án</b> và{' '}
            <b>vị trí</b> nếu có. Em sẽ làm lại hồ sơ theo chuẩn Light Human và hiển thị bản PDF ở khung
            bên phải.
          </div>
        </div>

        {/* Danh sách tin nhắn */}
        {chatMessages.map((m, idx) => {
          if (m.role === 'user' && m.kind === 'file') {
            return (
              <div key={idx} className="lh-msg me">
                <div className="who">Bạn</div>
                <div className="bub">
                  <div className="lh-file">
                    {ICON_FILE}
                    <div>
                      <div className="fn">{m.filename}</div>
                      <div className="fm">
                        Dự án: {m.project || '—'} · Vị trí: {m.position || 'theo CV'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          }

          if (m.kind === 'notes') {
            const n = m.notes || {}
            return (
              <div key={idx} className="lh-msg bot">
                <div className="who">Trợ lý Light Human</div>
                <div className="bub">
                  <b>Đã đọc xong CV của {m.name}.</b> Bản PDF hiển thị ở khung bên phải.
                  {n.removed && n.removed.length > 0 && (
                    <div className="lh-sec">
                      <div className="lb">
                        <span>Đã bỏ khỏi CV</span>
                        <i>{n.removed.length}</i>
                      </div>
                      <ul>
                        {n.removed.map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <div className="lh-sec">
                    <div className="lb">
                      <span>Lương mong muốn</span>
                    </div>
                    <span className="lh-sal">{m.salary || 'CV không ghi'}</span>
                    <div className="none">Không đưa vào PDF — dùng khi trao đổi với khách.</div>
                  </div>
                  {n.self_created && (n.self_created.length > 0 || (n.other && n.other.length > 0)) && (
                    <div className="lh-sec">
                      <div className="lb">
                        <span>Hệ thống tự lập / điều chỉnh</span>
                        <i>{(n.self_created || []).length + (n.other || []).length}</i>
                      </div>
                      <ul>
                        {[...(n.self_created || []), ...(n.other || [])].map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {n.recruiting_flags && n.recruiting_flags.length > 0 && (
                    <div className="lh-sec">
                      <div className="lb">
                        <span>Lưu ý tuyển dụng</span>
                        <i>{n.recruiting_flags.length}</i>
                      </div>
                      <ul>
                        {n.recruiting_flags.map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {m.review && m.review.length > 0 && (
                    <div className="lh-sec">
                      <div className="lb">
                        <span>Cần xem lại khi duyệt</span>
                        <i>{m.review.length}</i>
                      </div>
                      <ul>
                        {m.review.map((x, i) => (
                          <li key={i}>{x}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {'hasPhoto' in m && (
                    <div className="lh-sec">
                      <div className="lb">
                        <span>Ảnh chân dung</span>
                      </div>
                      <div className="none">
                        {m.hasPhoto
                          ? 'Đã lấy từ CV gốc và đưa vào PDF.'
                          : 'Không tìm thấy ảnh trong CV gốc. Có thể thêm ở tab Chỉnh sửa nội dung.'}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )
          }

          if (m.kind === 'error') {
            return (
              <div key={idx} className="lh-msg bot err">
                <div className="who">Trợ lý Light Human</div>
                <div className="bub">
                  <b>{m.title || 'Lỗi.'}</b> {m.text}
                </div>
              </div>
            )
          }

          return (
            <div key={idx} className={`lh-msg ${m.role === 'user' ? 'me' : 'bot'}`}>
              <div className="who">{m.role === 'user' ? 'Bạn' : 'Trợ lý Light Human'}</div>
              <div className="bub">{m.text}</div>
            </div>
          )
        })}

        {/* Trạng thái đang gõ */}
        {isExtracting && (
          <div className="lh-msg bot">
            <div className="who">Trợ lý Light Human</div>
            <div className="bub">
              <span className="lh-typing">
                <i />
                <i />
                <i />
              </span>
            </div>
          </div>
        )}

        {/* Thông báo số lỗi nếu có */}
        {totalErrors > 0 && (
          <div className="lh-msg bot err tight">
            <div className="who">Trợ lý Light Human</div>
            <div className="bub">
              Hồ sơ còn <b>{totalErrors} lỗi</b> cần sửa trước khi tải PDF. Chi tiết ở khung bên phải.
            </div>
          </div>
        )}

        {/* Khối tin nhắn tóm tắt */}
        {summary && (
          <div style={{ marginTop: 'auto' }}>
            <div className="lh-msg bot tight">
              <div className="who">Tin nhắn tóm tắt</div>
            </div>
            <div className="summary-box">{summary}</div>
          </div>
        )}
      </div>

      {/* Form nạp CV */}
      <form className="cv-form" onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">File CV gốc</label>
          <div
            className="dropzone"
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
          >
            {file ? (
              <span style={{ fontWeight: 500, color: 'var(--navy)' }}>{file.name}</span>
            ) : (
              <span style={{ color: 'var(--muted)' }}>
                Kéo thả file CV vào đây hoặc bấm để chọn (PDF, DOCX, ảnh)
              </span>
            )}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }}
              accept=".pdf,.docx,.png,.jpg,.jpeg"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Tên dự án</label>
            <input
              type="text"
              className="form-input"
              placeholder="Message Coffee"
              value={project}
              onChange={(e) => setProject(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Vị trí</label>
            <input
              type="text"
              className="form-input"
              placeholder="Kế toán trưởng (không bắt buộc)"
              value={position}
              onChange={(e) => setPosition(e.target.value)}
            />
          </div>
        </div>

        <button
          type="submit"
          className="btn btn-primary btn-block"
          disabled={!file || isExtracting}
        >
          {isExtracting ? 'Đang đọc CV...' : 'Gửi CV'}
        </button>
      </form>
    </div>
  )
}
