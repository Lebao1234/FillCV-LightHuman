import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { Routes, Route, Outlet, Navigate } from 'react-router-dom'
import Header from './components/Header.jsx'
import { TABS } from './constants.js'
import HomePage from './pages/HomePage.jsx'
import {
  getConfig,
  extractCv,
  validateCv,
  buildPdf,
  getPdfStatus,
  translateCv,
} from './api/client.js'

// Ứng dụng chính FillCV Light Human

export default function App() {
  const [config, setConfig] = useState(null)

  // Trạng thái phiên CV
  const [runId, setRunId] = useState(null)
  const [cvData, setCvData] = useState(null)
  const [cv0, setCv0] = useState(null) // Hồ sơ hệ thống đọc ban đầu, dùng cho nút hoàn tác
  const [originalName, setOriginalName] = useState('')
  const [project, setProject] = useState('')
  const [position, setPosition] = useState('')
  const [pdfLang, setPdfLang] = useState('vi')
  const [keepContact, setKeepContact] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(null)

  // Trạng thái tiến độ & hàng đợi
  const [isExtracting, setIsExtracting] = useState(false)
  const [isBuildingPdf, setIsBuildingPdf] = useState(false)
  const [queuePos, setQueuePos] = useState(0)
  const [queueWhat, setQueueWhat] = useState('')
  const [activeStep, setActiveStep] = useState(0)
  const [stageLabels, setStageLabels] = useState([])

  // Lỗi nếu có
  const [error, setError] = useState(null)

  // Kết quả bản PDF
  const [pdfData, setPdfData] = useState(null)
  const [currentFingerprint, setCurrentFingerprint] = useState('')
  const [summary, setSummary] = useState('')

  // Validation & Review
  const [structureErrors, setStructureErrors] = useState([])
  const [violations, setViolations] = useState([])
  const [review, setReview] = useState(null)
  const [photoUrl, setPhotoUrl] = useState(null)

  // Xác nhận duyệt
  const [checkedGenerated, setCheckedGenerated] = useState(false)
  const [reviewed, setReviewed] = useState(false)

  // Trạng thái khung PDF tính từ backend
  const [pdfStatus, setPdfStatus] = useState(null)

  // Mốc "đã lưu": nội dung đã dựng thành PDF gần nhất, và giờ người dùng bấm lưu
  const [savedSnapshot, setSavedSnapshot] = useState('')
  const [savedAt, setSavedAt] = useState(null)

  // Dịch nội dung sang tiếng Anh (dịch máy offline trên máy chủ)
  const [isTranslating, setIsTranslating] = useState(false)
  const [translateReport, setTranslateReport] = useState(null)
  const [translateError, setTranslateError] = useState(null)

  // Tab đang chọn
  const [activeTab, setActiveTab] = useState('pdf')

  // Nội dung hồ sơ mới nhất, để biết người dùng có gõ thêm trong lúc đang dựng PDF không
  const cvRef = useRef(null)
  // Cặp hồ sơ {vi, en} khi nội dung đã được dịch tự động/thủ công: để đổi lại tiếng Việt khôi phục đúng bản gốc
  const translatedRef = useRef(null)
  useEffect(() => {
    cvRef.current = cvData
  }, [cvData])

  // Có chỉnh sửa nào chưa được lưu vào bản PDF không (so với lần dựng gần nhất)
  const isDirty = useMemo(
    () => Boolean(cvData) && Boolean(savedSnapshot) && JSON.stringify([cvData, project, position]) !== savedSnapshot,
    [cvData, project, position, savedSnapshot]
  )

  // Chặn đóng/tải lại trang khi còn chỉnh sửa chưa lưu (nội dung chỉ nằm trong trình duyệt)
  useEffect(() => {
    if (!isDirty) return undefined
    const warn = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [isDirty])

  // Lấy cấu hình ban đầu
  useEffect(() => {
    getConfig()
      .then((cfg) => {
        setConfig(cfg)
        if (cfg.default_stage_labels) {
          setStageLabels(cfg.default_stage_labels)
        }
      })
      .catch((err) => {
        console.error('Không tải được cấu hình:', err)
      })
  }, [])

  // Cập nhật trạng thái khi các checkbox hoặc dữ liệu thay đổi
  useEffect(() => {
    if (!pdfData) return
    let active = true

    getPdfStatus({
      has_pdf: Boolean(pdfData.filename),
      pdf_fingerprint: pdfData.fingerprint,
      current_fingerprint: currentFingerprint || pdfData.fingerprint,
      checklist: pdfData.checklist,
      has_violations: violations.length > 0,
      has_structure_errors: structureErrors.length > 0,
      checked_generated: checkedGenerated,
      reviewed: reviewed,
    })
      .then((res) => {
        if (active) setPdfStatus(res)
      })
      .catch((err) => {
        console.error('Lỗi tính trạng thái PDF:', err)
      })

    return () => {
      active = false
    }
  }, [checkedGenerated, reviewed, pdfData, currentFingerprint, violations, structureErrors])

  // Dựng PDF
  const handleBuildPdf = useCallback(
    async (targetCv, targetRunId, targetPrj, targetPos, targetLang, targetKeepContact = keepContact) => {
      setIsBuildingPdf(true)
      try {
        const res = await buildPdf({
          runId: targetRunId,
          cv: targetCv,
          project: targetPrj,
          position: targetPos,
          lang: targetLang,
          keepContact: targetKeepContact,
        })
        // Máy chủ dọn hồ sơ (bỏ dòng trống...) trước khi dựng: lấy đúng bản đó làm bản đã lưu
        const savedCv = res.cv || targetCv
        // Chỉ đồng bộ form khi người dùng chưa gõ thêm trong lúc chờ, tránh ghi đè chữ họ vừa nhập
        if (res.cv && JSON.stringify(cvRef.current) === JSON.stringify(targetCv)) setCvData(res.cv)
        setSavedSnapshot(JSON.stringify([savedCv, targetPrj, targetPos]))
        setPdfData(res)
        setCurrentFingerprint(res.fingerprint)
        setSummary(res.summary || '')
        setPdfStatus(res.status)
        setError(null)
        return true
      } catch (err) {
        setError(err.message || 'Dựng PDF thất bại.')
        return false
      } finally {
        setIsBuildingPdf(false)
        setQueuePos(0)
      }
    },
    [keepContact]
  )

  // Gửi file CV lên backend
  const handleSubmitCv = ({ file, project: prj, position: pos, lang: chosenLang, keepContact: chosenKeepContact = false }) => {
    setIsExtracting(true)
    setQueuePos(0)
    setActiveStep(0)
    setError(null)
    setOriginalName(file.name)
    setProject(prj)
    setPosition(pos)
    setKeepContact(chosenKeepContact)
    setElapsedSeconds(null)
    if (chosenLang) {
      setPdfLang(chosenLang)
    }

    extractCv(file, prj, pos, {
      keepContact: chosenKeepContact,
      onWait: (posInQueue, what) => {
        setQueuePos(posInQueue)
        setQueueWhat(what)
      },
      onProgress: (stepIdx, label, labels) => {
        setActiveStep(stepIdx)
        if (labels && labels.length > 0) setStageLabels(labels)
      },
      onDone: (data) => {
        const autoLang = data.cv?.language === 'en' ? 'en' : 'vi'
        const initialLang = chosenLang || autoLang
        setPdfLang(initialLang)
        setElapsedSeconds(data.elapsed_seconds || null)
        setIsExtracting(false)
        setRunId(data.run_id)
        setCvData(data.cv)
        setCv0(data.cv)
        setPhotoUrl(data.photo_url)
        setOriginalName(data.original_filename)
        setProject(prj)
        setPosition(pos || data.cv.target_title || '')
        setReview({
          confidence: data.confidence,
          notes: (data.warnings || []).map((w) => [w.path, w.message]),
        })

        // Tự động kiểm tra checkbox self_created
        const hasSelfCreated =
          data.cv.model_notes && data.cv.model_notes.self_created && data.cv.model_notes.self_created.length > 0
        setCheckedGenerated(!hasSelfCreated)
        setReviewed(false)

        // Dựng PDF tự động lần đầu với lựa chọn contact đã chọn trước khi tạo; xuất English thì dịch nội dung trước
        const firstPosition = pos || data.cv.target_title || ''
        translatedRef.current = null
        const buildFirst = async () => {
          let cvForPdf = data.cv
          if (initialLang === 'en' && data.cv.language !== 'en' && config?.translation?.available) {
            setIsBuildingPdf(true) // giữ màn hình chờ trong lúc dịch
            const en = await translateNow(data.cv, data.run_id)
            if (en) {
              translatedRef.current = { vi: data.cv, en }
              cvForPdf = en
              setCvData(en)
              validateCv(en, prj, firstPosition, data.run_id, 'en', chosenKeepContact)
                .then((val) => {
                  setStructureErrors(val.structure_errors || [])
                  setViolations(val.violations || [])
                })
                .catch((err) => console.error('Lỗi validate:', err))
            }
          }
          handleBuildPdf(cvForPdf, data.run_id, prj, firstPosition, initialLang, chosenKeepContact)
        }
        buildFirst()
      },
      onError: (errMsg) => {
        setIsExtracting(false)
        setQueuePos(0)
        setError(errMsg)
      },
    })
  }

  // Đổi ngôn ngữ PDF
  const handleChangeLang = async (newLang) => {
    if (!cvData || !runId) {
      setPdfLang(newLang)
      return
    }
    const snap = translatedRef.current
    const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)
    // Sang English: nội dung còn tiếng Việt thì dịch máy trước (lỗi/không có dịch máy thì chỉ đổi nhãn như cũ)
    if (newLang === 'en' && config?.translation?.available && cvData.language !== 'en' && !(snap && same(cvData, snap.en))) {
      const en = await translateNow(cvData, runId)
      if (en) {
        translatedRef.current = { vi: cvData, en }
        setPdfLang('en')
        handleCvChange(en, 'en')
        handleBuildPdf(en, runId, project, position, 'en', keepContact)
        return
      }
    }
    // Về tiếng Việt: nội dung chưa sửa sau khi dịch thì khôi phục đúng bản tiếng Việt trước khi dịch
    if (newLang === 'vi' && snap && same(cvData, snap.en)) {
      translatedRef.current = null
      setPdfLang('vi')
      handleCvChange(snap.vi, 'vi')
      handleBuildPdf(snap.vi, runId, project, position, 'vi', keepContact)
      return
    }
    setPdfLang(newLang)
    handleBuildPdf(cvData, runId, project, position, newLang, keepContact)
  }

  // Đổi tuỳ chọn giữ nguyên / cắt contact
  const handleChangeKeepContact = (newKeepContact) => {
    setKeepContact(newKeepContact)
    if (cvData) {
      validateCv(cvData, project, position, runId, pdfLang, newKeepContact)
        .then((val) => {
          setStructureErrors(val.structure_errors || [])
          setViolations(val.violations || [])
          if (val.fingerprint) setCurrentFingerprint(val.fingerprint)
        })
        .catch((err) => console.error('Lỗi validate:', err))
      if (runId) {
        handleBuildPdf(cvData, runId, project, position, pdfLang, newKeepContact)
      }
    }
  }

  // Cập nhật nội dung hồ sơ và tự động validate
  const handleCvChange = (newCv, lang = pdfLang) => {
    setCvData(newCv)
    validateCv(newCv, project, position, runId, lang, keepContact)
      .then((val) => {
        const structErrs = val.structure_errors || []
        const viols = val.violations || []
        setStructureErrors(structErrs)
        setViolations(viols)
        if (val.fingerprint) {
          setCurrentFingerprint(val.fingerprint)
        }
      })
      .catch((err) => console.error('Lỗi validate:', err))
  }

  // Lưu chỉnh sửa: dựng lại PDF theo mẫu từ nội dung đang sửa
  const handleSaveEdits = async () => {
    const ok = await handleBuildPdf(cvData, runId, project, position, pdfLang, keepContact)
    if (ok) {
      setSavedAt(new Date())
      setActiveTab('pdf') // lưu xong chuyển sang bản PDF vừa cập nhật
    }
  }

  // Dịch nội dung hồ sơ sang tiếng Anh; kết quả thay vào form để nhân viên đọc lại và sửa trước khi lưu
  const handleTranslate = async () => {
    if (!cvData || isTranslating) return
    const ok = window.confirm(
      'Dịch nội dung hồ sơ sang tiếng Anh bằng dịch máy?\n\n' +
        'Nội dung đang sửa sẽ được thay bằng bản dịch (có thể quay lại bằng "Về bản đọc ban đầu"). ' +
        'Dịch máy chỉ là bản nháp: hãy đọc lại toàn bộ trước khi gửi khách.'
    )
    if (!ok) return
    const en = await translateNow(cvData, runId)
    if (en) {
      translatedRef.current = { vi: cvData, en }
      setPdfLang('en')
      handleCvChange(en, 'en')
    }
  }

  // Gọi dịch máy cho một hồ sơ (không hỏi lại); trả hồ sơ đã dịch hoặc null nếu lỗi
  const translateNow = async (cv, rid) => {
    setIsTranslating(true)
    setTranslateError(null)
    try {
      const res = await translateCv(cv, rid)
      setCheckedGenerated(false) // bản dịch máy là mục hệ thống tự lập: phải tick lại sau khi đọc
      setReviewed(false)
      setTranslateReport({ summary: res.summary, items: res.items, engine: res.engine })
      return res.cv
    } catch (err) {
      setTranslateError(err.message || 'Dịch máy thất bại.')
      return null
    } finally {
      setIsTranslating(false)
    }
  }

  // Hoàn tác mọi chỉnh sửa về hồ sơ hệ thống đọc ban đầu (chưa lưu cho tới khi bấm Lưu)
  const handleRevert = () => {
    if (!cv0) return
    if (!window.confirm('Bỏ toàn bộ chỉnh sửa và quay về nội dung hệ thống đọc ban đầu từ CV gốc?')) return
    translatedRef.current = null
    handleCvChange(JSON.parse(JSON.stringify(cv0)))
  }

  // Làm mới ứng dụng
  const handleReset = () => {
    if (isDirty && !window.confirm('Còn chỉnh sửa chưa lưu. Làm mới sẽ mất toàn bộ. Tiếp tục?')) return
    setRunId(null)
    setCvData(null)
    setCv0(null)
    setPhotoUrl(null)
    setOriginalName('')
    setProject('')
    setPosition('')
    setPdfData(null)
    setCurrentFingerprint('')
    setSummary('')
    setError(null)
    setStructureErrors([])
    setViolations([])
    setReview(null)
    setCheckedGenerated(false)
    setReviewed(false)
    setPdfStatus(null)
    setSavedSnapshot('')
    setSavedAt(null)
    translatedRef.current = null
    setTranslateReport(null)
    setTranslateError(null)
    setPdfLang('vi')
    setKeepContact(false)
    setElapsedSeconds(null)
    setActiveTab('pdf')
  }

  // Đổi tab bằng phím mũi tên trái/phải, Home/End (WAI-ARIA tabs)
  const handleTabKeyDown = (e) => {
    const idx = TABS.findIndex((t) => t.id === activeTab)
    let next
    if (e.key === 'ArrowRight') next = (idx + 1) % TABS.length
    else if (e.key === 'ArrowLeft') next = (idx - 1 + TABS.length) % TABS.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = TABS.length - 1
    else return
    e.preventDefault()
    setActiveTab(TABS[next].id)
    document.getElementById(`tab-${TABS[next].id}`)?.focus()
  }

  const isBusy = isExtracting || (isBuildingPdf && !pdfData)

  // Toàn bộ trạng thái + hành động chia sẻ cho các trang qua Outlet context
  const session = {
    isExtracting, isBuildingPdf, queuePos, queueWhat, activeStep, stageLabels, cvData, originalName,
    project, setProject, position, setPosition, pdfLang, elapsedSeconds, summary, review, error,
    structureErrors, violations, handleSubmitCv, handleReset, isBusy, activeTab, setActiveTab,
    handleTabKeyDown, pdfData, pdfStatus, handleBuildPdf, runId, keepContact, checkedGenerated,
    setCheckedGenerated, reviewed, setReviewed, handleChangeLang, handleChangeKeepContact,
    handleCvChange, handleSaveEdits, handleRevert, photoUrl, setPhotoUrl, isDirty, savedAt,
    translation: config?.translation, isTranslating, translateReport, translateError, handleTranslate,
  }

  return (
    <Routes>
      <Route element={<AppLayout config={config} session={session} />}>
        <Route index element={<HomePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

// Khung chung của mọi trang: header thương hiệu + vùng nội dung của trang con
function AppLayout({ config, session }) {
  return (
    <div className="block-container mx-auto max-w-[1480px] p-4 sm:px-4 sm:pt-4 sm:pb-6 lg:px-8 lg:pt-6 lg:pb-8">
      <Header logoB64={config?.logo_header_b64} />
      <Outlet context={session} />
    </div>
  )
}
