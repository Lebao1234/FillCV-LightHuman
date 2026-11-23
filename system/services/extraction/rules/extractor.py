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
from services.extraction import manual
from services.extraction.rules import translation
from services.extraction.rules.pdf_text import Line, TextQualityError, TooManyPagesError, read_lines
from services.extraction import base
from services.extraction.rules import analysis, content, personal, rulebook, sections

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
            captured: dict[str, list[str]] = {k: list(v) for k, v in ident.contacts.items()}
            notes += personal.scrub_cv(cv, removed, captured)
            kept_kinds: set[str] = set()
            if doc.keep_contact:                                 # người dùng chọn giữ liên hệ: đưa vào dòng thông tin đầu hồ sơ
                contact_rows, kept_kinds = personal.contact_facts(captured, cv["language"])
                cv["facts"] = list(cv.get("facts") or []) + contact_rows
                removed -= kept_kinds
                self._removed_by_sections -= kept_kinds
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

        # Chuẩn hoá và gộp mục "Giới thiệu" -> "Mục tiêu nghề nghiệp"
        target_summary_title = "Career Objective" if lang == "en" else "Mục tiêu nghề nghiệp"

        def _is_summary_raw(r: sections.RawSection) -> bool:
            norm_t = rulebook.norm(r.title)
            return r.key == "summary" or any(w in norm_t for w in ("muc tieu", "gioi thieu", "about me", "career objective", "summary", "profile", "tom tat"))

        summary_raw = next((r for r in raws if _is_summary_raw(r)), None)

        if ident.intro:
            if summary_raw:
                summary_raw.lines = ident.intro + summary_raw.lines
            else:
                raws.insert(0, sections.RawSection(target_summary_title, "summary", "text", lang, ident.intro, 0.6,
                                                   "đoạn văn ở đầu CV không có tiêu đề — tiêu đề mục do hệ thống đặt"))
                summary_raw = raws[0]
            self_created.append(f'Tiêu đề mục "{target_summary_title}" do hệ thống đặt cho đoạn văn ở đầu CV')

        # Đổi tất cả tiêu đề mục dạng summary / giới thiệu thành tiêu đề chuẩn
        for r in raws:
            if _is_summary_raw(r):
                r.title = target_summary_title
                r.key = "summary"

        # Nếu có nhiều hơn 1 mục summary trong raws, gộp các dòng lại vào mục đầu tiên
        summary_indices = [idx for idx, r in enumerate(raws) if r.key == "summary"]
        if len(summary_indices) > 1:
            first_idx = summary_indices[0]
            for extra_idx in summary_indices[1:]:
                raws[first_idx].lines.extend(raws[extra_idx].lines)
            raws = [r for idx, r in enumerate(raws) if idx not in summary_indices[1:]]

        # Sắp xếp raws theo thứ tự chuẩn hoá:
        # 1. Mục tiêu nghề nghiệp
        # 2. Kinh nghiệm làm việc
        # 3. Học vấn
        # 4. Kĩ năng
        # 5. Các mục còn lại (giữ nguyên thứ tự tương đối)
        def _section_priority(r: sections.RawSection) -> int:
            norm_t = rulebook.norm(r.title)
            if r.key == "summary" or any(w in norm_t for w in ("muc tieu", "gioi thieu", "about me", "career objective", "summary", "profile", "tom tat")):
                return 1
            if r.key in ("experience", "career_path") or r.type in ("experience", "career_path") or any(w in norm_t for w in ("kinh nghiem", "work experience", "employment", "qua trinh lam viec", "lich su lam viec", "lo trinh su nghiep")):
                return 2
            if r.key == "education" or r.type == "education" or any(w in norm_t for w in ("hoc van", "education", "trinh do", "dao tao", "bang cap")):
                return 3
            if r.key in ("skills", "tools", "competencies", "languages") or any(w in norm_t for w in ("ky nang", "skill", "cong cu", "tool", "nang luc", "ngoai ngu", "language", "tin hoc")):
                return 4
            return 5

        raws = sorted(raws, key=_section_priority)
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
        if info.get("two_columns"):
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
