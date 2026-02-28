import { useState, useEffect } from 'react'
import { checkHealth } from '../api/client'
import styles from './Header.module.css'

export default function Header() {
  const [online, setOnline] = useState(null)

  useEffect(() => {
    checkHealth()
      .then(() => setOnline(true))
      .catch(() => setOnline(false))
  }, [])

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.logo}>
          <span className={styles.dot} />
          PRIVEX
        </div>
        <div className={styles.right}>
          <span className={styles.tagline}>AI Privacy Firewall</span>
          <span className={`${styles.status} ${online === true ? styles.ok : online === false ? styles.err : styles.checking}`}>
            {online === null ? '◌ CONNECTING' : online ? '● API ONLINE' : '✕ API OFFLINE'}
          </span>
        </div>
      </div>
    </header>
  )
}
