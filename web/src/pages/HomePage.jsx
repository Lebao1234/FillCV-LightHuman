import { useOutletContext } from 'react-router-dom'
import ExtractionPanel from '../components/ExtractionPanel.jsx'
import StageScreen from '../components/StageScreen.jsx'
import PdfPanel from '../components/PdfPanel.jsx'
import OriginalCvPreview from '../components/OriginalCvPreview.jsx'
import ProfileForm from '../components/profile/ProfileForm.jsx'
import { TABS, CONTACT_LABELS } from '../constants.js'

// Trang chính (/): nạp CV, theo dõi bóc tách; khung phải có 3 tab: bản PDF, CV gốc, chỉnh sửa nội dung
export default function HomePage() {
  const {
    isExtracting, isBuildingPdf, queuePos, queueWhat, activeStep, stageLabels, cvData, originalName,
    project, position, pdfLang, elapsedSeconds, summary, error, structureErrors, violations,
    handleSubmitCv, handleReset, isBusy, activeTab, setActiveTab, handleTabKeyDown, pdfData, pdfStatus,
    handleBuildPdf, runId, keepContact, checkedGenerated, setCheckedGenerated, reviewed, setReviewed,
    handleChangeLang, handleChangeKeepContact, handleCvChange, setProject, setPosition, photoUrl, setPhotoUrl,
    isDirty, savedAt, handleSaveEdits, handleRevert, translation, isTranslating, translateReport,
    translateError, handleTranslate,
  } = useOutletContext()

  return (
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
          photoUrl={photoUrl}
          originalName={originalName}
          project={project}
          position={position}
          pdfLang={pdfLang}
          keepContact={keepContact}
          elapsedSeconds={elapsedSeconds}
          summary={summary}
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
                  onUpdatePdf={() => handleBuildPdf(cvData, runId, project, position, pdfLang, keepContact)}
                  checkedGenerated={checkedGenerated}
                  setCheckedGenerated={setCheckedGenerated}
                  reviewed={reviewed}
                  setReviewed={setReviewed}
                  pdfLang={pdfLang}
                  onChangeLang={handleChangeLang}
                  keepContact={keepContact}
                  contactMissing={!(cvData.facts || []).some((f) => CONTACT_LABELS.includes(f.label))}
                  onChangeKeepContact={handleChangeKeepContact}
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
                  isDirty={isDirty}
                  isSaving={isBuildingPdf}
                  savedAt={savedAt}
                  saveError={error}
                  structureErrors={structureErrors}
                  violations={violations}
                  onSave={handleSaveEdits}
                  onRevert={handleRevert}
                  onViewPdf={() => setActiveTab('pdf')}
                  translationAvailable={Boolean(translation?.available)}
                  isTranslating={isTranslating}
                  translateReport={translateReport}
                  translateError={translateError}
                  onTranslate={handleTranslate}
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
  )
}
