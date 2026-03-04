import styles from './Header.module.css'

export default function Header() {
  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.brand}>
          <div className={styles.logo}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 2L18 6V14L10 18L2 14V6L10 2Z" stroke="#22c55e" strokeWidth="1.5" fill="none"/>
              <path d="M10 6L14 8V12L10 14L6 12V8L10 6Z" fill="#22c55e" opacity=".3"/>
              <circle cx="10" cy="10" r="2" fill="#22c55e"/>
            </svg>
            <span className={styles.name}>PRIVEX</span>
          </div>
          <span className={styles.divider}/>
          <span className={styles.tagline}>Privacy Redaction Engine</span>
        </div>
        <div className={styles.right}>
          <span className={styles.version}>v2.0</span>
          <div className={styles.dot}/>
          <span className={styles.status}>OPERATIONAL</span>
        </div>
      </div>
    </header>
  )
}
