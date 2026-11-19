const ICON_FILE = (
  <svg
    width="18"
    height="18"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
    strokeLinecap="round"
    strokeLinejoin="round"
  >
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 17h4" />
  </svg>
)

// Thanh trạng thái trên cùng của tab Bản PDF
export default function StatusBar({
  filename = 'Chưa có bản PDF',
  aside = 'Bấm Cập nhật PDF để dựng',
  pillKind = 'idle',
  pillText = 'Chưa dựng',
}) {
  return (
    <div className="lh-bar">
      {ICON_FILE}
      <div className="txt">
        <div className="fn">{filename}</div>
        <div className="fm">{aside}</div>
      </div>
      <span className={`lh-pill ${pillKind}`}>{pillText}</span>
    </div>
  )
}
