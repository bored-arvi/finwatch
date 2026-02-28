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

  // LLM engine state
  const [llmEngine,    setLlmEngine]    = useState('ollama')
  const [geminiKey,    setGeminiKey]    = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [savingKey,    setSavingKey]    = useState(false)
  const [keyMsg,       setKeyMsg]       = useState('')

  const scanning = stage && stage !== 'done' && stage !== 'error'

  useEffect(() => {
    getLLMConfig().then(r => setLlmEngine(r.data.engine)).catch(() => {})
  }, [])

  const handleSaveKey = async () => {
    setSavingKey(true); setKeyMsg('')
    try {
      const r = await setLLMConfig(geminiKey)
      setLlmEngine(r.data.engine)
      setKeyMsg(r.data.engine === 'gemini' ? '✓ Gemini active' : '✓ Switched to Ollama')
    } catch (e) {
      setKeyMsg('✕ Failed — check key or backend')
    } finally {
      setSavingKey(false)
    }
  }

  const handleClearKey = async () => {
    setGeminiKey('')
    try {
      await setLLMConfig('')
      setLlmEngine('ollama')
      setKeyMsg('✓ Switched to Ollama')
    } catch {}
  }

  const handleScan = async (mode, payload) => {
    setActiveMode(mode)
    if (mode === 'image') {
      setProposing(true); setProposeError(null); setReviewData(null); setProposeLog([])
      const log = (lvl, msg) => setProposeLog(l => [
        ...l, { level: lvl, msg, ts: new Date().toLocaleTimeString() }
      ])
      try {
        log('info', 'Uploading image...')
        log('info', `LLM engine: ${llmEngine}`)
        log('info', 'Running face detection + OCR...')
        const resp = await proposeRedactions(payload)
        log('info', `LLM evaluated ${resp.data.proposals?.length ?? 0} candidates`)
        log('info', `${resp.data.sensitive_count} sensitive · ${resp.data.safe_count} safe — ready for review`)
        setReviewData(resp.data)
      } catch (e) {
        const msg = e.response?.data?.detail || e.message
        setProposeError(msg)
        log('error', `Failed: ${msg}`)
      } finally {
        setProposing(false)
      }
    } else {
      // audio, video, text → direct scan
      run(mode, payload)
    }
  }

  const handleReset = () => {
    reset()
    setReviewData(null); setProposeError(null); setProposeLog([]); setActiveMode(null)
  }

  const showReview  = activeMode === 'image' && (reviewData || proposing || proposeError)
  const showResults = activeMode !== 'image' && (result || stage)
  const pipeStage   = proposing ? 'detect' : reviewData ? 'review' : stage

  return (
    <div className={styles.app}>
      <Header />

      <main className={styles.main}>

        {/* Hero */}
        <div className={styles.hero}>
          <p className={styles.tag}>// LOCAL-FIRST · CONTEXTUAL AI · HUMAN-IN-THE-LOOP</p>
          <h1 className={styles.h1}>
            Detect. Review.<br />
            <span className={styles.accent}>Redact.</span>
          </h1>
        </div>

        {/* LLM engine indicator + settings toggle */}
        <div className={styles.llmBar}>
          <span
            className={styles.llmBadge}
            style={{
              color:       llmEngine === 'gemini' ? '#4d9eff' : '#00e676',
              borderColor: llmEngine === 'gemini' ? 'rgba(77,158,255,.35)' : 'rgba(0,230,118,.35)',
              background:  llmEngine === 'gemini' ? 'rgba(77,158,255,.07)' : 'rgba(0,230,118,.07)',
            }}
          >
            {llmEngine === 'gemini' ? '◆ GEMINI API' : '⬡ OLLAMA LOCAL'}
          </span>
          <button className={styles.settingsBtn} onClick={() => setShowSettings(s => !s)}>
            {showSettings ? '▲ hide' : '⚙ LLM settings'}
          </button>
        </div>

        {/* Gemini key panel */}
        {showSettings && (
          <div className={styles.settingsPanel}>
            <p className={styles.settingsTitle}>LLM Engine</p>
            <p className={styles.settingsSub}>
              Leave blank to use Ollama (fully local, private).
              Paste a Gemini API key to use Google Gemini — faster and more accurate on dense documents.
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
                <button className={`${styles.keyBtn} ${styles.keyBtnClear}`} onClick={handleClearKey}>
                  Clear
                </button>
              )}
            </div>
            {keyMsg && (
              <p className={styles.keyMsg} style={{ color: keyMsg.startsWith('✕') ? 'var(--red)' : 'var(--green)' }}>
                {keyMsg}
              </p>
            )}
          </div>
        )}

        {/* Pipeline */}
        <Pipeline stage={pipeStage} />

        {!reviewData ? (
          <>
            <div className={styles.grid}>
              <UploadPanel onScan={handleScan} scanning={scanning || proposing} progress={progress} />

              {showResults ? (
                <ResultsPanel result={result} stage={stage} />
              ) : (
                <div className={styles.reviewHint}>
                  <span className={styles.hintIcon}>👁</span>
                  <p className={styles.hintTitle}>Human-in-the-Loop Review</p>
                  <p className={styles.hintSub}>
                    For images: AI proposes redactions with reasoning.<br />
                    You approve or dismiss before anything is permanently changed.<br />
                    Video, audio and text are processed automatically.
                  </p>
                  <div className={styles.hintSteps}>
                    <div className={styles.step}><span>1</span> AI detects faces + text</div>
                    <div className={styles.step}><span>2</span> LLM explains each finding</div>
                    <div className={styles.step}><span>3</span> You approve or dismiss</div>
                    <div className={styles.step}><span>4</span> Apply & download</div>
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
            <button className={styles.resetBtn} onClick={handleReset}>↺ NEW SCAN</button>
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        PRIVEX · FastAPI + PaddleOCR + OpenCV DNN + Whisper ·{' '}
        {llmEngine === 'gemini' ? 'Gemini API' : 'Ollama LLaMA 3'}
      </footer>
    </div>
  )
}
