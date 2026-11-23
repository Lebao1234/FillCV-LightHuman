// Kiểm thử thanh lưu và cảnh báo trong form chỉnh sửa hồ sơ ProfileForm
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ProfileForm from '../components/profile/ProfileForm'

// Hồ sơ tối thiểu đủ để form hiển thị
const CV = { full_name: 'Trần Văn B', target_title: 'Kế toán', facts: [], stats: [], sections: [] }

// Dựng form với các giá trị mặc định, cho phép ghi đè từng prop
function setup(props = {}) {
  const handlers = { onChangeCv: vi.fn(), onChangeProject: vi.fn(), onChangePosition: vi.fn(), onChangePhoto: vi.fn() }
  render(<ProfileForm cv={CV} project="" position="" runId="r1" photoUrl={null} {...handlers} {...props} />)
  return handlers
}

describe('ProfileForm — thanh lưu', () => {
  // Chưa sửa gì thì nút Lưu bị khoá
  it('khoá nút Lưu khi chưa có thay đổi', () => {
    setup({ onSave: vi.fn() })
    expect(screen.getByRole('button', { name: /Lưu & cập nhật PDF/i })).toBeDisabled()
    expect(screen.getByText(/Chưa có thay đổi/i)).toBeInTheDocument()
  })

  // Có thay đổi thì báo chưa lưu và bấm Lưu gọi onSave
  it('báo "Có thay đổi chưa lưu" và gọi onSave khi bấm Lưu', () => {
    const onSave = vi.fn()
    setup({ isDirty: true, onSave })
    expect(screen.getByText(/Có thay đổi chưa lưu/i)).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: /Lưu & cập nhật PDF/i })
    expect(btn).toBeEnabled()
    fireEvent.click(btn)
    expect(onSave).toHaveBeenCalledTimes(1)
  })

  // Hồ sơ sai cấu trúc: hiện lỗi ngay tại tab và khoá nút Lưu
  it('hiện lỗi cấu trúc và khoá nút Lưu', () => {
    setup({ isDirty: true, structureErrors: ['full_name: Họ tên ứng viên đang trống'], onSave: vi.fn() })
    expect(screen.getByText(/Họ tên ứng viên đang trống/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Lưu & cập nhật PDF/i })).toBeDisabled()
  })

  // Sau khi lưu: hiện giờ lưu và nút Xem bản PDF
  it('hiện "Đã lưu" và nút Xem bản PDF sau khi lưu xong', () => {
    const onViewPdf = vi.fn()
    setup({ savedAt: new Date(2026, 10, 23, 9, 5), onSave: vi.fn(), onViewPdf })
    expect(screen.getByText(/Đã lưu lúc/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Xem bản PDF/i }))
    expect(onViewPdf).toHaveBeenCalledTimes(1)
  })

  // Nút hoàn tác gọi onRevert
  it('gọi onRevert khi bấm "Về bản đọc ban đầu"', () => {
    const onRevert = vi.fn()
    setup({ onSave: vi.fn(), onRevert })
    fireEvent.click(screen.getByRole('button', { name: /Về bản đọc ban đầu/i }))
    expect(onRevert).toHaveBeenCalledTimes(1)
  })

  // Lỗi lưu từ máy chủ được hiển thị trong form
  it('hiển thị lỗi lưu từ máy chủ', () => {
    setup({ saveError: 'Dựng PDF thất bại.', onSave: vi.fn() })
    expect(screen.getByText(/Dựng PDF thất bại/i)).toBeInTheDocument()
  })
})

describe('ProfileForm — dịch sang tiếng Anh', () => {
  // Máy chủ chưa bật dịch máy thì không hiện nút dịch
  it('ẩn khung dịch khi chưa bật dịch máy', () => {
    setup({ onSave: vi.fn(), translationAvailable: false })
    expect(screen.queryByRole('button', { name: /Dịch sang tiếng Anh/i })).not.toBeInTheDocument()
  })

  // Đã bật: hiện nút và bấm gọi onTranslate
  it('hiện nút dịch và gọi onTranslate khi bấm', () => {
    const onTranslate = vi.fn()
    setup({ onSave: vi.fn(), translationAvailable: true, onTranslate })
    fireEvent.click(screen.getByRole('button', { name: /Dịch sang tiếng Anh/i }))
    expect(onTranslate).toHaveBeenCalledTimes(1)
  })

  // Đang dịch: nút bị khoá
  it('khoá nút khi đang dịch', () => {
    setup({ onSave: vi.fn(), translationAvailable: true, isTranslating: true, onTranslate: vi.fn() })
    expect(screen.getByRole('button', { name: /Đang dịch/i })).toBeDisabled()
    expect(screen.getByTestId('translate-progress')).toHaveTextContent(/đã chờ 0 giây/i)
  })

  // Báo cáo: số đoạn đã dịch và danh sách đoạn phải tự dịch (không chứa nội dung CV)
  it('hiện báo cáo dịch và các đoạn giữ nguyên tiếng Việt', () => {
    const report = {
      summary: { translated: 5, glossary: 2, kept: 1, skipped: 3 },
      items: [{ path: 'sections[0].jobs[0].groups[0].bullets[1]', status: 'kept', reason: 'số liệu không khớp bản gốc' }],
    }
    setup({ onSave: vi.fn(), translationAvailable: true, translateReport: report, onTranslate: vi.fn() })
    expect(screen.getByText(/Đã dịch 7 đoạn/i)).toBeInTheDocument()
    expect(screen.getByText(/1 đoạn giữ nguyên tiếng Việt/i)).toBeInTheDocument()
    expect(screen.getByText(/số liệu không khớp bản gốc/i)).toBeInTheDocument()
  })

  // Lỗi từ máy chủ hiển thị ngay trong khung dịch
  it('hiển thị lỗi dịch', () => {
    setup({ onSave: vi.fn(), translationAvailable: true, translateError: 'Dịch máy gặp lỗi.', onTranslate: vi.fn() })
    expect(screen.getByText(/Dịch máy gặp lỗi/i)).toBeInTheDocument()
  })
})
