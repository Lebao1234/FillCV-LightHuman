import { useEffect, useState, useCallback } from 'react'
import Header from './components/Header.jsx'
import ChatPanel from './components/ChatPanel.jsx'
import StageScreen from './components/StageScreen.jsx'
import PdfPanel from './components/PdfPanel.jsx'
import OriginalCvPreview from './components/OriginalCvPreview.jsx'
import {
  getConfig,
  extractCv,
  buildPdf,
  getPdfStatus,
} from './api/client.js'

// Ứng dụng chính FillCV Light Human
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

  // Trạng thái tiến độ & hàng đợi
  const [isExtracting, setIsExtracting] = useState(false)
  const [isBuildingPdf, setIsBuildingPdf] = useState(false)
  const [queuePos, setQueuePos] = useState(0)
  const [queueWhat, setQueueWhat] = useState('')
  const [activeStep, setActiveStep] = useState(0)
  const [stageLabels, setStageLabels] = useState([])

  // Lịch sử Chat
  const [chatMessages, setChatMessages] = useState([])

  // Kết quả bản PDF
  const [pdfData, setPdfData] = useState(null)
  const [summary, setSummary] = useState('')

  // Validation & Review
  const [structureErrors] = useState([])
  const [violations] = useState([])
  const [, setReview] = useState(null)

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

  // Đánh giá trạng thái bản PDF qua backend
  const updatePdfStatus = useCallback(
    async (currentCv, currentPdfData, isCheckedGen, isRev) => {
      if (!currentPdfData) {
        setPdfStatus({
          outdated: false,
          pdf_dirty: false,
          can_download: false,
          pill_kind: 'idle',
          pill_text: 'Chưa dựng',
        })
        return
      }

      try {
        const res = await getPdfStatus({
          has_pdf: Boolean(currentPdfData.filename),
          pdf_fingerprint: currentPdfData.fingerprint,
          current_fingerprint: currentPdfData.fingerprint, // Khớp ban đầu
          checklist: currentPdfData.checklist,
          has_violations: violations.length > 0,
          has_structure_errors: structureErrors.length > 0,
          checked_generated: isCheckedGen,
          reviewed: isRev,
        })
        setPdfStatus(res)
      } catch (err) {
        console.error('Lỗi tính trạng thái PDF:', err)
      }
    },
    [violations.length, structureErrors.length]
  )

  // Cập nhật trạng thái khi các checkbox thay đổi
  useEffect(() => {
    if (pdfData) {
      updatePdfStatus(cvData, pdfData, checkedGenerated, reviewed)
    }
  }, [checkedGenerated, reviewed, pdfData, updatePdfStatus, cvData])

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
        setSummary(res.summary || '')
        setPdfStatus(res.status)
      } catch (err) {
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            kind: 'error',
            title: 'Dựng PDF thất bại.',
            text: err.message,
          },
        ])
      } finally {
        setIsBuildingPdf(false)
        setQueuePos(0)
      }
    },
    []
  )

  // Gửi file CV lên backend
  const handleSubmitCv = ({ file, project: prj, position: pos }) => {
    setIsExtracting(true)
    setQueuePos(0)
    setActiveStep(0)

    // Thêm tin nhắn file của user vào chat
    setChatMessages((prev) => [
      ...prev,
      {
        role: 'user',
        kind: 'file',
        filename: file.name,
        project: prj,
        position: pos,
      },
    ])

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
        setIsExtracting(false)
        setRunId(data.run_id)
        setCvData(data.cv)
        setCv0(data.cv)
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

        // Thêm tin nhắn ghi chú của trợ lý vào chat
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            kind: 'notes',
            name: data.cv.full_name,
            notes: data.cv.model_notes,
            salary: data.cv.expected_salary,
            hasPhoto: data.has_photo,
            review: (data.warnings || []).map((w) => w.message),
          },
        ])

        // Dựng PDF tự động lần đầu
        handleBuildPdf(data.cv, data.run_id, prj, pos || data.cv.target_title || '', pdfLang)
      },
      onError: (errMsg) => {
        setIsExtracting(false)
        setQueuePos(0)
        setChatMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            kind: 'error',
            title: 'Không đọc được CV.',
            text: errMsg,
          },
        ])
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

  // Làm mới ứng dụng
  const handleReset = () => {
    setRunId(null)
    setCvData(null)
    setCv0(null)
    setOriginalName('')
    setProject('')
    setPosition('')
    setPdfData(null)
    setSummary('')
    setChatMessages([])
    setReview(null)
    setCheckedGenerated(false)
    setReviewed(false)
    setPdfStatus(null)
    setActiveTab('pdf')
  }

  const isBusy = isExtracting || isBuildingPdf

  return (
    <div className="block-container">
      <Header logoB64={config?.logo_header_b64} />

      <main className="app-grid">
        {/* Cột trái: Khung Chat và Form Upload */}
        <section className="col-left">
          <ChatPanel
            chatMessages={chatMessages}
            isExtracting={isExtracting}
            onReset={handleReset}
            onSubmitCv={handleSubmitCv}
            structureErrors={structureErrors}
            violations={violations}
            summary={summary}
          />
        </section>

        {/* Cột phải: Hồ sơ PDF & Các tab chức năng */}
        <section className="col-right">
          <div className="lh-ph">
            <div className="h">Hồ sơ PDF</div>
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
              {/* Thanh chọn Tab */}
              <div className="tabs-header">
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'pdf' ? 'active' : ''}`}
                  onClick={() => setActiveTab('pdf')}
                >
                  Bản PDF
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'edit' ? 'active' : ''}`}
                  onClick={() => setActiveTab('edit')}
                >
                  Chỉnh sửa nội dung
                </button>
                <button
                  type="button"
                  className={`tab-btn ${activeTab === 'original' ? 'active' : ''}`}
                  onClick={() => setActiveTab('original')}
                >
                  CV gốc
                </button>
              </div>

              {/* Nội dung Tab */}
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
                <div style={{ padding: 'var(--sp-4)', background: 'var(--white)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)' }}>
                  <h4 style={{ margin: '0 0 var(--sp-2)' }}>Form chỉnh sửa hồ sơ</h4>
                  <p style={{ color: 'var(--muted)', fontSize: 'var(--fs-sm)' }}>
                    Tính năng chỉnh sửa chi tiết từng mục theo loại sẽ được triển khai đầy đủ ở Giai đoạn 3.
                  </p>
                </div>
              )}

              {activeTab === 'original' && (
                <OriginalCvPreview runId={runId} originalName={originalName} />
              )}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
