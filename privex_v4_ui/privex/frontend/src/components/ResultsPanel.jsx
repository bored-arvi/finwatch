import { useState } from 'react'
import { downloadUrl } from '../api/client'
import styles from './ResultsPanel.module.css'

function Badge({ color, children }) {
  return <span className={styles.badge} style={{ color, borderColor: color+'33', background: color+'11' }}>{children}</span>
}

function StatCard({ value, label, color }) {
  return (
    <div className={styles.statCard}>
      <span className={styles.statVal} style={{ color }}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

export default function ResultsPanel({ result, stage }) {
  const [dismissed, setDismissed] = useState(new Set())
  const [revealed,  setRevealed]  = useState(new Set())

  if (!result && stage !== 'done') {
    return (
      <div className={styles.card}>
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <path d="M16 4L28 10V22L16 28L4 22V10L16 4Z" stroke="currentColor" strokeWidth="1.5" opacity=".3"/>
              <circle cx="16" cy="16" r="4" stroke="currentColor" strokeWidth="1.5" opacity=".3"/>
            </svg>
          </div>
          <p className={styles.emptyTitle}>No scan yet</p>
          <p className={styles.emptySub}>Upload a file or paste text to detect PII</p>
        </div>
      </div>
    )
  }

  const detections  = result?.detections || result?.entities || []
  const visible     = detections.filter((_, i) => !dismissed.has(i))
  const isSensitive = result?.sensitive
  const faceCount   = result?.face_count ?? result?.face_detections ?? 0
  const textCount   = result?.text_redacted ?? result?.entity_count ?? 0
  const muteCount   = result?.muted_count ?? result?.muted_segments?.length ?? 0
  const totalCount  = detections.length

  const renderRedacted = () => {
    if (!result?.redacted_text) return null
    const parts = result.redacted_text.split(/(█+)/g)
    let key = 0
    return parts.map(part => {
      if (/^█+$/.test(part)) {
        const k = key++
        const show = revealed.has(k)
        return (
          <span key={k}
            className={`${styles.redacted} ${show ? styles.revealed : ''}`}
            onClick={() => setRevealed(p => { const n=new Set(p); show?n.delete(k):n.add(k); return n })}
            title={show ? 'Click to hide' : 'Click to reveal'}
          >{show ? '···' : part}</span>
        )
      }
      return <span key={`t${key++}`}>{part}</span>
    })
  }

  return (
    <div className={styles.card}>
      {/* Header */}
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>Results</span>
        <Badge color={isSensitive ? 'var(--red)' : 'var(--green)'}>
          {isSensitive ? `${totalCount} issue${totalCount !== 1 ? 's' : ''} found` : 'Clean'}
        </Badge>
      </div>

      {/* Stats */}
      <div className={styles.statsRow}>
        <StatCard value={faceCount}  label="Faces"      color="var(--red)"   />
        <StatCard value={textCount}  label="Text PII"   color="var(--amber)" />
        <StatCard value={muteCount}  label="Audio mutes" color="var(--blue)" />
        <StatCard value={isSensitive ? 'HIGH' : 'LOW'} label="Risk" color={isSensitive ? 'var(--red)' : 'var(--green)'} />
      </div>

      {/* Video info */}
      {result?.mode === 'video' && (
        <div className={styles.section}>
          <div className={styles.sectionHead}>Video Details</div>
          <div className={styles.statsRow}>
            <StatCard value={result.frames_processed ?? 0} label="Frames"   color="var(--blue)"  />
            <StatCard value={`${result.duration_seconds ?? 0}s`} label="Duration" color="var(--blue)" />
            <StatCard value={result.face_detections ?? 0}  label="Face hits" color="var(--red)"  />
            <StatCard value={result.sensitive_values?.length ?? 0} label="Text PII" color="var(--amber)" />
          </div>
          {result.sensitive_values?.length > 0 && (
            <div className={styles.tagList}>
              {result.sensitive_values.map((v,i) => (
                <span key={i} className={styles.piiTag}>{v}</span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Detections */}
      {detections.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHead}>
            Detections
            {dismissed.size > 0 && (
              <button className={styles.clearBtn} onClick={() => setDismissed(new Set())}>
                Restore {dismissed.size}
              </button>
            )}
          </div>
          {visible.length === 0 ? (
            <div className={styles.allDismissed}>All dismissed</div>
          ) : (
            <div className={styles.detList}>
              {detections.map((det, i) => {
                if (dismissed.has(i)) return null
                const type  = det.type || 'pii'
                const color = type === 'face' ? 'var(--red)' : type === 'text' ? 'var(--amber)' : 'var(--blue)'
                return (
                  <div key={i} className={styles.det} style={{ '--c': color, animationDelay: `${i*40}ms` }}>
                    <div className={styles.detDot} style={{ background: color }}/>
                    <div className={styles.detBody}>
                      <div className={styles.detLabel}>{det.label || det.text || type}</div>
                      {det.reason && <div className={styles.detReason}>{det.reason}</div>}
                      {det.value && det.value !== det.label && <div className={styles.detValue}>{det.value}</div>}
                    </div>
                    {det.confidence != null && (
                      <span className={styles.detConf}>{(det.confidence*100).toFixed(0)}%</span>
                    )}
                    <button className={styles.dismissBtn}
                      onClick={() => setDismissed(p => new Set([...p, i]))}>
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M1.5 1.5l7 7M8.5 1.5l-7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Redacted text */}
      {result?.redacted_text && (
        <div className={styles.section}>
          <div className={styles.sectionHead}>
            Redacted Output
            <span className={styles.hint}>click ██ to peek</span>
          </div>
          <div className={styles.textBox}>{renderRedacted()}</div>
        </div>
      )}

      {/* OCR text */}
      {result?.ocr_text && (
        <div className={styles.section}>
          <div className={styles.sectionHead}>OCR Text</div>
          <div className={styles.ocrBox}>{result.ocr_text}</div>
        </div>
      )}

      {/* Transcript */}
      {result?.transcript && (
        <div className={styles.section}>
          <div className={styles.sectionHead}>Transcript</div>
          <div className={styles.ocrBox}>{result.transcript}</div>
          {result.muted_segments?.length > 0 && (
            <div className={styles.tagList}>
              {result.muted_segments.map((s,i) => (
                <span key={i} className={styles.muteTag}>
                  🔇 {s.start.toFixed(2)}s–{s.end.toFixed(2)}s
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Download */}
      {result?.redacted_file && (
        <a href={downloadUrl(result.redacted_file)} className={styles.dlBtn} download>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 2v7M4 6l3 3 3-3M2 11h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Download Redacted File
        </a>
      )}
    </div>
  )
}
