"""Giai đoạn f) g) h) — ô số liệu tự lập, lưu ý tuyển dụng, ngôn ngữ CV. Chỉ dùng số liệu tính được từ CV.

Ô số liệu: số năm tính từ mốc thật, làm tròn XUỐNG (7 năm 11 tháng -> "7 năm"); không đủ dữ liệu thì không lập ô
đó (không bịa cho đủ 4 ô). Lưu ý tuyển dụng: chỉ nêu, không sửa CV, mỗi lưu ý một câu có mốc thời gian.
"""
import re
from datetime import date

from services.extraction.rules import rulebook
from services.extraction.rules import dates

_VI_CHARS = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.IGNORECASE)


# Ngôn ngữ CV: "vi" | "en" | "bilingual_vi_en"
def detect_language(text: str, heading_langs: list[str]) -> str:
    """Song ngữ khi có >= 2 tiêu đề mục tiếng Việt VÀ >= 2 tiêu đề tiếng Anh; tiếng Anh khi gần như không có dấu."""
    letters = sum(c.isalpha() for c in text)
    vi_ratio = len(_VI_CHARS.findall(text)) / max(letters, 1)
    if heading_langs.count("vi") >= 2 and heading_langs.count("en") >= 2:
        return "bilingual_vi_en"
    return "en" if vi_ratio < 0.01 else "vi"


# Mốc "mm/yyyy" để ghi trong câu lưu ý
def _ym(p: tuple[int, int] | None) -> str:
    return "nay" if p is None else f"{p[1]:02d}/{p[0]}"


# Các công việc có mốc thời gian: [(công ty, chức danh, đầu, cuối)]
def job_ranges(cv: dict) -> list[tuple[str, str, tuple[int, int], tuple[int, int] | None]]:
    """Lấy từ khoá tạm `_range` mà bộ dựng mục kinh nghiệm gắn vào từng công việc."""
    out = []
    for sec in cv["sections"]:
        for j in sec.get("jobs", []):
            r = j.get("_range")
            if r:
                out.append((j.get("company") or "", j.get("role") or "", r[0], r[1]))
    return out


# Lập ô số liệu từ dữ liệu thật (tối đa 4); trả (stats, câu ghi vào self_created)
def build_stats(cv: dict, today: date, lang: str) -> tuple[list[dict], list[str]]:
    """Kinh nghiệm (năm), kinh nghiệm quản lý, số doanh nghiệp, trình độ cao nhất — ô nào không tính được thì bỏ."""
    en = lang == "en"
    jobs = job_ranges(cv)
    stats: list[dict] = []
    total = dates.total_months([(s, e) for _, _, s, e in jobs], today)
    if total >= 12:
        stats.append({"value": f"{total // 12} {'years' if en else 'năm'}",
                      "label": "Years of experience" if en else "Kinh nghiệm làm việc"})
    elif total > 0:
        stats.append({"value": f"{total} {'months' if en else 'tháng'}",
                      "label": "Months of experience" if en else "Kinh nghiệm làm việc"})
    mgr_words = rulebook.rules()["experience"]["manager_words"]
    mgr = dates.total_months([(s, e) for _, role, s, e in jobs if rulebook.contains_any(role, mgr_words)], today)
    if mgr >= 12:
        stats.append({"value": f"{mgr // 12} {'years' if en else 'năm'}",
                      "label": "Management experience" if en else "Kinh nghiệm quản lý"})
    companies = {rulebook.norm(c) for c, *_ in jobs if c}
    if len(companies) >= 2:
        stats.append({"value": str(len(companies)), "label": "Companies" if en else "Doanh nghiệp đã làm việc"})
    degree = highest_degree(cv, lang)
    if degree:
        stats.append({"value": degree, "label": "Education" if en else "Trình độ học vấn"})
    stats = [{**s, "source": "generated"} for s in stats[:4]]
    notes = ([f"Hàng ô số liệu ({len(stats)} ô) do hệ thống tự lập từ mốc thời gian và học vấn trong CV"
              + ("" if len(stats) == 4 else " — không đủ dữ liệu để lập đủ 4 ô")] if stats else [])
    return stats, notes


# Bậc học cao nhất nhận ra được trong mục học vấn
def highest_degree(cv: dict, lang: str = "vi") -> str | None:
    """Theo thứ tự bậc trong [education].degree_levels; CV tiếng Anh trả tên bậc tiếng Anh."""
    levels = rulebook.rules()["education"]["degree_levels"]
    best = -1
    for sec in cv["sections"]:
        for e in sec.get("education", []):
            text = f"{e.get('title') or ''} {e.get('detail') or ''}"
            for i, (_, kws, _en) in enumerate(levels):
                if i > 0 and rulebook.contains_any(text, kws):         # bậc 0 = "chứng chỉ" không tính là trình độ
                    best = max(best, i)
    return (levels[best][2] if lang == "en" else levels[best][0]) if best > 0 else None


# Số tháng kinh nghiệm (không tính trùng) TRƯỚC mốc `start`
def _months_before(jobs: list, start: tuple[int, int], today: date) -> int:
    """Các công việc bắt đầu trước `start`, cắt phần sau `start` đi."""
    idx = lambda p: p[0] * 12 + p[1]
    lim = idx(start) - 1
    ranges = []
    for _, _, js, je in jobs:
        if idx(js) <= lim:
            e = min(idx(je or (today.year, today.month)), lim)
            ranges.append((js, ((e - 1) // 12, (e - 1) % 12 + 1)))
    return dates.total_months(ranges, today)


# Lưu ý tuyển dụng tính từ mốc thời gian (mỗi lưu ý một câu)
def recruiting_flags(cv: dict, today: date, has_education: bool, lang: str) -> list[str]:
    """Chồng chéo, khoảng trống >= 3 tháng, chức danh cao khi chưa đủ 4 năm, quản lý < 12 tháng,
    chứng chỉ KTT sau khi đã làm KTT, đi học trùng thời gian làm việc, thiếu Học vấn, CV song ngữ."""
    r = rulebook.rules()
    flags: list[str] = []
    jobs = sorted(job_ranges(cv), key=lambda j: j[2])
    now = (today.year, today.month)
    idx = lambda p: p[0] * 12 + p[1]
    for a, b in zip(jobs, jobs[1:]):
        a_end = a[3] or now
        if idx(b[2]) < idx(a_end):
            flags.append(f"Thời gian làm việc chồng chéo: {a[0] or a[1]} ({_ym(a[2])} – {_ym(a[3])}) và "
                         f"{b[0] or b[1]} ({_ym(b[2])} – {_ym(b[3])}).")
    merged_end = None
    for c, role, s, e in jobs:
        if merged_end is not None:
            gap = idx(s) - idx(merged_end) - 1
            if gap >= 3:
                flags.append(f"Khoảng trống {gap} tháng trong quá trình làm việc (từ {_ym(merged_end)} đến "
                             f"{_ym(s)}).")
        end = e or now
        merged_end = end if merged_end is None or idx(end) > idx(merged_end) else merged_end
    for c, role, s, e in jobs:
        before = _months_before(jobs, s, today)
        if role and rulebook.contains_any(role, r["experience"]["senior_words"]) and before < 48:
            flags.append(f"Chức danh \"{role}\" (từ {_ym(s)}) khi mới có khoảng {before // 12} năm "
                         f"{before % 12} tháng kinh nghiệm trước đó.")
        if role and rulebook.contains_any(role, r["experience"]["manager_words"]) and e is not None:
            dur = dates.months(s, e, today)
            if dur < 12:
                flags.append(f"Giữ vị trí quản lý \"{role}\" chỉ {dur} tháng ({_ym(s)} – {_ym(e)}).")
    ktt_roles = [s for _, role, s, _ in jobs if rulebook.contains_any(role, ["ke toan truong"])]
    for sec in cv["sections"]:
        for e in sec.get("education", []):
            text = f"{e.get('title') or ''} {e.get('detail') or ''}"
            p = dates.find_period(e.get("period") or "", today)
            if ktt_roles and p and rulebook.contains_any(text, r["education"]["chief_accountant_cert"]) \
                    and idx(p.start) > idx(min(ktt_roles)):
                flags.append(f"Chứng chỉ Kế toán trưởng ({e.get('period')}) có sau thời điểm bắt đầu làm Kế toán "
                             f"trưởng ({_ym(min(ktt_roles))}).")
            if p and p.is_range:
                # Khoá học chỉ ghi năm ("2014 – 2018"): coi như bắt đầu tháng 9, tốt nghiệp tháng 6 (niên khoá VN)
                # -> không báo trùng chỉ vì thiếu tháng
                years_only = not re.search(r"[/.\-]\s*\d{4}|[a-z]{3}", (e.get("period") or "").lower().replace(" – ", " "))
                p_start = (p.start[0], 9) if years_only else p.start
                p_end = (p.end[0], 6) if years_only and p.end else p.end
                for c, role, s, je in jobs:
                    ov = min(idx(p_end or now), idx(je or now)) - max(idx(p_start), idx(s)) + 1
                    if ov >= 3:
                        flags.append(f"Thời gian đi học ({e.get('period')}) trùng {ov} tháng với thời gian làm việc "
                                     f"tại {c or role} ({_ym(s)} – {_ym(je)}).")
    if not has_education:
        flags.append("CV không có mục Học vấn.")
    if cv.get("language") == "bilingual_vi_en":
        flags.append("CV song ngữ Việt–Anh: hồ sơ chỉ giữ phần tiếng Việt — làm thêm bản tiếng Anh nếu khách cần.")
    return list(dict.fromkeys(flags))
