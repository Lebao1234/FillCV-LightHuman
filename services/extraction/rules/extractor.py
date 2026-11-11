"""Bộ trích xuất theo luật cho CV dạng PDF có lớp chữ (không AI, không mạng). Đăng ký tên "rules".

Giai đoạn (mỗi giai đoạn = một bước thật trên màn hình chờ):
  read     đọc chữ + vị trí/cỡ chữ/đậm/nghiêng, nhận 2 cột     (pdf_text.py)
  sections tách mục theo tiêu đề, tìm họ tên + chức danh       (sections.py, personal.py)
  privacy  bỏ thông tin nhạy cảm theo nhãn, lấy năm sinh/giới tính/mong muốn/lương (personal.py)
  content  tách công việc, học vấn, kỹ năng... + chọn loại mục (content.py)
  check    ô số liệu, lưu ý tuyển dụng, ngôn ngữ, quét thông tin liên hệ lần cuối (analysis.py, personal.py)
Không đọc được (không phải PDF, PDF scan, chữ lỗi, không thấy mục nào) -> trả khung nhập tay kèm lý do.
"""
from datetime import date
from pathlib import Path

from infra import settings
from services.extraction import base, manual
from services.extraction.rules import analysis, content, personal, rulebook, sections, translation
from services.extraction.rules.pdf_text import Line, TextQualityError, TooManyPagesError, read_lines

NOTE_AUTO = "Hồ sơ do bộ đọc tự động (theo luật) dựng từ PDF — đối chiếu với CV gốc trước khi gửi khách."


# Bộ trích xuất theo luật
class RulesExtractor:
    name = "rules"
    stages = (base.Stage("read", "Đọc chữ trong PDF"),
              base.Stage("sections", "Tách các mục, tìm họ tên và chức danh"),
              base.Stage("privacy", "Lọc thông tin nhạy cảm (SĐT, email, địa chỉ, ngày sinh...)"),
              base.Stage("content", "Tách công việc, học vấn, kỹ năng"),
              base.Stage("check", "Lập ô số liệu, lưu ý tuyển dụng và kiểm tra lần cuối"))

    @property
    def version(self) -> str:
        """Số phiên bản bộ luật + mã băm file luật (đổi luật là đổi phiên bản ghi vào metadata PDF)."""
        return f"{rulebook.rules()['version']}+{rulebook.rules_hash()}"

    # Trích xuất một CV PDF; không đọc được thì trả khung nhập tay (không ném lỗi)
    def extract(self, doc: base.SourceDoc, progress: base.Progress) -> base.ExtractionResult:
        today = doc.today or date.today()
        runs: list[base.StageRun] = []
        with base.stage_run(runs, self.stages[0], progress) as run:
            if Path(doc.filename).suffix.lower() != ".pdf":
                manual.probe_file(doc.data, doc.filename)          # file hỏng -> lỗi rõ ràng
                run.status, run.detail = "skip", "không phải PDF"
                return self._fallback(runs, "Bộ đọc tự động hiện chỉ đọc CV dạng PDF có lớp chữ. Hãy xuất CV "
                                            "thành PDF rồi gửi lại, hoặc nhập tay theo khung bên dưới.")
            try:
                lines, info = read_lines(doc.data, settings.max_cv_pages())
            except TooManyPagesError as e:
                run.status, run.detail = "skip", "quá số trang cho phép"
                return self._fallback(runs, str(e))
            except TextQualityError as e:
                run.status, run.detail = "skip", "không có lớp chữ hoặc chữ lỗi"
                return self._fallback(runs, str(e))
            except Exception as e:
                raise base.ExtractionError("File CV bị hỏng hoặc không đúng định dạng PDF. Hãy mở file, lưu lại "
                                           "thành PDF rồi gửi lại.") from e
            lines, info["translated"], dropped = translation.clean_lines(lines)
            run.detail = f"{info['pages']} trang, {len(lines)} dòng" + (", 2 cột" if info["two_columns"] else "") \
                + (f", bỏ {dropped} dòng/phần dịch tiếng Anh" if info["translated"] else "")
        with base.stage_run(runs, self.stages[1], progress) as run:
            pre, raws = sections.split_sections(lines)
            ident = personal.Identity()
            personal.find_name_and_title(lines, sections.body_size(lines), ident)
            personal.find_original_stats(pre, ident)
            run.detail = f"{len(raws)} mục"
            if not raws:
                run.status = "skip"
                return self._fallback(runs, "Không nhận ra tiêu đề mục nào trong CV nên chưa tách được nội dung — "
                                            "hãy nhập tay, đối chiếu tab CV gốc.")
        with base.stage_run(runs, self.stages[2], progress) as run:
            pid = {id(l) for l in pre} | {id(l) for r in raws if r.type == "personal" for l in r.lines}
            did = frozenset(id(l) for r in raws if r.key == "desired" for l in r.lines)
            personal.strip_personal(pre, pid, ident, did)
            for r in raws:
                r.lines = personal.strip_personal(r.lines, pid, ident, did)
            raws = [r for r in raws if r.type != "personal"]
            run.detail = f"bỏ {len(ident.removed)} loại thông tin"
        with base.stage_run(runs, self.stages[3], progress) as run:
            cv, notes, conf = self._assemble(raws, ident, lines, info, today)
            run.detail = f"{sum(len(s.get('jobs', [])) for s in cv['sections'])} công việc"
        with base.stage_run(runs, self.stages[4], progress) as run:
            removed: set[str] = set(ident.removed)
            notes += personal.scrub_cv(cv, removed)
            if ident.stats:                                      # CV có sẵn hàng ô số liệu -> giữ nguyên
                stats, self_created = ident.stats, []
                conf["stats"] = 0.8
            else:
                stats, self_created = analysis.build_stats(cv, today, cv["language"])
                if stats:
                    conf["stats"] = 0.6
            cv["stats"] = stats
            has_edu = any(s["type"] == "education" for s in cv["sections"])
            cv["model_notes"]["recruiting_flags"] = analysis.recruiting_flags(cv, today, has_edu, cv["language"])
            cv["model_notes"]["self_created"] = cv["model_notes"]["self_created"] + self_created
            cv["model_notes"]["removed"] = personal.removed_names(removed | self._removed_by_sections)
            for sec in cv["sections"]:
                for j in sec.get("jobs", []):
                    j.pop("_range", None)
            run.detail = f"{len(stats)} ô số liệu, {len(cv['model_notes']['recruiting_flags'])} lưu ý"
        warnings = [base.ReviewNote(p or None, m) for p, m in notes]
        return base.ExtractionResult(cv=cv, warnings=warnings, confidence=conf, stages=runs,
                                     backend=f"{self.name}-{self.version}")

    # Ghép khối nhận diện + các mục thành hồ sơ đúng schema; trả (cv, cảnh báo, độ tin cậy)
    def _assemble(self, raws: list[sections.RawSection], ident: personal.Identity, lines: list[Line], info: dict,
                  today: date) -> tuple[dict, list[tuple[str, str]], dict[str, float]]:
        notes: list[tuple[str, str]] = []
        conf: dict[str, float] = {}
        self_created: list[str] = []
        other = [NOTE_AUTO]
        lang = analysis.detect_language(" ".join(l.text for r in raws for l in r.lines), [r.lang for r in raws])
        if lang == "bilingual_vi_en":
            vi_keys = {r.key for r in raws if r.lang == "vi"}
            dropped = [r for r in raws if r.lang == "en" and r.key in vi_keys]
            raws = [r for r in raws if r not in dropped]
            other.append(f"CV song ngữ: đã bỏ {len(dropped)} mục tiếng Anh trùng với mục tiếng Việt")
            notes.append(("", "CV song ngữ — hồ sơ chỉ giữ phần tiếng Việt, kiểm tra không sót nội dung"))
        if ident.intro:
            raws.insert(0, sections.RawSection("Giới thiệu", "summary", "text", "vi", ident.intro, 0.6,
                                               "đoạn văn ở đầu CV không có tiêu đề — tiêu đề mục do hệ thống đặt"))
            self_created.append("Tiêu đề mục \"Giới thiệu\" do hệ thống đặt cho đoạn văn ở đầu CV")
        self._removed_by_sections: set[str] = set()
        built_sections = []
        for r in raws:
            b = content.build_section(r, today, self._removed_by_sections)
            i = len(built_sections)
            built_sections.append(b.section)
            for rel, v in b.confidence.items():
                conf[f"sections[{i}]" + (f".{rel}" if rel else "")] = v
            notes += [(f"sections[{i}]" + (f".{rel}" if rel else ""), m) for rel, m in b.notes]
        if ident.full_name:
            name = ident.full_name
            conf["full_name"] = ident.name_conf
        else:
            name = manual.PLACEHOLDER_NAME
            conf["full_name"] = 0.0
            notes.append(("full_name", "không tìm thấy họ tên — đang để chữ tạm"))
            self_created.append(f"Họ tên đang để chữ tạm '{name}' — phải nhập họ tên thật")
        if ident.target_title:
            conf["target_title"] = ident.title_conf
        if info.get("translated"):
            other.append("CV có bản dịch tiếng Anh theo từng dòng: hồ sơ chỉ giữ phần tiếng Việt")
            notes.append(("", "CV song ngữ theo từng dòng — đã bỏ phần tiếng Anh, kiểm tra không sót nội dung"))
        if info["two_columns"]:
            notes.append(("", "CV dạng 2 cột — thứ tự các mục có thể khác bản gốc, đối chiếu tab CV gốc"))
            other.append("CV dạng 2 cột: đã đọc cột trái trước, cột phải sau")
        if ident.leftover:
            notes.append(("", f"{ident.leftover} dòng ở đầu CV chưa xếp được vào mục nào — đối chiếu tab CV gốc"))
        cv = {
            "language": lang, "full_name": name, "target_title": ident.target_title, "birth_year": ident.birth_year,
            "gender": ident.gender, "facts": ident.facts, "expected_salary": ident.expected_salary, "stats": [],
            "sections": built_sections,
            "model_notes": {"removed": [], "self_created": self_created, "recruiting_flags": [], "other": other},
        }
        return cv, notes, conf

    # Không đọc tự động được -> khung nhập tay + lý do (vẫn là một kết quả hợp lệ, không phải lỗi)
    def _fallback(self, runs: list[base.StageRun], reason: str) -> base.ExtractionResult:
        cv = manual.blank_cv(reason)
        notes, conf = manual.blank_review(cv, reason)
        return base.ExtractionResult(cv=cv, warnings=notes, confidence=conf, stages=runs,
                                     backend=f"{self.name}-{self.version}")
