# Hệ thống giao diện – Hồ sơ ứng viên Light Human

Tài liệu cho người sửa giao diện web app (`app.py`) và mẫu hồ sơ PDF (`template.html`).

## Nguyên tắc

1. **Một nguồn token duy nhất: [`infra/tokens.py`](../infra/tokens.py).** Web app, mẫu PDF, footer PDF và theme Streamlit cùng lấy giá trị từ đây. Không viết mã màu, cỡ chữ, khoảng cách hay bo góc trực tiếp vào CSS. Test `tests/test_design_tokens.py` sẽ báo lỗi nếu có.
2. **Mẫu PDF theo đúng SKILL.md.** Token PDF (`css_vars("pdf")`) giữ nguyên giá trị mục 5 SKILL.md. Sửa token mà làm đổi PDF tức là đổi chuẩn hồ sơ, cần chị Trâm duyệt.
3. **Navy là màu nhấn duy nhất, gold chỉ để trang trí.** Gold sáng (`--gold`) dùng cho vạch, chấm đầu dòng. Khi cần chữ màu vàng, dùng `--gold-text`.
4. **Chữ trên nền phải đạt WCAG AA (≥ 4.5:1).** Mọi cặp chữ/nền đang dùng được liệt kê trong `tokens.TEXT_BG_PAIRS` và được test kiểm tra.
5. **Không emoji.** Icon dùng SVG nét 1.5px hoặc Material Symbols của Streamlit (`icon=":material/...:"`).

## Cách đổi một token

1. Sửa giá trị trong `infra/tokens.py`.
2. Nếu là `navy`, `white`, `soft`, `ink`, `line` hoặc `r-md`: sửa luôn `.streamlit/config.toml`, vì file này không đọc được Python.
3. Chạy `python -m infra.tokens` (ở thư mục gốc dự án), rồi dán kết quả vào phần **Bảng token** bên dưới.
4. Chạy `python -m pytest`. Test kiểm tra tương phản, theme, CSS không có giá trị cứng, và tài liệu đã cập nhật.

## Bảng token

Phần này được sinh từ `python -m infra.tokens`, không sửa tay.

<!-- TOKENS:BEGIN -->
| Token | Giá trị |
|---|---|
| `--navy` | `#14285a` |
| `--navy-50` | `#eef1f7` |
| `--navy-100` | `#dfe4ef` |
| `--gold` | `#dca54b` |
| `--gold-text` | `#8a5e17` |
| `--gold-100` | `#f3e6cc` |
| `--yellow` | `#f2cf63` |
| `--ink` | `#1f2430` |
| `--muted` | `#5a6275` |
| `--faint` | `#687083` |
| `--white` | `#ffffff` |
| `--soft` | `#f5f6f8` |
| `--skeleton` | `#edf0f4` |
| `--skeleton-hi` | `#f8f9fb` |
| `--line` | `#d9dce3` |
| `--line-strong` | `#cdd2dc` |
| `--ok` | `#2f7a57` |
| `--ok-bg` | `#edf6f1` |
| `--ok-line` | `#cfe6da` |
| `--warn` | `#8f5a12` |
| `--warn-bg` | `#fbf4e8` |
| `--warn-line` | `#f1e1c6` |
| `--err` | `#b42318` |
| `--err-bg` | `#fdf1f0` |
| `--err-line` | `#f3d2cf` |
| `--info` | `#14285a` |
| `--info-bg` | `#eef1f7` |
| `--info-line` | `#dfe4ef` |
| `--pdf-stats-bg` | `#eef1f6` |
| `--pdf-ref-bg` | `#f6f7fa` |

| Cỡ chữ | Giá trị |
|---|---|
| `--fs-xs` | `11px` |
| `--fs-sm` | `12px` |
| `--fs-md` | `13px` |
| `--fs-base` | `14px` |
| `--fs-lg` | `16px` |
| `--fs-xl` | `18px` |

| Khoảng cách | Giá trị |
|---|---|
| `--sp-1` | `4px` |
| `--sp-2` | `8px` |
| `--sp-3` | `12px` |
| `--sp-4` | `16px` |
| `--sp-5` | `24px` |
| `--sp-6` | `32px` |
| `--sp-7` | `40px` |

| Bo góc | Giá trị |
|---|---|
| `--r-sm` | `4px` |
| `--r-md` | `8px` |
| `--r-lg` | `12px` |
| `--r-pill` | `999px` |

| Cặp chữ / nền | Tương phản |
|---|---|
| `ink` / `white` | 15.52:1 |
| `muted` / `white` | 6.11:1 |
| `faint` / `white` | 4.96:1 |
| `faint` / `soft` | 4.59:1 |
| `muted` / `soft` | 5.65:1 |
| `gold-text` / `white` | 5.68:1 |
| `gold-text` / `soft` | 5.26:1 |
| `white` / `navy` | 14.18:1 |
| `navy` / `navy-50` | 12.53:1 |
| `ok` / `ok-bg` | 4.71:1 |
| `warn` / `warn-bg` | 5.28:1 |
| `err` / `err-bg` | 5.95:1 |
| `info` / `info-bg` | 12.53:1 |
| `ink` / `navy-50` | 13.72:1 |
<!-- TOKENS:END -->

### Cách dùng thang giá trị

| Thang | Dùng cho |
|---|---|
| `--fs-xs` 11 | Nhãn chữ hoa (người gửi, tên mục), nhãn trạng thái |
| `--fs-sm` 12 | Chú thích, tên file, mô tả phụ |
| `--fs-md` 13 | Chữ trong hộp cảnh báo, checklist, tab, tiêu đề panel |
| `--fs-base` 14 | Chữ chính: tin nhắn chat, đoạn mô tả, tiêu đề nhỏ (h4) |
| `--fs-lg` 16 | Tên công cụ trên header |
| `--fs-xl` 18 | Tiêu đề trạng thái trống / đang xử lý |
| `--sp-1…7` | 4 · 8 · 12 · 16 · 24 · 32 · 40px. Khoảng cách trong thành phần dùng 1–4, giữa các khối dùng 5–7 |
| `--r-sm` / `--r-md` / `--r-lg` / `--r-pill` | 4px: vạch, code, góc nhọn của bong bóng · 8px: nút, ô nhập, thanh trạng thái, cảnh báo · 12px: form, khung lớn, bong bóng · 999px: nhãn trạng thái |
| `--dur-fast` / `--dur-base` + `--ease` | .2s cho phản hồi khi bấm · .45s cho hiệu ứng xuất hiện. Tất cả tự tắt khi bật `prefers-reduced-motion` |

Chấm tròn (`border-radius:50%`) và các kích thước cố định (logo cao 46px, cột số thứ tự 34px…) không thuộc thang khoảng cách.

---

## Thành phần

Các thành phần dưới đây là HTML do `app.py` tạo ra, dùng chung tiền tố `lh-`. Hàm tạo nằm trong `app.py`, ghi ở mục "Mã".

### Nhãn trạng thái (`lh-pill`)

Cho biết trạng thái bản PDF ở cuối thanh trạng thái.

| Biến thể | Dùng khi | Màu |
|---|---|---|
| `ok` | Sẵn sàng tải | `--ok` trên `--ok-bg` |
| `warn` | Nội dung đã sửa, cần cập nhật PDF | `--warn` trên `--warn-bg` |
| `err` | Còn lỗi cấu trúc / thông tin nhạy cảm | `--err` trên `--err-bg` |
| `idle` | Chờ duyệt, chưa dựng | `--muted` trên `--soft` |

- **Trạng thái:** chỉ hiển thị, không bấm được.
- **Truy cập:** chữ luôn ghi rõ trạng thái, không chỉ dựa vào màu. Chấm tròn đứng trước chữ chỉ để trang trí.
- **Nên:** một nhãn, 1–3 chữ. **Không nên:** đặt câu dài vào nhãn; câu giải thích để trong hộp cảnh báo.
- **Mã:** `<span class="lh-pill warn">Cần cập nhật</span>`

### Hộp cảnh báo (`lh-alert`)

Thông báo ngay trong khung PDF: lỗi cần sửa, nhắc cập nhật.

| Biến thể | Dùng khi |
|---|---|
| `err` | Chặn thao tác: còn SĐT/email, hồ sơ chưa hợp lệ, PDF còn thông tin liên hệ |
| `warn` | Cần làm thêm nhưng không phải lỗi: nội dung đã đổi, cần cập nhật PDF |
| `info` | Thông tin trung tính |
| `ok` | Xác nhận đã xong |

| Thuộc tính (`alert(kind, title, items)`) | Kiểu | Mô tả |
|---|---|---|
| `kind` | `"err" \| "warn" \| "info" \| "ok"` | Biến thể |
| `title` | str (HTML đã escape) | Một câu nói rõ chuyện gì và phải làm gì |
| `items` | list[str] \| None | Chi tiết, mỗi dòng một ý. Dùng `<code>` cho giá trị bị bắt |

- **Truy cập:** tiêu đề in đậm, đọc được ngay. Màu chỉ là tín hiệu phụ, viền trái 3px giúp phân biệt cả khi in đen trắng.
- **Nên:** escape mọi dữ liệu từ CV (`E(...)`). **Không nên:** dùng `st.error` của Streamlit trong khung PDF, vì sẽ lệch phong cách.

### Bong bóng chat (`lh-msg`)

| Biến thể | Dùng khi | Hình dạng |
|---|---|---|
| `bot` | Trợ lý trả lời | Căn trái, nền trắng, viền `--line`, góc trên trái nhọn |
| `me` | Tin của người dùng (thẻ file) | Căn phải, nền `--navy-50`, góc trên phải nhọn |
| `bot err` | Lỗi đọc CV / dựng PDF | Nền `--err-bg` |
| `tight` | Nhãn đặt sát ngay trên một khối khác (vd tin nhắn tóm tắt) | Khoảng dưới `--sp-2` |

- **Cấu trúc:** `.who` là nhãn người gửi (chữ hoa `--fs-xs`), `.bub` là nội dung. Kết quả đọc CV chia thành các `.lh-sec` (nhãn + số lượng + danh sách).
- **Trạng thái:** đang xử lý dùng `.lh-typing` (ba chấm nhấp nháy).
- **Chuyển động:** hiện dần và dịch lên 6px (`lhIn`, `--dur-base`).
- **Mã:** `render_message(m)` trong `ui/components.py`. Tin lưu trong `st.session_state.chat` dạng `{role, kind, ...}`.

### Thanh trạng thái PDF (`lh-bar`)

Một dòng trên cùng tab Bản PDF: icon tài liệu, tên file (mono), "A4 · n trang", và nhãn trạng thái.

- **Trạng thái:** nhãn bên phải theo bảng của `lh-pill`. Tên file dài bị cắt bằng dấu "…".
- **Mã:** điền vào `bar_slot` sau khi đã biết trạng thái duyệt, để thanh luôn nằm trên cùng.

### Dòng checklist (`lh-check`)

Một mục kiểm tra chất lượng PDF: chấm `--ok` / `--err`, tên mục, chi tiết bên dưới (`small`, `--faint`). Dùng biến thể `.no` khi mục không đạt.

### Khung A4 (`lh-stage`)

Trạng thái trống và trạng thái đang xử lý của khung PDF.

| Biến thể | Dùng khi | Hành vi |
|---|---|---|
| `stage(False)` | Chưa có hồ sơ | Trang A4 mờ + 3 bước hướng dẫn 01–03 |
| `stage(True, step)` | Đang đọc CV / dựng PDF | Vệt sáng chạy qua các vạch (`lhShim`); bước `step` đang làm (chữ đậm, số `--gold-text`), các bước trước bị gạch |

- **Truy cập:** vệt sáng tự tắt khi bật giảm chuyển động; tiến độ vẫn đọc được qua chữ của từng bước.
- **Không nên:** dùng vòng xoay (`st.spinner`) trong khung PDF.

### Header (`lh-top`) và tiêu đề panel (`lh-ph`)

- **Header:** logo (cao 46px, cắt bằng `render.crop_logo`), vạch ngăn, tên công cụ (`--fs-lg`) và mô tả (`--fs-sm`, `--faint`). Màn hình hẹp (< 900px) thì ẩn vạch ngăn.
- **Tiêu đề panel:** chữ hoa `--fs-md`, theo sau là vạch gold 14×2px. Cao cố định 40px để hai cột thẳng hàng với nút "Làm mới".

### Nút (Streamlit)

| Biến thể | Dùng khi |
|---|---|
| `type="primary"` (nền navy) | Một hành động chính tại một thời điểm: Gửi CV, Cập nhật PDF (khi cần), Tải PDF (khi sẵn sàng) |
| `type="secondary"` | Hành động phụ hoặc chưa sẵn sàng |
| `type="tertiary"` | Hành động nhẹ trên tiêu đề: Làm mới |

- **Trạng thái:** hover và focus theo Streamlit; khi bấm thu nhỏ còn 98% (`--dur-fast`). Khi bị khoá (disabled) luôn có `help=` giải thích vì sao.
- **Icon:** Material Symbols (`:material/refresh:`, `:material/download:`…), không dùng emoji.

### Thành phần PDF

Header, khối nhận diện, ô số liệu, thẻ năng lực, lộ trình, kinh nghiệm, học vấn và người tham chiếu: xem **mục 3–5 SKILL.md**. CSS nằm trong `template.html`, màu lấy từ `css_vars("pdf")`.

---

## Thêm thành phần mới

1. Kiểm tra bảng trên xem đã có thành phần gần giống chưa (ví dụ một thông báo mới thì dùng `lh-alert`, không tạo hộp mới).
2. Dùng tiền tố `lh-`, chỉ dùng `var(--...)` từ `infra/tokens.py`. Cần màu mới thì thêm vào `COLORS`, kèm cặp chữ/nền vào `TEXT_BG_PAIRS` nếu là màu chữ.
3. Có đủ các trạng thái cần thiết (trống, đang tải, lỗi) và tôn trọng `prefers-reduced-motion`.
4. Thêm một mục vào tài liệu này: dùng khi nào, có biến thể nào, trạng thái ra sao, lưu ý truy cập.
