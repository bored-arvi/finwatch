import { useState } from 'react'
import Header      from './components/Header.jsx'
import Pipeline    from './components/Pipeline.jsx'
import UploadPanel from './components/UploadPanel.jsx'
import ResultsPanel from './components/ResultsPanel.jsx'
import LogTerminal  from './components/LogTerminal.jsx'
import { useScan }  from './hooks/useScan.js'
import styles from './App.module.css'

export default function App() {
  const { stage, result, error, progress, logs, run, reset } = useScan()
  const scanning = stage && stage !== 'done' && stage !== 'error'

  return (
    <div className={styles.app}>
      <Header />

      <main className={styles.main}>
        {/* Hero */}
        <div className={styles.hero}>
          <p className={styles.tag}>// LOCAL-FIRST · LLM-AGNOSTIC · OFFLINE CAPABLE</p>
          <h1 className={styles.h1}>
            Detect. Redact.<br />
            <span className={styles.accent}>Protect.</span>
          </h1>
        </div>

        {/* Pipeline visualizer */}
        <Pipeline stage={stage} />

        {/* Error banner */}
        {error && (
          <div className={styles.errorBanner}>
            <span>⚠ {error}</span>
            <button onClick={reset} className={styles.errClose}>✕</button>
          </div>
        )}

        {/* Two-column layout */}
        <div className={styles.grid}>
          <UploadPanel
            onScan={run}
            scanning={!!scanning}
            progress={progress}
          />
          <ResultsPanel result={result} stage={stage} />
        </div>

        {/* Log terminal */}
        <LogTerminal logs={logs} />

        {/* Reset */}
        {(result || error) && (
          <div className={styles.resetRow}>
            <button className={styles.resetBtn} onClick={reset}>↺ NEW SCAN</button>
          </div>
        )}
      </main>

      <footer className={styles.footer}>
        PRIVEX — AI PRIVACY FIREWALL &nbsp;·&nbsp;
        FastAPI + PaddleOCR + OpenCV DNN + Whisper + Ollama
      </footer>
    </div>
  )
}
