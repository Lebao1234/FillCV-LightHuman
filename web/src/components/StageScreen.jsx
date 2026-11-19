// Màn hình chờ hoặc trạng thái chưa có hồ sơ dạng khung trang A4
export default function StageScreen({
  busy = false,
  step = 0,
  queuePos = 0,
  queueWhat = 'đọc CV',
  labels = null,
}) {
  const defaultIdleSteps = [
    'Đính kèm CV gốc ở khung bên trái',
    'Nhập tên dự án và vị trí (nếu có)',
    'Duyệt bản PDF, sửa nếu cần, rồi tải về',
  ]

  const defaultBusySteps = [
    'Đọc CV gốc và trích xuất nội dung',
    'Bỏ thông tin liên hệ, chuẩn hoá theo mẫu',
    'Dựng PDF và kiểm tra chất lượng',
  ]

  const stepLabels = labels && labels.length > 0 ? labels : busy ? defaultBusySteps : defaultIdleSteps

  return (
    <div className={`lh-stage ${busy ? 'lh-busy' : ''}`}>
      <div className="lh-sheet">
        <div className="hd">
          <div className="r" style={{ width: '30%' }} />
          <div className="r" style={{ width: '22%' }} />
        </div>
        <div className="r ttl" />
        <div className="r acc" />
        <div className="r" style={{ width: '70%' }} />
        <div className="gap" />
        <div className="r" style={{ width: '40%' }} />
        <div className="r" style={{ width: '96%' }} />
        <div className="r" style={{ width: '90%' }} />
        <div className="r" style={{ width: '94%' }} />
        <div className="r" style={{ width: '62%' }} />
        <div className="gap" />
        <div className="r" style={{ width: '46%' }} />
        <div className="r" style={{ width: '92%' }} />
        <div className="r" style={{ width: '88%' }} />
        <div className="r" style={{ width: '70%' }} />
      </div>

      <div className="txt">
        {busy ? (
          queuePos > 0 ? (
            <>
              <h4>Đang xếp hàng {queueWhat}</h4>
              <p>
                Đang có nhiều hồ sơ được xử lý cùng lúc — hồ sơ này đứng thứ <b>{queuePos}</b> trong hàng.
                App sẽ tự {queueWhat} khi tới lượt, chị không cần bấm lại.
              </p>
            </>
          ) : (
            <>
              <h4>Đang làm hồ sơ</h4>
              <p>
                Từng bước bên dưới là việc đang chạy thật. Có thể tiếp tục xem lại tin nhắn bên trái trong lúc chờ.
              </p>
            </>
          )
        ) : (
          <>
            <h4>Chưa có hồ sơ</h4>
            <p>
              Bản PDF theo chuẩn Light Human sẽ hiển thị tại đây, kèm công cụ chỉnh sửa và đối chiếu với CV gốc.
            </p>
          </>
        )}

        <div className="lh-steps">
          {stepLabels.map((lbl, idx) => {
            let cls = ''
            if (busy) {
              if (idx < step) cls = 'done'
              else if (idx === step) cls = 'on'
            }
            return (
              <div key={idx} className={cls}>
                {lbl}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
