"""Đo chất lượng bộ đọc theo luật — CHỈ IN CON SỐ, không in nội dung CV (dùng được với CV thật).

    python -m services.extraction.rules.measure "duong/dan/cv.pdf"                 # CV thật: chỉ đếm, không có đáp án
    python -m services.extraction.rules.measure "cv_gia.pdf" --expect "dap_an.json" # CV giả có đáp án: tỉ lệ trường đúng

Đáp án là JSON đúng schema (vd tests/fixtures/*.json). So không phân biệt hoa/thường và bỏ dấu ** (template in hoa
tên công ty/tiêu đề mục; in đậm là định dạng, không phải nội dung).
"""
import json
import re
import sys
from datetime import date
from pathlib import Path


# Chuẩn hoá chuỗi để so: hạ chữ, bỏ **, gọn khoảng trắng
def _n(v) -> str:
    return re.sub(r"\s+", " ", str(v or "").replace("**", "")).strip().casefold()


# Các "điểm so" của một hồ sơ: [(nhóm, khoá, giá trị đã chuẩn hoá)]
def _facts(cv: dict) -> list[tuple[str, str, str]]:
    out = [("header", k, _n(cv.get(k))) for k in ("full_name", "target_title", "birth_year", "gender", "language")]
    out += [("header", "facts", _n(" | ".join(f"{f['label']}: {f['value']}" for f in cv.get("facts", []))))]
    out += [("stats", f"stats[{i}]", _n(f"{s['value']} | {s['label']}")) for i, s in enumerate(cv.get("stats", []))]
    for i, s in enumerate(cv["sections"]):
        out.append(("section", f"sections[{i}].type+title", _n(f"{s['type']} | {s['title']}")))
        for j, job in enumerate(s.get("jobs", [])):
            p = f"sections[{i}].jobs[{j}]"
            out += [("job", f"{p}.{k}", _n(job.get(k))) for k in ("company", "period", "role")]
            out += [("bullet", f"{p}.b{k}", _n(b)) for k, b in enumerate(x for g in job["groups"] for x in g["bullets"])]
            out += [("job", f"{p}.sub{k}", _n(f"{r['name']} | {r['period']}")) for k, r in enumerate(job["sub_roles"])]
        for key in ("paragraphs", "bullets", "tags"):
            out += [("bullet", f"sections[{i}].{key}[{k}]", _n(x)) for k, x in enumerate(s.get(key, []))]
        for k, e in enumerate(s.get("education", [])):
            out.append(("education", f"sections[{i}].education[{k}]", _n(f"{e['title']} | {e['detail']} | {e['period']}")))
        for k, c in enumerate(s.get("career_path", [])):
            out.append(("career", f"sections[{i}].career_path[{k}]", _n(f"{c['period']} | {c['title']} | {c['company']}")))
        for k, c in enumerate(s.get("cards", [])):
            out.append(("bullet", f"sections[{i}].cards[{k}]", _n(f"{c['title']} | {' / '.join(c['items'])}")))
        for k, r in enumerate(s.get("references", [])):
            out.append(("reference", f"sections[{i}].references[{k}]", _n(f"{r['name']} | {r['title']} | {r['company']}")))
    return out


# Chấm kết quả so với đáp án: {nhóm: (đúng, tổng)} + danh sách khoá sai
def score(got: dict, want: dict) -> tuple[dict[str, tuple[int, int]], list[str]]:
    """Một điểm so là đúng khi cùng khoá và cùng giá trị (đã chuẩn hoá)."""
    g = {k: v for _, k, v in _facts(got)}
    res: dict[str, list[int]] = {}
    wrong = []
    for group, k, v in _facts(want):
        ok = g.get(k) == v
        res.setdefault(group, [0, 0])
        res[group][0] += ok
        res[group][1] += 1
        if not ok:
            wrong.append(k)
    return {k: (a, b) for k, (a, b) in res.items()}, wrong


# Đếm cấu trúc của một kết quả (cho CV thật không có đáp án)
def counts(res) -> dict:
    """Số mục theo loại, số công việc/vị trí con/gạch đầu dòng, số trường dưới ngưỡng tin cậy, số cảnh báo."""
    from services.extraction import base
    cv = res.cv
    jobs = [j for s in cv["sections"] for j in s.get("jobs", [])]
    return {
        "giai_doan": [(s.key, s.status, round(s.seconds, 2)) for s in res.stages],
        "so_muc": len(cv["sections"]),
        "loai_muc": [s["type"] for s in cv["sections"]],
        "so_cong_viec": len(jobs),
        "cong_viec_thieu_ten_cong_ty": sum(not j["company"] for j in jobs),
        "cong_viec_thieu_chuc_danh": sum(not j["role"] for j in jobs),
        "cong_viec_thieu_thoi_gian": sum(not j["period"] for j in jobs),
        "so_vi_tri_con": sum(len(j["sub_roles"]) for j in jobs),
        "so_gach_dau_dong_cong_viec": sum(len(g["bullets"]) for j in jobs for g in j["groups"]),
        "co_ho_ten": cv["full_name"] != "Chưa nhập họ tên",
        "co_chuc_danh": bool(cv["target_title"]), "co_nam_sinh": bool(cv["birth_year"]),
        "so_o_so_lieu": len(cv["stats"]), "nguon_o_so_lieu": sorted({s["source"] for s in cv["stats"]}),
        "so_loai_thong_tin_da_bo": len(cv["model_notes"]["removed"]),
        "so_luu_y_tuyen_dung": len(cv["model_notes"]["recruiting_flags"]),
        "so_truong_tin_cay_thap": sum(v < base.REVIEW_THRESHOLD for v in res.confidence.values()),
        "so_canh_bao": len(res.warnings),
    }


# Chạy từ dòng lệnh: đọc một PDF, in con số (và điểm nếu có đáp án)
def main(argv: list[str]) -> int:
    """Không in nội dung CV — chỉ con số và đường dẫn trường (vd sections[2].jobs[0].role)."""
    sys.stdout.reconfigure(encoding="utf-8")
    from services.extraction import base
    from services.extraction.rules.extractor import RulesExtractor
    from services.privacy import checks
    pdf = Path(argv[0])
    res = RulesExtractor().extract(base.SourceDoc(pdf.read_bytes(), pdf.name, today=date.today()), lambda k: None)
    cv = base.validate(res.cv)
    out = counts(res)
    out["so_cho_con_thong_tin_lien_he"] = len(checks.scan_pii(cv))            # phải bằng 0
    for k, v in out.items():
        print(f"{k:32} {v}")
    print("truong_tin_cay_thap:", sorted(k for k, v in res.confidence.items() if v < base.REVIEW_THRESHOLD))
    if "--expect" in argv:
        want = json.loads(Path(argv[argv.index("--expect") + 1]).read_text(encoding="utf-8"))
        groups, wrong = score(cv, want)
        for g, (a, b) in groups.items():
            print(f"dung_{g:24} {a}/{b} ({a / b:.0%})")
        print("sai:", wrong)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
