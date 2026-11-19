import { useRef, useState } from 'react'
import { cropPhoto, deletePhoto } from '../../api/client.js'

// Thành phần xem, thay thế hoặc xoá ảnh chân dung ứng viên
export default function PortraitEditor({ runId, photoUrl, onPhotoChange }) {
  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)
  const fileInputRef = useRef(null)

  const handleUpload = async (e) => {
    if (!e.target.files || !e.target.files[0]) return
    const file = e.target.files[0]
    setLoading(true)
    setErrorMsg(null)

    try {
      const res = await cropPhoto(file)
      onPhotoChange(res.photo_b64)
    } catch (err) {
      setErrorMsg(err.message || 'Không đọc được file ảnh này, hãy thử ảnh khác.')
    } finally {
      setLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDelete = async () => {
    if (!runId && !photoUrl) return
    setLoading(true)
    setErrorMsg(null)

    try {
      if (runId) {
        await deletePhoto(runId)
      }
      onPhotoChange(null)
    } catch (err) {
      setErrorMsg(err.message || 'Không xoá được ảnh.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ marginBottom: 'var(--sp-4)', padding: 'var(--sp-3)', background: 'var(--soft)', borderRadius: 'var(--r-md)' }}>
      <h4 style={{ margin: '0 0 var(--sp-2)' }}>Ảnh chân dung</h4>
      {errorMsg && <div className="lh-alert err" style={{ margin: 'var(--sp-2) 0' }}>{errorMsg}</div>}
      <div style={{ display: 'flex', gap: 'var(--sp-4)', alignItems: 'center' }}>
        <div style={{ width: '96px', height: '126px', border: '1px solid var(--line)', borderRadius: 'var(--r-sm)', background: 'var(--white)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' }}>
          {photoUrl ? (
            <img src={photoUrl} alt="Chân dung" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          ) : (
            <span style={{ fontSize: 'var(--fs-xs)', color: 'var(--faint)' }}>Không có ảnh</span>
          )}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--sp-2)' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => fileInputRef.current && fileInputRef.current.click()}
            disabled={loading}
          >
            {loading ? 'Đang xử lý...' : 'Thay ảnh (không bắt buộc)'}
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleUpload}
            style={{ display: 'none' }}
            accept=".png,.jpg,.jpeg"
          />
          {photoUrl && (
            <button
              type="button"
              className="btn btn-tertiary"
              onClick={handleDelete}
              disabled={loading}
              style={{ alignSelf: 'flex-start' }}
            >
              Bỏ ảnh
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

