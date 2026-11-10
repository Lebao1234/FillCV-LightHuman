"""Form sửa hồ sơ trong tab "Chỉnh sửa nội dung" (Q2: tách theo từng loại mục, giảm lồng nhau).

Mỗi hàm _sua_* vẽ ô nhập cho một phần và trả lại dữ liệu đã sửa. Key của widget giữ nguyên như trước khi
tách file (vd '0-s3j1r0m') -> nội dung đang gõ không bị mất và test AppTest vẫn tìm đúng ô.
"""
import copy
import logging
from typing import Callable

import streamlit as st

from ui.table_text import bang_sang_chu, chu_sang_bang, dong, giu_nguon_stats
from infra.settings import DUOI_ANH, loai_cho_uploader
from core.pipeline import la_dung
from services.ai.extract import ExtractError, kiem_tra_file
from infra.logging_setup import an_ten_file
from services.pdf.render import crop_portrait
from ui.components import alert

log = logging.getLogger("app")
COT_META = ["Nhãn (để trống = dòng nghiêng)", "Nội dung"]
CHU_THICH_TOI_DA = 35       # ô số liệu: chú thích dài hơn có thể tràn ô (mục 4 SKILL.md)
SO_O_SO_LIEU_TOI_DA = 4


def bang(rows: list[dict], cot: list[str], key: str, ten_cot: list[str]) -> list[dict]:
    """Bảng dạng chữ: mỗi dòng 1 mục, các cột cách nhau bằng dấu '|'.

    (Không dùng st.data_editor vì nó cần pandas/pyarrow — bị Windows chặn trên một số máy.)
    Cột đúng/sai (vd 'Hiện tại') ghi 'x' nếu đúng, để trống nếu sai.
    """
    text = bang_sang_chu(rows, cot)
    ra = st.text_area(f"Mỗi dòng 1 mục · {' | '.join(ten_cot)}", text, key=key,
                      height=max(80, 32 * (len(rows) + 1)))
    return chu_sang_bang(ra, cot)


def _o_dong(nhan: str, xs: list[str], key: str, height: int | None = None) -> list[str]:
    """Ô nhiều dòng -> danh sách (mỗi dòng 1 mục)."""
    kw = {"height": height} if height else {}
    return dong(st.text_area(nhan, "\n".join(xs), key=key, **kw))


def _sua_meta(rows: list[dict], key: str) -> list[dict]:
    meta = bang(rows, ["label", "text"], key, COT_META)
    for m in meta:
        m["text"] = m.get("text") or ""
    return meta


def _sua_nhom(groups: list[dict], key: str, nhan_gach: str, height: int) -> None:
    """Sửa tại chỗ tiêu đề (nếu có) + gạch đầu dòng của từng nhóm việc."""
    for gi, g in enumerate(groups):
        if g.get("title") is not None:
            g["title"] = st.text_input("Nhóm việc", g["title"], key=f"{key}g{gi}t") or None
        g["bullets"] = _o_dong(nhan_gach, g["bullets"], f"{key}g{gi}b", height)


# ----- Từng loại mục -----
def _sua_text(sec: dict, sk: str) -> None:
    sec["paragraphs"] = _o_dong("Đoạn văn (mỗi dòng 1 đoạn)", sec["paragraphs"], f"{sk}p", 150)


def _sua_bullets(sec: dict, sk: str) -> None:
    sec["bullets"] = _o_dong("Gạch đầu dòng (mỗi dòng 1 ý)", sec["bullets"], f"{sk}b", 200)


def _sua_tags(sec: dict, sk: str) -> None:
    sec["tags"] = _o_dong("Thẻ (mỗi dòng 1 thẻ)", sec["tags"], f"{sk}tg")


def _sua_cards(sec: dict, sk: str) -> None:
    for ci, c in enumerate(sec["cards"]):
        c["title"] = st.text_input(f"Thẻ {ci + 1} – tên", c["title"], key=f"{sk}c{ci}t")
        c["items"] = _o_dong(f"Thẻ {ci + 1} – nội dung", c["items"], f"{sk}c{ci}i")


def _sua_career_path(sec: dict, sk: str) -> None:
    sec["career_path"] = bang(sec["career_path"], ["period", "title", "company", "current"], f"{sk}cp",
                              ["Thời gian", "Chức danh", "Công ty", "Hiện tại (x)"])
    for r in sec["career_path"]:
        r["current"] = la_dung(r.get("current"))
        for f in ("period", "title", "company"):
            r[f] = r.get(f) or ""


def _sua_education(sec: dict, sk: str) -> None:
    sec["education"] = bang(sec["education"], ["title", "detail", "period"], f"{sk}ed",
                            ["Văn bằng", "Trường/nơi cấp", "Năm"])
    for r in sec["education"]:
        r["title"] = r.get("title") or ""


def _sua_references(sec: dict, sk: str) -> None:
    sec["references"] = bang(sec["references"], ["name", "title", "company"], f"{sk}rf",
                             ["Họ tên", "Chức danh", "Công ty"])
    for r in sec["references"]:
        r["name"] = r.get("name") or ""


def _sua_vi_tri_con(r: dict, rk: str, so: int) -> None:
    r["name"] = st.text_input(f"Vị trí con {so}", r["name"], key=f"{rk}n")
    r["period"] = st.text_input("Thời gian", r.get("period") or "", key=f"{rk}p") or None
    # Q1: dòng phụ + tiêu đề nhóm của vị trí con cũng phải sửa được — scan_pii quét cả các trường này,
    # thiếu ô sửa thì lỗi ở đây sẽ khoá nút tải mà không cách nào gỡ.
    st.caption("Dòng phụ của vị trí con (label để trống = dòng nghiêng)")
    r["meta"] = _sua_meta(r["meta"], f"{rk}m")
    _sua_nhom(r["groups"], rk, "Gạch đầu dòng", 150)


def _sua_cong_viec(j: dict, jk: str, so: int) -> None:
    st.markdown(f"**Công việc {so}**")
    c1, c2 = st.columns([3, 1])
    j["company"] = c1.text_input("Công ty", j["company"], key=f"{jk}c")
    j["period"] = c2.text_input("Thời gian", j.get("period") or "", key=f"{jk}p") or None
    j["role"] = st.text_input("Chức danh", j.get("role") or "", key=f"{jk}r") or None
    st.caption("Dòng phụ (label để trống = dòng nghiêng)")
    j["meta"] = _sua_meta(j["meta"], f"{jk}m")
    _sua_nhom(j["groups"], jk, "Gạch đầu dòng (mỗi dòng 1 ý)", 180)
    for ri, r in enumerate(j["sub_roles"]):
        _sua_vi_tri_con(r, f"{jk}r{ri}", ri + 1)
    st.divider()


def _sua_experience(sec: dict, sk: str) -> None:
    for ji, j in enumerate(sec["jobs"]):
        _sua_cong_viec(j, f"{sk}j{ji}", ji + 1)


SUA_THEO_LOAI: dict[str, Callable[[dict, str], None]] = {
    "text": _sua_text, "bullets": _sua_bullets, "tags": _sua_tags, "cards": _sua_cards,
    "career_path": _sua_career_path, "education": _sua_education, "references": _sua_references,
    "experience": _sua_experience,
}


# ----- Các phần của form -----
def _sua_thong_tin_chung(cv: dict, k: str) -> None:
    st.markdown("#### Thông tin chung")
    c1, c2 = st.columns(2)
    cv["full_name"] = c1.text_input("Họ và tên", cv["full_name"], key=f"{k}ten")
    cv["target_title"] = c2.text_input("Chức danh", cv.get("target_title") or "", key=f"{k}cd") or None
    c1, c2 = st.columns(2)
    nam = c1.text_input("Năm sinh", str(cv.get("birth_year") or ""), key=f"{k}ns")
    cv["birth_year"] = int(nam) if nam.strip().isdigit() else None
    cv["gender"] = c2.text_input("Giới tính", cv.get("gender") or "", key=f"{k}gt") or None
    st.caption("Thông tin nhanh khác (vd: Mong muốn)")
    cv["facts"] = [{"label": r["label"] or "", "value": r["value"]}
                   for r in bang(cv["facts"], ["label", "value"], f"{k}facts", ["Nhãn", "Nội dung"])
                   if r["value"]]   # dòng không có nội dung -> bỏ, tránh in chữ 'None' ra PDF


def _sua_so_lieu(cv: dict, k: str) -> None:
    st.markdown("#### Hàng ô số liệu (tối đa 4)")
    stats_moi = bang(cv["stats"], ["value", "label"], f"{k}stats", ["Số liệu", "Chú thích"])[:SO_O_SO_LIEU_TOI_DA]
    cv["stats"] = giu_nguon_stats(stats_moi, cv["stats"])    # giữ cờ original/generated của AI
    for s in cv["stats"]:
        if len(s["label"]) > CHU_THICH_TOI_DA:
            st.warning(f"Chú thích '{s['label']}' dài hơn {CHU_THICH_TOI_DA} ký tự, có thể tràn ô.")


def sua_ho_so(cv: dict, k: str) -> dict:
    """Vẽ form sửa và trả về BẢN SAO hồ sơ đã sửa (không đổi `cv` gốc)."""
    cv = copy.deepcopy(cv)
    _sua_thong_tin_chung(cv, k)
    _sua_so_lieu(cv, k)
    st.markdown("#### Các mục nội dung")
    for i, sec in enumerate(cv["sections"]):
        sk = f"{k}s{i}"
        with st.expander(f"{i + 1}. {sec['title']}  ·  ({sec['type']})"):
            sec["title"] = st.text_input("Tiêu đề mục", sec["title"], key=f"{sk}t")
            SUA_THEO_LOAI[sec["type"]](sec, sk)
    return cv


def sua_anh_chan_dung(ss) -> None:
    """Ảnh chân dung: xem, thay (cắt 29:38) hoặc bỏ. Ghi thẳng vào session state `ss`."""
    st.markdown("#### Ảnh chân dung")
    c1, c2 = st.columns([1, 4])
    with c1:
        if ss.photo:
            st.image(ss.photo, width=96)
        else:
            st.caption("Không có ảnh")
    with c2:
        up = st.file_uploader("Thay ảnh (không bắt buộc)", type=loai_cho_uploader(DUOI_ANH),
                              key=f"{ss.run}anh{ss.anh_ver}")
        if up:
            ma_anh = getattr(up, "file_id", None) or f"{up.name}-{up.size}"
            if ss.get("anh_da_xu_ly") != ma_anh:      # chỉ cắt 1 lần cho mỗi file mới
                try:
                    kiem_tra_file(up.getvalue(), up.name)   # S7
                    ss.photo = crop_portrait(up.getvalue())
                    ss.anh_da_xu_ly = ma_anh
                    st.rerun()
                except ExtractError as e:
                    st.markdown(alert("err", str(e)), unsafe_allow_html=True)
                except Exception:
                    log.exception("Không đọc được ảnh chân dung tải lên %s", an_ten_file(up.name))
                    st.markdown(alert("err", "Không đọc được file ảnh này, hãy thử ảnh khác."),
                                unsafe_allow_html=True)
        if ss.photo and st.button("Bỏ ảnh", icon=":material/close:", type="secondary"):
            ss.photo = None
            ss.anh_ver += 1          # đổi key -> ô tải ảnh được làm trống, ảnh không quay lại
            ss.anh_da_xu_ly = None
            st.rerun()
