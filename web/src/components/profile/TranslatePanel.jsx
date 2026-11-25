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

const LANG_LABELS = { vi: 'Tiếng Việt', en: 'English' }

// Câu giải thích dưới thanh chuyển ngôn ngữ, tuỳ ngôn ngữ CV gốc và chiều dịch máy chủ hỗ trợ
function hintText({ sourceLang, available, targets }) {
  const other = sourceLang === 'en' ? 'vi' : 'en'
  const source = LANG_LABELS[sourceLang]
  if (!available) {
    return `CV gốc ${source}. Máy chủ chưa bật dịch: chọn ${LANG_LABELS[other]} chỉ đổi nhãn và tiêu đề mục, nội dung giữ nguyên.`
  }
  if (!targets.includes(other)) {
    return `CV gốc ${source}. Bộ dịch hiện tại chưa dịch được sang ${LANG_LABELS[other]}: chọn ${LANG_LABELS[other]} chỉ đổi nhãn và tiêu đề mục, nội dung giữ nguyên.`
  }
  return `CV gốc ${source}. Chọn ${LANG_LABELS[other]}: nội dung được dịch máy (họ tên, tên công ty, tên trường giữ nguyên); bản dịch là bản nháp, cần đọc lại. Chọn lại ${source} để khôi phục bản gốc.`
}

// Thanh chọn ngôn ngữ hồ sơ trong trang chỉnh sửa: đổi ngôn ngữ = dịch (nếu cần) + dựng lại PDF theo ngôn ngữ mới
export default function TranslatePanel({
  lang = 'vi',
  sourceLang = 'vi',
  available = false,
  targets = ['en'],
  online = false,
  isTranslating = false,
  isBusy = false,
  report = null,
  error = null,
  onChangeLang,
}) {
  const source = sourceLang === 'en' ? 'en' : 'vi'
  const sourceName = source === 'en' ? 'tiếng Anh' : 'tiếng Việt'
  const summary = report?.summary
  const keptItems = (report?.items || []).filter((i) => i.status === 'kept')
  const options = [
    { code: 'vi', label: 'Tiếng Việt' },
    { code: 'en', label: 'English' },
  ]

  return (
    <div className="mb-4 rounded-md border border-line bg-soft p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="m-0">Ngôn ngữ hồ sơ</h4>
        <div role="radiogroup" aria-label="Ngôn ngữ hồ sơ" className="inline-flex overflow-hidden rounded-md border border-line bg-white">
          {options.map((o) => (
            <button
              key={o.code}
              type="button"
              role="radio"
              aria-checked={lang === o.code}
              disabled={isTranslating || isBusy}
              onClick={() => lang !== o.code && onChangeLang && onChangeLang(o.code)}
              className={`px-4 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${
                lang === o.code ? 'bg-navy text-white' : 'text-ink hover:bg-soft'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>
      </div>
      <p className="m-0 mt-2 text-sm text-muted">{hintText({ sourceLang: source, available, targets })}</p>
      {available && online && (
        <p className="m-0 mt-1 text-sm text-warn" role="note">
          Lưu ý: bộ dịch đang dùng là dịch vụ online, nội dung các đoạn cần dịch được gửi ra ngoài máy chủ.
        </p>
      )}

      {isTranslating && <TranslateProgress />}

      {error && (
        <div className="lh-alert err mt-3" role="alert">
          <div className="t">Chưa dịch được</div>
          <ul>
            <li>{error}</li>
            <li>Bản PDF chỉ đổi nhãn và tiêu đề mục, nội dung giữ {sourceName}.</li>
          </ul>
        </div>
      )}

      {summary && lang !== source && !isTranslating && (
        <div className={`lh-alert mt-3 ${keptItems.length > 0 ? 'warn' : 'ok'}`} role="status">
          <div className="t">
            Đã dịch {summary.translated + summary.glossary} đoạn
            {summary.glossary > 0 ? ` (${summary.glossary} đoạn theo bảng thuật ngữ)` : ''}
            {summary.kept > 0 ? `, ${summary.kept} đoạn giữ nguyên ${sourceName}` : ''}
          </div>
          <ul>
            <li>Đọc lại và sửa bản dịch bên dưới rồi bấm Lưu & cập nhật PDF.</li>
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
