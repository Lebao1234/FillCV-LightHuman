# Đề xuất dài hạn (chưa triển khai — chờ quyết định)

## 1. Đăng nhập / phân quyền

Hiện tại app không có đăng nhập; an toàn vì chỉ mở trên `localhost`. Cần đăng nhập khi muốn nhiều người dùng chung
qua mạng.

| Phương án | Cách làm | Ưu | Nhược | Công sức |
|---|---|---|---|---|
| **A. Reverse proxy có xác thực** (khuyên dùng trước) | Caddy/Nginx basic auth, hoặc Cloudflare Access / oauth2-proxy đặt trước app; app vẫn ở localhost | Không sửa code; tách bạch bảo mật khỏi app | Cần máy chủ/hạ tầng; phân quyền thô (vào được hay không) | S — vài giờ hạ tầng |
| **B. Đăng nhập trong app** (`st.login`, OIDC Google Workspace / Microsoft 365) | Cấu hình `.streamlit/secrets.toml`, chỉ cho email trong danh sách | Đăng nhập bằng tài khoản công ty; biết ai làm hồ sơ nào (ghi vào log) | Cần tài khoản OIDC; sửa app + test | M — 0,5–1 ngày |
| C. Mật khẩu chung | 1 mật khẩu trong secrets, so sánh an toàn | Nhanh nhất | Không biết ai dùng; lộ mật khẩu là lộ hết | S — 1–2 giờ |

Phân quyền chi tiết (vd người làm hồ sơ / quản trị xem log) chưa cần ở quy mô hiện tại; nếu chọn B có thể thêm sau
bằng danh sách email theo vai trò.

## 2. CI chạy test mỗi lần commit

| Phương án | Cách làm | Công sức |
|---|---|---|
| **GitHub Actions** (khuyên dùng khi repo lên GitHub) | `windows-latest`, cài `requirements-dev.txt` + `playwright install chromium`; push: `pytest -m "not slow"` (~20 s), pull request: toàn bộ + báo cáo độ phủ | S — ~2 giờ |
| Hook trước commit trên máy | `pre-commit` chạy `pytest -m "not slow"` trước mỗi commit | S — <1 giờ |

Lưu ý: CI không cần `OPENAI_API_KEY` — test dùng client OpenAI giả.

## 3. Việc khác đã ghi nhận

| Việc | Trạng thái | Ghi chú |
|---|---|---|
| R2 — một phiên Chromium cho các lần thử cỡ chữ | Đề xuất **không làm** | Đo: CV thường không nhanh hơn (~2,6 s); chỉ CV dài phải thử 3 cỡ chữ mới lợi (~7,8 s → ~2,5 s) |
| Nút "Huỷ" khi đang chờ OpenAI | Không khả thi với kiến trúc hiện tại | Streamlit không ngắt được lời gọi mạng đang chạy; hạn tổng 180 s là giới hạn chờ |
| Báo lỗi thân thiện khi `config/company.toml` sai cú pháp | Chờ quyết định | Hiện ghi hướng dẫn trong README |
| Luật nhận diện thông tin nhạy cảm ra file dữ liệu (`data/pii_rules`) | Chưa làm | Cho phép bộ phận tuyển dụng tự thêm từ khoá mà không sửa code |
| Đổi tên hàm/biến tiếng Việt sang tiếng Anh | Chưa làm | Tên file đã chuẩn hoá tiếng Anh; tên trong code giữ nguyên để tránh rủi ro |
