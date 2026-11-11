# Prompt OpenAI cũ — LỖI THỜI, chỉ để tham khảo

App **không còn dùng OpenAI** (đã gỡ 11/2026). Các file trong thư mục này là bản prompt cuối cùng từng gửi cho AI,
giữ lại làm **đặc tả nghiệp vụ** cho bộ trích xuất theo luật (`services/extraction/`). Code không đọc các file này.

| File | Nội dung | Còn giá trị |
|---|---|---|
| `system_prompt.txt` | Quy tắc trích xuất: bảo mật thông tin, ngôn ngữ, chức danh, định dạng `**in đậm**`, hàng 4 ô số liệu, lưu ý tuyển dụng | **Có** — đặc tả cho bộ luật; quy tắc gốc vẫn là `SKILL.md` |
| `user.txt` | Mẫu tin nhắn gửi kèm CV (ngày hôm nay, dự án, vị trí) | Không |
| `fix_json.txt` | Câu yêu cầu AI sửa JSON hỏng | Không |
| `version.txt` | Số phiên bản prompt cuối cùng (1.0) | Không |

Cấu trúc JSON hồ sơ (schema) vẫn dùng và chỉ có một bản: `prompts/schema.json` ↔ `services/ai/models.py`.
Metadata PDF giờ ghi phiên bản **bộ trích xuất** (`extractor <tên>-<phiên bản>`) thay cho phiên bản prompt.
