import { useEffect, useRef } from 'react'
import styles from './LogTerminal.module.css'

const LEVEL = { info: styles.info, warn: styles.warn, error: styles.err }

export default function LogTerminal({ logs }) {
  const ref = useRef()
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [logs])

  return (
    <div className={styles.term} ref={ref}>
      <div className={styles.line}>
        <span className={styles.ts}>[INIT]</span>
        <span className={styles.info}> INFO</span>
        <span className={styles.msg}>  PRIVEX system ready — local-first mode</span>
      </div>
      {logs.map((l, i) => (
        <div key={i} className={styles.line}>
          <span className={styles.ts}>[{l.ts}]</span>
          <span className={LEVEL[l.level] || styles.info}> {l.level.toUpperCase().padEnd(5)}</span>
          <span className={styles.msg}>  {l.msg}</span>
        </div>
      ))}
      <span className={styles.cursor}>▋</span>
    </div>
  )
}
