# Đo tốc độ, RAM và xuất bảng đối chiếu để chấm chất lượng dịch máy vi -> en trên các hồ sơ JSON
"""Dùng để quyết định có dùng mô hình dịch này không (xem docs/dich-may-offline.md, mục "Kế hoạch thử nghiệm").

    cd system
    set PYTHONPATH=.                      (PowerShell: $env:PYTHONPATH='.')
    python scripts/benchmark_translation.py                                  # hồ sơ giả tests/fixtures/fake_candidate.json
    python scripts/benchmark_translation.py data/benchmark/*.json --dump data/benchmark/review.tsv

Mỗi file JSON là một hồ sơ (đúng schema CVData) hoặc file xuất của app (khoá "cv"). CV thật chỉ để trong data/ (không commit).
`--dump` ghi bảng đường dẫn / tiếng Việt / tiếng Anh / trạng thái để người đọc chấm: dùng ngay / sửa nhẹ / dịch lại.
"""
import argparse
import csv
import json
import os
import statistics
import sys
import time
from pathlib import Path

SYSTEM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SYSTEM_DIR))

from services.translation import nmt  # noqa: E402


# RAM của tiến trình hiện tại (MB); không có psutil thì trả None
def rss_mb() -> float | None:
    try:
        import psutil

        return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
    except ImportError:
        return None


# Đọc hồ sơ từ file JSON (hồ sơ trần hoặc file xuất của app)
def load_cv(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["cv"] if isinstance(data, dict) and "cv" in data and "sections" not in data else data


# Lấy giá trị chữ theo đường dẫn dạng "sections[0].jobs[1].role" để ghi bảng đối chiếu
def value_at(cv: dict, path: str):
    cur = cv
    for part in path.replace("]", "").replace("[", ".").split("."):
        cur = cur[int(part)] if part.isdigit() else cur[part]
    return cur


# Điểm vào dòng lệnh
def main() -> int:
    parser = argparse.ArgumentParser(description="Đo dịch máy vi -> en trên hồ sơ JSON")
    parser.add_argument("files", nargs="*", help="file JSON hồ sơ (mặc định: hồ sơ giả của test)")
    parser.add_argument("--dump", help="ghi bảng đối chiếu TSV để chấm chất lượng (chứa nội dung CV: đặt trong data/)")
    args = parser.parse_args()

    files = [Path(f) for f in args.files] or [SYSTEM_DIR / "tests" / "fixtures" / "fake_candidate.json"]
    if not nmt.is_available():
        print("Dịch máy chưa sẵn sàng: thiếu mô hình (TRANSLATE_MODEL_DIR) hoặc thư viện ctranslate2/sentencepiece.", file=sys.stderr)
        return 2

    before = rss_mb()
    t0 = time.perf_counter()
    nmt.translate_cv(load_cv(files[0]))   # lần đầu: gồm thời gian nạp mô hình
    first = time.perf_counter() - t0
    print(f"Nạp mô hình + dịch hồ sơ đầu: {first:.1f} giây")

    times, rows = [], []
    totals = {"translated": 0, "glossary": 0, "kept": 0, "skipped": 0}
    for f in files:
        cv = load_cv(f)
        nmt._cache.clear()                # đo thật, không dùng bộ nhớ tạm
        t = time.perf_counter()
        res = nmt.translate_cv(cv)
        times.append(time.perf_counter() - t)
        for k, v in res.summary().items():
            totals[k] += v
        for item in res.items:
            if item["status"] != "skipped":
                rows.append([f.name, item["path"], value_at(cv, item["path"]), value_at(res.cv, item["path"]),
                             item["status"], item["reason"], ""])
        print(f"- {f.name}: {times[-1]:.1f} giây, {res.summary()}")

    after = rss_mb()
    print(f"\nSố hồ sơ: {len(files)}; thời gian dịch trung bình {statistics.mean(times):.1f} giây, lớn nhất {max(times):.1f} giây")
    print(f"Tổng: {totals}")
    if before is not None and after is not None:
        print(f"RAM tiến trình: {before:.0f} MB -> {after:.0f} MB (tăng {after - before:.0f} MB)")
    else:
        print("Cài psutil để đo RAM: python -m pip install psutil")
    print(f"Mô hình: {nmt.engine_name()}")

    if args.dump:
        out = Path(args.dump)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            w.writerow(["file", "đường dẫn", "tiếng Việt", "tiếng Anh", "trạng thái", "lý do", "chấm (dùng ngay / sửa nhẹ / dịch lại)"])
            w.writerows(rows)
        print(f"Đã ghi bảng đối chiếu: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
