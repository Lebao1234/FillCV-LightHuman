# Chuyển mô hình dịch Opus-MT (HuggingFace) sang định dạng CTranslate2 để app chạy offline
"""Chạy MỘT LẦN trên máy dev (cần thêm `transformers` và `torch`, KHÔNG cần trên máy chủ chạy app).

    cd system
    python -m pip install transformers torch
    python scripts/convert_opus_mt.py                                   # Helsinki-NLP/opus-mt-vi-en -> data/models/opus-mt-vi-en
    python scripts/convert_opus_mt.py --preset vinai                    # vinai/vinai-translate-vi2en-v2 -> data/models/vinai-vi2en
    python scripts/convert_opus_mt.py --model Helsinki-NLP/opus-mt-vi-en --out data/models/opus-mt-vi-en

Opus-MT: model.bin + source.spm + target.spm (khoảng 80-100 MB, lượng tử hoá int8). Nhẹ, chất lượng vừa.
VinAI (mBART, huấn luyện trên PhoMT): model.bin + sentencepiece.bpe.model (~0,4 GB, RAM ~1 GB). Dịch tốt hơn rõ rệt nhưng
dùng giấy phép AGPL-3.0: phải được duyệt giấy phép trước khi dùng thật (xem docs/dich-may-offline.md). Chép thư mục này lên
máy chủ (data/models/...) hoặc trỏ TRANSLATE_MODEL_DIR tới nó. Xem docs/dich-may-offline.md.
"""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


# Mô hình dựng sẵn: tên trên HuggingFace, thư mục xuất mặc định, file tách từ cần chép theo (cũng là file bắt buộc phải có)
PRESETS = {
    "opus": ("Helsinki-NLP/opus-mt-vi-en", "opus-mt-vi-en", ["source.spm", "target.spm"]),
    "opus-en-vi": ("Helsinki-NLP/opus-mt-en-vi", "opus-mt-en-vi", ["source.spm", "target.spm"]),   # chiều Anh -> Việt, Apache-2.0
    "vinai": ("vinai/vinai-translate-vi2en-v2", "vinai-vi2en", ["sentencepiece.bpe.model"]),
    "nllb": ("facebook/nllb-200-distilled-600M", "nllb-200-vi-en", ["sentencepiece.bpe.model"]),
}


# Chuyển một mô hình HuggingFace (Marian/mBART) sang CTranslate2 int8
def convert(model: str, out_dir: Path, quantization: str = "int8", copy_files: list[str] | None = None) -> Path:
    from ctranslate2.converters import TransformersConverter

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    converter = TransformersConverter(model, copy_files=copy_files or ["source.spm", "target.spm"])
    converter.convert(str(out_dir), quantization=quantization, force=True)
    return out_dir


# Điểm vào dòng lệnh
def main() -> int:
    parser = argparse.ArgumentParser(description="Chuyển mô hình dịch vi -> en sang CTranslate2")
    parser.add_argument("--preset", default="opus", choices=sorted(PRESETS),
                        help="opus (Việt->Anh, CC-BY 4.0), opus-en-vi (Anh->Việt, Apache-2.0), vinai (AGPL-3.0), nllb (CC-BY-NC 4.0: CẤM thương mại)")
    parser.add_argument("--model", help="ghi đè tên mô hình trên HuggingFace hoặc thư mục cục bộ")
    parser.add_argument("--out", help="ghi đè thư mục xuất (mặc định data/models/<tên preset>)")
    parser.add_argument("--quantization", default="int8", choices=["int8", "int8_float16", "float16", "float32"])
    args = parser.parse_args()
    model, dirname, copy_files = PRESETS[args.preset]
    out_dir = Path(args.out) if args.out else REPO_ROOT / "data" / "models" / dirname
    out = convert(args.model or model, out_dir, args.quantization, copy_files)
    missing = [f for f in ["model.bin", *copy_files] if not (out / f).is_file()]
    if missing:
        print(f"Chuyển xong nhưng thiếu file: {', '.join(missing)}", file=sys.stderr)
        return 1
    print(f"Đã chuyển xong: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
