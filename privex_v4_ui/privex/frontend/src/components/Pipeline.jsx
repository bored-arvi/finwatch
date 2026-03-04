import styles from './Pipeline.module.css'

const STEPS = [
  { id: 'upload',   label: 'Upload',   icon: '↑' },
  { id: 'detect',   label: 'Detect',   icon: '◎' },
  { id: 'classify', label: 'Classify', icon: '⬡' },
  { id: 'review',   label: 'Review',   icon: '👁' },
  { id: 'redact',   label: 'Redact',   icon: '■' },
  { id: 'done',     label: 'Done',     icon: '✓' },
]

const ORDER = STEPS.map(s => s.id)

export default function Pipeline({ stage }) {
  if (!stage) return null
  const idx = ORDER.indexOf(stage)

  return (
    <div className={styles.wrap}>
      {STEPS.map((s, i) => {
        const done    = i < idx
        const active  = i === idx
        const pending = i > idx
        return (
          <div key={s.id} className={styles.step}>
            <div className={`${styles.node} ${done ? styles.done : active ? styles.active : styles.pending}`}>
              {done ? (
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                  <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              ) : (
                <span className={styles.nodeIcon}>{active ? s.icon : ''}</span>
              )}
            </div>
            <span className={`${styles.label} ${active ? styles.labelActive : done ? styles.labelDone : ''}`}>
              {s.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className={`${styles.line} ${i < idx ? styles.lineDone : ''}`}/>
            )}
          </div>
        )
      })}
    </div>
  )
}
