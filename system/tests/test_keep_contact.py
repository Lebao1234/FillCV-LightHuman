"""Test lựa chọn "Giữ nguyên liên hệ" lúc bóc tách CV: mặc định cắt bỏ, chọn giữ thì thành dòng thông tin đầu hồ sơ."""
import pymupdf as fitz
import pytest

from core import pipeline
from services.privacy import checks


# Dựng PDF giả (dữ liệu giả) có khối liên hệ ở đầu CV
@pytest.fixture(scope="module")
def cv_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 60

    def put(text, size=10.5):
        nonlocal y
        page.insert_text((50, y), text, fontsize=size)
        y += size * 1.9

    put("NGUYEN VAN GIA", 26)
    put("Ke toan truong", 14)
    put("Dien thoai: 0912 345 678")
    put("Email: gia.nguyen@example.com")
    put("Dia chi: 12 Nguyen Trai, Quan 1, Ho Chi Minh")
    put("")
    put("KINH NGHIEM LAM VIEC", 15)
    put("CONG TY ABC", 12)
    put("01/2018 - Nay")
    put("Phu trach ke toan tong hop va lap bao cao tai chinh hang thang cho ban giam doc.")
    put("")
    put("HOC VAN", 15)
    put("Dai hoc Kinh te - Cu nhan Ke toan")
    data = doc.tobytes()
    doc.close()
    return data


# Gom mọi chuỗi trong hồ sơ để tìm thông tin liên hệ
def all_text(cv: dict) -> str:
    return " ".join(str(v) for v in checks_walk(cv))


# Duyệt mọi chuỗi (không quan tâm đường dẫn)
def checks_walk(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from checks_walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from checks_walk(v)
    elif isinstance(node, str):
        yield node


# Mặc định: cắt bỏ liên hệ như cũ
def test_default_strips_contact(cv_pdf):
    cv = pipeline.read_cv(cv_pdf, "a.pdf", "", "").cv
    text = all_text(cv)
    assert "0912" not in text and "example.com" not in text and "Nguyen Trai" not in text
    assert not any(f["label"] in {"Điện thoại", "Email", "Địa chỉ"} for f in cv["facts"])
    assert "Số điện thoại" in cv["model_notes"]["removed"]


# Chọn giữ: SĐT, email, địa chỉ thành dòng thông tin; không còn báo là "đã loại bỏ"
def test_keep_contact_adds_contact_facts(cv_pdf):
    cv = pipeline.read_cv(cv_pdf, "a.pdf", "", "", keep_contact=True).cv
    # CV giả gõ không dấu nên nhận là tiếng Anh -> nhãn "Phone"/"Address"; CV tiếng Việt thì "Điện thoại"/"Địa chỉ"
    facts = {f["label"]: f["value"] for f in cv["facts"]}
    assert "0912 345 678" in (facts.get("Điện thoại") or facts["Phone"])
    assert facts["Email"] == "gia.nguyen@example.com"
    assert "12 Nguyen Trai" in (facts.get("Địa chỉ") or facts["Address"])
    removed = cv["model_notes"]["removed"]
    assert "Số điện thoại" not in removed and "Email" not in removed and "Địa chỉ nhà" not in removed
    # Chỉ liên hệ được giữ: nội dung chính vẫn sạch bản sao thừa của SĐT/email
    body = all_text({"sections": cv["sections"]})
    assert "0912" not in body and "example.com" not in body
    # Kiểm tra PII ở chế độ giữ liên hệ không coi các dòng này là vi phạm, còn chế độ cắt thì có
    assert checks.scan_pii_export(cv, "", "", keep_contact=True) == []
    assert checks.scan_pii_export(cv, "", "", keep_contact=False) != []


# Khi mẫu CV gốc để dính các mục liên hệ trên 1 dòng với dấu chấm (•) hoặc nhãn Address
def test_inline_bullet_contacts_separated():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 60), "NGUYEN NGOC KIM NGAN", fontsize=24)
    page.insert_text((50, 90), "Cham soc khach hang", fontsize=14)
    page.insert_text(
        (50, 110),
        "Address: The Riverside Residences – Tan My ward • Ho Chi Minh, Vietnam • kngan.ng224@gmail.com • +84 3333 69580",
        fontsize=10,
    )
    page.insert_text((50, 150), "KINH NGHIEM LAM VIEC", fontsize=14)
    page.insert_text((50, 170), "CONCENTRIX MALAYSIA", fontsize=12)
    page.insert_text((50, 190), "Advisor II - Trust & Safety Associate", fontsize=10)
    data = doc.tobytes()
    doc.close()

    cv = pipeline.read_cv(data, "kim_ngan.pdf", "Concentrix", "Advisor", keep_contact=True).cv
    facts_dict = {f["label"]: f["value"] for f in cv["facts"]}

    # SĐT, Email và Địa chỉ phải được tách riêng thành từng dòng (xuống hàng), không bị dính làm một
    assert "Phone" in facts_dict or "Điện thoại" in facts_dict
    assert "Email" in facts_dict
    assert "Address" in facts_dict or "Địa chỉ" in facts_dict

    phone_val = facts_dict.get("Phone") or facts_dict.get("Điện thoại")
    assert "+84 3333 69580" in phone_val
    assert facts_dict["Email"] == "kngan.ng224@gmail.com"

    addr_val = facts_dict.get("Address") or facts_dict.get("Địa chỉ")
    assert "The Riverside Residences" in addr_val
    assert "kngan.ng224@gmail.com" not in addr_val
    assert "+84 3333 69580" not in addr_val

    # Kiểm tra render HTML sinh ra class fact-contact để xuống hàng
    from services.pdf import render
    html = render.render_html(cv, "Concentrix", "Candidate Profile", lang="en")
    assert "fact-contact" in html
    assert ".facts .fact-contact" in html
