// Module giao tiếp API duy nhất của ứng dụng FillCV Light Human
/**
 * Quản lý toàn bộ các lệnh gọi API từ frontend tới backend theo đúng hợp đồng docs/api.md.
 * Không gọi fetch trực tiếp trong các component React.
 */

const BASE_URL = ''

/**
 * Xử lý response JSON từ fetch, ném lỗi kèm câu thông báo tiếng Việt nếu thất bại.
 * @param {Response} res
 * @returns {Promise<any>}
 */
async function handleJson(res) {
  if (!res.ok) {
    let errMsg = 'Đã có lỗi xảy ra khi kết nối máy chủ.'
    try {
      const data = await res.json()
      if (data && data.error) {
        errMsg = data.error
      }
    } catch {
      // Giữ thông báo mặc định nếu không parse được json
    }
    throw new Error(errMsg)
  }
  return res.json()
}

// Kiểm tra sức khoẻ server
export async function checkHealth() {
  const res = await fetch(`${BASE_URL}/health`)
  return handleJson(res)
}

// Lấy cấu hình khởi tạo của hệ thống
export async function getConfig() {
  const res = await fetch(`${BASE_URL}/api/config`)
  return handleJson(res)
}

/**
 * Gửi file CV lên server và lắng nghe tiến độ trích xuất qua Server-Sent Events (SSE).
 * @param {File} file - File CV gốc
 * @param {string} project - Tên dự án
 * @param {string} position - Vị trí tuyển dụng
 * @param {object} callbacks - Các hàm callback nhận sự kiện
 * @param {function(number, string): void} [callbacks.onWait] - Khi đang xếp hàng (vị trí, hành động)
 * @param {function(number, string, string[]): void} [callbacks.onProgress] - Khi bắt đầu một bước thật
 * @param {function(object): void} [callbacks.onDone] - Khi trích xuất hoàn thành
 * @param {function(string): void} [callbacks.onError] - Khi gặp lỗi
 * @param {boolean} [callbacks.keepContact] - Giữ thông tin liên hệ của ứng viên thay vì cắt bỏ
 * @returns {function(): void} Hàm hủy kết nối (abort)
 */
export function extractCv(file, project, position, { onWait, onProgress, onDone, onError, keepContact = false }) {
  const controller = new AbortController()
  const formData = new FormData()
  formData.append('file', file)
  if (project) formData.append('project', project)
  if (position) formData.append('position', position)
  if (keepContact) formData.append('keep_contact', 'true')

  ;(async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/cv/extract`, {
        method: 'POST',
        body: formData,
        headers: { Accept: 'text/event-stream' },
        signal: controller.signal,
      })

      if (!res.ok) {
        let msg = 'Chưa gửi được CV lên máy chủ.'
        try {
          const errData = await res.json()
          if (errData && errData.error) msg = errData.error
        } catch {
          // Bỏ qua lỗi parse
        }
        onError && onError(msg)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const blocks = buffer.split('\n\n')
        buffer = blocks.pop() // Giữ phần chưa hoàn chỉnh lại buffer

        for (const block of blocks) {
          if (!block.trim()) continue
          let eventType = 'message'
          let eventData = null

          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              try {
                eventData = JSON.parse(line.slice(6))
              } catch {
                eventData = line.slice(6)
              }
            }
          }

          if (eventType === 'wait' && onWait && eventData) {
            onWait(eventData.queue_pos, eventData.what || 'đọc CV')
          } else if (eventType === 'progress' && onProgress && eventData) {
            onProgress(eventData.step, eventData.label, eventData.labels || [])
          } else if (eventType === 'done' && onDone && eventData) {
            onDone(eventData)
          } else if (eventType === 'error' && onError && eventData) {
            onError(eventData.error || 'Có lỗi khi đọc CV.')
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        onError && onError(err.message || 'Mất kết nối với máy chủ khi đọc CV.')
      }
    }
  })()

  return () => controller.abort()
}

// Kiểm tra tính hợp lệ cấu trúc và rà soát PII
export async function validateCv(cv, project = '', position = '', runId = '', lang = 'vi', keepContact = false) {
  const payload = { cv, project, position, run_id: runId, lang }
  if (keepContact) {
    payload.keep_contact = true
  }
  const res = await fetch(`${BASE_URL}/api/cv/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handleJson(res)
}

// Dịch nội dung hồ sơ tiếng Việt sang tiếng Anh bằng dịch máy offline trên máy chủ
export async function translateCv(cv, runId = '') {
  const res = await fetch(`${BASE_URL}/api/cv/translate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cv, run_id: runId }),
  })
  return handleJson(res)
}

// Dựng PDF từ hồ sơ đang sửa
export async function buildPdf({ runId, cv, project = '', position = '', lang = 'vi', keepContact = false }) {
  const payload = { run_id: runId, cv, project, position, lang }
  if (keepContact) {
    payload.keep_contact = true
  }
  const res = await fetch(`${BASE_URL}/api/pdf/build`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handleJson(res)
}

// Tính toán trạng thái thanh status bar và quyền tải PDF
export async function getPdfStatus(params) {
  const res = await fetch(`${BASE_URL}/api/pdf/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  return handleJson(res)
}

// Lấy thông tin số trang và định dạng CV gốc
export async function getOriginalInfo(runId) {
  const res = await fetch(`${BASE_URL}/api/preview/original/${encodeURIComponent(runId)}/info`)
  return handleJson(res)
}

// Lấy thông tin số trang bản PDF đã dựng
export async function getPdfInfo(runId) {
  const res = await fetch(`${BASE_URL}/api/preview/pdf/${encodeURIComponent(runId)}/info`)
  return handleJson(res)
}

// URL ảnh trang CV gốc
export function getOriginalPageUrl(runId, page = 1) {
  return `${BASE_URL}/api/preview/original/${encodeURIComponent(runId)}/${page}`
}

// URL ảnh trang PDF đã dựng
export function getPdfPageUrl(runId, page = 1) {
  return `${BASE_URL}/api/preview/pdf/${encodeURIComponent(runId)}/${page}`
}

// URL tải file PDF về máy
export function getDownloadUrl(runId, saveCopy = true) {
  return `${BASE_URL}/api/pdf/download/${encodeURIComponent(runId)}?save_copy=${saveCopy}`
}

// Cắt ảnh chân dung tỉ lệ 29:38
export async function cropPhoto(file) {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${BASE_URL}/api/photo/crop`, {
    method: 'POST',
    body: formData,
  })
  return handleJson(res)
}

// URL xem trước ảnh chân dung của phiên
export function getPhotoPreviewUrl(runId) {
  return `${BASE_URL}/api/photo/preview/${encodeURIComponent(runId)}`
}

// Bỏ ảnh chân dung khỏi phiên
export async function deletePhoto(runId) {
  const res = await fetch(`${BASE_URL}/api/photo/${encodeURIComponent(runId)}`, {
    method: 'DELETE',
  })
  return handleJson(res)
}
