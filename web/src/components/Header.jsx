// Header của trang web: hiển thị logo và tiêu đề chuẩn thương hiệu Light Human
export default function Header({ logoB64, companyName = 'Light Human' }) {
  return (
    <header className="lh-top grid grid-cols-[auto_1fr] items-center gap-4 pb-6 mb-6 border-b border-line sm:gap-3">
      {logoB64 ? (
        <img className="h-10 object-contain" src={`data:image/png;base64,${logoB64}`} alt={companyName} />
      ) : (
        <div className="font-bold text-xl text-navy">
          {companyName}
        </div>
      )}
      <div className="id flex items-center gap-4 min-w-0">
        <div className="sep w-px h-7 bg-line hidden sm:block" />
        <div className="name font-semibold text-ink text-lg tracking-[-0.01em]">
          Hồ sơ ứng viên
          <small className="block text-xs text-muted font-normal mt-0.5">
            Làm lại CV theo chuẩn Light Human để gửi khách hàng
          </small>
        </div>
      </div>
    </header>
  )
}
