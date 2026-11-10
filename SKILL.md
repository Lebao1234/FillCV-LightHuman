---
name: lighthuman-cv
description: Làm lại CV ứng viên theo chuẩn Light Human để gửi khách hàng. Dùng khi chị Trâm (CEO Light Human) gửi CV ứng viên (PDF/DOCX/ảnh), kể cả khi chỉ đính kèm file mà không nhắn gì.
---

# Light Human – CV ứng viên gửi khách hàng

## 0. Nguyên tắc giao tiếp

- Trả lời bằng **tiếng Việt**, xưng **"em"**, gọi **"chị"**.
- Đã đủ thông tin thì **làm luôn**, không hỏi lại.
- **Không bịa** thông tin. Mọi chỗ em tự lập hoặc tự điều chỉnh đều phải báo chị.

---

## 1. Đầu vào

| Đầu vào | Bắt buộc | Nếu thiếu |
|---|---|---|
| File CV gốc (PDF/DOCX/ảnh) | Có | — |
| Tên dự án + vị trí (vd: "Dự án Takumi – vị trí BA") | Nên có | Xem quy tắc **1.1** |
| Logo `Logo_Light_Human-02.png` (PNG nền trong) | Có | Xin chị đính kèm. **KHÔNG tự vẽ lại logo.** |

**1.1. Xác định dự án/vị trí khi chị không nói**
1. Ứng viên cùng vị trí với CV ngay trước trong cuộc trò chuyện → dùng lại dự án/vị trí đó.
2. Không có căn cứ → hỏi chị **một câu ngắn**.
3. Không ai trả lời → để trống dòng dự án, lấy vị trí từ chức danh mục tiêu trên CV.
4. Luôn nói rõ dự án đã gắn để chị sửa nếu sai.

**1.2. CV cập nhật** — Nếu chị gửi bản mới của CV đã làm: so sánh văn bản với bản cũ (diff), chỉ áp phần thay đổi vào file đã làm, **giữ nguyên tên file**, báo chị đã đổi những gì.

---

## 2. Quy trình

1. **Đọc CV gốc**: `pdftotext -layout`, `pdfimages -list`; trích ảnh chân dung (`pdfimages -png`).
2. **Chuẩn bị logo**: `Image.crop(im.getbbox())` để cắt sát viền trong suốt, thu về ~1200px chiều rộng.
3. **Lọc dữ liệu**: bỏ thông tin nhạy cảm theo mục **3.2**, ghi lại mức lương mong muốn để báo chị.
4. **Viết HTML**: header (mục **3.1**) + nội dung (mục **4**) + CSS mẫu (mục **5**).
5. **Xuất PDF** bằng Playwright (mục **6**), xuất thẳng ra tên file chuẩn (mục **3.6**).
6. **Kiểm tra** theo checklist (mục **7**); sửa và xuất lại nếu chưa đạt.
7. **Gửi chị** file đính kèm + tóm tắt + lưu ý tuyển dụng (mục **8**).

---

## 3. Quy tắc bắt buộc

### 3.1. Header
- **Trái**: logo Light Human, cắt sát viền trong suốt, cao **15mm**.
- **Giữa**: thông tin Light Human, 4 dòng, nhãn đậm navy:
  - **Địa chỉ:** 213 Chu Văn An, Phường Bình Thạnh, TP. Hồ Chí Minh
  - **Điện thoại:** 028 3842 5188
  - **Email:** info@lighthuman.vn
  - **Website:** https://lighthuman.vn/

  Ngăn với khối bên phải bằng vạch dọc xám mảnh.
- **Phải**: "HỒ SƠ ỨNG VIÊN" (in hoa, navy, đậm); dòng dưới "Dự án: **<tên dự án>**" (tên dự án đậm, màu gold).
  - **KHÔNG** có dòng tiếng Anh "Candidate Profile".
- Dưới header chỉ **một đường kẻ navy 2pt**. **KHÔNG** có gạch vàng/gold.

### 3.2. Bảo mật thông tin ứng viên

| Loại thông tin | Xử lý |
|---|---|
| SĐT, email, Zalo, LinkedIn, Facebook | **Xóa** |
| Địa chỉ nhà (kể cả quận/phường) | **Xóa** |
| Link portfolio (Behance, GitHub, website cá nhân…) | Giữ **tên dự án**, bỏ đường link |
| Ngày sinh | Chỉ giữ **năm sinh** |
| Nơi sinh, tình trạng hôn nhân, quốc tịch | **Xóa** |
| Giới tính, thành phố làm việc (vd "Hà Nội") | Được giữ |
| Mức lương mong muốn | Bỏ khỏi CV, **báo con số cho chị** trong tin nhắn |
| Người tham chiếu | Giữ tên + chức danh + công ty; ẩn SĐT/email; thêm ghi chú nghiêng (bên dưới) |

> *Thông tin liên hệ người tham chiếu sẽ được Light Human cung cấp khi Quý khách hàng có nhu cầu kiểm tra tham chiếu.*

### 3.3. Nội dung & ngôn ngữ
- Giữ nguyên nội dung chuyên môn và **đủ các mục** của CV gốc; chỉ sửa lỗi chính tả/ngắt dòng rõ ràng.
- Nếu CV ghi một chức danh ở lộ trình sự nghiệp → dùng **thống nhất** chức danh đó ở mọi chỗ.
- Ngôn ngữ:
  - CV tiếng Việt → giữ tiếng Việt.
  - CV tiếng Anh → giữ tiếng Anh (tiêu đề mục tiếng Anh; header Light Human vẫn tiếng Việt).
  - CV song ngữ Việt–Anh → chỉ giữ phần tiếng Việt, báo chị và đề nghị làm bản tiếng Anh nếu khách cần.

### 3.4. Ảnh chân dung
- CV gốc có ảnh → giữ (dùng ảnh gốc, **không** dùng mặt nạ tròn; cắt giữa theo tỉ lệ **29:38**; ảnh selfie thì cắt quanh khuôn mặt).
- Không có ảnh → bỏ khung ảnh.
- Ảnh kém (selfie, mờ, đen trắng, chụp nghiêng) → nhắc chị xin ảnh thẻ.

### 3.5. Font
- **Times New Roman** toàn bộ. Trên Linux dùng fallback **Liberation Serif** (metric tương đương) và **nhúng font** vào PDF.

### 3.6. Tên file (KHÔNG DẤU)

```
LH - CV <Tên vị trí> - <Họ và tên ứng viên> - <ddmmyyyy>.pdf
```

- Ví dụ: `LH - CV Ke toan truong - Tran Hong Linh - 05112026.pdf`, `LH - CV BA - Pham Hong Phuc - 06112026.pdf`
- Ngày = ngày xuất file theo **giờ Việt Nam**, trừ khi chị nói khác.
- Bỏ dấu bằng `unicodedata` và đổi `đ/Đ` → `d/D`.
- `<title>` của HTML (= tiêu đề PDF) **đúng bằng tên file** (không có `.pdf`).
- Xuất thẳng ra tên này, không để lại file tên cũ.

```python
import unicodedata
def khong_dau(s: str) -> str:
    s = s.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")
```

---

## 4. Bố cục & nhận diện

### 4.1. Màu thương hiệu

| Tên | Mã | Dùng cho |
|---|---|---|
| Navy | `#14285a` | Tiêu đề, nhãn, ngày tháng |
| Gold | `#dca54b` | Chức danh, tên dự án, bullet, ô vuông trước tiêu đề mục, viền dưới hàng ô số liệu |
| Yellow | `#f2cf63` | Vạch dọc trước mục con |
| Ink | `#1f2430` | Chữ thường |
| Muted | `#5a6275` | Chữ phụ |
| Line | `#d9dce3` | Đường kẻ |
| Nền ô số liệu | `#eef1f6` | Hàng ô số liệu |

### 4.2. Thứ tự trang

1. **Header** (mục 3.1).
2. **Khối nhận diện**: ảnh 29×38mm viền mảnh + **TÊN** in hoa navy 25pt + chức danh mục tiêu/hiện tại màu gold + dòng thông tin nhanh (Năm sinh, Giới tính, …).
3. **Hàng 4 ô số liệu** (mục 4.3).
4. **Các mục nội dung** theo đúng thứ tự CV gốc, thường là:
   Tóm tắt → (Thành tích nổi bật) → Kỹ năng/Năng lực cốt lõi → (Lộ trình sự nghiệp) → Kinh nghiệm làm việc → Học vấn & Chứng chỉ → Kỹ năng & Hoạt động → Người tham chiếu.

   Tiêu đề mục: in hoa navy, ô vuông gold xoay 45° phía trước, gạch chân xám.

### 4.3. Hàng ô số liệu nổi bật
- CV gốc **có** ô số liệu/điểm nhấn (vd "13+ năm · 7 nhân sự · 2 doanh nghiệp · Kế toán trưởng") → **PHẢI** giữ dạng hàng ô riêng ngay dưới khối tên, **KHÔNG** gộp vào dòng chữ.
- CV gốc **không có** → được lập 4 ô từ số liệu **có thật** trong CV (số năm kinh nghiệm, số năm quản lý, bằng cấp, chứng chỉ, quy mô đội…) và **báo chị là em tự lập**.
- Định dạng: lưới 4 cột nền `#eef1f6`, viền dưới gold 2pt; số 15pt navy đậm; chú thích 8.4pt màu phụ, `white-space: nowrap`.

### 4.4. Định dạng từng mục
- **Năng lực cốt lõi**: thẻ trong lưới 2 cột (3 cột nếu CV gốc có sidebar kỹ năng/domain/tools); mỗi thẻ có vạch vàng bên trái, tên thẻ đậm navy. Công cụ/phần mềm có thể để dạng tag nhỏ viền xám.
- **Lộ trình sự nghiệp** (nếu CV gốc có): bảng 3 cột Thời gian – Chức danh – Công ty; dòng hiện tại tô gold.
- **Kinh nghiệm làm việc**, mỗi công việc:
  - TÊN CÔNG TY in hoa đậm bên trái, thời gian navy đậm canh phải.
  - Dòng chức danh nghiêng, màu gold.
  - Dòng phụ (Ngành / Dự án / Công việc chính) nếu có.
  - Nhóm việc dùng tiêu đề nhỏ "▸" navy.
  - Bullet: in đậm navy cụm từ khóa nếu CV gốc có.
  - Vị trí/giai đoạn con: dòng phụ có vạch vàng bên trái, thời gian nghiêng canh phải.
- **Học vấn / Chứng chỉ**: tên văn bằng bên trái, năm (hoặc nơi cấp) canh phải.

### 4.5. Cỡ chữ & ngắt trang
- Mặc định **11.5pt**, line-height **1.42**, căn đều hai bên.
- CV dài: thu xuống **10.8–11pt**, line-height **1.34–1.38**, giảm khoảng cách để không có trang cuối gần trống.
- Bullet và khối công việc ngắn không bị cắt ngang (`break-inside: avoid`).
- Tiêu đề công ty/chức danh/dòng mô tả luôn đi cùng bullet đầu tiên (`break-after: avoid`) — không để tiêu đề mồ côi cuối trang.

### 4.6. Footer
Dùng footer của trình in (**không** dùng `position: fixed`), trên mỗi trang:
- Trái: *Hồ sơ do Light Human giới thiệu · Thông tin liên hệ của ứng viên được bảo mật*
- Phải: *lighthuman.vn · Trang X/Y*

---

## 5. CSS mẫu

```css
@page { size: A4; margin: 16mm 17mm 20mm 17mm; }
:root { --navy:#14285a; --gold:#dca54b; --yellow:#f2cf63; --ink:#1f2430; --muted:#5a6275; --line:#d9dce3; }
*{box-sizing:border-box} html,body{margin:0;padding:0}
body { font-family:"Times New Roman","Liberation Serif",Times,serif; color:var(--ink); font-size:11.5pt; line-height:1.42; background:#fff; }

/* Header */
.brand { display:flex; align-items:center; justify-content:space-between; padding-bottom:3.5mm; border-bottom:2pt solid var(--navy); }
.brand img { height:15mm; }
.brand .right { display:flex; align-items:center; gap:5mm; }
.brand .co { font-size:9pt; line-height:1.55; padding-right:5mm; border-right:0.8pt solid var(--line); }
.brand .co .lbl { color:var(--navy); font-weight:bold; display:inline-block; width:16mm; }
.brand .doc { text-align:right; font-size:9pt; color:var(--muted); letter-spacing:.06em; text-transform:uppercase; line-height:1.5; }
.brand .doc b { color:var(--navy); font-size:10.5pt; letter-spacing:.1em; }
.brand .doc .proj { display:block; margin-top:1mm; text-transform:none; letter-spacing:.02em; font-size:10.5pt; color:var(--ink); }
.brand .doc .proj b { color:var(--gold); font-size:11pt; letter-spacing:.02em; }

/* Khối nhận diện */
.identity { display:flex; align-items:center; gap:7mm; margin:8mm 0 5mm; }
.identity .photo { width:29mm; height:38mm; object-fit:cover; border:0.8pt solid var(--line); padding:1.2mm; flex:none; }
.identity h1 { font-size:25pt; color:var(--navy); margin:0 0 1.5mm; letter-spacing:.04em; line-height:1.1; }
.identity .title { font-size:13pt; font-weight:bold; color:var(--gold); margin-bottom:3mm; }
.facts { display:flex; flex-wrap:wrap; gap:1.5mm 7mm; font-size:10.5pt; } .facts b { color:var(--navy); }

/* Hàng ô số liệu */
.stats { display:grid; grid-template-columns:repeat(4,1fr); background:#eef1f6; border-bottom:2pt solid var(--gold); margin:0 0 2mm; }
.stat { text-align:center; padding:2.6mm .8mm 2.2mm; border-right:0.8pt solid #fff; } .stat:last-child{border-right:none}
.stat .n { font-size:15pt; font-weight:bold; color:var(--navy); line-height:1.2; }
.stat .l { font-size:8.4pt; color:var(--muted); margin-top:.6mm; white-space:nowrap; }

/* Tiêu đề mục & văn bản */
h2 { font-size:12.5pt; color:var(--navy); text-transform:uppercase; letter-spacing:.08em; margin:6mm 0 2.5mm; padding-bottom:1.2mm; border-bottom:0.8pt solid var(--line); display:flex; align-items:center; gap:2.5mm; break-after:avoid; }
h2::before { content:""; width:3mm; height:3mm; background:var(--gold); transform:rotate(45deg); flex:none; }
p { margin:0 0 2mm; text-align:justify; }
ul { margin:0 0 2mm; padding-left:5.5mm; } li { margin:0 0 1.4mm; text-align:justify; break-inside:avoid; } li::marker { color:var(--gold); }
.k { font-weight:bold; color:var(--navy); }
.avoid { break-inside:avoid; }

/* Năng lực cốt lõi & tag công cụ */
.cards { display:grid; grid-template-columns:repeat(2,1fr); gap:2.5mm 4mm; } .cards.c3 { grid-template-columns:repeat(3,1fr); }
.card { border-left:2pt solid var(--yellow); padding:.5mm 0 .5mm 3mm; break-inside:avoid; } .card .t { font-weight:bold; color:var(--navy); }
.tags { display:flex; flex-wrap:wrap; gap:1.5mm; } .tag { border:0.8pt solid var(--line); padding:.3mm 2mm; font-size:9.5pt; }

/* Lộ trình sự nghiệp */
.path { width:100%; border-collapse:collapse; font-size:10.5pt; }
.path td { padding:1.2mm 2mm; border-bottom:0.8pt solid var(--line); } .path td:first-child { color:var(--navy); font-weight:bold; white-space:nowrap; }
.path tr.now td { color:var(--gold); font-weight:bold; }

/* Kinh nghiệm làm việc */
.job { margin:0 0 4.5mm; }
.job-head { display:flex; justify-content:space-between; align-items:baseline; gap:4mm; break-after:avoid; }
.company { font-weight:bold; font-size:12pt; text-transform:uppercase; }
.date { flex:none; font-size:10.5pt; color:var(--navy); font-weight:bold; white-space:nowrap; }
.role { font-style:italic; color:var(--gold); font-weight:bold; margin:.6mm 0 1.6mm; break-after:avoid; }
.grp { font-weight:bold; color:var(--navy); margin:1.5mm 0 1mm; break-after:avoid; } .grp::before { content:"▸ "; }
.sub { display:flex; justify-content:space-between; align-items:baseline; margin:2mm 0 1.2mm; padding-left:3mm; border-left:2pt solid var(--yellow); break-after:avoid; }
.sub .name { font-weight:bold; color:var(--navy); } .sub .date { font-weight:normal; font-style:italic; }

/* Học vấn */
.edu { padding-left:5.5mm; } .edu li { display:flex; justify-content:space-between; gap:4mm; list-style:none; position:relative; }
.edu li::before { content:"▪"; color:var(--gold); position:absolute; left:-4.5mm; } .edu .yr { flex:none; color:var(--navy); font-weight:bold; }

/* Người tham chiếu */
.ref { border:0.8pt solid var(--line); border-left:3pt solid var(--navy); padding:3mm 4mm; background:#f6f7fa; }
```

---

## 6. Xuất PDF (Playwright – Chromium)

```python
FOOTER = """
<div style="width:100%; margin:0 17mm; padding-top:1.5mm; border-top:0.5pt solid #d9dce3;
            font-family:'Times New Roman','Liberation Serif',serif; font-size:8px; color:#5a6275;
            display:flex; justify-content:space-between;">
  <span>Hồ sơ do Light Human giới thiệu · Thông tin liên hệ của ứng viên được bảo mật</span>
  <span>lighthuman.vn · Trang <span class="pageNumber"></span>/<span class="totalPages"></span></span>
</div>"""

page.pdf(
    path=ten_file,                 # tên chuẩn theo mục 3.6
    format="A4",
    print_background=True,
    prefer_css_page_size=True,
    display_header_footer=True,
    header_template="<span></span>",
    footer_template=FOOTER,
)
```

---

## 7. Checklist trước khi gửi

- [ ] `pdffonts`: font serif (Times New Roman / Liberation Serif) đã **nhúng**.
- [ ] `pdftotext | grep`: không còn SĐT, email, địa chỉ, ngày sinh, link của ứng viên.
      *(028 3842 5188 và info@lighthuman.vn là của Light Human — được phép.)*
- [ ] Render ảnh từng trang và xem: không tràn chữ, không tiêu đề mồ côi, không trang cuối gần trống.
- [ ] Header đúng mục 3.1 (không "Candidate Profile", không gạch gold).
- [ ] Đủ các mục của CV gốc, không thêm thông tin bịa.
- [ ] Tên file và `<title>` đúng mục 3.6; không còn file tên cũ.

---

## 8. Trả lời chị

Gửi file PDF dạng **tệp đính kèm**, kèm tin nhắn ngắn theo khung:

```
Em gửi chị CV <Họ tên> – <Vị trí> ạ.

• Dự án đã gắn: <tên dự án> (chị sửa giúp em nếu chưa đúng)
• Đã bỏ: <SĐT, email, địa chỉ, ngày sinh, link…>
• Lương mong muốn: <con số> (em đã bỏ khỏi CV)
• Em tự lập/điều chỉnh: <vd: hàng 4 ô số liệu, sửa chính tả…>

Lưu ý để chị xác minh trước khi gửi khách:
• <…>
```

**Lưu ý tuyển dụng** — chỉ nêu, **không tự sửa trong CV**:
- Thời gian làm việc chồng chéo, hoặc trùng thời gian đi học.
- Khoảng trống trong quá trình làm việc.
- Chức danh/cấp bậc không khớp số năm kinh nghiệm (vd "Senior" nhưng < 4 năm).
- Giữ vị trí quản lý quá ngắn.
- Chứng chỉ Kế toán trưởng có **sau** thời điểm ghi làm Kế toán trưởng.
- Thiếu mục Học vấn, hoặc bằng cấp có thể không đạt yêu cầu.
- Ảnh kém chất lượng.
- CV song ngữ → đề nghị làm thêm bản ngôn ngữ còn lại nếu khách cần.
