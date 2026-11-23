// Kiểm thử định tuyến và tab "Chỉnh sửa nội dung" trên trang chính
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route, Outlet } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'

// Chỉ giả lập getConfig để App không gọi mạng thật khi khởi động
vi.mock('../api/client.js', async (importOriginal) => ({
  ...(await importOriginal()),
  getConfig: vi.fn().mockResolvedValue({}),
}))

import App from '../App'
import HomePage from '../pages/HomePage'

// Hồ sơ tối thiểu để form chỉnh sửa hiển thị
const CV = { full_name: 'Trần Văn B', target_title: 'Kế toán', facts: [], stats: [], sections: [] }

// Dựng trang chính với session giả (có hồ sơ, đang ở tab cho trước)
function renderHome(sessionOverrides = {}) {
  const session = {
    cvData: CV, handleCvChange: vi.fn(), project: '', setProject: vi.fn(), position: '', setPosition: vi.fn(),
    runId: 'r1', photoUrl: null, setPhotoUrl: vi.fn(), review: null, isDirty: false, isBuildingPdf: false,
    savedAt: null, error: null, structureErrors: [], violations: [], handleSaveEdits: vi.fn(),
    handleRevert: vi.fn(), setActiveTab: vi.fn(), activeTab: 'edit', handleTabKeyDown: vi.fn(),
    originalName: 'cv.pdf', stageLabels: [], isBusy: false, ...sessionOverrides,
  }
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route element={<Outlet context={session} />}>
          <Route index element={<HomePage />} />
        </Route>
      </Routes>
    </MemoryRouter>
  )
  return session
}

describe('Định tuyến và tab chỉnh sửa', () => {
  // Không còn trang /edit riêng: đường dẫn này về trang chính
  it('/edit -> trang chính', async () => {
    render(
      <MemoryRouter initialEntries={['/edit']}>
        <App />
      </MemoryRouter>
    )
    expect(await screen.findByText('Trạng thái bóc tách CV')).toBeInTheDocument()
  })

  // Đường dẫn lạ cũng về trang chính
  it('đường dẫn không tồn tại -> trang chính', async () => {
    render(
      <MemoryRouter initialEntries={['/khong-co']}>
        <App />
      </MemoryRouter>
    )
    expect(await screen.findByText('Trạng thái bóc tách CV')).toBeInTheDocument()
  })

  // Thanh tab có đủ 3 mục, tab chỉnh sửa nằm cùng hàng với Bản PDF và CV gốc
  it('thanh tab có Bản PDF, CV gốc, Chỉnh sửa nội dung', () => {
    renderHome()
    const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(tabs).toEqual(['Bản PDF', 'CV gốc', 'Chỉnh sửa nội dung'])
  })

  // Tab chỉnh sửa hiện form với dữ liệu hiện tại
  it('tab chỉnh sửa hiện form với nội dung hồ sơ', () => {
    renderHome()
    expect(screen.getByDisplayValue('Trần Văn B')).toBeInTheDocument()
  })

  // Bấm Lưu gọi handleSaveEdits
  it('bấm Lưu & cập nhật PDF gọi handleSaveEdits', () => {
    const session = renderHome({ isDirty: true })
    fireEvent.click(screen.getByRole('button', { name: /Lưu & cập nhật PDF/i }))
    expect(session.handleSaveEdits).toHaveBeenCalledTimes(1)
  })

  // Bấm tab chỉnh sửa đổi tab đang chọn
  it('bấm tab Chỉnh sửa nội dung gọi setActiveTab("edit")', () => {
    const session = renderHome({ activeTab: 'pdf', pdfData: null })
    fireEvent.click(screen.getByRole('tab', { name: 'Chỉnh sửa nội dung' }))
    expect(session.setActiveTab).toHaveBeenCalledWith('edit')
  })
})
