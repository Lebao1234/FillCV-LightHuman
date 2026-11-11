"""Giai đoạn c) d) e) — dựng nội dung từng mục theo schema: gộp dòng bị ngắt, tách công việc / học vấn / tham chiếu,
chọn `type` cho mục. Không đoán bừa: thiếu thì để trống và ghi cảnh báo + độ tin cậy thấp.
"""
import re
from dataclasses import dataclass, field, replace
from datetime import date

from services.extraction.rules import dates, rulebook
from services.extraction.rules.pdf_text import Line, Span, marked_text
from services.extraction.rules.sections import RawSection

_LABEL = re.compile(r"^\s*([^:：\t]{1,40}?)\s*[:：]\s*(.*)$")
_SPLIT = re.compile(r"\s*(?:\t+|\s\|\s|\|| [–—-] | · )\s*")


# Một "ý" sau khi gộp các dòng bị ngắt (một gạch đầu dòng, một đoạn văn, một dòng tiêu đề...)
@dataclass
class Item:
    text: str                       # có đánh dấu **in đậm**
    plain: str                      # không đánh dấu
    lines: list[Line] = field(default_factory=list)
    bullet: bool = False

    @property
    def first(self) -> Line:
        """Dòng đầu tiên của ý."""
        return self.lines[0]

    @property
    def words(self) -> int:
        """Số từ."""
        return len(self.plain.split())


# Kết quả dựng một mục: dữ liệu theo schema + cảnh báo/độ tin cậy theo đường dẫn tương đối trong mục
@dataclass
class Built:
    section: dict
    notes: list[tuple[str, str]] = field(default_factory=list)       # (đường dẫn tương đối, câu)
    confidence: dict[str, float] = field(default_factory=dict)       # đường dẫn tương đối ("" = cả mục)


# Nhãn thuộc danh sách từ khoá không (nhãn song ngữ 'Vị trí/ Position' -> thử từng phần)
def label_in(label: str, words: list[str]) -> bool:
    """'Vị trí/ Location' thuộc ['vi tri', ...] -> True."""
    return any(rulebook.in_list(p, words) for p in [label] + re.split(r"\s*/\s*", label or "") if p.strip())


# Dòng dạng "Nhãn: nội dung" -> (nhãn, nội dung) nếu nhãn ngắn
def label_of(text: str) -> tuple[str, str] | None:
    """'Lĩnh vực: Bán lẻ' -> ('Lĩnh vực', 'Bán lẻ'). Bỏ qua link 'https://...' và giờ '10:30'."""
    m = _LABEL.match(text or "")
    if not m or re.search(r"https?$|\d$", m.group(1)) or len(m.group(1).split()) > 5:
        return None
    return m.group(1).strip(), m.group(2).strip()


# Gộp các dòng bị ngắt thành từng ý
def logical_items(lines: list[Line]) -> list[Item]:
    """Dòng sau là phần tiếp của dòng trước khi: không phải gạch đầu dòng, cùng trang/cột, sát nhau, dòng trước
    chạm gần lề phải (bị ngắt vì hết chỗ), và không phải dòng "Nhãn:"/dòng có khoảng thời gian."""
    items: list[Item] = []
    prev: Line | None = None
    for l in lines:
        cont = False
        # câu bị ngắt sang trang sau: dòng đầu trang mới bắt đầu bằng chữ thường
        next_page = prev is not None and l.page == prev.page + 1 and l.text[:1].islower()
        if (prev is not None and items and not l.bullet and not l.cell and not prev.cell
                and (l.page == prev.page or next_page) and l.col == prev.col):
            lo, hi = (prev.left, prev.right) if prev.right > prev.left else (prev.x0, prev.x1)
            full = prev.x1 >= hi - 0.12 * max(hi - lo, 1)
            close = next_page or (l.y0 - prev.y1) < l.size * 0.9
            fresh = label_of(l.text) is not None or _has_range(l.text) or prev.text.rstrip().endswith(":")
            cont = (full and close and not fresh and "\t" not in prev.text and prev.bold == l.bold
                    if l.bold or prev.bold else full and close and not fresh and "\t" not in prev.text)
        if cont:
            it = items[-1]
            it.text = f"{it.text} {marked_text(l)}".strip()
            it.plain = f"{it.plain} {l.text.replace(chr(9), ' ')}".strip()
            it.lines.append(l)
        else:
            items.append(Item(marked_text(l), re.sub(r"\s+", " ", l.text.replace("\t", " ")).strip(), [l], l.bullet))
        prev = l
    for it in items:                                                 # gộp "**a** **b**" kề nhau
        it.text = re.sub(r"\*\*\s+\*\*", " ", it.text)
    return items


# Có khoảng thời gian dạng "từ – đến" trong chữ không
def _has_range(text: str) -> bool:
    p = dates.find_period(text)
    return bool(p and p.is_range)


# Tách một chuỗi thành các phần theo dấu ngăn (tab, |, " – ", " - ", " · ")
def parts_of(text: str) -> list[str]:
    """'Công ty ABC | Kế toán' -> ['Công ty ABC', 'Kế toán']."""
    return [p.strip(" ,;:") for p in _SPLIT.split(text or "") if p.strip(" ,;:")]


# Bỏ khoảng thời gian khỏi chữ, trả (phần còn lại, Period | None)
def cut_period(text: str, today: date) -> tuple[str, dates.Period | None]:
    """'Công ty ABC\t03/2019 - Nay' -> ('Công ty ABC', Period(03/2019 – Nay))."""
    p = dates.find_period(text, today)
    if not p:
        return text, None
    rest = re.sub(r"\(\s*\)", " ", text[:p.span[0]] + " " + text[p.span[1]:]).strip(" \t|,–—-:")
    rest = rest.removeprefix("(") if rest.count("(") > rest.count(")") and rest.startswith("(") else rest
    rest = rest.removesuffix(")") if rest.count(")") > rest.count("(") and rest.endswith(")") else rest
    rest = re.sub(r"\s*\($", "", rest)                           # "Kế toán (" còn lại khi ngày nằm trong ngoặc
    return _tidy(re.sub(r"\s{2,}", " ", rest)) or "", p


# Có phải dòng tiêu đề nhóm việc không (kết thúc bằng ':' hoặc nhãn nhóm, hoặc dòng đậm ngắn đứng trước gạch đầu dòng)
def _is_group_title(it: Item, nxt: Item | None) -> bool:
    if it.bullet or it.words > 10:
        return False
    if it.plain.startswith(GROUP_MARKS) or it.plain.endswith(":") \
            or rulebook.in_list(it.plain, rulebook.rules()["experience"]["group_labels"]):
        return True
    return it.first.bold and nxt is not None and nxt.bullet


# Ký hiệu đứng trước tiêu đề nhóm việc (khác ký hiệu gạch đầu dòng)
GROUP_MARKS = ("▸", "▹", "»")


# Chữ tiêu đề nhóm: bỏ ký hiệu nhóm và dấu ':' cuối
def _group_title(it: Item) -> str:
    return it.plain.lstrip("".join(GROUP_MARKS) + " ").rstrip(":").strip()


# =============================================================================== Kinh nghiệm làm việc
# Dòng mở đầu một công việc: không phải gạch đầu dòng, ngắn, có khoảng thời gian "từ – đến"
def _is_anchor(it: Item) -> bool:
    return not it.bullet and it.words <= 25 and _has_range(it.plain)


# Một phần đầu công việc có vẻ là tên công ty không
def _companyish(part: str, line: Line | None) -> bool:
    words = rulebook.rules()["experience"]["company_words"]
    if rulebook.contains_any(part, words):
        return True
    letters = [c for c in part if c.isalpha()]
    return bool(line and letters and (line.bold or all(c.isupper() for c in letters)) and not line.italic)


# Chia các phần đầu công việc thành (công ty, chức danh, phần còn lại)
def _assign_head(parts: list[tuple[str, Line]]) -> tuple[str, str, list[str]]:
    exp = rulebook.rules()["experience"]
    for k, (p, l) in enumerate(parts):                         # "Vị trí: Kế toán trưởng" -> chức danh theo nhãn
        lab = label_of(p)
        if lab and lab[1] and label_in(lab[0], exp["role_labels"]):
            comp, _, others = _assign_head(parts[:k] + parts[k + 1:])
            return comp, lab[1], others
    comp = next((p for p, l in parts if rulebook.contains_any(p, rulebook.rules()["experience"]["company_words"])),
                None) or next((p for p, l in parts if _companyish(p, l)), None)
    rest = [(p, l) for p, l in parts if p != comp]
    role_words = rulebook.rules()["experience"]["role_words"]
    # Chức danh: có từ chỉ chức danh > in đậm-nghiêng > dòng thường đầu tiên. Dòng CHỈ in nghiêng mà không có từ
    # chỉ chức danh thường là dòng mô tả công ty -> để làm dòng phụ.
    role = (next((p for p, l in rest if rulebook.contains_any(p, role_words) and len(p.split()) <= 8), None)
            or next((p for p, l in rest if l.italic and l.bold and len(p.split()) <= 8), None)
            or next((p for p, l in rest if not l.italic and len(p.split()) <= 8), None))
    others = [p for p, l in rest if p != role]
    return comp or "", role or "", others


# Dựng mục kinh nghiệm: tách công việc, dòng phụ, nhóm việc, vị trí con
def build_experience(raw: RawSection, items: list[Item], today: date) -> Built | None:
    """None nếu không thấy công việc nào (không có khoảng thời gian) -> người gọi chọn loại khác."""
    anchors = [i for i, it in enumerate(items) if _is_anchor(it)]
    if not anchors:
        return None
    built = Built({"type": "experience", "title": raw.title, "jobs": []})
    used: set[int] = set()
    starts: list[tuple[int, int, list[int]]] = []           # (anchor, đầu khối, các ý thuộc phần đầu)
    for n, a in enumerate(anchors):
        head = [a]
        lo = (starts[-1][0] + 1) if starts else 0
        b = a - 1
        while b >= lo and len(head) < 3:                     # nhìn lùi: tên công ty/chức danh đứng trước dòng ngày
            it = items[b]
            long_name = it.words > 12 and not (it.words <= 20 and _companyish(it.plain, None))
            if (it.bullet or long_name or label_of(it.plain) or it.plain.endswith((":", ".", ";")) or b in used
                    or _is_anchor(it) or it.first.x0 > items[a].first.x0 + 8
                    or not (it.first.bold or it.first.upper or _companyish(it.plain, None))):
                break
            words = rulebook.rules()["experience"]["company_words"]
            known = [items[h].plain for h in head if h != a or not label_of(cut_period(items[a].plain, today)[0])]
            if rulebook.contains_any(it.plain, words) and any(rulebook.contains_any(k, words) for k in known):
                break                                        # đã có tên công ty; dòng trên là tiêu đề phụ của mục
            head.insert(0, b)
            b -= 1
        nxt_anchor = anchors[n + 1] if n + 1 < len(anchors) else len(items)
        f = a + 1
        while f < nxt_anchor and len(head) < 4:              # nhìn tới: công ty/chức danh ngay sau dòng ngày
            it = items[f]
            if (it.bullet or it.words > 12 or label_of(it.plain) or it.plain.endswith((":", ".", ";"))
                    or it.first.x0 > items[a].first.x0 + 8
                    or _is_group_title(it, items[f + 1] if f + 1 < len(items) else None)):
                break
            # dòng ngắn ngay sau nhưng là phần đầu của công việc kế tiếp (nhìn lùi của anchor sau) -> dừng
            if f + 1 == nxt_anchor and not it.bullet and (it.first.bold or it.first.upper) and f + 1 < len(items):
                break
            head.append(f)
            f += 1
        used.update(head)
        starts.append((a, head[0], head))
    job = None
    for n, (a, first, head) in enumerate(starts):
        end = starts[n + 1][1] if n + 1 < len(starts) else len(items)
        parts: list[tuple[str, Line]] = []
        period = None
        for i in head:
            text = items[i].first.text if len(items[i].lines) == 1 else items[i].plain
            rest, p = cut_period(text, today) if i == a else (text, None)
            period = p or period
            parts += [(x, items[i].first) for x in parts_of(rest)]
        comp, role, others = _assign_head(parts)
        indented = job is not None and items[a].first.x0 > built_anchor_x + 8
        marked = items[a].plain.startswith(GROUP_MARKS)           # "▸ Giai đoạn kế toán (2019 – 2020)" trong 1 công ty
        if job is not None and (marked or not comp and (indented or items[a].first.italic or len(head) == 1)):
            name = role or comp or (others[0] if others else "")
            sub = {"name": name.lstrip("".join(GROUP_MARKS) + " "), "period": period.text if period else None,
                   "meta": [], "groups": []}
            job["sub_roles"].append(sub)
            target = sub
            path = f"jobs[{len(built.section['jobs']) - 1}].sub_roles[{len(job['sub_roles']) - 1}]"
            built.confidence[path] = 0.6
            built.notes.append((path, "vị trí con được nhận theo dòng thời gian thụt vào — kiểm tra lại"))
        else:
            job = {"company": comp, "period": period.text if period else None, "role": role or None,
                   "meta": [{"label": None, "text": o} for o in others], "groups": [], "sub_roles": [],
                   "_range": (period.start, period.end) if period else None}
            built.section["jobs"].append(job)
            built_anchor_x = items[a].first.x0
            target = job
            path = f"jobs[{len(built.section['jobs']) - 1}]"
            missing = [k for k, v in (("tên công ty", comp), ("chức danh", role)) if not v]
            built.confidence[path] = 0.9 if not missing else (0.6 if len(missing) == 1 else 0.4)
            if missing:
                built.notes.append((path, f"chưa tách được {' và '.join(missing)}"))
        _fill_body(target, items[max(head) + 1:end])
    return built


# Đưa các ý thân công việc vào dòng phụ / nhóm việc / gạch đầu dòng
def _fill_body(target: dict, body: list[Item]) -> None:
    exp = rulebook.rules()["experience"]
    group = None
    for k, it in enumerate(body):
        nxt = body[k + 1] if k + 1 < len(body) else None
        lab = label_of(it.plain) if not it.bullet else None
        if lab and lab[1] and "role" in target and not target["role"] and label_in(lab[0], exp["role_labels"]):
            target["role"] = lab[1]                               # "Vị trí: ..." ngay dưới tên công ty
            continue
        if lab and lab[1] and "role" in target and not target["role"] and label_in(lab[0], exp["progression_labels"]):
            last = re.split(r"\s*(?:→|->|⇒|»|>)\s*", lab[1])[-1]   # "Lộ trình: A (2019) → B (2021)" -> chức danh B
            last = re.split(r"\s*\.\s+|;\s*", cut_period(last, date.today())[0])[0]
            target["role"] = last.strip(" .") or None
        if lab and lab[1] and (label_in(lab[0], exp["meta_labels"]) or label_in(lab[0], exp["group_labels"])):
            label, value = lab
            target["meta"].append({"label": label, "text": _after_label(it.text, value)})
            continue
        if _is_group_title(it, nxt) or (lab and not lab[1]):
            group = {"title": _group_title(it), "bullets": []}
            target["groups"].append(group)
            continue
        if group is None:
            group = {"title": None, "bullets": []}
            target["groups"].append(group)
        group["bullets"].append(it.text)
    target["groups"] = [g for g in target["groups"] if g["bullets"] or g["title"]]


# Phần nội dung sau nhãn, giữ đánh dấu in đậm nếu có
def _after_label(marked: str, plain_value: str) -> str:
    m = re.match(r"^[^:：]*[:：]\s*(?:\*\*\s*)?(.*)$", marked)
    out = m.group(1).strip() if m else plain_value
    return out if out.count("**") % 2 == 0 else plain_value


# =============================================================================== Học vấn / chứng chỉ
# Nhãn trong mục học vấn -> (loại degree | major | school, nhãn, nội dung)
def _edu_label(text: str) -> tuple[str, str, str] | None:
    lab = label_of(text)
    if not lab:
        return None
    edu = rulebook.rules()["education"]
    for kind in ("degree", "major", "school"):
        if label_in(lab[0], edu[f"{kind}_labels"]):
            return kind, lab[0], lab[1]
    return None


# Bỏ mọi khoảng thời gian + chữ "năm/year" đứng thừa; trả (phần chữ còn lại, khoảng thời gian đầu tiên)
def _cut_dates(text: str, today: date) -> tuple[str, dates.Period | None]:
    """'Năm 2008\tChuyên ngành: Kế toán năm 2008' -> ('Chuyên ngành: Kế toán', 2008)."""
    first = None
    for _ in range(3):
        text, p = cut_period(text, today)
        if not p:
            break
        first = first or p
    text = re.sub(r"(?i)(?:^|(?<=\s))(?:vào năm|năm|nam|year)\s*(?=$|[\t.,;])", " ", text)
    return re.sub(r"\s{2,}", " ", text.replace("\t", " ")).strip(" .,;–-"), first


# Tách "<văn bằng> tại <trường>" -> (văn bằng, trường)
def _split_at(text: str) -> tuple[str, str | None]:
    words = rulebook.rules()["education"]["at_words"]
    m = re.search(r"\s+(?:" + "|".join(re.escape(w) for w in words) + r")\s+", text)
    if not m or m.start() == 0:
        return text, None
    return text[:m.start()].strip(), text[m.end():].strip() or None


# Dọn khoảng trắng thừa trong ngoặc: '( Đại học )' -> '(Đại học)'
def _tidy(text: str | None) -> str | None:
    if not text:
        return text
    return re.sub(r"\s{2,}", " ", re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", text))).strip(" .;,")


# Một văn bằng từ các phần đã gom: (chữ, nhãn) + khoảng thời gian
def _edu_entry(pieces: list[tuple[str, tuple | None]], period: dates.Period | None) -> dict | None:
    """Tên bằng = phần ĐẦU TIÊN (theo thứ tự) là nhãn 'Bằng cấp: ...' có nội dung, hoặc chữ thường không chỉ là tên
    trường; dòng chỉ có tên trường -> chi tiết."""
    edu = rulebook.rules()["education"]
    major = next((lab for _, lab in pieces if lab and lab[0] == "major" and lab[2]), None)
    details = [lab[2] for _, lab in pieces if lab and lab[0] == "school" and lab[2]]
    title = None
    for text, lab in pieces:
        if lab:
            if lab[0] == "degree" and lab[2] and title is None:
                title = lab[2]
            continue
        head, school = _split_at(re.sub(r"^\d{1,2}[.)]\s+", "", text))
        if title is None:
            parts = parts_of(head) or [head]
            deg = next((x for x in parts if rulebook.contains_any(x, edu["degree_words"])), None)
            not_school = next((x for x in parts if not rulebook.contains_any(x, edu["school_words"])), None)
            title = deg or not_school
            details += [x for x in parts if x != title]
        else:
            details.append(head)
        if school:
            details.append(school)
    if major:
        title = f"{title}, {major[1].lower()} {major[2]}" if title else major[2]
    if not title and details:
        title = details.pop(0)
    if not title:
        return None
    return {"title": _tidy(title), "detail": _tidy(" – ".join(d for d in details if d)) or None,
            "period": period.text if period else None}


# Học vấn dạng bảng "nội dung trước, ngày ở ô bên cạnh": ngày đứng riêng gắn vào văn bằng ngay trên chưa có ngày
def _education_content_led(infos: list[tuple[Item, str, dates.Period | None]]) -> list[dict]:
    """Văn bằng mới bắt đầu ở gạch đầu dòng, dòng đậm, dòng thụt ra trái, hoặc dòng có ngày khi văn bằng đang xét đã
    có ngày. Dòng 'Chuyên ngành:/Bằng cấp:' luôn thuộc văn bằng đang xét."""
    entries: list[dict] = []
    prev_x = None
    for it, rest, p in infos:
        if not rest.strip(" :"):                                          # ô chỉ có ngày
            if not p:
                continue
            if entries and entries[-1]["period"] is None:
                entries[-1]["period"] = p
            elif not (entries and entries[-1]["period"].text == p.text):
                entries.append({"pieces": [], "period": p})
            continue
        lab = _edu_label(rest)
        new = not entries or (bool(entries[-1]["pieces"]) and not lab and (
            it.bullet or it.first.bold or (prev_x is not None and it.first.x0 < prev_x - 20)
            or (p is not None and entries[-1]["period"] is not None)))
        if new:
            entries.append({"pieces": [], "period": None})
        entries[-1]["pieces"].append((rest, lab))
        if p and entries[-1]["period"] is None:
            entries[-1]["period"] = p
        prev_x = it.first.x0
    return [e for e in (_edu_entry(x["pieces"], x["period"]) for x in entries) if e]


# Dựng mục học vấn: mỗi văn bằng một dòng (tên bằng – nơi cấp, năm)
def build_education(raw: RawSection, items: list[Item], today: date) -> Built:
    """Ý mới bắt đầu ở dòng có năm, gạch đầu dòng hoặc dòng đậm; dòng tiếp theo không có năm -> nối vào chi tiết.
    Bảng 'nội dung trước, ngày ở ô riêng' (ý đầu tiên không có ngày, có dòng chỉ có ngày) -> _education_content_led."""
    infos = [(it, *_cut_dates(it.first.text if len(it.lines) == 1 else it.plain, today)) for it in items]
    first = next((x for x in infos if x[1].strip(" :")), None)
    if first is not None and first[2] is None and any(not r.strip(" :") and p for _, r, p in infos):
        built = Built({"type": "education", "title": raw.title, "education": _education_content_led(infos)})
        for n, e in enumerate(built.section["education"]):
            if not e["period"]:
                built.confidence[f"education[{n}]"] = 0.65
        return built
    entries: list[list[Item]] = []
    for it in items:
        if not entries or it.bullet or it.first.bold or dates.find_period(it.plain, today):
            if entries and not it.bullet and not dates.find_period(it.plain, today) and len(entries[-1]) == 1 \
                    and dates.find_period(entries[-1][0].plain, today) and not entries[-1][0].plain.strip(" 0123456789/–-"):
                entries[-1].append(it)                           # dòng chỉ có năm, tên trường ở dòng sau
                continue
            entries.append([it])
        else:
            entries[-1].append(it)
    built = Built({"type": "education", "title": raw.title, "education": []})
    for n, group in enumerate(entries):
        text = " | ".join(i.first.text if len(i.lines) == 1 else i.plain for i in group)
        rest, p = cut_period(text, today)
        parts = parts_of(rest)
        if not parts:
            continue
        edu = rulebook.rules()["education"]
        deg = next((x for x in parts if rulebook.contains_any(x, edu["degree_words"])), None)
        not_school = next((x for x in parts if not rulebook.contains_any(x, edu["school_words"])), None)
        title = deg or not_school or parts[0]
        detail = " – ".join(x for x in parts if x != title) or None
        built.section["education"].append({"title": title, "detail": detail, "period": p.text if p else None})
        if not p:
            built.confidence[f"education[{len(built.section['education']) - 1}]"] = 0.65
    return built


# =============================================================================== Lộ trình, tham chiếu, thẻ, đoạn văn
# Dựng lộ trình sự nghiệp: thời gian – chức danh – công ty
def build_career_path(raw: RawSection, items: list[Item], today: date) -> Built:
    """Mỗi ý có khoảng thời gian là một dòng; ý không có thời gian bị bỏ qua và ghi cảnh báo."""
    built = Built({"type": "career_path", "title": raw.title, "career_path": []})
    for it in items:
        rest, p = cut_period(it.first.text if len(it.lines) == 1 else it.plain, today)
        if not p:
            built.notes.append(("", "có dòng không có mốc thời gian nên không đưa vào lộ trình"))
            continue
        comp, role, others = _assign_head([(x, it.first) for x in parts_of(rest)])
        built.section["career_path"].append({"period": p.text, "title": role or (others[0] if others else ""),
                                             "company": comp, "current": p.present})
    return built


# Dựng người tham chiếu: chỉ giữ họ tên, chức danh, công ty (SĐT/email bị bỏ)
def build_references(raw: RawSection, items: list[Item], removed: set[str]) -> Built:
    """Ý mới ở gạch đầu dòng/dòng đậm/dòng không có nhãn; 'Chức vụ: ...', 'Công ty: ...' gán vào người đang xét."""
    r = rulebook.rules()
    built = Built({"type": "references", "title": raw.title, "references": []})
    cur = None
    for it in items:
        lab = label_of(it.plain)
        if lab and rulebook.in_list(lab[0], r["labels"]["remove"]):
            removed.add(rulebook.rules()["_removed_index"].get(rulebook.norm(lab[0]), "phone"))
            continue
        if lab and cur is not None:
            key = rulebook.norm(lab[0])
            if key in ("chuc vu", "chuc danh", "vi tri", "position", "title"):
                cur["title"] = lab[1] or None
            elif key in ("cong ty", "don vi", "noi lam viec", "company", "organization"):
                cur["company"] = lab[1] or None
            continue
        if it.words > 30 or (it.words > 12 and not re.search(r" [–—|-] |,", it.plain)):
            continue                                                 # câu ghi chú, không phải một người
        parts = [x for p in parts_of(it.plain) for x in re.split(r"\s*,\s*", p) if x and not _contactish(x)]
        if lab and rulebook.norm(lab[0]) in ("ho ten", "ho va ten", "name", "full name"):
            parts = [lab[1]]
        if not parts:
            continue
        comp = next((x for x in parts[1:] if rulebook.contains_any(x, r["experience"]["company_words"])), None)
        title = next((x for x in parts[1:] if x != comp), None)
        cur = {"name": parts[0], "title": title, "company": comp}
        built.section["references"].append(cur)
    return built


# Chuỗi trông như SĐT/email/link (để bỏ khỏi thông tin người tham chiếu)
def _contactish(text: str) -> bool:
    return bool(re.search(r"@|https?://|www\.|(?:\+?84|0)[\d .\-]{8,}", text))


# Dựng mục thẻ (công cụ, phần mềm): tách theo dấu phẩy/chấm phẩy/gạch đứng
def build_tags(raw: RawSection, items: list[Item]) -> Built:
    """'Excel, Word; SAP | Misa' -> 4 thẻ. Ý dài (> 6 từ) giữ nguyên làm một thẻ."""
    tags = []
    for it in items:
        lab = label_of(it.plain)
        body = lab[1] if lab and lab[1] else it.plain
        for t in re.split(r"\s*[,;|•·]\s*", body):
            if t.strip() and t.strip() not in tags:
                tags.append(t.strip())
    return Built({"type": "tags", "title": raw.title, "tags": tags})


# Dựng mục đoạn văn (mục tiêu, giới thiệu)
def build_text(raw: RawSection, items: list[Item]) -> Built:
    """Ý liền nhau không có gạch đầu dòng gộp thành một đoạn; gạch đầu dòng là đoạn riêng."""
    paras: list[str] = []
    for it in items:
        if paras and not it.bullet and not paras[-1].endswith((".", "!", "?", ":")) and it.plain[:1].islower():
            paras[-1] += " " + it.text
        else:
            paras.append(it.text)
    return Built({"type": "text", "title": raw.title, "paragraphs": paras})


# Dựng mục gạch đầu dòng
def build_bullets(raw: RawSection, items: list[Item]) -> Built:
    """Mỗi ý là một gạch đầu dòng (CV không có ký hiệu đầu dòng thì mỗi dòng/ý là một gạch)."""
    return Built({"type": "bullets", "title": raw.title, "bullets": [it.text for it in items]})


# Dựng mục thẻ năng lực: tiêu đề nhóm + các ý bên dưới
def build_cards(raw: RawSection, items: list[Item]) -> Built:
    """Dùng khi mục có các tiêu đề nhóm ('Chuyên môn:', dòng đậm ngắn) theo sau là gạch đầu dòng."""
    cards: list[dict] = []
    for k, it in enumerate(items):
        nxt = items[k + 1] if k + 1 < len(items) else None
        lab = label_of(it.plain) if not it.bullet else None
        if _is_card_title(it, nxt):
            cards.append({"title": _group_title(it), "items": []})
        elif lab and lab[1] and not it.bullet and it.words <= 30:
            cards.append({"title": lab[0], "items": [x.strip() for x in re.split(r"\s*[,;]\s*", lab[1]) if x.strip()]})
        elif cards:
            cards[-1]["items"].append(it.text)
        else:
            cards.append({"title": "", "items": [it.text]})
    return Built({"type": "cards", "title": raw.title, "cards": [c for c in cards if c["title"] or c["items"]]})


# Tiêu đề thẻ: tiêu đề nhóm, hoặc dòng đậm ngắn mà dòng sau không đậm (thẻ không có ký hiệu đầu dòng)
def _is_card_title(it: Item, nxt: Item | None) -> bool:
    return _is_group_title(it, nxt) or (not it.bullet and it.words <= 6 and it.first.bold and nxt is not None
                                        and not nxt.first.bold)


# Mục có cấu trúc "tiêu đề nhóm + gạch đầu dòng" không (để chọn dạng thẻ)
def has_groups(items: list[Item]) -> bool:
    """Ít nhất 2 tiêu đề nhóm, hoặc 2 dòng 'Nhãn: a, b, c'."""
    groups = sum(1 for k, it in enumerate(items) if _is_card_title(it, items[k + 1] if k + 1 < len(items) else None))
    labeled = sum(1 for it in items if not it.bullet and (lab := label_of(it.plain)) and lab[1] and "," in lab[1])
    return groups >= 2 or labeled >= 2


# Bố cục dạng lưới (2+ thẻ/ô nằm cạnh nhau, cách nhau bằng khoảng trống lớn): tách ô, đọc theo từng cột
def split_grid(lines: list[Line]) -> list[Line]:
    """Chỉ áp dụng khi phần lớn dòng có nhiều ô. Hàng toàn chữ đậm (tiêu đề thẻ) mở một khối mới; trong khối đọc
    hết cột 1 rồi cột 2... Mỗi ô thành một dòng riêng (không bao giờ bị gộp như dòng bị ngắt)."""
    if not lines or sum("\t" in l.text for l in lines) * 2 < len(lines):
        return lines
    blocks: list[list[list[Line]]] = []
    for l in lines:
        cells, cur = [], []
        for s in l.spans + [Span("\t")]:
            if s.text == "\t":
                if "".join(x.text for x in cur).strip():
                    t = "".join(x.text for x in cur).strip()
                    cells.append(replace(l, text=t, spans=cur, bullet=l.bullet, cell=True))
                cur = []
            else:
                cur.append(s)
        if not cells:
            continue
        title_row = all(c.bold for c in cells) and len(cells) > 1
        if title_row or not blocks:
            blocks.append([])
        blocks[-1].append(cells)
    out: list[Line] = []
    if not any(len(rows[0]) > 1 and all(c.bold for c in rows[0]) for rows in blocks):
        return [c for rows in blocks for r in rows for c in r]      # không có hàng tiêu đề thẻ -> đọc theo hàng
    for rows in blocks:
        for c in range(max(len(r) for r in rows)):
            out += [r[c] for r in rows if c < len(r)]
    return out


# =============================================================================== Chọn loại mục
# Dựng một mục: chọn type theo bảng từ khoá + nội dung, ghi lý do khi không chắc
def build_section(raw: RawSection, today: date, removed: set[str]) -> Built:
    """Trả Built với độ tin cậy "" (cả mục) và các cảnh báo (đường dẫn tương đối trong mục)."""
    grid = raw.type in ("bullets", "tags") or (raw.type == "auto" and not any(_has_range(l.text) for l in raw.lines))
    items = logical_items(split_grid(raw.lines) if grid else raw.lines)
    typ, reason = raw.type, raw.reason
    if typ in ("experience", "auto"):
        b = build_experience(raw, items, today)
        if b:
            b.confidence.setdefault("", raw.confidence if typ == "experience" else 0.65)
            if typ == "auto":
                b.notes.append(("", "mục có mốc thời gian nên được dựng dạng kinh nghiệm/dự án — kiểm tra lại"))
            return _with_reason(b, reason)
        if typ == "experience":
            reason = "không thấy mốc thời gian nào nên chưa tách được từng công việc — các dòng để dạng gạch đầu dòng"
            raw.confidence = 0.4
        typ = "auto"
    if typ == "education":
        b = build_education(raw, items, today)
    elif typ == "career_path":
        b = build_career_path(raw, items, today)
    elif typ == "references":
        b = build_references(raw, items, removed)
    elif typ == "tags":
        b = build_tags(raw, items)
    elif typ == "text":
        b = build_bullets(raw, items) if items and sum(i.bullet for i in items) > len(items) / 2 else build_text(raw, items)
    elif has_groups(items):
        b = build_cards(raw, items)
    elif typ == "auto" and items and all(i.words <= 4 for i in items) and len(items) >= 4:
        b = build_tags(raw, items)
    else:
        b = build_bullets(raw, items)
    b.confidence.setdefault("", raw.confidence if raw.type != "auto" else min(raw.confidence, 0.65))
    return _with_reason(b, reason)


# Ghi lý do không chắc (nếu có) thành cảnh báo cho cả mục
def _with_reason(b: Built, reason: str) -> Built:
    if reason:
        b.notes.insert(0, ("", reason))
    return b
