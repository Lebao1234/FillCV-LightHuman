// Kiểm thử component bảng trạng thái bóc tách CV ExtractionPanel
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ExtractionPanel from '../components/ExtractionPanel'

describe('ExtractionPanel Component', () => {
  // Kiểm tra hiển thị form nạp CV ban đầu khi chưa có dữ liệu
  it('hiển thị form kéo thả file và các ô nhập dự án khi chưa có hồ sơ', () => {
    render(<ExtractionPanel />)

    expect(screen.getByText('Trạng thái bóc tách CV')).toBeInTheDocument()
    expect(
      screen.getByText(/Kéo thả file CV vào đây hoặc bấm để chọn/i)
    ).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Message Coffee/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Bắt đầu bóc tách CV/i })
    ).toBeInTheDocument()
  })

  // Kiểm tra hiển thị banner hàng đợi khi đang xếp hàng
  it('hiển thị thông tin hàng đợi khi queuePos > 0', () => {
    render(
      <ExtractionPanel
        isExtracting={true}
        queuePos={2}
        queueWhat="đọc CV"
      />
    )

    expect(screen.getByText(/Vị trí thứ #2/i)).toBeInTheDocument()
    expect(screen.getByText(/Đang trong hàng đợi/i)).toBeInTheDocument()
  })

  // Kiểm tra hiển thị thông tin ứng viên và các thẻ kết quả khi bóc tách xong
  it('hiển thị đầy đủ thông tin ứng viên, dữ liệu đã bỏ và mức lương sau khi bóc tách', () => {
    const mockCv = {
      full_name: 'Đoàn Thị Mây',
      target_title: 'Kế Toán Trưởng',
      birth_year: 1988,
      gender: 'Nữ',
      has_photo: true,
      expected_salary: '32.000.000 - 37.000.000 VND',
      model_notes: {
        removed: ['Địa chỉ nhà', 'Ngày sinh đầy đủ', 'Tình trạng hôn nhân'],
      },
    }

    render(
      <ExtractionPanel
        cvData={mockCv}
        originalName="Doan Thi May.pdf"
        project="Message Coffee"
        position="Kế Toán Trưởng"
      />
    )

    expect(screen.getByText('Đoàn Thị Mây')).toBeInTheDocument()
    expect(screen.getAllByText('Kế Toán Trưởng').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('32.000.000 - 37.000.000 VND')).toBeInTheDocument()
    expect(screen.getByText('Địa chỉ nhà')).toBeInTheDocument()
    expect(screen.getByText('Ngày sinh đầy đủ')).toBeInTheDocument()
    expect(screen.getByText('Tình trạng hôn nhân')).toBeInTheDocument()
  })

  // Kiểm tra kích hoạt sự kiện làm mới
  it('gọi hàm onReset khi người dùng bấm nút làm mới', () => {
    const handleReset = vi.fn()
    const mockCv = { full_name: 'Nguyễn Văn A' }

    render(
      <ExtractionPanel
        cvData={mockCv}
        onReset={handleReset}
      />
    )

    const resetBtn = screen.getByRole('button', { name: /Làm mới \/ Nạp CV khác/i })
    fireEvent.click(resetBtn)
    expect(handleReset).toHaveBeenCalledTimes(1)
  })
})
