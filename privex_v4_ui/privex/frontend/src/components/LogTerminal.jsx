import { useEffect, useRef } from 'react'
import styles from './LogTerminal.module.css'

const COLORS = { info: 'var(--text2)', warn: 'var(--amber)', error: 'var(--red)', success: 'var(--green)' }

export default function LogTerminal({ logs }) {
  const ref = useRef()
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [logs])
  if (!logs?.length) return null

  return (
    <div className={styles.wrap}>
      <div className={styles.termHeader}>
        <div className={styles.dots}>
          <span className={styles.dot} style={{background:'#ff5f57'}}/>
          <span className={styles.dot} style={{background:'#ffbd2e'}}/>
          <span className={styles.dot} style={{background:'#28c840'}}/>
        </div>
        <span className={styles.termTitle}>console</span>
      </div>
      <div className={styles.body} ref={ref}>
        {logs.map((log, i) => (
          <div key={i} className={styles.line} style={{ animationDelay: `${i*20}ms` }}>
            <span className={styles.ts}>{log.ts}</span>
            <span className={styles.lvl} style={{ color: COLORS[log.level] || COLORS.info }}>
              {log.level === 'error' ? 'ERR' : log.level === 'warn' ? 'WRN' : 'INF'}
            </span>
            <span className={styles.msg} style={{ color: COLORS[log.level] || COLORS.info }}>
              {log.msg}
            </span>
          </div>
        ))}
        <div className={styles.cursor}/>
      </div>
    </div>
  )
}
