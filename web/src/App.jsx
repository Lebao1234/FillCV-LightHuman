import { useEffect, useState, useCallback } from 'react'
import Header from './components/Header.jsx'
import ExtractionPanel from './components/ExtractionPanel.jsx'
import StageScreen from './components/StageScreen.jsx'
import PdfPanel from './components/PdfPanel.jsx'
import OriginalCvPreview from './components/OriginalCvPreview.jsx'
import ProfileForm from './components/profile/ProfileForm.jsx'
import {
  getConfig,
  extractCv,
  validateCv,
  buildPdf,
  getPdfStatus,
} from './api/client.js'

// Ứng dụng chính FillCV Light Human
// Các tab của khung bên phải
const TABS = [
  { id: 'pdf', label: 'Bản PDF' },
  { id: 'edit', label: 'Chỉnh sửa nội dung' },
  { id: 'original', label: 'CV gốc' },
]

export default function App() {
  const [config, setConfig] = useState(null)

  // Trạng thái phiên CV
  const [runId, setRunId] = useState(null)
  const [cvData, setCvData] = useState(null)
  const [, setCv0] = useState(null)
  const [originalName, setOriginalName] = useState('')
  const [project, setProject] = useState('')
  const [position, setPosition] = useState('')
  const [pdfLang, setPdfLang] = useState('vi')
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

  // Tab đang chọn
  const [activeTab, setActiveTab] = useState('pdf')

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
    async (targetCv, targetRunId, targetPrj, targetPos, targetLang) => {
      setIsBuildingPdf(true)
      try {
        const res = await buildPdf({
          runId: targetRunId,
          cv: targetCv,
          project: targetPrj,
          position: targetPos,
          lang: targetLang,
        })
        setPdfData(res)
        setCurrentFingerprint(res.fingerprint)
        setSummary(res.summary || '')
        setPdfStatus(res.status)
        setError(null)
      } catch (err) {
        setError(err.message || 'Dựng PDF thất bại.')
      } finally {
        setIsBuildingPdf(false)
        setQueuePos(0)
      }
    },
    []
  )

  // Gửi file CV lên backend
  const handleSubmitCv = ({ file, project: prj, position: pos, lang: chosenLang }) => {
    setIsExtracting(true)
    setQueuePos(0)
    setActiveStep(0)
    setError(null)
    setOriginalName(file.name)
    setProject(prj)
    setPosition(pos)
    setElapsedSeconds(null)
    if (chosenLang) {
      setPdfLang(chosenLang)
    }

    extractCv(file, prj, pos, {
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

        // Dựng PDF tự động lần đầu
        handleBuildPdf(data.cv, data.run_id, prj, pos || data.cv.target_title || '', initialLang)
      },
      onError: (errMsg) => {
        setIsExtracting(false)
        setQueuePos(0)
        setError(errMsg)
      },
    })
  }

  // Đổi ngôn ngữ PDF
  const handleChangeLang = (newLang) => {
    setPdfLang(newLang)
    if (cvData && runId) {
      handleBuildPdf(cvData, runId, project, position, newLang)
    }
  }

  // Cập nhật nội dung hồ sơ và tự động validate
  const handleCvChange = (newCv) => {
    setCvData(newCv)
    validateCv(newCv, project, position, runId, pdfLang)
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

  // Làm mới ứng dụng
  const handleReset = () => {
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
    setPdfLang('vi')
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

  const isBusy = isExtracting || isBuildingPdf

  return (
    <div className="block-container mx-auto max-w-[1480px] p-4 sm:px-4 sm:pt-4 sm:pb-6 lg:px-8 lg:pt-6 lg:pb-8">
      <Header logoB64={config?.logo_header_b64} />

      <main className="app-grid grid grid-cols-1 lg:grid-cols-[5fr_7fr] gap-6 lg:gap-8 items-start">
        {/* Cột trái: Trạng thái bóc tách CV (Stateful Pipeline & Dashboard) */}
        <section className="col-left min-w-0 flex flex-col">
          <ExtractionPanel
            isExtracting={isExtracting}
            isBuildingPdf={isBuildingPdf}
            queuePos={queuePos}
            queueWhat={queueWhat || (isBuildingPdf ? 'dựng PDF' : 'đọc CV')}
            activeStep={activeStep}
            stageLabels={stageLabels}
            cvData={cvData}
            originalName={originalName}
            project={project}
            position={position}
            pdfLang={pdfLang}
            elapsedSeconds={elapsedSeconds}
            summary={summary}
            review={review}
            error={error}
            structureErrors={structureErrors}
            violations={violations}
            onSubmitCv={handleSubmitCv}
            onReset={handleReset}
          />
        </section>

        {/* Cột phải: Hồ sơ PDF & Các tab chức năng */}
        <section className="col-right min-w-0 flex flex-col">
          <div className="lh-ph flex items-center justify-between h-10 mb-3">
            <div className="h text-md font-semibold text-ink uppercase tracking-[0.06em] flex items-center gap-2 after:content-[''] after:w-3.5 after:h-0.5 after:bg-gold">
              Hồ sơ PDF
            </div>
          </div>

          {isBusy ? (
            <StageScreen
              busy={true}
              step={activeStep}
              queuePos={queuePos}
              queueWhat={queueWhat || (isBuildingPdf ? 'dựng PDF' : 'đọc CV')}
              labels={stageLabels}
            />
          ) : !cvData ? (
            <StageScreen busy={false} />
          ) : (
            <div>
              {/* Thanh chọn Tab: theo mẫu WAI-ARIA tabs, đổi tab bằng phím mũi tên */}
              <div
                className="tabs-header flex border-b border-line mb-4"
                role="tablist"
                aria-label="Các chế độ xem hồ sơ"
                onKeyDown={handleTabKeyDown}
              >
                {TABS.map((t) => (
                  <button
                    key={t.id}
                    id={`tab-${t.id}`}
                    type="button"
                    role="tab"
                    aria-selected={activeTab === t.id}
                    aria-controls="tab-panel"
                    tabIndex={activeTab === t.id ? 0 : -1}
                    className={`tab-btn px-4 py-2 bg-transparent border-b-2 text-md font-medium cursor-pointer transition-colors duration-200 outline-none focus-visible:outline-2 focus-visible:outline-navy ${
                      activeTab === t.id
                        ? 'active text-navy border-navy font-semibold'
                        : 'text-muted border-transparent hover:text-ink'
                    }`}
                    onClick={() => setActiveTab(t.id)}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Nội dung Tab */}
              <div id="tab-panel" role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
                {activeTab === 'pdf' && (
                  <PdfPanel
                    pdfData={pdfData}
                    structureErrors={structureErrors}
                    violations={violations}
                    status={pdfStatus}
                    isBuilding={isBuildingPdf}
                    onUpdatePdf={() => handleBuildPdf(cvData, runId, project, position, pdfLang)}
                    checkedGenerated={checkedGenerated}
                    setCheckedGenerated={setCheckedGenerated}
                    reviewed={reviewed}
                    setReviewed={setReviewed}
                    pdfLang={pdfLang}
                    onChangeLang={handleChangeLang}
                  />
                )}

                {activeTab === 'edit' && (
                  <ProfileForm
                    cv={cvData}
                    onChangeCv={handleCvChange}
                    project={project}
                    onChangeProject={setProject}
                    position={position}
                    onChangePosition={setPosition}
                    runId={runId}
                    photoUrl={photoUrl}
                    onChangePhoto={setPhotoUrl}
                    review={review}
                  />
                )}

                {activeTab === 'original' && (
                  <OriginalCvPreview runId={runId} originalName={originalName} />
                )}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
