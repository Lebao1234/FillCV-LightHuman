// Cấu hình ngôn ngữ và bảng ánh xạ chuyển đổi ngôn ngữ cho giao diện và hồ sơ CV
/**
 * Module quản lý cấu hình đa ngôn ngữ phía frontend, đồng bộ với bảng từ điển
 * cố định trên server (system/config/pdf_labels.toml và system/config/company.toml).
 * Không gọi bất kỳ dịch vụ dịch thuật bên ngoài nào.
 */

// Danh sách ngôn ngữ được hỗ trợ
export const SUPPORTED_LANGUAGES = [
  { code: 'vi', label: 'Tiếng Việt', fileSuffix: '' },
  { code: 'en', label: 'English', fileSuffix: ' - EN' },
]

// Ngôn ngữ mặc định
export const DEFAULT_LANGUAGE = 'vi'

// Bảng ánh xạ tiêu đề mục chuẩn giữa Tiếng Việt và Tiếng Anh
export const SECTION_TITLES = {
  summary: { vi: 'Mục tiêu nghề nghiệp', en: 'Career Objective' },
  highlights: { vi: 'Thành tích nổi bật', en: 'Key Achievements' },
  competencies: { vi: 'Năng lực cốt lõi', en: 'Core Competencies' },
  skills: { vi: 'Kỹ năng', en: 'Skills' },
  tools: { vi: 'Công cụ – Phần mềm', en: 'Tools & Software' },
  languages: { vi: 'Ngoại ngữ', en: 'Languages' },
  career_path: { vi: 'Lộ trình sự nghiệp', en: 'Career Path' },
  experience: { vi: 'Kinh nghiệm làm việc', en: 'Work Experience' },
  projects: { vi: 'Dự án', en: 'Projects' },
  education: { vi: 'Học vấn', en: 'Education' },
  activities: { vi: 'Hoạt động', en: 'Activities' },
  interests: { vi: 'Sở thích', en: 'Interests' },
  other: { vi: 'Thông tin thêm', en: 'Additional Information' },
  references: { vi: 'Người tham chiếu', en: 'References' },
}

// Bảng ánh xạ thuật ngữ ngắn (giới tính, thời gian, học vị)
export const TERM_PAIRS = [
  ['Nam', 'Male'],
  ['Nữ', 'Female'],
  ['Mong muốn', 'Desired'],
  ['Kinh nghiệm làm việc', 'Work experience'],
  ['Kinh nghiệm quản lý', 'Management experience'],
  ['Doanh nghiệp đã làm việc', 'Companies'],
  ['Trình độ học vấn', 'Education level'],
  ['năm', 'years'],
  ['tháng', 'months'],
  ['Tiến sĩ', 'Doctor of Philosophy (PhD)'],
  ['Thạc sĩ', "Master's Degree"],
  ['Cử nhân', "Bachelor's Degree"],
  ['Kỹ sư', 'Engineer'],
  ['Cao đẳng', 'Associate Degree'],
  ['Trung cấp', 'Vocational Diploma'],
]

// Từ điển hiển thị giao diện theo ngôn ngữ
export const UI_TRANSLATIONS = {
  vi: {
    app_title: 'Hồ sơ ứng viên',
    extraction_title: 'Trạng thái bóc tách CV',
    start_extraction: 'Bắt đầu bóc tách CV',
    reset_button: 'Làm mới / Nạp CV khác',
    dropzone_title: 'Kéo thả file CV vào đây hoặc bấm để chọn',
    dropzone_hint: 'Hỗ trợ định dạng PDF, DOCX, PNG, JPG (tối đa 20 MB)',
    project_label: 'Tên dự án',
    project_placeholder: 'Ví dụ: Message Coffee',
    position_label: 'Vị trí ứng tuyển',
    position_placeholder: 'Ví dụ: Kế toán trưởng (hoặc theo CV)',
    language_label: 'Ngôn ngữ xuất hồ sơ',
    candidate_detected: 'Ứng viên đã nhận diện',
    pii_removed: 'Đã loại bỏ khỏi CV (Bảo mật PII)',
    salary_expected: 'Lương mong muốn',
    salary_hint: 'Không đưa vào bản PDF xuất ra — chỉ lưu nội bộ để trao đổi với khách.',
    summary_label: 'Tin nhắn tóm tắt hồ sơ',
    copy_button: 'Sao chép',
    copied_button: 'Đã sao chép!',
    tab_pdf: 'Bản PDF',
    tab_edit: 'Chỉnh sửa nội dung',
    tab_original: 'CV gốc',
    update_pdf: 'Cập nhật PDF',
    download_pdf: 'Tải PDF',
  },
  en: {
    app_title: 'Candidate Profile',
    extraction_title: 'CV Extraction Pipeline',
    start_extraction: 'Start Extraction',
    reset_button: 'Reset / Upload New CV',
    dropzone_title: 'Drag and drop CV file here or click to select',
    dropzone_hint: 'Supports PDF, DOCX, PNG, JPG (up to 20 MB)',
    project_label: 'Project Name',
    project_placeholder: 'e.g. Message Coffee',
    position_label: 'Target Position',
    position_placeholder: 'e.g. Chief Accountant (or from CV)',
    language_label: 'Profile Output Language',
    candidate_detected: 'Identified Candidate',
    pii_removed: 'Removed from CV (PII Privacy)',
    salary_expected: 'Expected Salary',
    salary_hint: 'Excluded from export PDF — internal reference only for client discussion.',
    summary_label: 'Profile Summary Message',
    copy_button: 'Copy',
    copied_button: 'Copied!',
    tab_pdf: 'PDF Preview',
    tab_edit: 'Edit Content',
    tab_original: 'Original CV',
    update_pdf: 'Update PDF',
    download_pdf: 'Download PDF',
  },
}

// Lấy đối tượng cấu hình ngôn ngữ
export function getLanguageConfig(langCode) {
  return SUPPORTED_LANGUAGES.find((l) => l.code === langCode) || SUPPORTED_LANGUAGES[0]
}

// Chuẩn hoá chuỗi để tra cứu thuật ngữ
function normalizeKey(str) {
  return (str || '').trim().replace(/:$/, '').toLowerCase()
}

// Dịch một thuật ngữ ngắn giữa 2 ngôn ngữ
export function translateTerm(text, targetLang = 'vi') {
  if (!text) return text
  const clean = normalizeKey(text)
  const isTargetEn = targetLang === 'en'

  for (const [vi, en] of TERM_PAIRS) {
    if (isTargetEn && normalizeKey(vi) === clean) return en
    if (!isTargetEn && normalizeKey(en) === clean) return vi
  }

  // Xử lý đơn vị số lượng: "5 năm" -> "5 years" hoặc "5 years" -> "5 năm"
  const countMatch = text.match(/^(\d+\+?)\s+(.+)$/)
  if (countMatch) {
    const num = countMatch[1]
    const unit = countMatch[2]
    const translatedUnit = translateTerm(unit, targetLang)
    if (translatedUnit !== unit) {
      return `${num} ${translatedUnit}`
    }
  }

  return text
}

// Dịch tiêu đề mục chuẩn
export function translateSectionTitle(title, targetLang = 'vi') {
  if (!title) return title
  const clean = normalizeKey(title)
  const isTargetEn = targetLang === 'en'

  // Chuẩn hoá các biến thể của Giới thiệu / About me về Mục tiêu nghề nghiệp / Career Objective
  const introVariants = [
    'gioi thieu', 'gioi thieu ban than', 'about me', 'profile', 'summary', 'tom tat', 'tom tat ban than',
    'muc tieu', 'muc tieu nghe nghiep', 'muc tieu cong viec', 'career objective', 'objective', 'objectives'
  ]
  const unaccented = clean
    .replace(/[àáạảãâầấậẩẫăằắặẳẵ]/g, 'a')
    .replace(/[èéẹẻẽêềếệểễ]/g, 'e')
    .replace(/[ìíịỉĩ]/g, 'i')
    .replace(/[òóọỏõôồốộổỗơờớợởỡ]/g, 'o')
    .replace(/[ùúụủũưừứựửữ]/g, 'u')
    .replace(/[ỳýỵỷỹ]/g, 'y')
    .replace(/đ/g, 'd')

  if (introVariants.some((v) => unaccented === v || unaccented.includes(v))) {
    const translated = isTargetEn ? 'Career Objective' : 'Mục tiêu nghề nghiệp'
    return title === title.toUpperCase() ? translated.toUpperCase() : translated
  }

  for (const key of Object.keys(SECTION_TITLES)) {
    const item = SECTION_TITLES[key]
    if (normalizeKey(item.vi) === clean || normalizeKey(item.en) === clean) {
      const translated = isTargetEn ? item.en : item.vi
      return title === title.toUpperCase() ? translated.toUpperCase() : translated
    }
  }

  return title
}

// Lấy chuỗi giao diện tương ứng theo ngôn ngữ
export function getUiText(key, lang = 'vi') {
  const dict = UI_TRANSLATIONS[lang] || UI_TRANSLATIONS.vi
  return dict[key] || UI_TRANSLATIONS.vi[key] || key
}
