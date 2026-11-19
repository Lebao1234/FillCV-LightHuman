"""Test bộ đọc theo luật với các kiểu bố cục CV hay gặp (dựng dòng giả theo toạ độ — không dùng CV thật).

Bố cục mô phỏng: khối đầu trang trải ngang (tên, liên hệ, đoạn giới thiệu) rồi chia 2 cột có tiêu đề mục ở cả hai
cột; tiêu đề to hơn thân bài; câu dài bị xuống dòng; nhãn "Thành tựu:" cùng cỡ thân bài; tiêu đề chữ to bị ngắt
2 dòng; chú thích căn giữa dưới icon; ngày sinh không nhãn; phần tiếp của cột trái sang trang sau.
"""
from services.extraction.rules import content, pdf_text, personal, sections
from services.extraction.rules.pdf_text import Line

BODY, HEAD = 10.5, 16.5
PAGE_W = 595.0


# Tạo một dòng giả; `edges` = lề trái/phải của cột chứa dòng (read_lines gán cho mọi dòng thật)
def line(text, x0, y0, x1=None, size=BODY, page=0, col=-1, bullet=False, edges=(41, 340)):
    x1 = x1 if x1 is not None else x0 + len(text) * size * 0.5
    return Line(text, [], x0, y0, x1, y0 + size * 1.2, page, size, col, bullet, *edges)


# Trang: khối đầu trang trải ngang + 2 cột, mỗi cột có tiêu đề mục
def two_column_page() -> list[Line]:
    header = [line("Nguyễn Văn Giả", 46, 55, size=31.5), line("Chức danh mong muốn", 55, 108, size=14),
              *[line(f"Đoạn giới thiệu bản thân dòng {i} trải hết chiều ngang trang giấy", 168, 233 + 15 * i, 548)
                for i in range(6)]]
    left = [line("Kinh nghiệm làm việc", 53, 359, size=HEAD), line("CÔNG TY GIẢ LẬP", 41, 393, size=12)]
    left += [line(f"Mô tả công việc số {i} viết khá dài để đủ chữ cho cột trái", 41, 413 + 15 * i, 330)
             for i in range(10)]
    right = [line("Học vấn", 436, 357, size=HEAD), line("TRƯỜNG GIẢ LẬP", 372, 392, size=12),
             line("Ngành học giả lập dài vừa đủ", 372, 412, 540), line("Tốt nghiệp loại khá giả lập", 372, 444, 540),
             line("Sở thích", 433, 487, size=HEAD)]
    right += [line(f"Sở thích giả lập số {i} khá dài", 372, 520 + 15 * i, 540) for i in range(6)]
    return header + left + right


# ------------------------------------------------------------------ nhận 2 cột

# Khối đầu trang trải ngang không còn làm hỏng việc nhận 2 cột ở phần dưới
def test_columns_below_full_width_header():
    lines = two_column_page()
    assert pdf_text._find_gutter(lines, PAGE_W) is None                  # cả trang: khối đầu cắt ngang mọi khe
    gutter, top = pdf_text._find_columns(lines, PAGE_W)
    assert gutter is not None and 320 <= gutter <= 372
    assert 293 < top <= 357                                              # vùng 2 cột bắt đầu dưới khối đầu trang
    pdf_text._assign_cols(lines, gutter, top)
    assert {ln.col for ln in lines[:8]} == {-1}
    assert next(ln for ln in lines if ln.text == "Học vấn").col == 1
    assert next(ln for ln in lines if ln.text == "Kinh nghiệm làm việc").col == 0


# CV 1 cột có lưới thẻ 2 cột / ngày tháng căn phải: không có tiêu đề mục ở cột phải -> không phải 2 cột
def test_card_grid_in_single_column_cv_is_not_two_columns():
    lines = [line(f"Đoạn văn trải ngang trang giấy số {i} rất dài", 48, 60 + 15 * i, 548) for i in range(5)]
    lines.append(line("NĂNG LỰC CỐT LÕI", 64, 140, size=HEAD))
    for i in range(8):
        lines += [line(f"Thẻ trái số {i} có nội dung khá dài ở đây", 58, 170 + 18 * i, 290),
                  line(f"Thẻ phải số {i} có nội dung khá dài ở đây", 313, 170 + 18 * i, 540)]
    assert pdf_text._find_columns(lines, PAGE_W) == (None, float("-inf"))


# Dòng bản quyền của trang tạo CV bị bỏ
def test_watermark_line():
    assert pdf_text._WATERMARK.match("© Trang Tao CV")
    assert not pdf_text._WATERMARK.match("Chứng chỉ ©")


# ------------------------------------------------------------------ tách mục

# Mảnh câu xuống dòng và nhãn cùng cỡ thân bài không thành mục; tiêu đề 2 dòng được ghép
def test_sections_ignore_sentence_tails_and_body_labels():
    lines = [line("About", 46, 228, size=37.5),
             line("Đoạn giới thiệu bản thân nằm bên phải tiêu đề chữ to", 168, 233, 548),
             line("me", 89, 258, size=37.5),
             line("Kinh nghiệm làm việc", 53, 359, size=HEAD),
             line("Chăm sóc quầy kệ hàng giúp quầy được đẹp mắt hấp dẫn khách", 41, 431, 333, bullet=True),
             line("đến xem và mua", 41, 446),
             line("Tạo nhu cầu mua thêm sản phẩm, giúp khách có trải", 41, 492, 325, bullet=True),
             line("nghiệm tốt nhất.", 41, 507),
             line("Thành tựu:", 41, 696),
             line("Được quản lý khen xử lý tình huống tốt", 41, 709, 302, bullet=True),
             line("Kỹ năng", 53, 744, size=HEAD),
             line("Tin học văn phòng:", 41, 783),
             line("Gõ 10 ngón, Word, Excel", 41, 796)]
    _, secs = sections.split_sections(lines)
    assert [(s.key, s.title) for s in secs] == [("summary", "About me"), ("experience", "Kinh nghiệm làm việc"),
                                               ("skills", "Kỹ năng")]
    assert any(ln.text == "Thành tựu:" for ln in secs[1].lines)


# CV không có tiêu đề nổi bật (mọi thứ cùng cỡ chữ): nhãn khớp từ khoá vẫn là tiêu đề như trước
def test_plain_cv_keeps_keyword_headings():
    lines = [line("Kinh nghiệm làm việc", 41, 100), line("Phụ trách bán hàng khu vực", 41, 115, bullet=True),
             line("Kỹ năng", 41, 140), line("Làm việc nhóm", 41, 155, bullet=True)]
    _, secs = sections.split_sections(lines)
    assert [s.key for s in secs] == ["experience", "skills"]


# Phần tiếp ở đầu trang sau thuộc mục của cột có cùng lề trái, không phải mục cuối của cột phải
def test_page_continuation_goes_to_same_column():
    lines = [line("Kỹ năng", 53, 744, size=HEAD, col=0), line("Tìm kiếm thông tin:", 41, 783, col=0),
             line("Học vấn", 436, 357, size=HEAD, col=1), line("Trường giả lập", 372, 392, col=1),
             line("Sở thích", 433, 487, size=HEAD, col=1), line("Đọc sách", 382, 562, col=1),
             line("Giao tiếp:", 41, 39, page=1), line("Dễ hoà nhập môi trường mới.", 41, 52, page=1)]
    _, secs = sections.split_sections(lines)
    by_key = {s.key: [ln.text for ln in s.lines] for s in secs}
    assert by_key["skills"] == ["Tìm kiếm thông tin:", "Giao tiếp:", "Dễ hoà nhập môi trường mới."]
    assert by_key["interests"] == ["Đọc sách"]


# Trang sau (1 cột) mở mục mới -> nội dung thuộc mục mới, không bị dồn về mục của cột ở trang trước
def test_new_section_on_later_page_keeps_its_lines():
    lines = [line("Kinh nghiệm làm việc", 53, 100, size=HEAD, col=0), line("Mô tả công việc giả lập", 41, 130, col=0),
             line("Học vấn", 436, 100, size=HEAD, col=1), line("Trường giả lập", 372, 130, col=1),
             line("Tiếp phần mô tả công việc giả lập.", 41, 39, page=1),
             line("Kỹ năng", 53, 80, size=HEAD, page=1), line("Kỹ năng giả lập thứ nhất", 41, 110, page=1),
             line("Kỹ năng giả lập thứ hai", 41, 125, page=1)]
    _, secs = sections.split_sections(lines)
    by_key = {s.key: [ln.text for ln in s.lines] for s in secs}
    assert by_key["experience"] == ["Mô tả công việc giả lập", "Tiếp phần mô tả công việc giả lập."]
    assert by_key["education"] == ["Trường giả lập"]
    assert by_key["skills"] == ["Kỹ năng giả lập thứ nhất", "Kỹ năng giả lập thứ hai"]


# ------------------------------------------------------------------ nối dòng, thông tin cá nhân

# Chú thích căn giữa dưới icon được nối; danh sách căn trái viết thường thì không
def test_centered_caption_joined_but_left_list_not():
    captions = [line("Chụp ảnh,", 443, 563, 484), line("làm video", 443, 579, 483), line("ngắn", 453, 593, 473)]
    assert [it.plain for it in content.logical_items(captions)] == ["Chụp ảnh, làm video ngắn"]
    left_list = [line("excel", 41, 100, 70), line("word", 41, 115, 65), line("powerpoint", 41, 130, 100)]
    assert [it.plain for it in content.logical_items(left_list)] == ["excel", "word", "powerpoint"]


# Ngày sinh không nhãn đứng cạnh ô khác trong khối đầu CV: bỏ ngày đầy đủ nhưng giữ năm sinh
def test_unlabeled_birth_date_keeps_year():
    ln = line("27/04/2001\tfb ten gia lap", 61, 161, 323)
    ident = personal.Identity()
    kept = personal.strip_personal([ln], {id(ln)}, ident)
    assert ident.birth_year == 2001 and "birth" in ident.removed
    assert all("27/04" not in k.text for k in kept)
