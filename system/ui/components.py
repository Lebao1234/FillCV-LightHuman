# Gói ui/: giao diện — thành phần HTML (components), form sửa hồ sơ (profile_form), CSS (styles.css).
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


# Khối <style> của web app
def page_css() -> str:
    """Khối <style> của web app: biến token (tokens.py) + ui/styles.css."""
    css = (Path(__file__).parent / "styles.css").read_text(encoding="utf-8")
    return "<style>\n" + css_vars("web") + "\n" + css + "</style>\n"


# Danh sách HTML (hoặc 'Không có')
def _list_html(xs: list[str]) -> str:
    if not xs:
        return '<div class="none">Không có</div>'
    return "<ul>" + "".join(f"<li>{E(x)}</li>" for x in xs) + "</ul>"


# Một mục trong tin nhắn ghi chú
def _section(label: str, body: str, count: int | None = None) -> str:
    aside = f"<i>{count}</i>" if count is not None else ""
    return f'<div class="lh-sec"><div class="lb"><span>{label}</span>{aside}</div>{body}</div>'


# Vẽ một tin nhắn chat
def render_message(m: dict) -> str:
    if m["role"] == "user" and m.get("kind", "text") == "file":
        body = (f'<div class="lh-file">{ICON_FILE}<div><div class="fn">{E(m["filename"])}</div>'
                f'<div class="fm">Dự án: {E(m["project"] or "—")} · Vị trí: {E(m["position"] or "theo CV")}</div></div></div>')
        return f'<div class="lh-msg me"><div class="who">Bạn</div><div class="bub">{body}</div></div>'
    if m.get("kind", "text") == "notes":
        n = m["notes"]
        body = (f'<b>Đã đọc xong CV của {E(m["name"])}.</b> Bản PDF hiển thị ở khung bên phải.'
                + _section("Đã bỏ khỏi CV", _list_html(n["removed"]), len(n["removed"]))
                + _section("Lương mong muốn", f'<span class="lh-sal">{E(m["salary"] or "CV không ghi")}</span>'
                       '<div class="none">Không đưa vào PDF — dùng khi trao đổi với khách.</div>')
                + _section("Hệ thống tự lập / điều chỉnh", _list_html(n["self_created"] + n["other"]),
                       len(n["self_created"] + n["other"]))
                + _section("Lưu ý tuyển dụng", _list_html(n["recruiting_flags"]), len(n["recruiting_flags"]))
                + ("" if not m.get("review") else _section(   # cảnh báo của bộ trích xuất (kênh riêng, ngoài schema)
                    "Cần xem lại khi duyệt", _list_html(m["review"]), len(m["review"])))
                + ("" if "has_photo" not in m else _section(
                    "Ảnh chân dung",
                    '<div class="none">Đã lấy từ CV gốc và đưa vào PDF.</div>' if m["has_photo"] else
                    '<div class="none">Không tìm thấy ảnh trong CV gốc. Có thể thêm ở tab '
                    'Chỉnh sửa nội dung.</div>')))
        return f'<div class="lh-msg bot"><div class="who">Trợ lý Light Human</div><div class="bub">{body}</div></div>'
    css_class = "bot err" if m.get("kind", "text") == "error" else ("me" if m["role"] == "user" else "bot")
    who = "Bạn" if m["role"] == "user" else "Trợ lý Light Human"
    # Q4: "html" = đoạn HTML do code dựng sẵn và đã an toàn (qua các hàm tin_* bên dưới);
    #     "text" = chữ thường, LUÔN được escape -> dữ liệu từ CV/lỗi không thể chèn thẻ HTML.
    body = m["html"] if "html" in m else E(m.get("text", ""))
    return f'<div class="lh-msg {css_class}"><div class="who">{who}</div><div class="bub">{body}</div></div>'


# ----- Nội dung tin nhắn dựng sẵn (trả HTML an toàn, dùng cho trường "html" của tin nhắn) -----
GREETING_HTML = ("Chào chị. Gửi giúp em <b>CV gốc</b> (PDF, ảnh hoặc DOCX) kèm <b>tên dự án</b> và "
                 "<b>vị trí</b> nếu có. Em sẽ làm lại hồ sơ theo chuẩn Light Human và hiển thị bản PDF "
                 "ở khung bên phải.")

TYPING_HTML = ('<div class="lh-msg bot"><div class="who">Trợ lý Light Human</div><div class="bub">'
               '<span class="lh-typing"><i></i><i></i><i></i></span></div></div>')

SUMMARY_LABEL_HTML = '<div class="lh-msg bot tight"><div class="who">Tin nhắn tóm tắt</div></div>'


# Tin báo lỗi
def error_message(title: str, detail: str = "") -> str:
    """'<b>Tiêu đề.</b> chi tiết' — cả hai được escape."""
    return f"<b>{E(title)}</b> {E(detail)}".rstrip()


# Tin báo đã xuất PDF
def exported_message(filename: str) -> str:
    return (f'Đã xuất <span class="lh-sal">{E(filename)}</span>. Bản sao lưu trong '
            '<span class="lh-sal">data/output</span>.')


# Tin báo số lỗi cần sửa
def error_count_message(error_count: int) -> str:
    return f"Hồ sơ còn <b>{int(error_count)} lỗi</b> cần sửa trước khi tải PDF. Chi tiết ở khung bên phải."


# ----- Khung PDF -----
# Hộp cảnh báo
def alert(kind: str, title: str, items: list[str] | None = None) -> str:
    """Hộp cảnh báo. `title` là chữ thường (được escape); `items` là HTML an toàn (dùng các hàm ds_* bên dưới)."""
    items_html = "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>" if items else ""
    return f'<div class="lh-alert {kind}"><div class="t">{E(title)}</div>{items_html}</div>'


# Dòng lỗi cấu trúc
def structure_error_items(errors: list[str]) -> list[str]:
    return [E(x) for x in errors]


# Dòng vi phạm thông tin nhạy cảm
def violation_items(violations: list[dict]) -> list[str]:
    return [f"{E(v['kind'])} <code>{E(v['value'])}</code> tại <code>{E(v['field'])}</code>" for v in violations]


# Dòng thông tin nhạy cảm còn trong PDF
def pdf_pii_items(checklist: list[dict] | None) -> list[str] | None:
    return [E(r["detail"]) for r in (checklist or []) if r.get("code") == "pii" and not r["ok"]] or None


# Các hộp cảnh báo trên khung PDF
def warnings_html(structure_errors: list[str], violations: list[dict], outdated: bool, pdf_dirty: bool,
                  checklist: list[dict] | None) -> str:
    """Các hộp cảnh báo phía trên khung PDF, theo đúng thứ tự cũ: cấu trúc → PII → PDF cũ → PII trong PDF."""
    out = []
    if structure_errors:
        out.append(alert("err", "Hồ sơ chưa hợp lệ — sửa ở tab Chỉnh sửa nội dung", structure_error_items(structure_errors)))
    if violations:
        out.append(alert("err", "Còn thông tin nhạy cảm — phải sửa trước khi tải PDF", violation_items(violations)))
    if outdated and not structure_errors:
        out.append(alert("warn", "Nội dung đã thay đổi so với bản PDF đang hiển thị",
                         ["Bấm Cập nhật PDF để dựng lại trước khi tải."]))
    if pdf_dirty:
        out.append(alert("err", "Bản PDF vẫn còn thông tin liên hệ của ứng viên — phải sửa trước khi tải",
                         pdf_pii_items(checklist)))
    return "".join(out)


# Thanh trạng thái tab Bản PDF
def status_bar(filename: str, aside: str, pill_kind: str, pill_text: str) -> str:
    """Thanh trên cùng tab Bản PDF: icon + tên file + 'A4 · n trang' + nhãn trạng thái."""
    return (f'<div class="lh-bar">{ICON_FILE}<div class="txt"><div class="fn">{E(filename)}</div>'
            f'<div class="fm">{E(aside)}</div></div><span class="lh-pill {E(pill_kind)}">{E(pill_text)}</span></div>')


# Danh sách checklist
def checklist_html(checklist: list[dict]) -> str:
    return "".join(
        f'<div class="lh-check{"" if r["ok"] else " no"}"><span class="m"></span><span>{E(r["item"])}</span>'
        + (f'<small>{E(r["detail"])}</small>' if r["detail"] else "") + "</div>"
        for r in checklist)


# Tiêu đề panel
def panel_title(text: str) -> str:
    return f'<div class="lh-ph"><div class="h">{E(text)}</div></div>'


# Header trang (logo + tên)
def header_html(logo_b64: str, company_name: str = "Light Human") -> str:
    return (f'<div class="lh-top"><img src="data:image/png;base64,{logo_b64}" alt="{E(company_name)}">'
            '<div class="id"><div class="sep"></div>'
            '<div class="name">Hồ sơ ứng viên<small>Làm lại CV theo chuẩn Light Human để gửi khách hàng</small></div>'
            '</div></div>')


# Khung trang A4: trống / đang xử lý / xếp hàng
def stage(busy: bool, step: int = 0, queue_pos: int = 0, labels: list[str] | None = None,
          queue_what: str = "dựng PDF") -> str:
    """Khung trang A4: trạng thái trống (busy=False) hoặc đang xử lý (busy=True, `step` = bước đang chạy).

    `labels`: các bước THẬT của lượt xử lý (pipeline.stage_labels()); bỏ trống -> 3 bước mặc định.
    queue_pos > 0: đang xếp hàng chờ tới lượt `queue_what` ("dựng PDF" | "đọc CV"), vị trí trong hàng.
    """
    r = lambda w: f'<div class="r" style="width:{w}%"></div>'
    sheet = ('<div class="lh-sheet"><div class="hd"><div class="r" style="width:30%"></div>'
             '<div class="r" style="width:22%"></div></div><div class="r ttl"></div><div class="r acc"></div>'
             + r(70) + '<div class="gap"></div>' + r(40) + r(96) + r(90) + r(94) + r(62)
             + '<div class="gap"></div>' + r(46) + r(92) + r(88) + r(70) + "</div>")
    step_labels = labels or ["Đọc CV gốc và trích xuất nội dung", "Bỏ thông tin liên hệ, chuẩn hoá theo mẫu",
                             "Dựng PDF và kiểm tra chất lượng"]
    if busy:
        steps = "".join(f'<div class="{"done" if i < step else "on" if i == step else ""}">{E(s)}</div>'
                        for i, s in enumerate(step_labels))
        txt = ('<h4>Đang làm hồ sơ</h4><p>Từng bước bên dưới là việc đang chạy thật. Có thể tiếp tục xem lại tin nhắn bên trái '
               'trong lúc chờ.</p>')
        if queue_pos > 0:
            txt = (f'<h4>Đang xếp hàng {E(queue_what)}</h4><p>Đang có nhiều hồ sơ được xử lý cùng lúc — hồ sơ này '
                   f'đứng thứ <b>{int(queue_pos)}</b> trong hàng. App sẽ tự {E(queue_what)} khi tới lượt, chị không '
                   'cần bấm lại.</p>')
    else:
        steps = "".join(f"<div>{s}</div>" for s in
                        ["Đính kèm CV gốc ở khung bên trái", "Nhập tên dự án và vị trí (nếu có)",
                         "Duyệt bản PDF, sửa nếu cần, rồi tải về"])
        txt = ('<h4>Chưa có hồ sơ</h4><p>Bản PDF theo chuẩn Light Human sẽ hiển thị tại đây, kèm công cụ '
               'chỉnh sửa và đối chiếu với CV gốc.</p>')
    return (f'<div class="lh-stage{" lh-busy" if busy else ""}">{sheet}'
            f'<div class="txt">{txt}<div class="lh-steps">{steps}</div></div></div>')
