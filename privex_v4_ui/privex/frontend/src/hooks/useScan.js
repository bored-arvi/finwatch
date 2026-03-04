import { useState, useCallback } from 'react'
import { scanImage, scanAudio, scanText, scanVideo } from '../api/client'

const STAGES = ['upload', 'detect', 'classify', 'redact', 'done']

export function useScan() {
  const [stage,      setStage]      = useState(null)   // null | 'upload'|'detect'|'classify'|'redact'|'done'|'error'
  const [result,     setResult]     = useState(null)
  const [error,      setError]      = useState(null)
  const [progress,   setProgress]   = useState(0)
  const [logs,       setLogs]       = useState([])

  const addLog = useCallback((level, msg) => {
    setLogs(prev => [...prev, { level, msg, ts: new Date().toLocaleTimeString() }])
  }, [])

  const sleep = ms => new Promise(r => setTimeout(r, ms))

  const run = useCallback(async (mode, payload) => {
    setResult(null)
    setError(null)
    setLogs([])
    setProgress(0)

    try {
      // Step through pipeline stages
      setStage('upload')
      addLog('info', `Starting ${mode} scan...`)
      await sleep(300)

      setStage('detect')
      addLog('info', `Routing to detection pipeline...`)

      let resp
      if (mode === 'image') {
        resp = await scanImage(payload, p => setProgress(p))
      } else if (mode === 'audio') {
        resp = await scanAudio(payload, p => setProgress(p))
      } else if (mode === 'video') {
        addLog('info', 'Processing video — this may take 30-60 seconds...')
        resp = await scanVideo(payload, p => setProgress(p))
      } else {
        resp = await scanText(payload)
      }

      setStage('classify')
      addLog('info', `LLM classification complete`)
      await sleep(200)

      setStage('redact')
      addLog('info', `Applying redactions...`)
      await sleep(300)

      setStage('done')
      const data = resp.data
      addLog('info', `Scan complete — ${data.entity_count ?? 0} entities detected`)
      if (data.sensitive) {
        addLog('warn', `Sensitive data found — redacted output ready`)
      } else {
        addLog('info', `No sensitive data detected`)
      }
      setResult({ ...data, mode })

    } catch (e) {
      const msg = e.response?.data?.detail || e.message || 'Unknown error'
      setStage('error')
      setError(msg)
      addLog('error', `Scan failed: ${msg}`)
    }
  }, [addLog])

  const reset = useCallback(() => {
    setStage(null); setResult(null); setError(null); setProgress(0); setLogs([])
  }, [])

  return { stage, result, error, progress, logs, run, reset }
}
