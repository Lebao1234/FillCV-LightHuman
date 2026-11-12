# Chính sách xử lý dữ liệu cá nhân của ứng viên — công cụ "Hồ sơ ứng viên"

> **BẢN NHÁP — CẦN PHÁP CHẾ XÁC NHẬN TRƯỚC KHI ÁP DỤNG.**
> Tài liệu do đội kỹ thuật soạn để mô tả **công cụ đang xử lý dữ liệu thế nào** và gợi ý các điểm cần có theo
> pháp luật Việt Nam. Đây không phải ý kiến pháp lý. Các điểm đánh dấu **[cần xác minh]** phải được pháp chế kiểm tra.

## 1. Căn cứ pháp lý cần đối chiếu [cần xác minh]

- **Luật Bảo vệ dữ liệu cá nhân** (Luật số 91/2025/QH15, hiệu lực từ 01/01/2026) và các văn bản hướng dẫn thi hành.
- **Nghị định 13/2023/NĐ-CP** về bảo vệ dữ liệu cá nhân — cần xác định phần nào còn hiệu lực sau khi Luật có hiệu lực.
- Pháp chế cần xác nhận: văn bản nào đang áp dụng và nghĩa vụ lập hồ sơ đánh giá tác động xử lý dữ liệu.
  Từ 11/2026 công cụ **không còn gửi CV ra dịch vụ bên ngoài** (xem mục 3), nên không phát sinh việc chuyển dữ liệu
  ra nước ngoài qua công cụ này.

## 2. Dữ liệu nào, đi đâu, giữ bao lâu (theo hành vi hiện tại của công cụ)

| Dữ liệu | Nơi xử lý / lưu | Thời gian giữ | Ghi chú |
|---|---|---|---|
| File CV gốc (có SĐT, email, địa chỉ, ngày sinh, ảnh…) | Bộ nhớ phiên làm việc của app | Đến khi đóng trình duyệt / bấm "Làm mới" / app khởi động lại | Không ghi ra ổ đĩa |
| File CV gốc (nội dung đầy đủ) | Bộ trích xuất chạy **ngay trên máy chủ của app** | Như dòng trên | Không gửi ra dịch vụ bên ngoài (xem mục 3) |
| Hồ sơ PDF + JSON đã xuất (họ tên, năm sinh, quá trình làm việc — **đã bỏ** SĐT/email/địa chỉ/ngày sinh đầy đủ) | `data/output` trên máy chạy app | **Tự xoá sau 30 ngày** (`OUTPUT_RETENTION_DAYS`) | Bản gửi khách hàng |
| Lương mong muốn, ghi chú tuyển dụng | Chỉ hiển thị trong app và tin nhắn tóm tắt nội bộ | Như CV gốc | Không đưa vào PDF |
| Log kỹ thuật | `data/logs` | Xoay vòng ~6 MB | **Không** chứa nội dung CV, họ tên hay tên file (tên file ghi dạng mã băm) |

Biện pháp kỹ thuật đã có: app chỉ mở trên máy chạy (localhost), giới hạn 20 MB/file, chặn xuất PDF khi còn thông tin
liên hệ của ứng viên (quét cả dữ liệu lẫn chính file PDF), Chromium chạy có sandbox, log không chứa dữ liệu cá nhân.

## 3. Không còn chuyển dữ liệu cho bên thứ ba

- Từ 11/2026 công cụ **đã gỡ OpenAI**: CV được đọc bằng bộ trích xuất chạy trên chính máy chủ của app, không gọi
  dịch vụ AI hay API bên ngoài (`services/extraction/`).
- CV đã gửi tới OpenAI **trước thời điểm này** vẫn chịu điều khoản lưu trữ của OpenAI lúc đó [cần xác minh: thời hạn
  lưu phía OpenAI, có cần yêu cầu xoá không].

## 4. Sự đồng ý của ứng viên [cần xác minh]

Trước khi Light Human xử lý CV bằng công cụ này, ứng viên cần được thông báo và đồng ý. Mẫu gợi ý (đưa vào email
nhận CV / form ứng tuyển):

> Bằng việc gửi CV, tôi đồng ý để Light Human xử lý thông tin cá nhân trong CV nhằm mục đích giới thiệu tôi tới
> khách hàng tuyển dụng, bao gồm: (1) đọc và chuẩn hoá CV bằng công cụ nội bộ của Light Human (không gửi CV cho
> bên thứ ba); (2) lập hồ sơ giới thiệu **không chứa** số điện thoại, email, địa chỉ, ngày sinh
> đầy đủ của tôi để gửi khách hàng; (3) lưu hồ sơ giới thiệu tối đa 30 ngày. Tôi có quyền yêu cầu xem, sửa, xoá dữ
> liệu hoặc rút lại sự đồng ý bằng cách liên hệ info@lighthuman.vn.

Yêu cầu khi lấy đồng ý: rõ ràng, cụ thể, tự nguyện, lưu lại được bằng chứng; ứng viên rút đồng ý thì phải ngừng xử lý.

## 5. Quyền của ứng viên và cách đáp ứng

| Yêu cầu | Cách làm với công cụ hiện tại |
|---|---|
| Xem / sửa dữ liệu | Hồ sơ PDF + file `.json` cùng tên trong `data/output` |
| Xoá dữ liệu | Xoá file PDF và `.json` của ứng viên trong `data/output` (hoặc chờ tự xoá 30 ngày); log không chứa dữ liệu cá nhân |
| Rút đồng ý | Ngừng làm hồ sơ; xoá PDF đã xuất; nếu đã gửi khách hàng thì thông báo theo quy trình của công ty |

## 6. Việc cần quyết định

1. Pháp chế xác nhận văn bản áp dụng và nghĩa vụ hồ sơ đánh giá tác động xử lý dữ liệu.
2. Duyệt mẫu đồng ý ở mục 4 và nơi lấy đồng ý.
3. Dữ liệu đã gửi OpenAI trước 11/2026: có cần yêu cầu OpenAI xoá không?
4. Thời hạn lưu PDF: giữ 30 ngày hay đổi số khác.
5. Ai được dùng công cụ (xem đề xuất đăng nhập trong `docs/proposals.md`).
