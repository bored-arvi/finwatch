import { useState, useEffect } from 'react'
import Header       from './components/Header.jsx'
import Pipeline     from './components/Pipeline.jsx'
import UploadPanel  from './components/UploadPanel.jsx'
import ResultsPanel from './components/ResultsPanel.jsx'
import ReviewBoard  from './components/ReviewBoard.jsx'
import LogTerminal  from './components/LogTerminal.jsx'
import { useScan }  from './hooks/useScan.js'
import { proposeRedactions, getLLMConfig, setLLMConfig } from './api/client.js'
import styles from './App.module.css'

export default function App() {
  const { stage, result, error, progress, logs, run, reset } = useScan()

  const [reviewData,    setReviewData]    = useState(null)
  const [proposing,     setProposing]     = useState(false)
  const [proposeError,  setProposeError]  = useState(null)
  const [proposeLog,    setProposeLog]    = useState([])
  const [activeMode,    setActiveMode]    = useState(null)
  const [llmEngine,     setLlmEngine]     = useState('ollama')
  const [geminiKey,     setGeminiKey]     = useState('')
  const [showSettings,  setShowSettings]  = useState(false)
  const [savingKey,     setSavingKey]     = useState(false)
  const [keyMsg,        setKeyMsg]        = useState('')

  const scanning = stage && stage !== 'done' && stage !== 'error'

  useEffect(() => {
    getLLMConfig().then(r => setLlmEngine(r.data.engine)).catch(() => {})
  }, [])

  const handleSaveKey = async () => {
    setSavingKey(true); setKeyMsg('')
    try {
      const r = await setLLMConfig(geminiKey)
      setLlmEngine(r.data.engine)
      setKeyMsg(r.data.engine === 'gemini' ? '✓ Gemini active' : '✓ Using Ollama')
    } catch { setKeyMsg('✕ Failed') }
    finally { setSavingKey(false) }
  }

  const handleClearKey = async () => {
    setGeminiKey('')
    try { await setLLMConfig(''); setLlmEngine('ollama'); setKeyMsg('✓ Using Ollama') } catch {}
  }

  const handleScan = async (mode, payload) => {
    setActiveMode(mode)
    if (mode === 'image') {
      setProposing(true); setProposeError(null); setReviewData(null); setProposeLog([])
      const log = (lvl, msg) => setProposeLog(l => [...l, { level: lvl, msg, ts: new Date().toLocaleTimeString() }])
      try {
        log('info', 'Uploading image...')
        log('info', `Engine: ${llmEngine}`)
        log('info', 'Running face detection + OCR...')
        const resp = await proposeRedactions(payload)
        log('info', `${resp.data.proposals?.length ?? 0} candidates evaluated`)
        log('success', `${resp.data.sensitive_count} sensitive · ${resp.data.safe_count} safe`)
        setReviewData(resp.data)
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        setProposeError(msg)
        log('error', msg)
      } finally { setProposing(false) }
    } else {
      run(mode, payload)
    }
  }

  const handleReset = () => {
    reset(); setReviewData(null); setProposeError(null); setProposeLog([]); setActiveMode(null)
  }

  const showReview  = activeMode === 'image' && (reviewData || proposing || proposeError)
  const showResults = activeMode !== 'image' && (result || stage)
  const pipeStage   = proposing ? 'detect' : reviewData ? 'review' : stage

  return (
    <div className={styles.app}>
      <Header />

      <main className={styles.main}>

        <div className={styles.hero}>
          <p className={styles.eyebrow}>Privacy Redaction Engine</p>
          <h1 className={styles.h1}>
            Detect. Review.<br/>
            <span className={styles.accent}>Redact.</span>
          </h1>
          <p className={styles.heroSub}>
            Local-first PII detection across images, video, audio and text — with human-in-the-loop review.
          </p>
        </div>

        {/* LLM engine bar */}
        <div className={styles.llmBar}>
          <span className={styles.llmBadge} style={{
            color:       llmEngine === 'gemini' ? 'var(--blue)' : 'var(--green)',
            borderColor: llmEngine === 'gemini' ? 'rgba(59,130,246,.3)' : 'rgba(34,197,94,.3)',
            background:  llmEngine === 'gemini' ? 'rgba(59,130,246,.07)' : 'rgba(34,197,94,.07)',
          }}>
            {llmEngine === 'gemini' ? 'Gemini' : 'Ollama'}
          </span>
          <span className={styles.llmLabel}>
            {llmEngine === 'gemini' ? 'Google Gemini 2.5 Flash' : 'Local LLaMA 3'}
          </span>
          <button className={styles.settingsBtn} onClick={() => setShowSettings(s => !s)}>
            {showSettings ? 'Close' : '⚙ Settings'}
          </button>
        </div>

        {showSettings && (
          <div className={styles.settingsPanel}>
            <p className={styles.settingsTitle}>LLM Engine</p>
            <p className={styles.settingsSub}>
              Leave blank to use Ollama (local, private). Enter a Gemini API key to use Google Gemini — faster and more accurate on dense documents.
            </p>
            <div className={styles.keyRow}>
              <input
                className={styles.keyInput}
                type="password"
                placeholder="Paste Gemini API key — or leave blank for Ollama"
                value={geminiKey}
                onChange={e => setGeminiKey(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSaveKey()}
              />
              <button className={styles.keyBtn} onClick={handleSaveKey} disabled={savingKey}>
                {savingKey ? '...' : 'Apply'}
              </button>
              {(geminiKey || llmEngine === 'gemini') && (
                <button className={`${styles.keyBtn} ${styles.keyBtnClear}`} onClick={handleClearKey}>Clear</button>
              )}
            </div>
            {keyMsg && (
              <p className={styles.keyMsg} style={{ color: keyMsg.startsWith('✕') ? 'var(--red)' : 'var(--green)' }}>
                {keyMsg}
              </p>
            )}
          </div>
        )}

        {pipeStage && <Pipeline stage={pipeStage} />}

        {!reviewData ? (
          <>
            <div className={styles.grid}>
              <UploadPanel onScan={handleScan} scanning={scanning || proposing} progress={progress} />
              {showResults ? (
                <ResultsPanel result={result} stage={stage} />
              ) : (
                <div className={styles.hintCard}>
                  <span className={styles.hintIcon}>🛡️</span>
                  <p className={styles.hintTitle}>Human-in-the-Loop Review</p>
                  <p className={styles.hintSub}>
                    AI proposes redactions with reasoning. You approve or dismiss before anything is permanently changed.
                  </p>
                  <div className={styles.steps}>
                    {['Detect faces & text', 'LLM classifies PII', 'You review & approve', 'Apply & download'].map((s,i) => (
                      <div key={i} className={styles.stepRow}>
                        <span className={styles.stepNum}>{i+1}</span>
                        {s}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {proposeError && (
              <div className={styles.errorBanner}>
                <span>⚠ {proposeError}</span>
                <button onClick={handleReset} className={styles.errClose}>✕</button>
              </div>
            )}
          </>
        ) : (
          <ReviewBoard data={reviewData} onReset={handleReset} />
        )}

        <LogTerminal logs={showReview && !reviewData ? proposeLog : logs} />

        {!reviewData && (result || error) && (
          <div className={styles.resetRow}>
            <button className={styles.resetBtn} onClick={handleReset}>↺ New Scan</button>
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        PRIVEX · OpenCV DNN · PaddleOCR · Whisper · {llmEngine === 'gemini' ? 'Gemini 2.5 Flash' : 'Ollama LLaMA 3'} · ffmpeg
      </footer>
    </div>
  )
}
