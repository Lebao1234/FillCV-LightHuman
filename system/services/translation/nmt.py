# Dịch nội dung hồ sơ CV giữa tiếng Việt và tiếng Anh (dịch máy offline CTranslate2, hoặc online nếu được bật)
"""Dịch phần chữ tự do của hồ sơ (gạch đầu dòng, đoạn văn, chức danh, dòng phụ...) sang ngôn ngữ đích ("en" | "vi").

Chiều dịch: bộ offline (Opus-MT / VinAI vi2en) chỉ dịch vi -> en; bộ online dịch được cả hai chiều (supported_targets()).

Nguyên tắc (xem docs/dich-may-offline.md):
- Chạy hoàn toàn trên máy chủ: mô hình CTranslate2 nạp từ thư mục cục bộ, không gọi dịch vụ ngoài.
- KHÔNG đưa vào dịch máy: họ tên, tên công ty, tên trường, người tham chiếu, thẻ kỹ năng, thời gian, ô số liệu.
- Thứ tự: bảng thuật ngữ cố định (config/translation_glossary.toml, labels.translate_term) -> dịch máy cho phần còn lại.
- Mỗi đoạn dịch xong phải qua kiểm tra (số liệu giữ nguyên, độ dài hợp lý); không đạt thì GIỮ tiếng Việt và báo lại.
- Không bao giờ ghi nội dung CV vào log; báo cáo chỉ có đường dẫn trường + lý do.
"""
import copy
import hashlib
import importlib.util
import logging
import re
import threading
import tomllib
from functools import lru_cache
from dataclasses import dataclass, field
from typing import Iterator, Protocol

from infra import settings
from services.extraction.rules.translation import has_vi
from services.pdf import labels

# Giữ tên logger "app" như các module khác -> dòng log vẫn dạng "[run_id] app: ..."
log = logging.getLogger("app")

MAX_SEGMENTS = 600            # số đoạn tối đa một lượt dịch (CV bình thường vài chục đến vài trăm đoạn)
MAX_SEGMENT_CHARS = 400       # đoạn dài hơn thì tách theo câu trước khi dịch (mô hình giới hạn độ dài câu)
LENGTH_RATIO_MIN, LENGTH_RATIO_MAX = 0.3, 3.0   # tỉ lệ độ dài bản dịch / bản gốc, ngoài khoảng này coi là dịch hỏng
CACHE_MAX = 2000              # số đoạn nhớ trong bộ nhớ tiến trình (không ghi ra đĩa)

GLOSSARY_FILE = settings.PROJECT_ROOT / "config" / "translation_glossary.toml"

LANG_NAMES = {"vi": "tiếng Việt", "en": "tiếng Anh"}
# Loại hình doanh nghiệp Việt -> Anh (tiền tố tiếng Việt, hậu tố tiếng Anh); thứ tự: cụm dài trước cụm ngắn
_COMPANY_FORMS = [
    (r"công\s*ty\s+(?:tnhh|trách\s+nhiệm\s+hữu\s+hạn)\s+(?:mtv|một\s+thành\s+viên)", "One Member Co., Ltd."),
    (r"công\s*ty\s+(?:tnhh|trách\s+nhiệm\s+hữu\s+hạn)", "Co., Ltd."),
    (r"công\s*ty\s+(?:cp|cổ\s+phần)", "Joint Stock Company"),
    (r"cty\s+(?:tnhh)", "Co., Ltd."),
    (r"cty\s+(?:cp|cổ\s+phần)", "Joint Stock Company"),
    (r"ngân\s+hàng\s+(?:tmcp|thương\s+mại\s+cổ\s+phần)", "Joint Stock Commercial Bank"),
    (r"tổng\s+công\s+ty", "Corporation"),
    (r"tập\s+đoàn", "Group"),
    (r"doanh\s+nghiệp\s+tư\s+nhân", "Private Enterprise"),
    (r"công\s*ty|cty", "Company"),
]
_COMPANY_VI = [(re.compile(rf"^\s*(?:{pat})\b[\s.,:\-–]*(?P<name>.+?)\s*$", re.IGNORECASE), en) for pat, en in _COMPANY_FORMS]
# Chiều ngược Anh -> Việt: hậu tố tiếng Anh -> tiền tố tiếng Việt (cụm dài trước)
_COMPANY_EN = [
    (r"one\s+member\s+(?:co\.?,?\s*ltd\.?|company\s+limited|limited\s+liability\s+company)", "Công ty TNHH MTV"),
    (r"(?:co\.?,?\s*ltd\.?|company\s+limited|limited\s+liability\s+company|llc)", "Công ty TNHH"),
    (r"joint\s+stock\s+commercial\s+bank", "Ngân hàng TMCP"),
    (r"(?:joint\s+stock\s+company|jsc)", "Công ty Cổ phần"),
    (r"corporation|corp\.?", "Tổng công ty"),
    (r"group", "Tập đoàn"),
    (r"private\s+enterprise", "Doanh nghiệp tư nhân"),
    (r"company|co\.?", "Công ty"),
]
_COMPANY_EN_RE = [(re.compile(rf"^\s*(?P<name>.+?)[\s,]+(?:{pat})\s*$", re.IGNORECASE), vi) for pat, vi in _COMPANY_EN]

_PERIOD_PRESENT = re.compile(r"\b(?:Present|Now|Current|Currently|Today)\b", re.IGNORECASE)   # "Aug 2022 – Present" -> "Aug 2022 – Nay"
_LATIN_WORD = re.compile(r"[A-Za-z]{2,}")                                                      # có chữ để dịch (không chỉ số/ký hiệu)
_VI_WORD_RATIO = 0.4   # từ có dấu chiếm từ ngần này trở lên số từ thì đoạn coi là tiếng Việt (khi dịch sang vi)
_EN_FUNCTION_WORDS = re.compile(r"\b(?:the|and|for|with|of|at|by|from|using|in|to|on)\b")   # từ chức năng tiếng Anh (chữ thường)
_PERIOD_NOW = re.compile(r"\b(?:Hiện\s+nay|Hiện\s+tại|Nay|Đến\s+nay)\b", re.IGNORECASE)   # "03/2020 – Nay" -> "03/2020 – Present"

_SENTENCE_END = re.compile(r"(?<=[.!?;])\s+")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
_VN_MONEY = re.compile(r"đồng|vnd|vnđ|₫", re.IGNORECASE)          # tiền Việt trong bản gốc
_FOREIGN_MONEY = re.compile(r"\$|usd|dollar|€|£|euro", re.IGNORECASE)  # mô hình hay đổi "800 tỷ đồng" thành "$800 billion"


# Lỗi: chưa cài hoặc chưa bật dịch máy
class TranslatorUnavailable(RuntimeError):
    """Dịch máy chưa sẵn sàng (thiếu mô hình/thư viện hoặc bị tắt); thông điệp là câu tiếng Việt hiển thị cho người dùng."""


# Lỗi: chờ quá lâu tới lượt dịch
class TranslateQueueTimeout(RuntimeError):
    """Chờ quá lâu tới lượt dịch; thông điệp là câu tiếng Việt hiển thị cho người dùng."""


# Giao diện của một bộ dịch (để test thay bằng bản giả)
class Engine(Protocol):
    name: str

    # Dịch một danh sách câu sang ngôn ngữ đích "en" | "vi" (cùng thứ tự)
    def translate(self, texts: list[str], target: str = "en") -> list[str]: ...


# Bộ dịch thật loại Marian (Opus-MT): CTranslate2 (CPU, int8) + SentencePiece
class Ct2Engine:
    """Nạp mô hình Opus-MT đã chuyển sang CTranslate2 (model.bin + source.spm + target.spm). Dùng chung cả tiến trình."""

    online = False

    # Nạp mô hình và hai bộ tách từ; `target` = ngôn ngữ đích của mô hình ("en" cho opus-mt-vi-en, "vi" cho opus-mt-en-vi)
    def __init__(self, model_dir, threads: int, target: str = "en") -> None:
        import ctranslate2
        import sentencepiece

        self.name = f"{model_dir.name} (CTranslate2 int8)"
        self.targets = (target,)
        self._translator = ctranslate2.Translator(
            str(model_dir), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        self._src = sentencepiece.SentencePieceProcessor(model_file=str(model_dir / "source.spm"))
        self._tgt = sentencepiece.SentencePieceProcessor(model_file=str(model_dir / "target.spm"))

    # Dịch một lô câu theo chiều cố định của mô hình
    def translate(self, texts: list[str], target: str = "en") -> list[str]:
        if target not in self.targets:
            raise TranslatorUnavailable("Mô hình dịch này không dịch theo chiều được yêu cầu.")
        if target == "vi":
            return self._translate_en_vi(texts)
        # Bắt buộc có "</s>" cuối câu: thiếu thì mô hình không biết điểm dừng, dịch lặp từ đến hết 256 token (sai và chậm 30 lần)
        sources = [self._src.encode(t, out_type=str) + ["</s>"] for t in texts]
        results = self._translator.translate_batch(sources, beam_size=4, max_decoding_length=256)
        return [self._tgt.decode(r.hypotheses[0]).strip() for r in results]

    # Chiều Anh -> Việt (opus-mt-en-vi): mô hình lặp từ vô tận với cụm ngắn không có dấu câu (lỗi của chính mô hình gốc,
    # đã đối chiếu bằng transformers) -> thêm dấu chấm tạm, chặn lặp n-gram, giới hạn độ dài theo câu nguồn, rồi bỏ dấu chấm tạm
    def _translate_en_vi(self, texts: list[str]) -> list[str]:
        added = [not t.rstrip().endswith((".", "!", "?", ":", ";")) for t in texts]
        sources = [self._src.encode(t.rstrip() + ("." if a else ""), out_type=str) + ["</s>"] for t, a in zip(texts, added)]
        max_len = min(256, 3 * max((len(s) for s in sources), default=1) + 10)
        results = self._translator.translate_batch(
            sources, beam_size=4, max_decoding_length=max_len, no_repeat_ngram_size=3, repetition_penalty=1.2
        )
        out = []
        for r, a in zip(results, added):
            text = self._tgt.decode(r.hypotheses[0]).strip()
            out.append(text[:-1].rstrip() if a and text.endswith(".") else text)
        return out


# Bộ dịch thật loại mBART (VinAI Translate vi2en): cần sentencepiece.bpe.model, có mã ngôn ngữ vi_VN / en_XX
class Ct2MbartEngine:
    """Nạp mô hình VinAI vi2en đã chuyển sang CTranslate2 (model.bin + sentencepiece.bpe.model). Dùng chung cả tiến trình."""

    SPECIAL = {"</s>", "<s>", "<pad>", "vi_VN", "en_XX"}

    # Nạp mô hình và bộ tách từ từ thư mục mô hình
    def __init__(self, model_dir, threads: int) -> None:
        import ctranslate2
        import sentencepiece

        self.name = f"{model_dir.name} (CTranslate2 int8)"
        self._translator = ctranslate2.Translator(
            str(model_dir), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        self._sp = sentencepiece.SentencePieceProcessor(model_file=str(model_dir / "sentencepiece.bpe.model"))

    # Dịch một lô câu (mô hình chỉ có chiều vi -> en)
    def translate(self, texts: list[str], target: str = "en") -> list[str]:
        if target != "en":
            raise TranslatorUnavailable("Mô hình dịch offline hiện tại chỉ dịch tiếng Việt sang tiếng Anh.")
        # Đầu vào mBART: các mảnh + "</s>" + mã ngôn ngữ nguồn; đầu ra bắt đầu bằng mã ngôn ngữ đích (target_prefix)
        sources = [self._sp.encode(t, out_type=str) + ["</s>", "vi_VN"] for t in texts]
        results = self._translator.translate_batch(
            sources, target_prefix=[["en_XX"]] * len(sources), beam_size=4, max_decoding_length=256
        )
        return [self._sp.decode([p for p in r.hypotheses[0] if p not in self.SPECIAL]).strip() for r in results]


# Bộ dịch thật loại NLLB-200: cần sentencepiece.bpe.model, hỗ trợ cả 2 chiều vie_Latn <-> eng_Latn
class Ct2NllbEngine:
    """Nạp mô hình NLLB-200 đã chuyển sang CTranslate2 (model.bin + sentencepiece.bpe.model). Dùng chung cả tiến trình."""

    SPECIAL = {"</s>", "<s>", "<pad>", "<unk>", "vie_Latn", "eng_Latn"}
    targets = ("en", "vi")
    online = False
    _LANG_PAIR = {"en": ("vie_Latn", "eng_Latn"), "vi": ("eng_Latn", "vie_Latn")}

    # Nạp mô hình và bộ tách từ từ thư mục mô hình
    def __init__(self, model_dir, threads: int) -> None:
        import ctranslate2
        import sentencepiece

        self.name = f"{model_dir.name} (NLLB-200 CTranslate2 int8)"
        self._translator = ctranslate2.Translator(
            str(model_dir), device="cpu", compute_type="int8", inter_threads=1, intra_threads=threads
        )
        self._sp = sentencepiece.SentencePieceProcessor(model_file=str(model_dir / "sentencepiece.bpe.model"))

    # Dịch một lô câu theo chiều vi -> en hoặc en -> vi
    def translate(self, texts: list[str], target: str = "en") -> list[str]:
        if target not in self._LANG_PAIR:
            raise TranslatorUnavailable("Mô hình NLLB-200 chỉ hỗ trợ dịch Việt ↔ Anh.")
        src_lang, tgt_lang = self._LANG_PAIR[target]
        sources = [[src_lang] + self._sp.encode(t, out_type=str) + ["</s>"] for t in texts]
        results = self._translator.translate_batch(
            sources, target_prefix=[[tgt_lang]] * len(sources), beam_size=4, max_decoding_length=256
        )
        return [self._sp.decode([p for p in r.hypotheses[0] if p not in self.SPECIAL]).strip() for r in results]


# Ghép hai mô hình một chiều (vd Opus-MT vi-en + en-vi) thành một bộ dịch hai chiều
class PairEngine:
    """Chọn mô hình theo ngôn ngữ đích; mỗi mô hình chỉ dịch một chiều."""

    online = False

    # Nhận các bộ dịch con, mỗi bộ có thuộc tính targets
    def __init__(self, *engines) -> None:
        self._by_target = {t: e for e in engines for t in e.targets}
        self.targets = tuple(self._by_target)
        self.name = " + ".join(e.name for e in engines)

    # Dịch bằng mô hình ứng với ngôn ngữ đích
    def translate(self, texts: list[str], target: str = "en") -> list[str]:
        if target not in self._by_target:
            raise TranslatorUnavailable("Chưa có mô hình dịch cho chiều này trên máy chủ.")
        return self._by_target[target].translate(texts, target)


# Kiểm tra nhanh bộ từ vựng có phải NLLB-200 (chứa token vie_Latn) không
def _is_nllb_dir(model_dir) -> bool:
    for name in ("shared_vocabulary.json", "shared_vocabulary.txt"):
        vocab_file = model_dir / name
        if vocab_file.is_file() and "vie_Latn" in vocab_file.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


# Loại mô hình trong thư mục: "marian" (Opus-MT), "nllb" (NLLB-200), "mbart" (VinAI) hoặc None nếu thiếu file
def model_kind(model_dir) -> str | None:
    if not (model_dir / "model.bin").is_file():
        return None
    if (model_dir / "source.spm").is_file() and (model_dir / "target.spm").is_file():
        return "marian"
    if (model_dir / "sentencepiece.bpe.model").is_file():
        return "nllb" if _is_nllb_dir(model_dir) else "mbart"
    return None


_engine: Engine | None = None
_engine_lock = threading.Lock()
_slots = threading.BoundedSemaphore(settings.translate_max_concurrent())
_cache: dict[str, str] = {}
_cache_lock = threading.Lock()


# Gắn bộ dịch (dùng cho test); None = quay về nạp mô hình thật
def set_engine(engine: Engine | None) -> None:
    global _engine
    with _engine_lock:
        _engine = engine
    with _cache_lock:
        _cache.clear()


# Mô hình và thư viện đã đủ để dịch chưa (kiểm tra nhẹ, chưa nạp mô hình)
def is_available() -> bool:
    """True khi dịch máy được bật và (đã gắn bộ dịch HOẶC thư mục mô hình + thư viện đã đủ)."""
    if settings.translator_name() == "none":
        return False
    if _engine is not None:
        return True
    if model_kind(settings.translate_model_dir()) is None:
        return False
    return all(importlib.util.find_spec(m) is not None for m in ("ctranslate2", "sentencepiece"))


# Các ngôn ngữ đích bộ dịch hiện tại dịch sang được: NLLB-200 hỗ trợ ("en", "vi"), Opus-MT/VinAI chỉ ("en",)
def supported_targets() -> tuple[str, ...]:
    if not is_available():
        return ()
    if _engine is not None:
        return tuple(getattr(_engine, "targets", ("en",)))
    if model_kind(settings.translate_model_dir()) == "nllb":
        return ("en", "vi")
    return ("en", "vi") if model_kind(settings.translate_model_dir_en_vi()) == "marian" else ("en",)


# Bộ dịch hiện tại có gửi nội dung ra ngoài máy chủ không (luôn False vì chỉ chạy offline)
def is_online() -> bool:
    return bool(getattr(_engine, "online", False)) if _engine is not None else False


# Tên bộ dịch đang dùng (để báo trên giao diện)
def engine_name() -> str:
    return _engine.name if _engine is not None else settings.translate_model_dir().name


# Lấy bộ dịch, nạp mô hình ở lần dùng đầu tiên
def _get_engine() -> Engine:
    global _engine
    with _engine_lock:
        if _engine is None:
            if not is_available():
                raise TranslatorUnavailable(
                    "Chưa bật dịch máy trên máy chủ (thiếu mô hình dịch). Xem docs/dich-may-offline.md để cài."
                )
            model_dir = settings.translate_model_dir()
            kind = model_kind(model_dir)
            engine_cls = {"nllb": Ct2NllbEngine, "mbart": Ct2MbartEngine}.get(kind, Ct2Engine)
            try:
                main = engine_cls(model_dir, settings.translate_threads())
                envi_dir = settings.translate_model_dir_en_vi()
                if kind != "nllb" and model_kind(envi_dir) == "marian":
                    # Thêm mô hình chiều Anh -> Việt nếu có (Opus-MT en-vi)
                    _engine = PairEngine(main, Ct2Engine(envi_dir, settings.translate_threads(), target="vi"))
                else:
                    _engine = main
            except Exception as e:   # DLL bị chặn (Application Control), mô hình hỏng, thiếu RAM...
                log.error("Không nạp được mô hình dịch máy (%s): %s", type(e).__name__, e)
                raise TranslatorUnavailable(
                    "Không nạp được mô hình dịch máy trên máy chủ (thư viện bị chặn hoặc mô hình hỏng). Hãy báo quản trị viên."
                ) from e
            log.info("Đã nạp mô hình dịch máy: %s", _engine.name)
        return _engine


# Khoá tra bảng thuật ngữ: bỏ hoa/thường, khoảng trắng thừa, dấu ":" "." cuối; GIỮ dấu tiếng Việt
def _gkey(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().rstrip(":.").strip().casefold()


# Đọc bảng thuật ngữ cố định (cache; đổi file thì phải khởi động lại app)
@lru_cache(maxsize=1)
def _glossary() -> dict[str, str]:
    data = tomllib.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
    return {_gkey(k): v for k, v in data.get("phrases", {}).items()}


# Tra bảng thuật ngữ cho nguyên đoạn; không có trả None
def glossary_lookup(text: str) -> str | None:
    """'Kế toán trưởng' -> 'Chief Accountant'; 'KẾ TOÁN TRƯỞNG' -> 'CHIEF ACCOUNTANT'; cụm lạ -> None."""
    hit = _glossary().get(_gkey(text))
    if hit and text.strip().isupper():
        return hit.upper()
    return hit


# Bảng thuật ngữ tra ngược en -> vi (cụm tiếng Anh trùng nhau thì lấy cụm tiếng Việt khai báo trước)
@lru_cache(maxsize=1)
def _glossary_reverse() -> dict[str, str]:
    data = tomllib.loads(GLOSSARY_FILE.read_text(encoding="utf-8"))
    table: dict[str, str] = {}
    for vi, en in data.get("phrases", {}).items():
        table.setdefault(_gkey(en), vi)
    return table


# Tra bảng thuật ngữ theo chiều dịch; không có trả None
def glossary_lookup_to(text: str, target: str) -> str | None:
    """target="en": như glossary_lookup. target="vi": 'Chief Accountant' -> 'Kế toán trưởng' (viết hoa chữ đầu)."""
    if target == "en":
        return glossary_lookup(text)
    hit = _glossary_reverse().get(_gkey(text))
    if not hit:
        return None
    return hit.upper() if text.strip().isupper() else hit[:1].upper() + hit[1:]


# Một đoạn chữ trong hồ sơ cần xét dịch: vị trí + nơi giữ giá trị
@dataclass
class Slot:
    path: str
    holder: dict | list
    key: str | int
    kind: str = "text"            # "text": dịch máy được | "term": chỉ tra bảng thuật ngữ | "title": tiêu đề mục chuẩn
    split: str | None = None      # chuỗi nhiều phần ngăn bằng ký tự này (vd " · "): tra bảng từng phần

    # Giá trị chữ hiện tại của đoạn
    @property
    def text(self) -> str:
        return self.holder[self.key]

    # Ghi bản dịch vào hồ sơ
    def set(self, value: str) -> None:
        self.holder[self.key] = value


_MONTHS_EN = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MON_EN = r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_EN_MDY = re.compile(_MON_EN + r"\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{4})\b", re.IGNORECASE)              # June 16, 2021
_EN_DMY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MON_EN + r"\s*,?\s*(\d{4})\b", re.IGNORECASE)  # 16 June 2021
_EN_MY = re.compile(_MON_EN + r"\s*,?\s*(\d{4})\b", re.IGNORECASE)                                            # Jan 2019


# Ngày tiếng Anh trong khoảng thời gian -> dạng số kiểu Việt: "June 16, 2021" -> "16/06/2021", "Jan 2019" -> "01/2019"
def _english_dates_to_vi(text: str) -> str:
    def mon(name: str) -> int:
        return _MONTHS_EN[name[:3].lower()]

    text = _EN_MDY.sub(lambda m: f"{int(m.group(2)):02d}/{mon(m.group(1)):02d}/{m.group(3)}", text)
    text = _EN_DMY.sub(lambda m: f"{int(m.group(1)):02d}/{mon(m.group(2)):02d}/{m.group(3)}", text)
    return _EN_MY.sub(lambda m: f"{mon(m.group(1)):02d}/{m.group(2)}", text)


# Loại văn bằng tiếng Anh -> tiếng Việt (mẫu ở ĐẦU tên bằng; cụm dài trước cụm ngắn)
_DEGREE_EN = [
    (r"(?:master\s+of\s+business\s+administration|mba)\b", "Thạc sĩ Quản trị kinh doanh"),
    (r"(?:doctor\s+of\s+philosophy|ph\.?\s?d\.?)(?:\s+(?:in|of))?\b", "Tiến sĩ"),
    (r"(?:master(?:'s)?(?:\s+degree)?(?:\s+of\s+(?:science|arts))?|m\.?sc\.?|m\.?a\.?)(?:\s+(?:in|of))?\b", "Thạc sĩ"),
    (r"bachelor\s+of\s+engineering(?:\s+in)?\b", "Kỹ sư"),
    (r"(?:bachelor(?:'s)?(?:\s+degree)?(?:\s+of\s+(?:science|arts))?|b\.?sc\.?|b\.?a\.?)(?:\s+(?:in|of))?\b", "Cử nhân"),
    (r"(?:associate(?:'s)?\s+degree)(?:\s+(?:in|of))?\b", "Cao đẳng"),
    (r"(?:certificate|certification)(?:\s+(?:in|of|on))?\b", "Chứng chỉ"),
    (r"diploma(?:\s+(?:in|of))?\b", "Văn bằng"),
]
_DEGREE_EN_RE = [(re.compile(rf"^\s*{pat}\s*(?P<field>.*?)\s*$", re.IGNORECASE), vi) for pat, vi in _DEGREE_EN]
# Ngành học thường gặp (tiếng Anh -> tiếng Việt); không có trong bảng thì giữ nguyên tiếng Anh
_FIELDS_EN = {
    "business administration": "Quản trị kinh doanh", "accounting": "Kế toán", "finance": "Tài chính",
    "finance and banking": "Tài chính – Ngân hàng", "banking and finance": "Tài chính – Ngân hàng",
    "economics": "Kinh tế", "marketing": "Marketing", "human resources": "Quản trị nhân lực",
    "human resource management": "Quản trị nhân lực", "computer science": "Khoa học máy tính",
    "information technology": "Công nghệ thông tin", "law": "Luật", "english": "Ngôn ngữ Anh",
    "english language": "Ngôn ngữ Anh", "international business": "Kinh doanh quốc tế",
    "international relations": "Quan hệ quốc tế", "hospitality management": "Quản trị khách sạn",
    "tourism": "Du lịch", "logistics and supply chain management": "Logistics và Quản lý chuỗi cung ứng",
    "supply chain management": "Quản lý chuỗi cung ứng", "mechanical engineering": "Kỹ thuật cơ khí",
    "electrical engineering": "Kỹ thuật điện", "civil engineering": "Kỹ thuật xây dựng", "auditing": "Kiểm toán",
    "public relations": "Quan hệ công chúng", "psychology": "Tâm lý học", "education": "Giáo dục",
}


# Tên văn bằng tiếng Anh -> tiếng Việt: "Bachelor of Business Administration" -> "Cử nhân Quản trị kinh doanh";
# ngành không có trong bảng thì giữ nguyên ("Certificate in Internal Communication" -> "Chứng chỉ Internal Communication")
def degree_to_vi(text: str) -> str | None:
    src = (text or "").strip()
    for pat, vi in _DEGREE_EN_RE:
        m = pat.match(src)
        if m:
            field = m.group("field").strip(" ,–-:")
            field_vi = _FIELDS_EN.get(_gkey(field)) or glossary_lookup_to(field, "vi") or field
            return f"{vi} {field_vi}".strip()
    return None


# Dịch tên công ty theo luật cố định: chỉ đổi loại hình doanh nghiệp, giữ nguyên tên riêng (không qua dịch máy)
def translate_company(text: str, target: str = "en") -> str:
    """'CÔNG TY CỔ PHẦN MISA' -> 'MISA JOINT STOCK COMPANY'; 'Công ty TNHH Nhựa Thanh Khê' -> 'Nhựa Thanh Khê Co., Ltd.'.
    target='vi': 'MISA Joint Stock Company' -> 'Công ty Cổ phần MISA'. Không khớp mẫu nào -> giữ nguyên."""
    src = (text or "").strip()
    if not src:
        return text
    upper = src.isupper()
    if target == "en":
        for pat, form in _COMPANY_VI:
            m = pat.match(src)
            if m and m.group("name").strip(" .,-–"):
                out = f"{m.group('name').strip(' .,-–')} {form}"
                return out.upper() if upper else out
        return text
    for pat, form in _COMPANY_EN_RE:
        m = pat.match(src)
        if m and m.group("name").strip(" .,-–"):
            out = f"{form} {m.group('name').strip(' .,-–')}"
            return out.upper() if upper else out
    return text


# Mọi đoạn chữ trong danh sách chuỗi của một đối tượng
def _list_slots(obj: dict, field_name: str, path: str) -> Iterator[Slot]:
    items = obj.get(field_name)
    if isinstance(items, list):
        for i, v in enumerate(items):
            if isinstance(v, str):
                yield Slot(f"{path}.{field_name}[{i}]", items, i)


# Đoạn chữ của một trường chuỗi đơn
def _field_slot(obj: dict, field_name: str, path: str, kind: str = "text", split: str | None = None) -> Iterator[Slot]:
    if isinstance(obj.get(field_name), str):
        yield Slot(f"{path}.{field_name}" if path else field_name, obj, field_name, kind, split)


# Các dòng phụ (nhãn + nội dung) của công việc / vị trí con
def _meta_slots(meta, path: str) -> Iterator[Slot]:
    for i, m in enumerate(meta or []):
        yield from _field_slot(m, "label", f"{path}[{i}]")
        yield from _field_slot(m, "text", f"{path}[{i}]")


# Các nhóm việc (tiêu đề nhóm + gạch đầu dòng)
def _group_slots(groups, path: str) -> Iterator[Slot]:
    for i, g in enumerate(groups or []):
        yield from _field_slot(g, "title", f"{path}[{i}]")
        yield from _list_slots(g, "bullets", f"{path}[{i}]")


# Mọi đoạn chữ ĐƯỢC PHÉP dịch của hồ sơ (không gồm tên riêng, công ty, trường, thẻ kỹ năng, thời gian, số liệu)
def collect_slots(cv: dict) -> list[Slot]:
    """Danh sách đoạn chữ cần xét dịch, theo thứ tự xuất hiện trong hồ sơ (sửa trực tiếp `cv` truyền vào)."""
    slots: list[Slot] = list(_field_slot(cv, "target_title", ""))
    # Giới tính, nhãn + giá trị dòng thông tin, ô số liệu: chỉ tra bảng thuật ngữ (không đưa tên riêng/số liệu vào dịch máy)
    slots += _field_slot(cv, "gender", "", "term")
    for fi, f in enumerate(cv.get("facts") or []):
        slots += _field_slot(f, "label", f"facts[{fi}]", "term")
        slots += _field_slot(f, "value", f"facts[{fi}]", "term", " · ")
    for si, s in enumerate(cv.get("stats") or []):
        slots += _field_slot(s, "value", f"stats[{si}]", "term")
        slots += _field_slot(s, "label", f"stats[{si}]")          # nhãn ô số liệu là câu ngắn: cho dịch máy (có kiểm tra số)
    for si, sec in enumerate(cv.get("sections") or []):
        sp = f"sections[{si}]"
        slots += _field_slot(sec, "title", sp, "title")
        for ti in range(len(sec.get("tags") or [])):
            if isinstance(sec["tags"][ti], str):
                slots.append(Slot(f"{sp}.tags[{ti}]", sec["tags"], ti, "term"))
        slots += _list_slots(sec, "paragraphs", sp)
        slots += _list_slots(sec, "bullets", sp)
        for ci, c in enumerate(sec.get("cards") or []):
            slots += _field_slot(c, "title", f"{sp}.cards[{ci}]")
            slots += _list_slots(c, "items", f"{sp}.cards[{ci}]")
        for ci, c in enumerate(sec.get("career_path") or []):
            slots += _field_slot(c, "title", f"{sp}.career_path[{ci}]")
            slots += _field_slot(c, "company", f"{sp}.career_path[{ci}]", "company")
            slots += _field_slot(c, "period", f"{sp}.career_path[{ci}]", "period")
        for ei, e in enumerate(sec.get("education") or []):
            slots += _field_slot(e, "title", f"{sp}.education[{ei}]")
            slots += _field_slot(e, "period", f"{sp}.education[{ei}]", "period")
        for ri, r in enumerate(sec.get("references") or []):
            slots += _field_slot(r, "title", f"{sp}.references[{ri}]")
            slots += _field_slot(r, "company", f"{sp}.references[{ri}]", "company")
        for ji, job in enumerate(sec.get("jobs") or []):
            jp = f"{sp}.jobs[{ji}]"
            slots += _field_slot(job, "role", jp)
            slots += _field_slot(job, "company", jp, "company")
            slots += _field_slot(job, "period", jp, "period")
            slots += _meta_slots(job.get("meta"), f"{jp}.meta")
            slots += _group_slots(job.get("groups"), f"{jp}.groups")
            for ri, sub in enumerate(job.get("sub_roles") or []):
                rp = f"{jp}.sub_roles[{ri}]"
                slots += _field_slot(sub, "name", rp)
                slots += _field_slot(sub, "period", rp, "period")
                slots += _meta_slots(sub.get("meta"), f"{rp}.meta")
                slots += _group_slots(sub.get("groups"), f"{rp}.groups")
    return slots


# Các dãy số trong đoạn chữ (bỏ dấu chấm/phẩy phân cách để "1.000" và "1,000" coi như nhau)
def _numbers(text: str) -> list[str]:
    return sorted(re.sub(r"[.,]", "", n) for n in _NUMBER.findall(text))


# Bản dịch có đạt kiểm tra không; trả (đạt, lý do nếu không đạt)
def check_translation(source: str, target: str, target_lang: str = "en") -> tuple[bool, str]:
    """Số liệu phải giữ nguyên (không mất/đổi/thêm số), bản dịch không rỗng, độ dài hợp lý, không chép nguyên bản gốc."""
    if not target.strip():
        return False, "bản dịch rỗng"
    if target.strip() == source.strip():
        return False, "mô hình không dịch được"
    if _numbers(source) != _numbers(target):
        return False, "số liệu không khớp bản gốc"
    if target_lang == "en" and _VN_MONEY.search(source) and _FOREIGN_MONEY.search(target):
        return False, "đổi đơn vị tiền tệ (đồng thành ngoại tệ)"
    ratio = len(target) / max(1, len(source))
    if not (LENGTH_RATIO_MIN <= ratio <= LENGTH_RATIO_MAX):
        return False, "độ dài bản dịch bất thường"
    return True, ""


# Tách đoạn dài thành các câu để mô hình dịch được
def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_SEGMENT_CHARS:
        return [text]
    parts, cur = [], ""
    for sentence in _SENTENCE_END.split(text):
        if cur and len(cur) + len(sentence) + 1 > MAX_SEGMENT_CHARS:
            parts.append(cur)
            cur = sentence
        else:
            cur = f"{cur} {sentence}".strip()
    if cur:
        parts.append(cur)
    return parts


# Mã băm của đoạn chữ làm khoá nhớ tạm
def _key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Dịch danh sách đoạn (đã khử trùng, có nhớ tạm) bằng bộ dịch
def _translate_texts(engine: Engine, texts: list[str], target: str = "en") -> dict[str, str]:
    out: dict[str, str] = {}
    pending: list[str] = []
    with _cache_lock:
        for t in dict.fromkeys(texts):
            hit = _cache.get(_key(f"{target}:{t}"))
            if hit is not None:
                out[t] = hit
            else:
                pending.append(t)
    if pending:
        pieces = [(t, _split_long(t)) for t in pending]
        flat = [p for _, ps in pieces for p in ps]
        translated = engine.translate(flat, target=target)
        if len(translated) != len(flat):
            raise RuntimeError("Bộ dịch trả số câu không khớp")
        it = iter(translated)
        with _cache_lock:
            if len(_cache) > CACHE_MAX:
                _cache.clear()
            for t, ps in pieces:
                out[t] = " ".join(next(it) for _ in ps)
                _cache[_key(f"{target}:{t}")] = out[t]
    return out


# Kết quả dịch một hồ sơ
@dataclass
class TranslateResult:
    cv: dict
    engine: str
    items: list[dict] = field(default_factory=list)   # [{path, status, reason}] — KHÔNG chứa nội dung CV

    # Đếm số đoạn theo trạng thái
    def count(self, status: str) -> int:
        return sum(1 for i in self.items if i["status"] == status)

    # Tóm tắt số lượng để trả cho giao diện
    def summary(self) -> dict:
        return {
            "translated": self.count("translated"),
            "glossary": self.count("glossary"),
            "kept": self.count("kept"),
            "skipped": self.count("skipped"),
        }


# Ghi chú vào model_notes để nhân viên biết phải đọc lại (ô "Đã kiểm tra các mục hệ thống tự lập")
def _add_notes(cv: dict, result: TranslateResult, target: str = "en") -> None:
    notes = cv.setdefault("model_notes", {})
    src_name, tgt_name = LANG_NAMES["vi" if target == "en" else "en"], LANG_NAMES[target]
    done = result.count("translated")
    kept = result.count("kept")
    if done:
        msg = f"Dịch máy {src_name} sang {tgt_name} {done} đoạn nội dung (offline) — cần đọc lại toàn bộ trước khi gửi khách"
        notes.setdefault("self_created", [])
        if msg not in notes["self_created"]:
            notes["self_created"].append(msg)
    if kept:
        msg = f"{kept} đoạn giữ nguyên {src_name} vì bản dịch máy không đạt kiểm tra (số liệu/độ dài) — cần tự dịch"
        notes.setdefault("other", [])
        if msg not in notes["other"]:
            notes["other"].append(msg)


# Dịch một đoạn chỉ bằng bảng thuật ngữ / bảng nhãn / tiêu đề chuẩn; không có trong bảng -> None
def _term_only(slot: Slot, text: str, target: str = "en") -> str | None:
    def one(t: str) -> str:
        t = t.strip()
        if slot.kind == "company":    # chỉ đổi loại hình doanh nghiệp, tên riêng giữ nguyên
            return translate_company(t, target)
        if slot.kind == "period":     # chỉ đổi chữ chỉ "đến nay"; ngày tháng giữ nguyên
            return _PERIOD_NOW.sub("Present", t) if target == "en" else _english_dates_to_vi(_PERIOD_PRESENT.sub("Nay", t))
        if slot.kind == "title":
            return labels.translate_title(t, target)
        return glossary_lookup_to(t, target) or labels.translate_term(t, target) or t

    if slot.split:
        parts = [one(p) for p in text.split(slot.split)]
        return slot.split.join(parts)
    return one(text)


# Nạp sẵn mô hình (gọi lúc khởi động, chạy nền): lỗi chỉ ghi log, lần dịch đầu sẽ báo lại
def preload() -> bool:
    if not is_available():
        return False
    try:
        _get_engine()
        return True
    except TranslatorUnavailable:
        return False


# Đoạn chữ đã ở ngôn ngữ đích (không cần dịch) hay chưa
def _already_in(text: str, target: str) -> bool:
    """target="en": đoạn không có dấu tiếng Việt coi là đã tiếng Anh (hoặc gõ không dấu).
    target="vi": đoạn có dấu tiếng Việt coi là đã tiếng Việt; đoạn không có chữ Latin (chỉ số/ký hiệu) cũng bỏ qua."""
    if target == "en":
        return not has_vi(text)
    words = [w for w in text.split() if _LATIN_WORD.search(w) or has_vi(w)]
    if not words or not _LATIN_WORD.search(text):
        return True
    # Câu tiếng Anh chèn tên riêng có dấu ("Led team at Công ty ABC", "... for Tập đoàn Hòa Phát in Hà Nội") không được
    # coi là tiếng Việt: có từ chức năng tiếng Anh, hoặc tỉ lệ từ có dấu thấp
    if _EN_FUNCTION_WORDS.search(text):
        return False
    return sum(1 for w in words if has_vi(w)) / len(words) >= _VI_WORD_RATIO


# Dịch toàn bộ nội dung tự do của hồ sơ sang ngôn ngữ đích ("en": vi -> en, "vi": en -> vi)
def translate_cv(cv: dict, target: str = "en") -> TranslateResult:
    """Trả bản sao hồ sơ đã dịch + báo cáo từng đoạn. `cv` truyền vào giữ nguyên.

    `target` phải nằm trong supported_targets() nếu có đoạn cần dịch máy (bộ offline chỉ dịch sang "en").

    Chờ tới lượt (TRANSLATE_MAX_CONCURRENT); quá TRANSLATE_QUEUE_TIMEOUT giây -> TranslateQueueTimeout.
    """
    work = copy.deepcopy(cv)
    slots = collect_slots(work)
    if len(slots) > MAX_SEGMENTS:
        raise TranslatorUnavailable(f"Hồ sơ có {len(slots)} đoạn chữ, vượt giới hạn dịch {MAX_SEGMENTS} đoạn.")
    result = TranslateResult(cv=work, engine=engine_name())

    # 1) Phân loại: bỏ qua / bảng thuật ngữ / cần dịch máy
    to_translate: list[Slot] = []
    for slot in slots:
        text = slot.text.strip()
        if not text:
            continue
        if slot.kind != "text":
            # Chỉ tra bảng: không có trong bảng thì giữ nguyên, không báo (tên riêng, thẻ lạ...)
            new = _term_only(slot, text, target)
            if new is not None and new != text:
                slot.set(new)
                result.items.append({"path": slot.path, "status": "glossary", "reason": ""})
            continue
        if target == "vi" and ".education[" in slot.path and slot.path.endswith(".title"):
            # Tên văn bằng tiếng Anh: dịch máy hay sai hẳn nghĩa ("Bachelor of ..." -> "Một phần của thế giới") -> luật cố định
            degree = degree_to_vi(text)
            if degree:
                slot.set(degree)
                result.items.append({"path": slot.path, "status": "glossary", "reason": ""})
                continue
        if _already_in(text, target):
            reason = ("không có dấu tiếng Việt (đã là tiếng Anh hoặc gõ không dấu)" if target == "en"
                      else "đã là tiếng Việt hoặc không có chữ để dịch")
            result.items.append({"path": slot.path, "status": "skipped", "reason": reason})
            continue
        term = glossary_lookup_to(text, target) or labels.translate_term(text, target)
        if term and term != text:
            slot.set(term)
            result.items.append({"path": slot.path, "status": "glossary", "reason": ""})
            continue
        to_translate.append(slot)

    # 2) Dịch máy phần còn lại (cần bộ dịch; không có đoạn nào cần dịch thì khỏi nạp mô hình)
    if to_translate:
        if not _slots.acquire(timeout=settings.translate_queue_timeout()):
            raise TranslateQueueTimeout(
                f"Đang có người khác dịch, đã chờ quá {settings.translate_queue_timeout()} giây. Vui lòng bấm dịch lại sau ít phút."
            )
        try:
            engine = _get_engine()
            result.engine = engine.name
            if target not in getattr(engine, "targets", ("en",)):
                raise TranslatorUnavailable(
                    f"Bộ dịch hiện tại ({engine.name}) chưa dịch được sang {LANG_NAMES.get(target, target)}."
                )
            # Bỏ dấu in đậm **...** trước khi dịch (mô hình làm hỏng ký hiệu này)
            sources = {s.path: s.text.strip().replace("**", "") for s in to_translate}
            translated = _translate_texts(engine, list(sources.values()), target)
        finally:
            _slots.release()
        for slot in to_translate:
            src = sources[slot.path]
            out = translated[src].strip()
            if target == "vi" and out == src:
                # Sang tiếng Việt: tên riêng/thuật ngữ thường được giữ nguyên, không coi là lỗi
                result.items.append({"path": slot.path, "status": "skipped", "reason": "giữ nguyên (tên riêng hoặc thuật ngữ)"})
                continue
            ok, reason = check_translation(src, out, target)
            if ok:
                slot.set(out)
                result.items.append({"path": slot.path, "status": "translated", "reason": ""})
            else:
                result.items.append({"path": slot.path, "status": "kept", "reason": reason})

    _add_notes(work, result, target)
    log.info("Dịch máy xong (sang %s): %s", target, result.summary())
    return result
