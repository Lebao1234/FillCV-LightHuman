import { useEffect, useState } from 'react'

// Thanh tiến độ khi đang dịch: máy chủ không báo phần trăm nên hiện thanh chạy liên tục + số giây đã chờ (mount lúc bắt đầu dịch)
function TranslateProgress() {
  const [seconds, setSeconds] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setSeconds((n) => n + 1), 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="mt-3" role="status" aria-live="polite" data-testid="translate-progress">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
        <div className="h-full w-1/3 animate-[lhSlide_1.2s_ease-in-out_infinite] rounded-full bg-navy motion-reduce:animate-none" />
      </div>
      <p className="m-0 mt-1.5 text-sm text-muted">
        Đang dịch... đã chờ {seconds} giây.
        {seconds >= 20 ? ' CV dài có thể mất khoảng 1 phút, vui lòng không đóng trang.' : ''}
      </p>
    </div>
  )
}

// Khung dịch nội dung hồ sơ sang tiếng Anh bằng dịch máy offline (chỉ hiện khi máy chủ đã bật dịch máy)
export default function TranslatePanel({ available = false, isTranslating = false, report = null, error = null, onTranslate }) {
  if (!available) return null

  const summary = report?.summary
  const keptItems = (report?.items || []).filter((i) => i.status === 'kept')

  return (
    <div className="mb-4 rounded-md border border-line bg-soft p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h4 className="m-0">Dịch nội dung sang tiếng Anh</h4>
          <p className="m-0 mt-1 text-sm text-muted">
            Dịch máy chạy ngay trên máy chủ, CV không gửi ra ngoài. Họ tên, tên công ty, tên trường và thời gian được giữ nguyên; thẻ kỹ năng chỉ đổi khi có trong bảng thuật ngữ.
            Đây chỉ là bản nháp: hãy đọc lại toàn bộ trước khi gửi khách.
          </p>
        </div>
        <button type="button" className="btn btn-secondary text-sm" onClick={onTranslate} disabled={isTranslating}>
          {isTranslating ? 'Đang dịch...' : 'Dịch sang tiếng Anh'}
        </button>
      </div>

      {isTranslating && <TranslateProgress />}

      {error && (
        <div className="lh-alert err mt-3" role="alert">
          <div className="t">Chưa dịch được</div>
          <ul>
            <li>{error}</li>
          </ul>
        </div>
      )}

      {summary && (
        <div className={`lh-alert mt-3 ${keptItems.length > 0 ? 'warn' : 'ok'}`} role="status">
          <div className="t">
            Đã dịch {summary.translated + summary.glossary} đoạn
            {summary.glossary > 0 ? ` (${summary.glossary} đoạn theo bảng thuật ngữ)` : ''}
            {summary.kept > 0 ? `, ${summary.kept} đoạn giữ nguyên tiếng Việt` : ''}
          </div>
          <ul>
            <li>Ngôn ngữ xuất PDF đã chuyển sang English. Sửa lại nội dung nếu cần rồi bấm Lưu & cập nhật PDF.</li>
            {summary.skipped > 0 && <li>{summary.skipped} đoạn không có dấu tiếng Việt nên được bỏ qua (đã là tiếng Anh hoặc gõ không dấu).</li>}
          </ul>
          {keptItems.length > 0 && (
            <details className="mt-1">
              <summary className="cursor-pointer text-sm font-medium">Các đoạn cần tự dịch ({keptItems.length})</summary>
              <ul>
                {keptItems.map((i) => (
                  <li key={i.path}>
                    <code>{i.path}</code>: {i.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  )
}
