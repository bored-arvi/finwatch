import styles from './Pipeline.module.css'

const STEPS = [
  { id: 'upload',   icon: '⬆', label: 'Upload'   },
  { id: 'detect',   icon: '⬡', label: 'Detect'   },
  { id: 'classify', icon: '◈', label: 'Classify'  },
  { id: 'review',   icon: '👁', label: 'Review'   },
  { id: 'redact',   icon: '▣', label: 'Redact'    },
  { id: 'done',     icon: '✓', label: 'Done'      },
]

const ORDER = ['upload','detect','classify','review','redact','done']

function stepState(id, currentStage) {
  if (!currentStage || currentStage === 'error') return 'idle'
  const ci = ORDER.indexOf(currentStage)
  const si = ORDER.indexOf(id)
  if (si < ci)  return 'done'
  if (si === ci) return 'active'
  return 'idle'
}

export default function Pipeline({ stage }) {
  return (
    <div className={styles.pipeline}>
      {STEPS.map((step, i) => {
        const state = stepState(step.id, stage)
        return (
          <div key={step.id} className={styles.group}>
            <div className={`${styles.step} ${styles[state]}`}>
              <span className={styles.icon}>{step.icon}</span>
              <span className={styles.label}>{step.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`${styles.arrow} ${state === 'done' ? styles.arrowDone : ''}`} />
            )}
          </div>
        )
      })}
    </div>
  )
}
