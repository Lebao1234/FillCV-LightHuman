"""Bảng dạng chữ cho form sửa hồ sơ: mỗi dòng 1 mục, các cột cách nhau bằng dấu '|'.

Tách khỏi app.py thành hàm thuần (không dùng Streamlit) để test được.
Ô có chứa ký tự '|' được ghi thành '\\|' để không bị hiểu là dấu ngăn cột.
"""
import re

_NGAN_COT = re.compile(r"(?<!\\)\|")   # '|' không đứng sau dấu '\'


def dong(text: str) -> list[str]:
    """Ô nhập nhiều dòng -> danh sách (mỗi dòng 1 mục, bỏ dòng trống)."""
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def _o_sang_chu(v) -> str:
    """Giá trị ô -> chữ. Cột đúng/sai ghi 'x' nếu đúng, để trống nếu sai."""
    s = "x" if v is True else "" if v in (None, False) else str(v)
    return s.replace("|", "\\|")


def bang_sang_chu(rows: list[dict], cot: list[str]) -> str:
    return "\n".join(" | ".join(_o_sang_chu(r.get(c)) for c in cot) for r in rows)


def chu_sang_bang(text: str, cot: list[str]) -> list[dict]:
    ket_qua = []
    for line in dong(text):
        phan = [p.strip().replace("\\|", "|") for p in _NGAN_COT.split(line)]
        if len(phan) > len(cot):                  # dư cột -> gộp vào cột cuối
            phan = phan[:len(cot) - 1] + [" | ".join(phan[len(cot) - 1:])]
        phan += [""] * (len(cot) - len(phan))
        ket_qua.append({c: (p or None) for c, p in zip(cot, phan)})
    return ket_qua


def giu_nguon_stats(moi: list[dict], cu: list[dict]) -> list[dict]:
    """Gắn lại 'source' cho ô số liệu sau khi sửa (form chỉ có cột số liệu + chú thích).

    Ghép với ô cũ chưa dùng theo thứ tự ưu tiên: trùng cả hai -> trùng số liệu -> trùng chú thích.
    Không ghép được (dòng mới) -> 'original'.
    """
    con = list(cu or [])
    ket_qua = []
    for s in moi:
        value, label = s.get("value") or "", s.get("label") or ""
        ghep = None
        for khop in (lambda c: c.get("value") == value and c.get("label") == label,
                     lambda c: value and c.get("value") == value,
                     lambda c: label and c.get("label") == label):
            ghep = next((c for c in con if khop(c)), None)
            if ghep:
                break
        if ghep:
            con.remove(ghep)
        ket_qua.append({"value": value, "label": label,
                        "source": (ghep or {}).get("source") or "original"})
    return ket_qua
