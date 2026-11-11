"""Form sửa hồ sơ trong tab "Chỉnh sửa nội dung" (Q2: tách theo từng loại mục, giảm lồng nhau).

Mỗi hàm _edit_* vẽ ô nhập cho một phần và trả lại dữ liệu đã sửa. Key của widget giữ nguyên như trước khi
tách file (vd '0-s3j1r0m') -> nội dung đang gõ không bị mất và test AppTest vẫn tìm đúng ô.
Phần nào bộ trích xuất cảnh báo hoặc có độ tin cậy thấp được gắn nhãn "Cần xem" (dữ liệu `review` ngoài schema).
"""
import copy
import logging
from typing import Callable

import streamlit as st

from ui.table_text import rows_to_text, text_to_rows, split_lines, keep_stat_sources
from infra.settings import IMAGE_EXTENSIONS, uploader_types
from core.pipeline import is_truthy
from services.extraction.base import ExtractionError, check_file
from infra.logging_setup import mask_filename
from services.pdf.render import crop_portrait
from ui.components import alert
from services.extraction import base as extraction

log = logging.getLogger("app")
META_COLUMNS = ["Nhãn (để trống = dòng nghiêng)", "Nội dung"]
STAT_LABEL_MAX_LEN = 35       # ô số liệu: chú thích dài hơn có thể tràn ô (mục 4 SKILL.md)
MAX_STATS = 4


# Ô bảng dạng chữ (cột ngăn bằng '|')
def table_input(rows: list[dict], columns: list[str], key: str, column_labels: list[str]) -> list[dict]:
    """Bảng dạng chữ: mỗi dòng 1 mục, các cột cách nhau bằng dấu '|'.

    (Không dùng st.data_editor vì nó cần pandas/pyarrow — bị Windows chặn trên một số máy.)
    Cột đúng/sai (vd 'Hiện tại') ghi 'x' nếu đúng, để trống nếu sai.
    """
    text = rows_to_text(rows, columns)
    edited_text = st.text_area(f"Mỗi dòng 1 mục · {' | '.join(column_labels)}", text, key=key,
                      height=max(80, 32 * (len(rows) + 1)))
    return text_to_rows(edited_text, columns)


# Ô nhiều dòng -> danh sách
def _lines_input(label: str, xs: list[str], key: str, height: int | None = None) -> list[str]:
    """Ô nhiều dòng -> danh sách (mỗi dòng 1 mục)."""
    kw = {"height": height} if height else {}
    return split_lines(st.text_area(label, "\n".join(xs), key=key, **kw))


# Sửa dòng phụ
def _edit_meta(rows: list[dict], key: str) -> list[dict]:
    meta = table_input(rows, ["label", "text"], key, META_COLUMNS)
    for m in meta:
        m["text"] = m.get("text") or ""
    return meta


# Sửa các nhóm gạch đầu dòng
def _edit_groups(groups: list[dict], key: str, bullet_label: str, height: int) -> None:
    """Sửa tại chỗ tiêu đề (nếu có) + gạch đầu dòng của từng nhóm việc."""
    for gi, g in enumerate(groups):
        if g.get("title") is not None:
            g["title"] = st.text_input("Nhóm việc", g["title"], key=f"{key}g{gi}t") or None
        g["bullets"] = _lines_input(bullet_label, g["bullets"], f"{key}g{gi}b", height)


# ----- Từng loại mục -----
# Mục dạng đoạn văn
def _edit_text(sec: dict, sk: str) -> None:
    sec["paragraphs"] = _lines_input("Đoạn văn (mỗi dòng 1 đoạn)", sec["paragraphs"], f"{sk}p", 150)


# Mục dạng gạch đầu dòng
def _edit_bullets(sec: dict, sk: str) -> None:
    sec["bullets"] = _lines_input("Gạch đầu dòng (mỗi dòng 1 ý)", sec["bullets"], f"{sk}b", 200)


# Mục dạng thẻ
def _edit_tags(sec: dict, sk: str) -> None:
    sec["tags"] = _lines_input("Thẻ (mỗi dòng 1 thẻ)", sec["tags"], f"{sk}tg")


# Mục dạng thẻ năng lực
def _edit_cards(sec: dict, sk: str) -> None:
    for ci, c in enumerate(sec["cards"]):
        c["title"] = st.text_input(f"Thẻ {ci + 1} – tên", c["title"], key=f"{sk}c{ci}t")
        c["items"] = _lines_input(f"Thẻ {ci + 1} – nội dung", c["items"], f"{sk}c{ci}i")


# Mục lộ trình nghề nghiệp
def _edit_career_path(sec: dict, sk: str) -> None:
    sec["career_path"] = table_input(sec["career_path"], ["period", "title", "company", "current"], f"{sk}cp",
                              ["Thời gian", "Chức danh", "Công ty", "Hiện tại (x)"])
    for r in sec["career_path"]:
        r["current"] = is_truthy(r.get("current"))
        for f in ("period", "title", "company"):
            r[f] = r.get(f) or ""


# Mục học vấn
def _edit_education(sec: dict, sk: str) -> None:
    sec["education"] = table_input(sec["education"], ["title", "detail", "period"], f"{sk}ed",
                            ["Văn bằng", "Trường/nơi cấp", "Năm"])
    for r in sec["education"]:
        r["title"] = r.get("title") or ""


# Mục người tham chiếu
def _edit_references(sec: dict, sk: str) -> None:
    sec["references"] = table_input(sec["references"], ["name", "title", "company"], f"{sk}rf",
                             ["Họ tên", "Chức danh", "Công ty"])
    for r in sec["references"]:
        r["name"] = r.get("name") or ""


# Một vị trí con
def _edit_sub_role(r: dict, rk: str, number: int) -> None:
    r["name"] = st.text_input(f"Vị trí con {number}", r["name"], key=f"{rk}n")
    r["period"] = st.text_input("Thời gian", r.get("period") or "", key=f"{rk}p") or None
    # Q1: dòng phụ + tiêu đề nhóm của vị trí con cũng phải sửa được — scan_pii quét cả các trường này,
    # thiếu ô sửa thì lỗi ở đây sẽ khoá nút tải mà không cách nào gỡ.
    st.caption("Dòng phụ của vị trí con (label để trống = dòng nghiêng)")
    r["meta"] = _edit_meta(r["meta"], f"{rk}m")
    _edit_groups(r["groups"], rk, "Gạch đầu dòng", 150)


# Một công việc
def _edit_job(j: dict, jk: str, number: int) -> None:
    st.markdown(f"**Công việc {number}**")
    c1, c2 = st.columns([3, 1])
    j["company"] = c1.text_input("Công ty", j["company"], key=f"{jk}c")
    j["period"] = c2.text_input("Thời gian", j.get("period") or "", key=f"{jk}p") or None
    j["role"] = st.text_input("Chức danh", j.get("role") or "", key=f"{jk}r") or None
    st.caption("Dòng phụ (label để trống = dòng nghiêng)")
    j["meta"] = _edit_meta(j["meta"], f"{jk}m")
    _edit_groups(j["groups"], jk, "Gạch đầu dòng (mỗi dòng 1 ý)", 180)
    for ri, r in enumerate(j["sub_roles"]):
        _edit_sub_role(r, f"{jk}r{ri}", ri + 1)
    st.divider()


# Mục kinh nghiệm làm việc
def _edit_experience(sec: dict, sk: str) -> None:
    for ji, j in enumerate(sec["jobs"]):
        _edit_job(j, f"{sk}j{ji}", ji + 1)


EDITORS_BY_TYPE: dict[str, Callable[[dict, str], None]] = {
    "text": _edit_text, "bullets": _edit_bullets, "tags": _edit_tags, "cards": _edit_cards,
    "career_path": _edit_career_path, "education": _edit_education, "references": _edit_references,
    "experience": _edit_experience,
}


# ----- Các phần của form -----
# Thông tin chung
def _edit_general_info(cv: dict, k: str, review: dict | None = None) -> None:
    st.markdown("#### Thông tin chung")
    _review_badge(review, "full_name", "target_title", "birth_year", "gender", "facts", "expected_salary")
    c1, c2 = st.columns(2)
    cv["full_name"] = c1.text_input("Họ và tên", cv["full_name"], key=f"{k}name")
    cv["target_title"] = c2.text_input("Chức danh", cv.get("target_title") or "", key=f"{k}title") or None
    c1, c2 = st.columns(2)
    year = c1.text_input("Năm sinh", str(cv.get("birth_year") or ""), key=f"{k}birth")
    cv["birth_year"] = int(year) if year.strip().isdigit() else None
    cv["gender"] = c2.text_input("Giới tính", cv.get("gender") or "", key=f"{k}gender") or None
    st.caption("Thông tin nhanh khác (vd: Mong muốn)")
    cv["facts"] = [{"label": r["label"] or "", "value": r["value"]}
                   for r in table_input(cv["facts"], ["label", "value"], f"{k}facts", ["Nhãn", "Nội dung"])
                   if r["value"]]   # dòng không có nội dung -> bỏ, tránh in chữ 'None' ra PDF


# Hàng ô số liệu
def _edit_stats(cv: dict, k: str, review: dict | None = None) -> None:
    st.markdown("#### Hàng ô số liệu (tối đa 4)")
    _review_badge(review, "stats")
    new_stats = table_input(cv["stats"], ["value", "label"], f"{k}stats", ["Số liệu", "Chú thích"])[:MAX_STATS]
    cv["stats"] = keep_stat_sources(new_stats, cv["stats"])    # giữ cờ original/generated của bộ trích xuất
    for s in cv["stats"]:
        if len(s["label"]) > STAT_LABEL_MAX_LEN:
            st.warning(f"Chú thích '{s['label']}' dài hơn {STAT_LABEL_MAX_LEN} ký tự, có thể tràn ô.")


# Nhãn "Cần xem" cho một nhóm trường (cảnh báo của bộ trích xuất / độ tin cậy thấp); trả True nếu có
def _review_badge(review: dict | None, *paths: str) -> bool:
    msgs = extraction.review_messages(review, paths)
    if msgs:
        st.caption(":orange-badge[Cần xem] " + " · ".join(msgs))
    return bool(msgs)


# Toàn bộ form sửa hồ sơ
def edit_profile(cv: dict, k: str, review: dict | None = None) -> dict:
    """Vẽ form, trả BẢN SAO hồ sơ đã sửa; `review` (kênh riêng của bộ trích xuất) gắn nhãn "Cần xem"."""
    cv = copy.deepcopy(cv)
    _edit_general_info(cv, k, review)
    _edit_stats(cv, k, review)
    st.markdown("#### Các mục nội dung")
    for i, sec in enumerate(cv["sections"]):
        sk = f"{k}s{i}"
        flag = "Cần xem · " if extraction.review_messages(review, (f"sections[{i}]",)) else ""
        with st.expander(f"{flag}{i + 1}. {sec['title']}  ·  ({sec['type']})"):
            _review_badge(review, f"sections[{i}]")
            sec["title"] = st.text_input("Tiêu đề mục", sec["title"], key=f"{sk}t")
            EDITORS_BY_TYPE[sec["type"]](sec, sk)
    return cv


# Xem / thay / bỏ ảnh chân dung
def edit_portrait(ss) -> None:
    """Ảnh chân dung: xem, thay (cắt 29:38) hoặc bỏ. Ghi thẳng vào session state `ss`."""
    st.markdown("#### Ảnh chân dung")
    c1, c2 = st.columns([1, 4])
    with c1:
        if ss.photo:
            st.image(ss.photo, width=96)
        else:
            st.caption("Không có ảnh")
    with c2:
        up = st.file_uploader("Thay ảnh (không bắt buộc)", type=uploader_types(IMAGE_EXTENSIONS),
                              key=f"{ss.run}photo{ss.photo_ver}")
        if up:
            photo_id = getattr(up, "file_id", None) or f"{up.name}-{up.size}"
            if ss.get("processed_photo_id") != photo_id:      # chỉ cắt 1 lần cho mỗi file mới
                try:
                    check_file(up.getvalue(), up.name)   # S7
                    ss.photo = crop_portrait(up.getvalue())
                    ss.processed_photo_id = photo_id
                    st.rerun()
                except ExtractionError as e:
                    st.markdown(alert("err", str(e)), unsafe_allow_html=True)
                except Exception:
                    log.exception("Không đọc được ảnh chân dung tải lên %s", mask_filename(up.name))
                    st.markdown(alert("err", "Không đọc được file ảnh này, hãy thử ảnh khác."),
                                unsafe_allow_html=True)
        if ss.photo and st.button("Bỏ ảnh", icon=":material/close:", type="secondary"):
            ss.photo = None
            ss.photo_ver += 1          # đổi key -> ô tải ảnh được làm trống, ảnh không quay lại
            ss.processed_photo_id = None
            st.rerun()
