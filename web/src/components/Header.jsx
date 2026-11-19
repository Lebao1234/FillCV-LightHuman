// Header của trang web: hiển thị logo và tiêu đề chuẩn thương hiệu Light Human
export default function Header({ logoB64, companyName = 'Light Human' }) {
  return (
    <header className="lh-top">
      {logoB64 ? (
        <img src={`data:image/png;base64,${logoB64}`} alt={companyName} />
      ) : (
        <div style={{ fontWeight: 700, fontSize: 'var(--fs-xl)', color: 'var(--navy)' }}>
          {companyName}
        </div>
      )}
      <div className="id">
        <div className="sep" />
        <div className="name">
          Hồ sơ ứng viên
          <small>Làm lại CV theo chuẩn Light Human để gửi khách hàng</small>
        </div>
      </div>
    </header>
  )
}
