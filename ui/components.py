"""Thành phần giao diện dạng HTML (A1) — hàm THUẦN: nhận dữ liệu, trả chuỗi HTML, không gọi Streamlit.

Mọi dữ liệu đến từ CV phải đi qua E() (html.escape) trước khi ghép vào HTML.
CSS của các thành phần nằm ở ui/styles.css, token ở tokens.py — xem docs/design-system.md.
"""
import html
from pathlib import Path

from infra.tokens import css_vars

ICON_FILE = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 '
             '2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>')

E = html.escape


def css_trang() -> str:
    """Khối <style> của web app: biến token (tokens.py) + ui/styles.css."""
    css = (Path(__file__).parent / "styles.css").read_text(encoding="utf-8")
    return "<style>\n" + css_vars("web") + "\n" + css + "</style>\n"


def _ds(xs: list[str]) -> str:
    if not xs:
        return '<div class="none">Không có</div>'
    return "<ul>" + "".join(f"<li>{E(x)}</li>" for x in xs) + "</ul>"


def _sec(nhan: str, than: str, dem: int | None = None) -> str:
    phu = f"<i>{dem}</i>" if dem is not None else ""
    return f'<div class="lh-sec"><div class="lb"><span>{nhan}</span>{phu}</div>{than}</div>'


def ve_tin(m: dict) -> str:
    if m["role"] == "user" and m.get("kind", "text") == "file":
        than = (f'<div class="lh-file">{ICON_FILE}<div><div class="fn">{E(m["ten"])}</div>'
                f'<div class="fm">Dự án: {E(m["project"] or "—")} · Vị trí: {E(m["position"] or "theo CV")}</div></div></div>')
        return f'<div class="lh-msg me"><div class="who">Bạn</div><div class="bub">{than}</div></div>'
    if m.get("kind", "text") == "notes":
        n = m["notes"]
        than = (f'<b>Đã đọc xong CV của {E(m["name"])}.</b> Bản PDF hiển thị ở khung bên phải.'
                + _sec("Đã bỏ khỏi CV", _ds(n["removed"]), len(n["removed"]))
                + _sec("Lương mong muốn", f'<span class="lh-sal">{E(m["salary"] or "CV không ghi")}</span>'
                       '<div class="none">Không đưa vào PDF — dùng khi trao đổi với khách.</div>')
                + _sec("Hệ thống tự lập / điều chỉnh", _ds(n["self_created"] + n["other"]),
                       len(n["self_created"] + n["other"]))
                + _sec("Lưu ý tuyển dụng", _ds(n["recruiting_flags"]), len(n["recruiting_flags"]))
                + ("" if "co_anh" not in m else _sec(
                    "Ảnh chân dung",
                    '<div class="none">Đã lấy từ CV gốc và đưa vào PDF.</div>' if m["co_anh"] else
                    '<div class="none">Không tìm thấy ảnh trong CV gốc. Có thể thêm ở tab '
                    'Chỉnh sửa nội dung.</div>')))
        return f'<div class="lh-msg bot"><div class="who">Trợ lý Light Human</div><div class="bub">{than}</div></div>'
    lop = "bot err" if m.get("kind", "text") == "error" else ("me" if m["role"] == "user" else "bot")
    ai = "Bạn" if m["role"] == "user" else "Trợ lý Light Human"
    # Q4: "html" = đoạn HTML do code dựng sẵn và đã an toàn (qua các hàm tin_* bên dưới);
    #     "text" = chữ thường, LUÔN được escape -> dữ liệu từ CV/lỗi không thể chèn thẻ HTML.
    than = m["html"] if "html" in m else E(m.get("text", ""))
    return f'<div class="lh-msg {lop}"><div class="who">{ai}</div><div class="bub">{than}</div></div>'


# ----- Nội dung tin nhắn dựng sẵn (trả HTML an toàn, dùng cho trường "html" của tin nhắn) -----
LOI_CHAO_HTML = ("Chào chị. Gửi giúp em <b>CV gốc</b> (PDF, ảnh hoặc DOCX) kèm <b>tên dự án</b> và "
                 "<b>vị trí</b> nếu có. Em sẽ làm lại hồ sơ theo chuẩn Light Human và hiển thị bản PDF "
                 "ở khung bên phải.")

TIN_DANG_GO = ('<div class="lh-msg bot"><div class="who">Trợ lý Light Human</div><div class="bub">'
               '<span class="lh-typing"><i></i><i></i><i></i></span></div></div>')

NHAN_TIN_TOM_TAT = '<div class="lh-msg bot tight"><div class="who">Tin nhắn tóm tắt</div></div>'


def tin_loi(tieu_de: str, chi_tiet: str = "") -> str:
    """'<b>Tiêu đề.</b> chi tiết' — cả hai được escape."""
    return f"<b>{E(tieu_de)}</b> {E(chi_tiet)}".rstrip()


def tin_da_xuat(ten_file: str) -> str:
    return (f'Đã xuất <span class="lh-sal">{E(ten_file)}</span>. Bản sao lưu trong '
            '<span class="lh-sal">data/output</span>.')


def tin_so_loi(so_loi: int) -> str:
    return f"Hồ sơ còn <b>{int(so_loi)} lỗi</b> cần sửa trước khi tải PDF. Chi tiết ở khung bên phải."


# ----- Khung PDF -----
def alert(kind: str, tieu_de: str, items: list[str] | None = None) -> str:
    """Hộp cảnh báo. `tieu_de` là chữ thường (được escape); `items` là HTML an toàn (dùng các hàm ds_* bên dưới)."""
    ds = "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else ""
    return f'<div class="lh-alert {kind}"><div class="t">{E(tieu_de)}</div>{ds}</div>'


def ds_loi_cau_truc(loi: list[str]) -> list[str]:
    return [E(x) for x in loi]


def ds_vi_pham(vi_pham: list[dict]) -> list[str]:
    return [f"{E(v['loai'])} <code>{E(v['gia_tri'])}</code> tại <code>{E(v['field'])}</code>" for v in vi_pham]


def ds_pii_trong_pdf(checklist: list[dict] | None) -> list[str] | None:
    return [E(r["chi_tiet"]) for r in (checklist or []) if r.get("ma") == "pii" and not r["ok"]] or None


def canh_bao_html(loi_cau_truc: list[str], vi_pham: list[dict], cu: bool, pdf_ban: bool,
                  checklist: list[dict] | None) -> str:
    """Các hộp cảnh báo phía trên khung PDF, theo đúng thứ tự cũ: cấu trúc → PII → PDF cũ → PII trong PDF."""
    out = []
    if loi_cau_truc:
        out.append(alert("err", "Hồ sơ chưa hợp lệ — sửa ở tab Chỉnh sửa nội dung", ds_loi_cau_truc(loi_cau_truc)))
    if vi_pham:
        out.append(alert("err", "Còn thông tin nhạy cảm — phải sửa trước khi tải PDF", ds_vi_pham(vi_pham)))
    if cu and not loi_cau_truc:
        out.append(alert("warn", "Nội dung đã thay đổi so với bản PDF đang hiển thị",
                         ["Bấm Cập nhật PDF để dựng lại trước khi tải."]))
    if pdf_ban:
        out.append(alert("err", "Bản PDF vẫn còn thông tin liên hệ của ứng viên — phải sửa trước khi tải",
                         ds_pii_trong_pdf(checklist)))
    return "".join(out)


def thanh_trang_thai(ten_file: str, phu: str, pill_loai: str, pill_chu: str) -> str:
    """Thanh trên cùng tab Bản PDF: icon + tên file + 'A4 · n trang' + nhãn trạng thái."""
    return (f'<div class="lh-bar">{ICON_FILE}<div class="txt"><div class="fn">{E(ten_file)}</div>'
            f'<div class="fm">{E(phu)}</div></div><span class="lh-pill {E(pill_loai)}">{E(pill_chu)}</span></div>')


def checklist_html(checklist: list[dict]) -> str:
    return "".join(
        f'<div class="lh-check{"" if r["ok"] else " no"}"><span class="m"></span><span>{E(r["muc"])}</span>'
        + (f'<small>{E(r["chi_tiet"])}</small>' if r["chi_tiet"] else "") + "</div>"
        for r in checklist)


def tieu_de_panel(chu: str) -> str:
    return f'<div class="lh-ph"><div class="h">{E(chu)}</div></div>'


def header_html(logo_b64: str, ten_cong_ty: str = "Light Human") -> str:
    return (f'<div class="lh-top"><img src="data:image/png;base64,{logo_b64}" alt="{E(ten_cong_ty)}">'
            '<div class="id"><div class="sep"></div>'
            '<div class="name">Hồ sơ ứng viên<small>Làm lại CV theo chuẩn Light Human để gửi khách hàng</small></div>'
            '</div></div>')


def stage(busy: bool, buoc: int = 0, so_cho: int = 0) -> str:
    """Khung trang A4: trạng thái trống (busy=False) hoặc đang xử lý (busy=True, buoc 0..2).

    so_cho > 0: đang xếp hàng chờ tới lượt dựng PDF (vị trí trong hàng).
    """
    r = lambda w: f'<div class="r" style="width:{w}%"></div>'
    sheet = ('<div class="lh-sheet"><div class="hd"><div class="r" style="width:30%"></div>'
             '<div class="r" style="width:22%"></div></div><div class="r ttl"></div><div class="r acc"></div>'
             + r(70) + '<div class="gap"></div>' + r(40) + r(96) + r(90) + r(94) + r(62)
             + '<div class="gap"></div>' + r(46) + r(92) + r(88) + r(70) + "</div>")
    buoc_ds = ["Đọc CV gốc và trích xuất nội dung", "Bỏ thông tin liên hệ, chuẩn hoá theo mẫu",
               "Dựng PDF và kiểm tra chất lượng"]
    if busy:
        steps = "".join(f'<div class="{"done" if i < buoc else "on" if i == buoc else ""}">{s}</div>'
                        for i, s in enumerate(buoc_ds))
        txt = ('<h4>Đang làm hồ sơ</h4><p>Thường mất 30–90 giây. Có thể tiếp tục xem lại tin nhắn bên trái '
               'trong lúc chờ.</p>')
        if so_cho > 0:
            txt = (f'<h4>Đang xếp hàng dựng PDF</h4><p>Đang có nhiều hồ sơ được dựng cùng lúc — hồ sơ này đứng thứ '
                   f'<b>{int(so_cho)}</b> trong hàng. App sẽ tự dựng khi tới lượt, chị không cần bấm lại.</p>')
    else:
        steps = "".join(f"<div>{s}</div>" for s in
                        ["Đính kèm CV gốc ở khung bên trái", "Nhập tên dự án và vị trí (nếu có)",
                         "Duyệt bản PDF, sửa nếu cần, rồi tải về"])
        txt = ('<h4>Chưa có hồ sơ</h4><p>Bản PDF theo chuẩn Light Human sẽ hiển thị tại đây, kèm công cụ '
               'chỉnh sửa và đối chiếu với CV gốc.</p>')
    return (f'<div class="lh-stage{" lh-busy" if busy else ""}">{sheet}'
            f'<div class="txt">{txt}<div class="lh-steps">{steps}</div></div></div>')
