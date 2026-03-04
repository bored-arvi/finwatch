import { useState, useRef } from 'react'
import styles from './UploadPanel.module.css'

const MODES = [
  { id: 'image', label: 'Image', icon: '🖼', accept: 'image/*',           hint: 'PNG, JPG, WEBP', desc: 'Detect faces & text PII' },
  { id: 'video', label: 'Video', icon: '🎬', accept: 'video/*,.mp4,.mov', hint: 'MP4, MOV — max 3s', desc: 'Frame-by-frame redaction' },
  { id: 'audio', label: 'Audio', icon: '🎙', accept: 'audio/*,.wav',      hint: 'WAV, MP3, OGG',    desc: 'Mute spoken PII' },
  { id: 'text',  label: 'Text',  icon: '📄', accept: null,                hint: 'Paste any text',   desc: 'Redact sensitive values' },
]

export default function UploadPanel({ onScan, scanning, progress }) {
  const [mode,     setMode]     = useState('image')
  const [file,     setFile]     = useState(null)
  const [text,     setText]     = useState('')
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const current = MODES.find(m => m.id === mode)
  const canScan = !scanning && (mode === 'text' ? text.trim().length > 0 : file !== null)

  const handleFile = f => { if (f) setFile(f) }
  const handleDrop = e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }
  const handleScan = () => { if (canScan) onScan(mode, mode === 'text' ? text : file) }
  const handleMode = m => { setMode(m); setFile(null); setText('') }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>Input</span>
        {(file || text) && (
          <span className={styles.readyPill}>
            <span className={styles.readyDot}/>
            Ready
          </span>
        )}
      </div>

      {/* Mode selector */}
      <div className={styles.modeGrid}>
        {MODES.map(m => (
          <button
            key={m.id}
            className={`${styles.modeBtn} ${mode === m.id ? styles.modeActive : ''}`}
            onClick={() => handleMode(m.id)}
          >
            <span className={styles.modeIcon}>{m.icon}</span>
            <span className={styles.modeLabel}>{m.label}</span>
          </button>
        ))}
      </div>

      {/* Drop zone */}
      {mode !== 'text' && (
        <div
          className={`${styles.drop} ${dragging ? styles.dragging : ''} ${file ? styles.hasFile : ''}`}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={handleDrop}
          onClick={() => !file && inputRef.current?.click()}
        >
          <input ref={inputRef} type="file" accept={current.accept}
            style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />

          {file ? (
            <div className={styles.fileRow}>
              <div className={styles.fileThumb}>{current.icon}</div>
              <div className={styles.fileMeta}>
                <div className={styles.fileName}>{file.name.length > 28 ? file.name.slice(0,28)+'…' : file.name}</div>
                <div className={styles.fileSize}>{(file.size/1024).toFixed(1)} KB · {current.label}</div>
              </div>
              <button className={styles.removeBtn} onClick={e => { e.stopPropagation(); setFile(null) }}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M2 2L12 12M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
          ) : (
            <div className={styles.dropInner}>
              <div className={styles.dropIconWrap}>
                <span className={styles.dropIcon}>{current.icon}</span>
              </div>
              <p className={styles.dropTitle}>Drop {current.label.toLowerCase()} here</p>
              <p className={styles.dropSub}>{current.hint} · <span className={styles.browse} onClick={() => inputRef.current?.click()}>browse</span></p>
            </div>
          )}
        </div>
      )}

      {/* Textarea */}
      {mode === 'text' && (
        <div className={styles.textWrap}>
          <textarea
            className={styles.textarea}
            placeholder="Paste any text containing PII — names, phone numbers, IDs, bank details, addresses..."
            value={text}
            onChange={e => setText(e.target.value)}
            rows={7}
          />
          {text && (
            <div className={styles.textMeta}>{text.length} chars · {text.split(/\s+/).filter(Boolean).length} words</div>
          )}
        </div>
      )}

      {/* Scan button */}
      <button className={styles.scanBtn} onClick={handleScan} disabled={!canScan}>
        {scanning ? (
          <span className={styles.scanInner}>
            <span className={styles.spinner}/>
            {progress > 0 && progress < 100 ? `Uploading ${progress}%` : 'Processing...'}
          </span>
        ) : (
          <span className={styles.scanInner}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M5 8h6M8 5v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Scan for PII
          </span>
        )}
      </button>
    </div>
  )
}
