// Kiểm thử component thanh trạng thái StatusBar
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import StatusBar from '../components/StatusBar'

describe('StatusBar Component', () => {
  // Kiểm tra hiển thị tên file, dòng phụ và nhãn trạng thái khi sẵn sàng
  it('hiển thị thông tin file và nhãn trạng thái khi sẵn sàng', () => {
    render(
      <StatusBar
        filename="LH - Nguyen Van A.pdf"
        aside="A4 · 2 trang"
        pillKind="ok"
        pillText="Sẵn sàng"
      />
    )

    expect(screen.getByText('LH - Nguyen Van A.pdf')).toBeInTheDocument()
    expect(screen.getByText('A4 · 2 trang')).toBeInTheDocument()
    expect(screen.getByText('Sẵn sàng')).toBeInTheDocument()
    expect(screen.getByText('Sẵn sàng')).toHaveClass('ok')
  })

  // Kiểm tra hiển thị trạng thái mặc định khi chưa dựng PDF
  it('hiển thị trạng thái mặc định chưa dựng', () => {
    render(<StatusBar />)

    expect(screen.getByText('Chưa có bản PDF')).toBeInTheDocument()
    expect(screen.getByText('Bấm Cập nhật PDF để dựng')).toBeInTheDocument()
    expect(screen.getByText('Chưa dựng')).toBeInTheDocument()
    expect(screen.getByText('Chưa dựng')).toHaveClass('idle')
  })

  // Kiểm tra hiển thị nhãn cảnh báo
  it('hiển thị nhãn cảnh báo khi trạng thái là warn', () => {
    render(
      <StatusBar
        filename="LH - Tran Thi B.pdf"
        aside="A4 · 1 trang"
        pillKind="warn"
        pillText="Cần xem lại"
      />
    )

    expect(screen.getByText('Cần xem lại')).toBeInTheDocument()
    expect(screen.getByText('Cần xem lại')).toHaveClass('warn')
  })
})
