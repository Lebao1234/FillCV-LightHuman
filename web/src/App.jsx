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
  // Khi nội dung đã được dịch: {base, baseLang, out, outLang} — bản trước khi dịch và bản dịch, để quay về ngôn ngữ gốc khôi phục đúng bản cũ
  const translatedRef = useRef(null)

  // Ngôn ngữ của CV gốc ('en' nếu bộ đọc nhận là tiếng Anh, còn lại coi là tiếng Việt)
  const sourceLangOf = (cv) => (cv?.language === 'en' ? 'en' : 'vi')

  // Bộ dịch trên máy chủ có dịch sang ngôn ngữ này được không (offline chỉ sang 'en', online cả hai chiều)
  const canTranslateTo = (lang) =>
    Boolean(config?.translation?.available) && (config.translation.targets || ['en']).includes(lang)
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
          let langForPdf = initialLang
          const sourceLang = sourceLangOf(data.cv)
          if (initialLang !== sourceLang) {
            setIsBuildingPdf(true) // giữ màn hình chờ trong lúc dịch
            const out = canTranslateTo(initialLang) ? await translateNow(data.cv, data.run_id, initialLang) : null
            if (!out) {
              // Không dịch được: dựng bằng ngôn ngữ gốc của CV để bản PDF không lẫn hai thứ tiếng
              langForPdf = sourceLang
              setPdfLang(sourceLang)
              if (!canTranslateTo(initialLang)) {
                setTranslateError('Máy chủ chưa dịch được sang ngôn ngữ đã chọn nên hồ sơ được dựng bằng ngôn ngữ gốc của CV.')
              }
            }
            if (out) {
              translatedRef.current = { base: data.cv, baseLang: sourceLang, out, outLang: initialLang }
              cvForPdf = out
              setCvData(out)
              validateCv(out, prj, firstPosition, data.run_id, langForPdf, chosenKeepContact)
                .then((val) => {
                  setStructureErrors(val.structure_errors || [])
                  setViolations(val.violations || [])
                })
                .catch((err) => console.error('Lỗi validate:', err))
            }
          }
          handleBuildPdf(cvForPdf, data.run_id, prj, firstPosition, langForPdf, chosenKeepContact)
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
    // Ngôn ngữ của NỘI DUNG đang hiển thị: bản đã dịch thì theo bản dịch, chưa dịch thì theo CV gốc
    const contentLang = snap ? snap.outLang : sourceLangOf(cvData)

    // Nội dung đã đúng ngôn ngữ được chọn: chỉ cần đổi nhãn/tiêu đề và dựng lại
    if (newLang === contentLang) {
      setPdfLang(newLang)
      handleBuildPdf(cvData, runId, project, position, newLang, keepContact)
      return
    }
    // Quay về ngôn ngữ trước khi dịch: khôi phục đúng bản gốc (không dịch ngược để khỏi sai lệch)
    if (snap && newLang === snap.baseLang) {
      const edited = !same(cvData, snap.out)
      if (edited && !window.confirm('Bạn đã sửa bản dịch. Quay về ngôn ngữ gốc sẽ khôi phục nội dung trước khi dịch và mất phần đã sửa. Tiếp tục?')) return
      translatedRef.current = null
      setPdfLang(newLang)
      handleCvChange(snap.base, newLang)
      handleBuildPdf(snap.base, runId, project, position, newLang, keepContact)
      return
    }
    // Sang ngôn ngữ khác với nội dung: dịch máy nội dung trước (nếu bộ dịch hỗ trợ chiều này)
    if (canTranslateTo(newLang)) {
      const out = await translateNow(cvData, runId, newLang)
      if (out) {
        translatedRef.current = { base: cvData, baseLang: contentLang, out, outLang: newLang }
        setPdfLang(newLang)
        handleCvChange(out, newLang)
        handleBuildPdf(out, runId, project, position, newLang, keepContact)
        return
      }
    }
    // Không dịch được (chưa bật dịch, chiều không hỗ trợ, hoặc lỗi): KHÔNG âm thầm tạo bản lẫn hai thứ tiếng, hỏi lại người dùng
    const names = { vi: 'Tiếng Việt', en: 'English' }
    const ok = window.confirm(
      `Chưa dịch được nội dung sang ${names[newLang]}.

` +
        `Nếu tiếp tục, bản PDF chỉ đổi nhãn và tiêu đề mục sang ${names[newLang]}, còn nội dung vẫn là ${names[contentLang]} (hai thứ tiếng lẫn nhau).

` +
        'Vẫn đổi ngôn ngữ?'
    )
    if (!ok) return
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

  // Gọi dịch máy cho một hồ sơ (không hỏi lại); trả hồ sơ đã dịch hoặc null nếu lỗi
  const translateNow = async (cv, rid, target = 'en') => {
    setIsTranslating(true)
    setTranslateError(null)
    try {
      const res = await translateCv(cv, rid, target)
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
    setPdfLang(sourceLangOf(cv0)) // nội dung về bản gốc thì nhãn cũng về ngôn ngữ gốc, tránh lẫn hai thứ tiếng
    handleCvChange(JSON.parse(JSON.stringify(cv0)), sourceLangOf(cv0))
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
    translation: config?.translation, isTranslating, translateReport, translateError,
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
