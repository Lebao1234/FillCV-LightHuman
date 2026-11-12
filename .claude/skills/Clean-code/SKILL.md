---
name: clean-code
description: Quy ước viết code của dự án FillCV-LightHuman (Streamlit, Python). Dùng khi viết hàm mới, sửa hoặc refactor code trong system/, review một thay đổi, hoặc khi người dùng yêu cầu "clean code", "dọn code", "đặt tên lại", "tách hàm".
---

# Clean code — FillCV-LightHuman

Mọi đường dẫn tính từ `system/`. Chạy lệnh Python từ `system/`.

## Trước khi sửa

1. Đọc file định sửa và nơi gọi nó. Không đoán chữ ký hàm.
2. Xác định lớp của file (`ui` → `core` → `services` → `infra`). Thay đổi thuộc lớp nào thì đặt ở lớp đó; xem skill `senior-architect` nếu chưa rõ.
3. Chỉ sửa đúng phạm vi được yêu cầu. Thấy vấn đề khác thì báo, không tự sửa kèm.

## Quy ước bắt buộc

**Ngôn ngữ**
- Định danh (hàm, biến, lớp, key của dict/session, key trong `config/*.toml`, tên file): tiếng Anh, PEP 8.
- Chữ hiển thị cho người dùng, nội dung PDF, chú thích và docstring: tiếng Việt có dấu.

**Chú thích và chữ ký**
- Mỗi hàm và lớp có một dòng `#` tiếng Việt ngay phía trên, nói nó làm gì.
- Hàm công khai (không bắt đầu bằng `_`) có type hint đầy đủ và docstring.
- Chú thích giải thích lý do hoặc ràng buộc, không kể lại code. Không ghi lịch sử sửa đổi vào chú thích.

**Import**
- Import không có tiền tố `system.`: viết `from infra.settings import ...`, không viết `from system.infra.settings import ...`. VS Code có thể tự thêm tiền tố này khi di chuyển file; phải bỏ đi.
- Trong `core/`, gọi lớp dưới qua module: `from services.pdf import render` rồi `render.build_pdf(...)`. Không `from services.pdf.render import build_pdf`, vì test thay hàm giả trên module và cách import trực tiếp sẽ bỏ qua hàm giả.

**Giới hạn kích thước**
- `app.py` dưới 250 dòng, chỉ điều phối giao diện và `session_state`. Không đặt nghiệp vụ hay CSS vào đây.
- `edit_profile` trong `ui/profile_form.py` không quá 15 dòng; mỗi loại mục có một hàm `_edit_*` riêng, đăng ký trong `EDITORS_BY_TYPE`.
- `ui/components.py` là hàm thuần: nhận dữ liệu, trả chuỗi HTML, không gọi Streamlit.

**Không hardcode**
- Từ khoá nhận diện CV: `config/extraction_rules.toml` (không dấu, chữ thường). Không viết từ khoá hay nội dung lấy từ CV thật vào code.
- Thông tin công ty: `config/company.toml`.
- Màu, cỡ chữ, bo góc, khoảng cách, lề PDF: `infra/tokens.py`. `ui/styles.css` không chứa mã màu hay số px viết thẳng.
- Giá trị cấu hình: thêm vào `infra/settings.py` (mặc định + biến môi trường). Dự án không đọc `.env`.

**Xử lý lỗi và log**
- Lỗi hiện cho người dùng là câu tiếng Việt dễ hiểu; chi tiết kỹ thuật chỉ ghi vào log.
- Không ghi nội dung CV, họ tên hay tên file vào log; dùng `mask_filename()`.
- Câu cảnh báo cho người duyệt do code soạn, không chép chữ từ CV vào.

## Khi đổi tên

Các tên sau nằm ở hai nơi và hỏng im lặng nếu chỉ đổi một bên. Đổi tên nào thì tìm cả hai bên:

| Bên này | Bên kia |
|---|---|
| Biến trong `services/pdf/template.html` | Tham số của `render.render_html()` |
| `{name}` trong `footer_intro` (`config/company.toml`) | `render_worker.footer_html()` |
| Key session trong `app.py` (`review`, `stage_labels`, …) | `ui/profile_form.py` |
| Dict checklist `{code, item, ok, detail}`, dict vi phạm `{field, kind, value}` | `ui/components.py`, `core/pdf_status.py` |
| `prompts/schema.json` | `services/ai/models.py` |

## Kiểm tra sau khi sửa

```powershell
cd system
python -m ruff check .                 # CI chạy lệnh này và chặn khi có lỗi
python -m pytest -q -m "not slow"      # khi thư mục tests/ tồn tại
```

Nếu chưa có `tests/`, tối thiểu phải chạy thử để chắc app còn khởi động:

```powershell
python -c "from streamlit.testing.v1 import AppTest; print(AppTest.from_file('app.py', default_timeout=60).run().exception)"
```

Báo lại lệnh đã chạy và kết quả. Lệnh nào không chạy được thì nói rõ, không ghi là đã kiểm tra.
