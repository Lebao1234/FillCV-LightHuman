"""Design tokens — NGUỒN DUY NHẤT cho màu, chữ, khoảng cách, bo góc, chuyển động.

Dùng ở:
  - app.py            : css_vars("web") chèn vào đầu khối CSS của web app
  - template.html     : css_vars("pdf") -> :root của hồ sơ PDF (giá trị theo mục 5 SKILL.md)
  - render_worker.py  : MAU[...] cho footer PDF (footer của Chromium không đọc được biến CSS)
  - .streamlit/config.toml : phải khớp MAU (test kiểm tra) vì file toml không đọc được Python

Đổi một màu -> sửa ở đây, rồi chạy `python -m infra.tokens` để in lại bảng cho docs/design-system.md.
Tài liệu: docs/design-system.md
"""

# ---------------------------------------------------------------------------
# Màu
# ---------------------------------------------------------------------------
# Màu gốc: thương hiệu + trung tính. Chữ/đường kẻ lấy đúng giá trị SKILL.md mục 5 để
# web app và PDF dùng chung một bộ (trước đây web app dùng #1c2333/#5b6476/#e3e6ec, lệch PDF).
MAU = {
    # Thương hiệu
    "navy": "#14285a",          # màu nhấn chính: nút, tiêu đề, tên ứng viên trong PDF
    "navy-50": "#eef1f7",       # nền bong bóng tin của người dùng
    "navy-100": "#dfe4ef",      # viền bong bóng người dùng, khối tiêu đề trong khung A4
    "gold": "#dca54b",          # điểm nhấn trang trí: vạch, chấm đầu dòng. KHÔNG dùng làm màu chữ nhỏ
    "gold-text": "#8a5e17",     # gold đậm khi cần làm CHỮ (đạt 4.5:1 trên nền trắng/xám nhạt)
    "gold-100": "#f3e6cc",      # vệt gold nhạt trong khung A4
    "yellow": "#f2cf63",        # viền trái thẻ năng lực trong PDF
    # Chữ
    "ink": "#1f2430",           # chữ chính
    "muted": "#5a6275",         # chữ phụ
    "faint": "#687083",         # chữ nhạt: nhãn, chú thích (trước #8a92a3 — chỉ 3.1:1, không đạt AA)
    # Bề mặt & đường kẻ
    "white": "#ffffff",
    "soft": "#f5f6f8",          # nền phụ: khung A4, ô tải file, khối code
    "skeleton": "#edf0f4",      # vạch giả nội dung trong khung A4
    "skeleton-hi": "#f8f9fb",   # vệt sáng chạy qua khi đang tải
    "line": "#d9dce3",          # đường kẻ, viền
    "line-strong": "#cdd2dc",   # viền nét đứt ô tải file
    # Trạng thái
    "ok": "#2f7a57", "ok-bg": "#edf6f1", "ok-line": "#cfe6da",
    "warn": "#8f5a12", "warn-bg": "#fbf4e8", "warn-line": "#f1e1c6",   # warn trước #a8691b — 4.1:1
    "err": "#b42318", "err-bg": "#fdf1f0", "err-line": "#f3d2cf",
    "info": "#14285a", "info-bg": "#eef1f7", "info-line": "#dfe4ef",
    # Riêng PDF (giữ đúng mẫu SKILL.md)
    "pdf-stats-bg": "#eef1f6",  # nền hàng ô số liệu
    "pdf-ref-bg": "#f6f7fa",    # nền khối người tham chiếu
}

# ---------------------------------------------------------------------------
# Chữ, khoảng cách, bo góc, bóng, chuyển động (web app)
# ---------------------------------------------------------------------------
FONT = {
    "sans": '"Be Vietnam Pro", system-ui, sans-serif',
    "mono": '"JetBrains Mono", ui-monospace, monospace',
    "serif-pdf": '"Times New Roman", "Liberation Serif", Times, serif',
}
CO_CHU = {"xs": "11px", "sm": "12px", "md": "13px", "base": "14px", "lg": "16px", "xl": "18px"}
KHOANG_CACH = {"1": "4px", "2": "8px", "3": "12px", "4": "16px", "5": "24px", "6": "32px", "7": "40px"}
BO_GOC = {"sm": "4px", "md": "8px", "lg": "12px", "pill": "999px"}
BONG = {"sheet": "0 24px 48px -28px rgba(20, 40, 90, .22)"}
CHUYEN_DONG = {"ease": "cubic-bezier(.16, 1, .3, 1)", "fast": ".2s", "base": ".45s"}

# A7: lề trang A4 của hồ sơ PDF (mm) — mục 5 SKILL.md. Dùng chung cho @page (template.html),
# lề footer (render_worker.py) và vùng nội dung khi đo độ đầy trang cuối (pdf_utils.pdf_layout).
PDF_LE_MM = {"tren": 16, "phai": 17, "duoi": 20, "trai": 17}
A4_MM = (210, 297)

# Các token PDF dùng (tên biến CSS giữ nguyên như mục 5 SKILL.md để template không đổi)
_PDF = ["navy", "gold", "yellow", "ink", "muted", "line", "white", "pdf-stats-bg", "pdf-ref-bg"]


def css_vars(noi_dung: str = "web") -> str:
    """Khối `:root{...}` cho web app ("web") hoặc hồ sơ PDF ("pdf")."""
    if noi_dung == "pdf":
        dong = [f"--{k}:{MAU[k]}" for k in _PDF]
    else:
        dong = [f"--{k}:{v}" for k, v in MAU.items() if not k.startswith("pdf-")]
        dong += [f"--font-{k}:{v}" for k, v in FONT.items() if k != "serif-pdf"]
        dong += [f"--fs-{k}:{v}" for k, v in CO_CHU.items()]
        dong += [f"--sp-{k}:{v}" for k, v in KHOANG_CACH.items()]
        dong += [f"--r-{k}:{v}" for k, v in BO_GOC.items()]
        dong += [f"--shadow-{k}:{v}" for k, v in BONG.items()]
        dong += [f"--{'ease' if k == 'ease' else 'dur-' + k}:{v}" for k, v in CHUYEN_DONG.items()]
    return ":root{" + "; ".join(dong) + ";}"


# ---------------------------------------------------------------------------
# Độ tương phản (WCAG 2.1) — dùng trong test và khi chọn màu mới
# ---------------------------------------------------------------------------
def _do_sang(hex_mau: str) -> float:
    h = hex_mau.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def tuong_phan(chu: str, nen: str) -> float:
    a, b = _do_sang(MAU.get(chu, chu)), _do_sang(MAU.get(nen, nen))
    return (max(a, b) + .05) / (min(a, b) + .05)


# Các cặp chữ/nền thực sự xuất hiện trên giao diện — đều phải >= 4.5:1
CAP_CHU_NEN = [
    ("ink", "white"), ("muted", "white"), ("faint", "white"), ("faint", "soft"), ("muted", "soft"),
    ("gold-text", "white"), ("gold-text", "soft"), ("white", "navy"), ("navy", "navy-50"),
    ("ok", "ok-bg"), ("warn", "warn-bg"), ("err", "err-bg"), ("info", "info-bg"), ("ink", "navy-50"),
]


def bang_markdown() -> str:
    """Bảng token cho docs/design-system.md (chạy `python -m infra.tokens`)."""
    out = ["| Token | Giá trị |", "|---|---|"]
    out += [f"| `--{k}` | `{v}` |" for k, v in MAU.items()]
    for ten, nhom, tien_to in [("Cỡ chữ", CO_CHU, "fs"), ("Khoảng cách", KHOANG_CACH, "sp"), ("Bo góc", BO_GOC, "r")]:
        out += ["", f"| {ten} | Giá trị |", "|---|---|"] + [f"| `--{tien_to}-{k}` | `{v}` |" for k, v in nhom.items()]
    out += ["", "| Cặp chữ / nền | Tương phản |", "|---|---|"]
    out += [f"| `{c}` / `{n}` | {tuong_phan(c, n):.2f}:1 |" for c, n in CAP_CHU_NEN]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(bang_markdown())
