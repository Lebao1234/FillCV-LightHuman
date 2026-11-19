// Kiểm thử module API client kết nối backend
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getConfig,
  validateCv,
  buildPdf,
  getPdfStatus,
  deletePhoto,
  getDownloadUrl,
  getPdfPageUrl,
  getOriginalPageUrl,
} from '../api/client'

describe('API Client Module', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // Kiểm tra lấy cấu hình hệ thống
  it('getConfig gọi đúng endpoint /api/config', async () => {
    const mockConfig = { max_upload_mb: 20, allowed_extensions: ['.pdf'] }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockConfig,
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await getConfig()
    expect(fetchMock).toHaveBeenCalledWith('/api/config')
    expect(result).toEqual(mockConfig)
  })

  // Kiểm tra kiểm tra hợp lệ hồ sơ
  it('validateCv gửi POST /api/cv/validate với payload JSON', async () => {
    const mockRes = { valid: true, structure_errors: [], violations: [], normalized_cv: {} }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRes,
    })
    vi.stubGlobal('fetch', fetchMock)

    const cv = { full_name: 'Test' }
    const result = await validateCv(cv, 'P1', 'V1', 'r1', 'vi')

    expect(fetchMock).toHaveBeenCalledWith('/api/cv/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cv, project: 'P1', position: 'V1', run_id: 'r1', lang: 'vi' }),
    })
    expect(result).toEqual(mockRes)
  })

  // Kiểm tra dựng PDF
  it('buildPdf gửi POST /api/pdf/build', async () => {
    const mockRes = { run_id: 'r1', filename: 'LH - Test.pdf' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockRes,
    })
    vi.stubGlobal('fetch', fetchMock)

    const params = { runId: 'r1', cv: { full_name: 'Test' }, project: 'P1', position: 'V1', lang: 'vi' }
    const result = await buildPdf(params)

    expect(fetchMock).toHaveBeenCalledWith('/api/pdf/build', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: 'r1', cv: { full_name: 'Test' }, project: 'P1', position: 'V1', lang: 'vi' }),
    })
    expect(result).toEqual(mockRes)
  })

  // Kiểm tra tính toán trạng thái PDF
  it('getPdfStatus gửi POST /api/pdf/status', async () => {
    const mockStatus = { can_download: true, pill_text: 'Sẵn sàng' }
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockStatus,
    })
    vi.stubGlobal('fetch', fetchMock)

    const params = { has_pdf: true, reviewed: true }
    const result = await getPdfStatus(params)

    expect(fetchMock).toHaveBeenCalledWith('/api/pdf/status', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    expect(result).toEqual(mockStatus)
  })

  // Kiểm tra xoá ảnh chân dung
  it('deletePhoto gửi DELETE /api/photo/{runId}', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await deletePhoto('run_123')
    expect(fetchMock).toHaveBeenCalledWith('/api/photo/run_123', {
      method: 'DELETE',
    })
    expect(result).toEqual({ ok: true })
  })

  // Kiểm tra các helper sinh URL
  it('sinh URL tải và xem trước chính xác', () => {
    expect(getDownloadUrl('r1', true)).toBe('/api/pdf/download/r1?save_copy=true')
    expect(getDownloadUrl('r1', false)).toBe('/api/pdf/download/r1?save_copy=false')
    expect(getPdfPageUrl('r1', 2)).toBe('/api/preview/pdf/r1/2')
    expect(getOriginalPageUrl('r1', 1)).toBe('/api/preview/original/r1/1')
  })

  // Kiểm tra xử lý lỗi khi backend trả về mã lỗi HTTP
  it('ném lỗi tiếng Việt khi API trả về status khác 200', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Dữ liệu không hợp lệ.' }),
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(validateCv({})).rejects.toThrow('Dữ liệu không hợp lệ.')
  })
})
