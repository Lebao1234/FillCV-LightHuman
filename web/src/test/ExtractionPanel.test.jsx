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
    expect(screen.getByText(/Ngôn ngữ xuất hồ sơ/i)).toBeInTheDocument()
    expect(screen.getByText(/Thông tin liên hệ \(SĐT, Email\.\.\.\)/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Cắt bỏ toàn bộ liên hệ/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Giữ nguyên liên hệ/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Bắt đầu bóc tách CV/i })).toBeInTheDocument()
  })

  // Kiểm tra hiển thị thời gian bóc tách và ngôn ngữ trong thẻ nguồn file
  it('hiển thị thời gian bóc tách thành công và ngôn ngữ hồ sơ đã chọn', () => {
    const mockCv = { full_name: 'Trần Văn B' }
    render(
      <ExtractionPanel
        cvData={mockCv}
        originalName="sample.pdf"
        project="Test Prj"
        position="Developer"
        pdfLang="en"
        elapsedSeconds={1.25}
      />
    )

    expect(screen.getByText(/Hoàn tất trong 1.25s/i)).toBeInTheDocument()
    expect(screen.getByText(/English/i)).toBeInTheDocument()
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
        photoUrl="/api/photo/preview/r1"
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

  // Kiểm tra gửi tuỳ chọn keepContact khi bấm bóc tách CV
  it('truyền lựa chọn keepContact khi submit form bóc tách', () => {
    const handleSubmit = vi.fn()
    const { container } = render(<ExtractionPanel onSubmitCv={handleSubmit} />)

    // Chọn file
    const file = new File(['dummy content'], 'test.pdf', { type: 'application/pdf' })
    const fileInput = container.querySelector('input[type="file"]')
    fireEvent.change(fileInput, { target: { files: [file] } })

    // Chọn giữ nguyên liên hệ
    const keepRadio = screen.getByLabelText(/Giữ nguyên liên hệ/i)
    fireEvent.click(keepRadio)

    // Bấm bóc tách
    const submitBtn = screen.getByRole('button', { name: /Bắt đầu bóc tách CV/i })
    fireEvent.click(submitBtn)

    expect(handleSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        keepContact: true,
      })
    )
  })

  // Ảnh chân dung báo theo ảnh thật của phiên (photoUrl), không theo trường trong hồ sơ
  it('báo có/không ảnh chân dung theo photoUrl', () => {
    const cv = { full_name: 'A', target_title: 'B' }
    const { rerender } = render(<ExtractionPanel cvData={cv} originalName="a.pdf" />)
    expect(screen.getByText('Không có trong CV')).toBeInTheDocument()
    rerender(<ExtractionPanel cvData={cv} originalName="a.pdf" photoUrl="/api/photo/preview/r1" />)
    expect(screen.getByText('Đã lấy từ CV gốc')).toBeInTheDocument()
  })
})
