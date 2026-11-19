// Kiểm thử component huy hiệu nhắc nhở ReviewBadge
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ReviewBadge from '../components/profile/ReviewBadge'

describe('ReviewBadge Component', () => {
  // Kiểm tra không hiển thị gì khi không có review object
  it('không render khi review là null hoặc undefined', () => {
    const { container } = render(<ReviewBadge review={null} paths="full_name" />)
    expect(container).toBeEmptyDOMElement()
  })

  // Kiểm tra không hiển thị gì khi độ tin cậy >= 0.7 và không có ghi chú
  it('không render khi độ tin cậy >= 0.7 và không có ghi chú', () => {
    const review = {
      confidence: { full_name: 0.95 },
      notes: [],
    }
    const { container } = render(<ReviewBadge review={review} paths="full_name" />)
    expect(container).toBeEmptyDOMElement()
  })

  // Kiểm tra hiển thị cảnh báo khi độ tin cậy thấp (< 0.7)
  it('hiển thị nhãn Cần xem khi độ tin cậy < 0.7', () => {
    const review = {
      confidence: { full_name: 0.55 },
      notes: [],
    }
    render(<ReviewBadge review={review} paths="full_name" />)
    expect(screen.getByText(/Cần xem/i)).toBeInTheDocument()
    expect(screen.getByText(/55%/i)).toBeInTheDocument()
  })

  // Kiểm tra hiển thị ghi chú cảnh báo trích xuất
  it('hiển thị nội dung ghi chú từ danh sách notes', () => {
    const review = {
      confidence: {},
      notes: [
        ['sections[0].title', 'Tiêu đề trích xuất không chắc chắn'],
      ],
    }
    render(<ReviewBadge review={review} paths="sections[0].title" />)
    expect(screen.getByText(/Tiêu đề trích xuất không chắc chắn/i)).toBeInTheDocument()
  })
})
