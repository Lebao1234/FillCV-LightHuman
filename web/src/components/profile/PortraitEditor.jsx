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
    <div className="mb-4 p-3 bg-soft rounded-md">
      <h4 className="mt-0 mx-0 mb-2">Ảnh chân dung</h4>
      {errorMsg && <div className="lh-alert err my-2 mx-0">{errorMsg}</div>}
      <div className="flex gap-4 items-center">
        <div className="w-[96px] h-[126px] border border-line rounded-sm bg-white flex items-center justify-center overflow-hidden">
          {photoUrl ? (
            <img src={photoUrl} alt="Chân dung" className="w-full h-[100%] object-cover" />
          ) : (
            <span className="text-xs text-faint">Không có ảnh</span>
          )}
        </div>
        <div className="flex flex-col gap-2">
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
            onChange={handleUpload} className="hidden"
            accept=".png,.jpg,.jpeg"
          />
          {photoUrl && (
            <button
              type="button"
              className="btn btn-tertiary self-start"
              onClick={handleDelete}
              disabled={loading}
            >
              Bỏ ảnh
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

