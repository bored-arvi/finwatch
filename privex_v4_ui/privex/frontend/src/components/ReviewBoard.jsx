import { useState, useRef, useEffect } from 'react'
import { applyRedactions, downloadUrl } from '../api/client'
import styles from './ReviewBoard.module.css'

const TYPE_COLOR = { face: '#ef4444', text: '#f59e0b', default: '#3b82f6' }

export default function ReviewBoard({ data, onReset }) {
  const [proposals,   setProposals]   = useState(() => (data.proposals || []).map(p => ({ ...p })))
  const [hoveredId,   setHoveredId]   = useState(null)
  const [applying,    setApplying]    = useState(false)
  const [result,      setResult]      = useState(null)
  const [error,       setError]       = useState(null)
  const [filter,      setFilter]      = useState('all')
  const canvasRef = useRef()
  const imageRef  = useRef()

  const imgW = data.image_w || 800
  const imgH = data.image_h || 600
  const src  = `data:image/jpeg;base64,${data.preview_b64}`

  useEffect(() => {
    const canvas = canvasRef.current
    const img    = imageRef.current
    if (!canvas || !img || !img.complete) return
    const cw = canvas.width, ch = canvas.height
    const sx = cw / imgW,   sy = ch / imgH
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, cw, ch)

    proposals.forEach(p => {
      const { x, y, w, h } = p.bbox
      if (!w || !h) return
      const rx = x*sx, ry = y*sy, rw = w*sx, rh = h*sy
      const color    = TYPE_COLOR[p.type] || TYPE_COLOR.default
      const hovered  = hoveredId === p.id

      if (p.approved) {
        ctx.fillStyle = hovered ? color + 'cc' : color + '88'
        ctx.fillRect(rx, ry, rw, rh)
        ctx.fillStyle = 'rgba(255,255,255,0.9)'
        ctx.font = `600 ${Math.max(9, Math.min(12, rh * 0.3))}px Geist Mono, monospace`
        ctx.textAlign = 'center'
        ctx.fillText((p.type === 'face' ? 'FACE' : p.label || 'PII').slice(0, 12), rx + rw/2, ry + rh/2 + 4)
        ctx.textAlign = 'left'
      } else {
        ctx.setLineDash([4, 3])
        ctx.strokeStyle = color + '44'
        ctx.lineWidth = 1.5
        ctx.strokeRect(rx, ry, rw, rh)
        ctx.setLineDash([])
      }
      if (hovered) {
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.strokeRect(rx - 1, ry - 1, rw + 2, rh + 2)
      }
    })
  }, [proposals, hoveredId, imgW, imgH])

  const toggle          = id => setProposals(p => p.map(x => x.id === id ? { ...x, approved: !x.approved } : x))
  const approveAll      = ()  => setProposals(p => p.map(x => ({ ...x, approved: true })))
  const dismissAll      = ()  => setProposals(p => p.map(x => ({ ...x, approved: false })))
  const aiSuggestion    = ()  => setProposals(p => p.map(x => ({ ...x, approved: x.sensitive })))

  const handleApply = async () => {
    setApplying(true); setError(null)
    try {
      const boxes = proposals.filter(p => p.approved && p.bbox.w > 0).map(p => p.bbox)
      const resp  = await applyRedactions(data.session_token, boxes)
      setResult(resp.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally { setApplying(false) }
  }

  const approvedCount  = proposals.filter(p => p.approved).length
  const sensitiveCount = proposals.filter(p => p.sensitive).length
  const safeCount      = proposals.filter(p => !p.sensitive).length
  const filtered       = proposals.filter(p =>
    filter === 'sensitive' ? p.sensitive : filter === 'safe' ? !p.sensitive : true
  )

  // ── Done state ───────────────────────────────────────────────────────────────
  if (result) {
    return (
      <div className={styles.doneState}>
        <div className={styles.doneHeader}>
          <span className={styles.doneIcon}>✓</span>
          <div>
            <div className={styles.doneTitle}>{result.applied_count} redaction{result.applied_count !== 1 ? 's' : ''} applied</div>
            <div className={styles.doneSub}>Your redacted image is ready to download</div>
          </div>
          <button className={styles.resetBtn} onClick={onReset} style={{ marginLeft: 'auto' }}>↺ New scan</button>
        </div>
        <div className={styles.donePreview}>
          {result.redacted_b64 && (
            <img src={`data:image/jpeg;base64,${result.redacted_b64}`} alt="Redacted" />
          )}
          <a href={downloadUrl(result.redacted_file)} className={styles.dlBtn} download>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 2v7M4 6l3 3 3-3M2 11h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Download Redacted Image
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.wrap}>
      {/* Top bar */}
      <div className={styles.topBar}>
        <div className={styles.topTitle}>Human Review</div>
        <div className={styles.topMeta}>
          <span style={{ color: 'var(--red)' }}>{sensitiveCount} sensitive</span>
          {' · '}
          <span style={{ color: 'var(--green)' }}>{safeCount} safe</span>
          {' · '}
          <span>{approvedCount} to redact</span>
        </div>
        <button className={styles.applyBtn} onClick={handleApply} disabled={applying || approvedCount === 0}>
          {applying ? 'Applying…' : `Apply ${approvedCount} redaction${approvedCount !== 1 ? 's' : ''}`}
        </button>
        <button className={styles.resetBtn} onClick={onReset}>Cancel</button>
      </div>

      {error && <div className={styles.errorBanner}>⚠ {error}</div>}

      <div className={styles.board}>
        {/* Canvas */}
        <div className={styles.canvasWrap}>
          <div className={styles.canvasInner}>
            <img ref={imageRef} src={src} alt="Original"
              onLoad={() => {
                const c = canvasRef.current
                if (c) { c.width = imageRef.current.offsetWidth; c.height = imageRef.current.offsetHeight; setProposals(p => [...p]) }
              }}
            />
            <canvas ref={canvasRef} />
          </div>
          <div className={styles.canvasLabel}>
            <span style={{ color: '#ef4444' }}>■ Face</span>
            {'  '}
            <span style={{ color: '#f59e0b' }}>■ Text PII</span>
            {'  '}
            <span style={{ color: '#3b82f6' }}>■ Other</span>
            {'  ·  '}
            <span style={{ color: 'var(--text3)' }}>Hover to highlight · Click item to toggle</span>
          </div>
        </div>

        {/* Sidebar */}
        <div className={styles.sidebar}>
          <div className={styles.sideHead}>
            <div className={styles.sideTitle}>Proposals</div>
            <div className={styles.filters}>
              {[['all', `All ${proposals.length}`], ['sensitive', `Sensitive ${sensitiveCount}`], ['safe', `Safe ${safeCount}`]].map(([f, l]) => (
                <button key={f} className={`${styles.filterBtn} ${filter === f ? styles.filterActive : ''}`} onClick={() => setFilter(f)}>{l}</button>
              ))}
            </div>
            <div className={styles.quickActions}>
              <button className={styles.qa} onClick={aiSuggestion}>AI suggestion</button>
              <button className={styles.qa} onClick={approveAll}>Approve all</button>
              <button className={styles.qa} onClick={dismissAll}>Dismiss all</button>
            </div>
          </div>

          <div className={styles.list}>
            {filtered.length === 0 && <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text3)', fontSize: '12px' }}>No items</div>}
            {filtered.map(p => {
              const color = TYPE_COLOR[p.type] || TYPE_COLOR.default
              return (
                <div key={p.id}
                  className={`${styles.item} ${hoveredId === p.id ? styles.itemHovered : ''}`}
                  style={{ borderLeftColor: p.approved ? color : 'var(--border)' }}
                  onMouseEnter={() => setHoveredId(p.id)}
                  onMouseLeave={() => setHoveredId(null)}
                >
                  <div className={styles.itemTop}>
                    <div className={styles.itemLabel}>{p.label || p.type}</div>
                    <span className={styles.sensitiveChip} style={{
                      color:       p.sensitive ? 'var(--red)'   : 'var(--green)',
                      borderColor: p.sensitive ? 'rgba(239,68,68,.3)' : 'rgba(34,197,94,.3)',
                      background:  p.sensitive ? 'rgba(239,68,68,.07)' : 'rgba(34,197,94,.07)',
                    }}>
                      {p.sensitive ? 'PII' : 'SAFE'}
                    </span>
                    <button className={styles.toggleBtn}
                      style={{
                        color:       p.approved ? color : 'var(--text3)',
                        borderColor: p.approved ? color+'66' : 'var(--border)',
                        background:  p.approved ? color+'11' : 'transparent',
                      }}
                      onClick={() => toggle(p.id)}
                    >
                      {p.approved ? 'Redact' : 'Skip'}
                    </button>
                  </div>
                  {p.value && <div className={styles.itemValue}>{p.value}</div>}
                  {p.reason && <div className={styles.itemReason}>{p.reason}</div>}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
