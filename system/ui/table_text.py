"""Bảng dạng chữ cho form sửa hồ sơ: mỗi dòng 1 mục, các cột cách nhau bằng dấu '|'.

Tách khỏi app.py thành hàm thuần (không dùng Streamlit) để test được.
Ô có chứa ký tự '|' được ghi thành '\\|' để không bị hiểu là dấu ngăn cột.
"""
import re

_COLUMN_SEP = re.compile(r"(?<!\\)\|")   # '|' không đứng sau dấu '\'


# Ô nhiều dòng -> danh sách
def split_lines(text: str) -> list[str]:
    """Ô nhập nhiều dòng -> danh sách (mỗi dòng 1 mục, bỏ dòng trống)."""
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


# Giá trị ô -> chữ
def _cell_to_text(v) -> str:
    """Giá trị ô -> chữ. Cột đúng/sai ghi 'x' nếu đúng, để trống nếu sai."""
    s = "x" if v is True else "" if v in (None, False) else str(v)
    return s.replace("|", "\\|")


# Danh sách dòng -> bảng chữ
def rows_to_text(rows: list[dict], columns: list[str]) -> str:
    return "\n".join(" | ".join(_cell_to_text(r.get(c)) for c in columns) for r in rows)


# Bảng chữ -> danh sách dòng
def text_to_rows(text: str, columns: list[str]) -> list[dict]:
    result = []
    for line in split_lines(text):
        parts = [p.strip().replace("\\|", "|") for p in _COLUMN_SEP.split(line)]
        if len(parts) > len(columns):                  # dư cột -> gộp vào cột cuối
            parts = parts[:len(columns) - 1] + [" | ".join(parts[len(columns) - 1:])]
        parts += [""] * (len(columns) - len(parts))
        result.append({c: (p or None) for c, p in zip(columns, parts)})
    return result


# Giữ cờ nguồn của ô số liệu sau khi sửa
def keep_stat_sources(edited: list[dict], old: list[dict]) -> list[dict]:
    """Gắn lại 'source' cho ô số liệu sau khi sửa (form chỉ có cột số liệu + chú thích).

    Ghép với ô cũ chưa dùng theo thứ tự ưu tiên: trùng cả hai -> trùng số liệu -> trùng chú thích.
    Không ghép được (dòng mới) -> 'original'.
    """
    remaining = list(old or [])
    result = []
    for s in edited:
        value, label = s.get("value") or "", s.get("label") or ""
        match = None
        for matcher in (lambda c: c.get("value") == value and c.get("label") == label,
                     lambda c: value and c.get("value") == value,
                     lambda c: label and c.get("label") == label):
            match = next((c for c in remaining if matcher(c)), None)
            if match:
                break
        if match:
            remaining.remove(match)
        result.append({"value": value, "label": label,
                        "source": (match or {}).get("source") or "original"})
    return result
