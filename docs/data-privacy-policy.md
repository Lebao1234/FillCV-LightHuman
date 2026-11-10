# Chính sách xử lý dữ liệu cá nhân của ứng viên — công cụ "Hồ sơ ứng viên"

> **BẢN NHÁP — CẦN PHÁP CHẾ XÁC NHẬN TRƯỚC KHI ÁP DỤNG.**
> Tài liệu do đội kỹ thuật soạn để mô tả **công cụ đang xử lý dữ liệu thế nào** và gợi ý các điểm cần có theo
> pháp luật Việt Nam. Đây không phải ý kiến pháp lý. Các điểm đánh dấu **[cần xác minh]** phải được pháp chế kiểm tra.

## 1. Căn cứ pháp lý cần đối chiếu [cần xác minh]

- **Luật Bảo vệ dữ liệu cá nhân** (Luật số 91/2025/QH15, hiệu lực từ 01/01/2026) và các văn bản hướng dẫn thi hành.
- **Nghị định 13/2023/NĐ-CP** về bảo vệ dữ liệu cá nhân — cần xác định phần nào còn hiệu lực sau khi Luật có hiệu lực.
- Pháp chế cần xác nhận: văn bản nào đang áp dụng, nghĩa vụ lập hồ sơ đánh giá tác động xử lý dữ liệu, và hồ sơ
  đánh giá tác động **chuyển dữ liệu ra nước ngoài** (vì CV được gửi tới OpenAI — xem mục 3).

## 2. Dữ liệu nào, đi đâu, giữ bao lâu (theo hành vi hiện tại của công cụ)

| Dữ liệu | Nơi xử lý / lưu | Thời gian giữ | Ghi chú |
|---|---|---|---|
| File CV gốc (có SĐT, email, địa chỉ, ngày sinh, ảnh…) | Bộ nhớ phiên làm việc của app | Đến khi đóng trình duyệt / bấm "Làm mới" / app khởi động lại | Không ghi ra ổ đĩa |
| File CV gốc (nội dung đầy đủ) | **OpenAI** (máy chủ ở nước ngoài) để AI đọc | Xem mục 3 | Bắt buộc để trích xuất tự động |
| Hồ sơ PDF đã xuất (họ tên, năm sinh, quá trình làm việc — **đã bỏ** SĐT/email/địa chỉ/ngày sinh đầy đủ) | `data/output` trên máy chạy app | **Tự xoá sau 30 ngày** (`OUTPUT_RETENTION_DAYS`) | Bản gửi khách hàng |
| Lương mong muốn, ghi chú tuyển dụng | Chỉ hiển thị trong app và tin nhắn tóm tắt nội bộ | Như CV gốc | Không đưa vào PDF |
| Log kỹ thuật | `data/logs` | Xoay vòng ~6 MB | **Không** chứa nội dung CV, họ tên hay tên file (tên file ghi dạng mã băm) |

Biện pháp kỹ thuật đã có: app chỉ mở trên máy chạy (localhost), giới hạn 20 MB/file, chặn xuất PDF khi còn thông tin
liên hệ của ứng viên (quét cả dữ liệu lẫn chính file PDF), Chromium chạy có sandbox, log không chứa dữ liệu cá nhân.

## 3. Chuyển dữ liệu cho OpenAI [cần xác minh]

- CV được gửi tới OpenAI qua API để trích xuất. Đây có thể được coi là **chuyển dữ liệu cá nhân ra nước ngoài**.
- Theo điều khoản OpenAI tại thời điểm soạn (cần xác minh lại với điều khoản hiện hành):
  - Dữ liệu gửi qua API **không dùng để huấn luyện mô hình** theo mặc định.
  - OpenAI có thể lưu dữ liệu API trong thời gian giới hạn (thường tới 30 ngày) để giám sát lạm dụng.
  - Với Responses API, khi `store=true` phản hồi được lưu để có thể tham chiếu lại; app hiện đặt theo `OPENAI_STORE`.
  - Có chương trình **Zero Data Retention** cho khách hàng đủ điều kiện (phải đăng ký với OpenAI).
- **Tuỳ chọn kỹ thuật đã sẵn sàng:** đặt `OPENAI_STORE=0` trong `.env` → OpenAI không lưu phản hồi
  (chi phí gọi lại khi AI trả JSON lỗi sẽ cao hơn một chút). **Đề xuất:** chuyển sang `0` khi chính sách được duyệt.
- Cần làm: ký/chấp nhận Data Processing Addendum của OpenAI; cân nhắc đăng ký Zero Data Retention.

## 4. Sự đồng ý của ứng viên [cần xác minh]

Trước khi Light Human xử lý CV bằng công cụ này, ứng viên cần được thông báo và đồng ý. Mẫu gợi ý (đưa vào email
nhận CV / form ứng tuyển):

> Bằng việc gửi CV, tôi đồng ý để Light Human xử lý thông tin cá nhân trong CV nhằm mục đích giới thiệu tôi tới
> khách hàng tuyển dụng, bao gồm: (1) dùng dịch vụ trí tuệ nhân tạo của bên thứ ba (OpenAI, máy chủ đặt ở nước
> ngoài) để đọc và chuẩn hoá CV; (2) lập hồ sơ giới thiệu **không chứa** số điện thoại, email, địa chỉ, ngày sinh
> đầy đủ của tôi để gửi khách hàng; (3) lưu hồ sơ giới thiệu tối đa 30 ngày. Tôi có quyền yêu cầu xem, sửa, xoá dữ
> liệu hoặc rút lại sự đồng ý bằng cách liên hệ info@lighthuman.vn.

Yêu cầu khi lấy đồng ý: rõ ràng, cụ thể, tự nguyện, lưu lại được bằng chứng; ứng viên rút đồng ý thì phải ngừng xử lý.

## 5. Quyền của ứng viên và cách đáp ứng

| Yêu cầu | Cách làm với công cụ hiện tại |
|---|---|
| Xem / sửa dữ liệu | Hồ sơ PDF trong `data/output`; sửa bằng cách làm lại hồ sơ |
| Xoá dữ liệu | Xoá file PDF của ứng viên trong `data/output` (hoặc chờ tự xoá 30 ngày); log không chứa dữ liệu cá nhân |
| Rút đồng ý | Ngừng làm hồ sơ; xoá PDF đã xuất; nếu đã gửi khách hàng thì thông báo theo quy trình của công ty |

## 6. Việc cần quyết định

1. Pháp chế xác nhận văn bản áp dụng và nghĩa vụ hồ sơ đánh giá tác động (xử lý + chuyển ra nước ngoài).
2. Duyệt mẫu đồng ý ở mục 4 và nơi lấy đồng ý.
3. Chuyển `OPENAI_STORE=0`? Đăng ký Zero Data Retention với OpenAI?
4. Thời hạn lưu PDF: giữ 30 ngày hay đổi số khác.
5. Ai được dùng công cụ (xem đề xuất đăng nhập trong `docs/proposals.md`).
