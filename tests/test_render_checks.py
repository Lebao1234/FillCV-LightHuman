"""Test tên file, filter in đậm, quét thông tin nhạy cảm (không gọi API)."""
import copy
import json
from datetime import date
from pathlib import Path

from services.privacy.checks import scan_pii, scan_text
from services.pdf.render import bold_filter, build_filename, khong_dau

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "sample_candidate.json").read_text(encoding="utf-8"))


# ---- Tên file ----
def test_khong_dau():
    assert khong_dau("Đặng Thị Lan") == "Dang Thi Lan"
    assert khong_dau("Kế toán trưởng") == "Ke toan truong"
    assert khong_dau("đường Đỗ") == "duong Do"


def test_build_filename():
    assert build_filename("Kế toán trưởng", "Đặng Thị Lan", date(2026, 11, 6)) == \
        "LH - CV Ke toan truong - Dang Thi Lan - 06112026.pdf"


def test_build_filename_bo_ky_tu_cam():
    assert build_filename("BA/QA", "Phạm  Hồng Phúc", date(2026, 1, 5)) == \
        "LH - CV BA QA - Pham Hong Phuc - 05012026.pdf"


# ---- In đậm ----
def test_bold_filter():
    assert str(bold_filter("Quản lý **10 nhân sự**")) == 'Quản lý <span class="k">10 nhân sự</span>'


def test_bold_filter_chong_chen_html():
    out = str(bold_filter("<script>x</script> **a**"))
    assert "<script>" not in out and '<span class="k">a</span>' in out


# ---- Quét thông tin nhạy cảm ----
def test_fixture_sach():
    assert scan_pii(FIXTURE) == []


def test_bat_sdt_email_chen_vao():
    cv = copy.deepcopy(FIXTURE)
    cv["sections"][0]["bullets"].append("Liên hệ 0909 123 456 hoặc may.doan@gmail.com")
    cv["facts"].append({"label": "Zalo", "value": "+84 912345678"})
    loai = {v["loai"] for v in scan_pii(cv)}
    assert {"Số điện thoại", "Email", "Mạng xã hội"} <= loai


def test_bat_ngay_sinh_va_link():
    loai = {l for l, _ in scan_text("Sinh 01/03/1988, portfolio https://behance.net/may")}
    assert {"Ngày sinh đầy đủ", "Đường link"} <= loai


def test_whitelist_light_human():
    assert scan_text("028 3842 5188 · info@lighthuman.vn · https://lighthuman.vn/") == []


def test_khong_bao_nham_moc_thoi_gian():
    assert scan_text("07/2018 – 09/2022, 12/2008 – 12/2011, năm 2007, 30.000.000 VND") == []


def test_bo_qua_luong_va_ghi_chu():
    # Lương và model_notes không vào PDF nên không quét
    cv = copy.deepcopy(FIXTURE)
    cv["model_notes"]["other"].append("SĐT gốc 0909123456 đã xoá")
    assert scan_pii(cv) == []


# ---- Hồi quy theo code review ----
def test_khong_bao_nham_ten_cong_nghe():
    assert scan_text("ASP.NET Core, VB.NET, ADO.NET") == []
    assert scan_text("Chạy quảng cáo Facebook Ads, dùng GitHub Actions") == []


def test_van_bat_tai_khoan_mxh():
    assert ("Mạng xã hội", "Facebook: nguyenvana") in scan_text("Facebook: nguyenvana")


def test_whitelist_khop_dung_ten_mien():
    assert scan_text("https://lighthuman.vn.mysite.com/cv")
    assert scan_text("facebook.com/lighthuman.vnfan")
    assert scan_text("https://www.lighthuman.vn/tuyen-dung") == []


def test_crop_portrait_theo_exif():
    import io
    from PIL import Image
    from services.pdf.render import crop_portrait
    im = Image.new("RGB", (400, 300), "red")
    ex = im.getexif()
    ex[0x0112] = 6                         # ảnh điện thoại: cần xoay 90°
    b = io.BytesIO()
    im.save(b, "JPEG", exif=ex)
    w, h = Image.open(io.BytesIO(crop_portrait(b.getvalue()))).size
    assert h > w


def test_facts_trong_khong_in_none():
    from services.pdf.render import render_html
    cv = copy.deepcopy(FIXTURE)
    cv["facts"] = [{"label": "Mong muốn", "value": None}, {"label": "", "value": "Đi làm ngay"}]
    html = render_html(cv, "", "t")      # GĐ3: template cần thêm ct/le/font -> dùng hàm dựng thật
    assert "None" not in html and "Đi làm ngay" in html


def test_muc_cards_render_duoc():
    """c.items trùng dict.items() -> template phải dùng c['items']."""
    from services.pdf.render import render_html
    cv = copy.deepcopy(FIXTURE)
    cv["sections"].append({"type": "cards", "title": "Năng lực cốt lõi", "paragraphs": [], "bullets": [],
                           "cards": [{"title": "Kế toán quản trị", "items": ["Lập báo cáo **quản trị**"]}],
                           "tags": [], "career_path": [], "jobs": [], "education": [], "references": []})
    html = render_html(cv, "", "t")      # GĐ3: template cần thêm ct/le/font -> dùng hàm dựng thật
    assert "Kế toán quản trị" in html and '<span class="k">quản trị</span>' in html


# ===== Lỗi 1: SĐT có mã quốc gia/vùng trong ngoặc =====
import pytest
from services.privacy.checks import MAU


@pytest.mark.parametrize("sdt", ["(+84) 912 345 678", "(+84) 909 123 456", "(028) 3842 5188",
                                 "+84 912 345 678", "0912.345.678", "0912-345-678", "ĐT: (+84)912345678"])
def test_loi1_bat_sdt_dang_ngoac(sdt):
    assert MAU["Số điện thoại"].search(sdt), sdt


def test_loi1_scan_text_bat_sdt_ngoac():
    assert ("Số điện thoại" in {l for l, _ in scan_text("ĐT: (+84) 909 123 456")})
    assert ("Số điện thoại" in {l for l, _ in scan_text("Bàn: (028) 3912 3456")})
    # Số tổng đài Light Human (whitelist) vẫn được phép dù viết trong ngoặc
    assert scan_text("(028) 3842 5188") == []


@pytest.mark.parametrize("text", ["Năm 2019", "2019 - 2021", "15/06/2020", "01.03.2019",
                                  "Lương 30.000.000 - 35.000.000 VND", "Doanh thu 10.000.000.000 đồng",
                                  "Chứng chỉ số CPA0123456789", "Mã: AB-01234567"])
def test_loi1_khong_bat_nham(text):
    assert not MAU["Số điện thoại"].search(text), text


# ===== Lỗi 2: lỗi bất kỳ khi đọc CV không được làm kẹt app =====
APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _app_dang_cho(monkeypatch, loi):
    import zipfile
    from services.ai import extract
    from streamlit.testing.v1 import AppTest
    goi = []

    def gia(*a, **k):
        goi.append(1)
        raise loi
    monkeypatch.setattr(extract, "extract_cv", gia)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["pending"] = {"data": b"PK-hong", "ten": "cv.docx", "project": "X", "position": ""}
    return at, goi


@pytest.mark.parametrize("loi", [__import__("zipfile").BadZipFile("File is not a zip file"),
                                 ConnectionError("network down"), ValueError("bất ngờ")])
def test_loi2_moi_loi_doc_cv_deu_duoc_bat(monkeypatch, loi):
    at, goi = _app_dang_cho(monkeypatch, loi)
    at.run()
    assert not at.exception                          # không lọt traceback
    assert at.session_state["pending"] is None       # không kẹt trạng thái chờ
    assert any("Không đọc được CV" in e.value for e in at.error)
    at.run()
    assert len(goi) == 1                             # rerun không gọi lại API


# ===== Lỗi 3: quét cả dự án/vị trí + cổng tải phải theo checklist PDF =====
def test_loi3_quet_du_an_va_vi_tri():
    from services.privacy.checks import scan_pii_xuat
    loi = scan_pii_xuat(FIXTURE, "Message Coffee - LH 0909123456", "Kế toán (zalo: abc)")
    assert {(v["field"], v["loai"]) for v in loi} >= {("Tên dự án", "Số điện thoại"), ("Vị trí", "Mạng xã hội")}
    assert scan_pii_xuat(FIXTURE, "Message Coffee", "Kế toán trưởng") == []


def test_loi3_pdf_sach():
    from services.privacy.checks import pdf_sach
    sach = [{"ma": "pii", "muc": "x", "ok": True, "chi_tiet": "Sạch"}, {"ma": "trang_cuoi", "muc": "y", "ok": False, "chi_tiet": ""}]
    ban = [{"ma": "pii", "muc": "x", "ok": False, "chi_tiet": "Số điện thoại: 0909123456"}]
    assert pdf_sach(sach) and not pdf_sach(ban) and not pdf_sach([]) and not pdf_sach(None)


def _app_co_pdf(monkeypatch, checklist, project="Message Coffee"):
    """App đã có hồ sơ; build_pdf/scan_pdf được thay bằng bản giả cho nhanh."""
    from services.privacy import checks
    import pymupdf as fitz
    from services.pdf import render
    from streamlit.testing.v1 import AppTest

    def build_gia(cv, project, position, photo, out_dir, d=None):
        p = Path(out_dir) / "LH - CV Test.pdf"
        doc = fitz.open(); doc.new_page(); doc.save(p); doc.close()
        return p
    monkeypatch.setattr(render, "build_pdf", build_gia)
    monkeypatch.setattr(checks, "scan_pdf", lambda p: checklist)
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in dict(cv0=copy.deepcopy(FIXTURE), goc=b"", ten_goc="x.docx", project=project,
                     position="Kế toán trưởng", photo=None, auto_build=True, chat=[]).items():
        at.session_state[k] = v
    at.run()
    for c in at.checkbox:
        c.check()
    at.run()
    return at


def test_loi3_khoa_tai_khi_pdf_con_pii(monkeypatch):
    ban = [{"ma": "pii", "muc": "Không còn SĐT...", "ok": False, "chi_tiet": "Số điện thoại: 0909123456"}]
    at = _app_co_pdf(monkeypatch, ban)
    assert not at.exception
    assert [d.proto.disabled for d in at.get("download_button")] == [True]


def test_loi3_cho_tai_khi_pdf_sach(monkeypatch):
    sach = [{"ma": "pii", "muc": "Không còn SĐT...", "ok": True, "chi_tiet": "Sạch"}]
    at = _app_co_pdf(monkeypatch, sach)
    assert [d.proto.disabled for d in at.get("download_button")] == [False]


def test_loi3_khoa_tai_khi_du_an_co_sdt(monkeypatch):
    sach = [{"ma": "pii", "muc": "Không còn SĐT...", "ok": True, "chi_tiet": "Sạch"}]
    at = _app_co_pdf(monkeypatch, sach, project="Message Coffee - LH 0909123456")
    assert [d.proto.disabled for d in at.get("download_button")] == [True]


# ===== Lỗi 4: chỉ coi là ngày sinh khi có ngữ cảnh "sinh" hoặc năm trong khoảng năm sinh =====
def _co_ngay_sinh(text):
    return "Ngày sinh đầy đủ" in {l for l, _ in scan_text(text)}


@pytest.mark.parametrize("text", ["Chứng chỉ CPA cấp ngày 15/06/2020", "01/03/2019 – 30/06/2021",
                                  "Hoàn thành dự án 12.11.2023"])
def test_loi4_khong_chan_ngay_thuong(text):
    assert not _co_ngay_sinh(text), text


@pytest.mark.parametrize("text", ["Ngày sinh: 12/05/1995", "Sinh ngày 03-08-2001", "DOB 7/9/2012",
                                  "Date of birth: 21.02.1988", "12/05/1995"])
def test_loi4_van_chan_ngay_sinh(text):
    assert _co_ngay_sinh(text), text


# ===== Lỗi 5: userinfo và link nhúng trong URL whitelist =====
@pytest.mark.parametrize("text", ["https://lighthuman.vn:x@facebook.com/abc", "https://lighthuman.vn:a@linkedin.com/in/x",
                                  "https://lighthuman.vn@evil.com/cv", "https://lighthuman.vn/r?u=facebook.com/nguyenvana",
                                  "https://lighthuman.vn/go?to=https://linkedin.com/in/x"])
def test_loi5_khong_lot_link_ung_vien(text):
    assert "Đường link" in {l for l, _ in scan_text(text)}, text


@pytest.mark.parametrize("text", ["https://lighthuman.vn/", "https://www.lighthuman.vn/tuyen-dung?id=12",
                                  "lighthuman.vn", "https://lighthuman.vn:443/viec-lam"])
def test_loi5_van_cho_phep_link_light_human(text):
    assert scan_text(text) == [], text


# ===== Lỗi 6: ô chứa '|' không được làm lệch cột =====
COT_CP = ["period", "title", "company", "current"]


def test_loi6_o_chua_gach_dung_khong_lech_cot():
    from ui.table_text import bang_sang_chu, chu_sang_bang
    rows = [{"period": "2019", "title": "KT", "company": "ABC | Chi nhánh HN", "current": True}]
    lai = chu_sang_bang(bang_sang_chu(rows, COT_CP), COT_CP)
    assert lai == [{"period": "2019", "title": "KT", "company": "ABC | Chi nhánh HN", "current": "x"}]
    # Ổn định qua nhiều lần rerun
    assert chu_sang_bang(bang_sang_chu(lai, COT_CP), COT_CP) == lai


def test_loi6_giu_hanh_vi_cu():
    from ui.table_text import chu_sang_bang
    # Dư cột (gõ '|' không thoát) -> gộp vào cột cuối như trước
    assert chu_sang_bang("Mong muốn | Full-time | HCM", ["label", "value"]) == \
        [{"label": "Mong muốn", "value": "Full-time | HCM"}]
    # Thiếu cột -> None; dòng trống bị bỏ
    assert chu_sang_bang("2020 | Kế toán\n\n", COT_CP) == \
        [{"period": "2020", "title": "Kế toán", "company": None, "current": None}]


# ===== Lỗi 7: giữ nguồn (original/generated) của ô số liệu qua form sửa =====
def test_loi7_giu_nguon_stats():
    from ui.table_text import bang_sang_chu, chu_sang_bang, giu_nguon_stats
    cu = [{"value": "18 năm", "label": "Kinh nghiệm", "source": "original"},
          {"value": "30%", "label": "Tăng doanh thu", "source": "generated"}]
    moi = chu_sang_bang(bang_sang_chu(cu, ["value", "label"]), ["value", "label"])
    assert [s["source"] for s in giu_nguon_stats(moi, cu)] == ["original", "generated"]
    # Xoá dòng đầu -> dòng còn lại vẫn là 'generated' (không lấy nhầm theo vị trí)
    moi = chu_sang_bang("30% | Tăng doanh thu", ["value", "label"])
    assert giu_nguon_stats(moi, cu) == [{"value": "30%", "label": "Tăng doanh thu", "source": "generated"}]
    # Sửa chú thích nhưng giữ số -> vẫn là ô do hệ thống lập
    moi = chu_sang_bang("30% | Tăng trưởng doanh thu", ["value", "label"])
    assert giu_nguon_stats(moi, cu)[0]["source"] == "generated"
    # Dòng mới hoàn toàn -> 'original'; ô trống -> chuỗi rỗng
    moi = chu_sang_bang("5 | ", ["value", "label"])
    assert giu_nguon_stats(moi, cu) == [{"value": "5", "label": "", "source": "original"}]


# ===== Lỗi 8: lỗi ở lần dựng PDF tự động phải hiện ngay trong khung chat =====
def test_loi8_loi_dung_tu_dong_hien_ngay(monkeypatch):
    from services.pdf import render
    from streamlit.testing.v1 import AppTest

    def hong(*a, **k):
        raise RuntimeError("Chromium không phản hồi")
    monkeypatch.setattr(render, "build_pdf", hong)
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in dict(cv0=copy.deepcopy(FIXTURE), goc=b"", ten_goc="x.docx", project="X",
                     position="Kế toán", photo=None, auto_build=True, chat=[]).items():
        at.session_state[k] = v
    at.run()
    assert not at.exception
    assert at.session_state["auto_build"] is False           # không dựng lại vô hạn
    assert any("Dựng PDF thất bại" in m.value and "Chromium" in m.value for m in at.markdown)


# ===== Lỗi 9: ảnh nền trong suốt phải ra nền trắng, không đen =====
@pytest.mark.parametrize("mode", ["RGBA", "LA", "P"])
def test_loi9_anh_trong_suot_ra_nen_trang(mode):
    import io
    from PIL import Image
    from services.pdf.render import crop_portrait
    im = Image.new("RGBA", (290, 380), (0, 0, 0, 0))           # nền trong suốt
    im.paste((200, 30, 30, 255), (100, 100, 190, 280))          # "người" ở giữa
    if mode == "LA":
        im = im.convert("LA")
    elif mode == "P":
        im = im.convert("P")
        im.info["transparency"] = im.getpixel((0, 0))
    b = io.BytesIO()
    im.save(b, "PNG")
    out = Image.open(io.BytesIO(crop_portrait(b.getvalue()))).convert("RGB")
    goc = out.getpixel((2, 2))
    assert min(goc) > 240, f"{mode}: góc ảnh là {goc}, phải là nền trắng"


# ===== Lỗi 10: header và PDF dùng chung một hàm cắt logo =====
def test_loi10_cat_logo_dung_chung(tmp_path):
    from PIL import Image
    from services.pdf.render import cat_logo, prepare_logo
    src = tmp_path / "logo.png"
    im = Image.new("RGBA", (1000, 600), (0, 0, 0, 0))
    im.paste((20, 40, 90, 255), (200, 150, 800, 390))          # logo 600x240 giữa viền trong suốt
    im.save(src)
    nho = cat_logo(src, 300)
    assert nho.size == (300, 120) and nho.getbbox() == (0, 0, 300, 120)
    dst = tmp_path / "out.png"
    prepare_logo(src, dst)
    with Image.open(dst) as ra:                                 # Q3: đóng file
        assert ra.size == cat_logo(src, 1200).size == (1200, 480)


def test_loi10_app_khong_tu_cat_logo():
    code = Path(APP).read_text(encoding="utf-8")
    assert "cat_logo(" in code and "getbbox" not in code


# ===== Ảnh chân dung: lấy được từ PDF (ảnh vuông/tròn), DOCX, ảnh CV, PDF scan =====
def _png(w, h, mau=(200, 30, 30), nen=None):
    import io
    from PIL import Image
    im = Image.new("RGB", (w, h), nen or mau)
    if nen:                                   # ô màu ở giữa ảnh = "khuôn mặt"
        im.paste(mau, (w * 2 // 5, h * 2 // 5, w * 3 // 5, h * 3 // 5))
    b = io.BytesIO(); im.save(b, "PNG")
    return b.getvalue()


@pytest.fixture
def mat_gia(monkeypatch):
    """Giả lập nhận diện khuôn mặt: điểm giữa ảnh màu đỏ => có mặt ở giữa ảnh."""
    from services.pdf import render

    def tim(im):
        r, g, b = im.convert("RGB").getpixel((im.width // 2, im.height // 2))
        if r > 150 and g < 80 and b < 80:
            return (im.width * 2 // 5, im.height * 2 // 5, im.width // 5, im.height // 5)
        return None
    monkeypatch.setattr(render, "_tim_mat", tim)


def _pdf(anh: list[tuple[bytes, tuple]]) -> bytes:
    import pymupdf as fitz
    doc = fitz.open(); page = doc.new_page()          # A4: 595 x 842 pt
    page.insert_text((300, 100), "NGUYEN VAN A - Ke toan")
    for data, rect in anh:
        page.insert_image(fitz.Rect(*rect), stream=data)
    out = doc.tobytes(); doc.close()
    return out


def _kich_thuoc(jpeg):
    import io
    from PIL import Image
    return Image.open(io.BytesIO(jpeg)).size


def test_anh_pdf_vuong_hoac_tron_van_lay(mat_gia):
    from services.pdf.render import extract_photo_from_pdf
    # Avatar vuông 400x400 hiển thị 100x100pt (kiểu Canva/TopCV) -> trước đây bị loại vì không "dọc"
    ra = extract_photo_from_pdf(_pdf([(_png(400, 400, nen=(240, 240, 240)), (40, 40, 140, 140))]))
    assert ra is not None
    w, h = _kich_thuoc(ra)
    assert abs(w / h - 29 / 38) < 0.02


def test_anh_pdf_bo_qua_icon_logo_va_anh_nen(mat_gia):
    from services.pdf.render import extract_photo_from_pdf
    icon = (_png(200, 200, nen=(240, 240, 240)), (40, 40, 60, 60))          # icon nhỏ 20pt
    logo = (_png(400, 400, mau=(20, 40, 90)), (400, 40, 500, 140))          # vuông, không có mặt
    assert extract_photo_from_pdf(_pdf([icon, logo])) is None


def test_anh_pdf_scan_tim_mat_tren_trang(mat_gia):
    from services.pdf.render import extract_photo_from_pdf
    # PDF scan: cả trang là 1 ảnh, "mặt" nằm giữa trang
    scan = (_png(1240, 1754, nen=(250, 250, 250)), (0, 0, 595, 842))
    assert extract_photo_from_pdf(_pdf([scan])) is not None


def test_anh_tu_docx(mat_gia, tmp_path):
    import io
    import docx
    from services.pdf.render import extract_photo
    d = docx.Document(); d.add_paragraph("NGUYEN VAN A")
    d.add_picture(io.BytesIO(_png(300, 400, nen=(235, 235, 235))))
    b = io.BytesIO(); d.save(b)
    assert extract_photo(b.getvalue(), "cv.docx") is not None


def test_anh_tu_cv_dang_anh(mat_gia):
    from services.pdf.render import extract_photo
    assert extract_photo(_png(1240, 1754, nen=(250, 250, 250)), "cv.jpg") is not None
    assert extract_photo(_png(1240, 1754, mau=(250, 250, 250)), "cv.png") is None   # không có mặt


def test_extract_photo_file_hong_tra_none():
    from services.pdf.render import extract_photo
    for ten in ("a.pdf", "a.docx", "a.png", "a.txt"):
        assert extract_photo(b"khong phai file that", ten) is None


def test_khung_quanh_mat_dung_ti_le_va_chua_mat():
    from services.pdf.render import khung_quanh_mat
    for kt, mat in [((1240, 1754), (560, 300, 120, 120)), ((300, 400), (60, 80, 180, 180)), ((800, 600), (0, 0, 100, 100))]:
        l, t, r, b = khung_quanh_mat(kt, mat)
        assert 0 <= l < r <= kt[0] and 0 <= t < b <= kt[1]
        assert abs((r - l) / (b - t) - 29 / 38) < 0.02
        x, y, w, h = mat
        assert l <= x + w / 2 <= r and t <= y + h / 2 <= b


def _avatar_tron(d=400, nen=(240, 240, 240)):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (d, d), nen)
    im.paste((200, 30, 30), (d * 2 // 5, d * 2 // 5, d * 3 // 5, d * 3 // 5))
    im = im.convert("RGBA")
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d - 1, d - 1), fill=255)
    im.putalpha(m)
    return im


def test_avatar_tron_khong_lo_goc(monkeypatch):
    """Avatar tròn: cắt khung 29:38 nằm gọn trong hình tròn -> 4 góc là nội dung ảnh, không đen/trắng."""
    import io
    from services.pdf import render
    # Mặt to như ảnh thật (~42% bề rộng avatar) -> khung quanh mặt sẽ chạm tới các góc
    monkeypatch.setattr(render, "_tim_mat", lambda im: (int(im.width * .29), int(im.height * .25), int(im.width * .42), int(im.height * .42)))
    from PIL import Image
    from services.pdf.render import crop_portrait, extract_photo_from_pdf
    b = io.BytesIO(); _avatar_tron().save(b, "PNG")
    for ra in (crop_portrait(b.getvalue()),
               extract_photo_from_pdf(_pdf([(b.getvalue(), (40, 40, 150, 150))]))):
        out = Image.open(io.BytesIO(ra)).convert("RGB")
        assert abs(out.width / out.height - 29 / 38) < 0.02
        for xy in [(1, 1), (out.width - 2, 1), (1, out.height - 2), (out.width - 2, out.height - 2)]:
            assert 200 < min(out.getpixel(xy)) and max(out.getpixel(xy)) < 250, (xy, out.getpixel(xy))


def test_app_lay_anh_cho_moi_loai_file(monkeypatch):
    """App gọi extract_photo cho mọi loại file (không chỉ PDF) và báo trong chat."""
    from services.ai import extract
    from services.pdf import render
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr(extract, "extract_cv", lambda *a, **k: copy.deepcopy(FIXTURE))
    monkeypatch.setattr(render, "extract_photo", lambda data, ten: b"ANH" if ten.endswith(".docx") else None)
    monkeypatch.setattr(render, "build_pdf", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bỏ qua")))
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["pending"] = {"data": b"x", "ten": "cv.docx", "project": "X", "position": ""}
    at.run()
    assert at.session_state["photo"] == b"ANH"
    assert any("Đã lấy từ CV gốc" in m.value for m in at.markdown)
