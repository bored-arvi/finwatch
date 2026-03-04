import axios from 'axios'

const api = axios.create({ baseURL: '/' })

export const scanImage = (file, onProgress) => {
  const fd = new FormData(); fd.append('file', file)
  return api.post('/scan/image', fd, {
    onUploadProgress: e => onProgress?.(Math.round(e.loaded / e.total * 100))
  })
}

export const scanAudio = (file, onProgress) => {
  const fd = new FormData(); fd.append('file', file)
  return api.post('/scan/audio', fd, {
    onUploadProgress: e => onProgress?.(Math.round(e.loaded / e.total * 100))
  })
}

export const scanVideo = (file, onProgress) => {
  const fd = new FormData(); fd.append('file', file)
  return api.post('/scan/video', fd, {
    onUploadProgress: e => onProgress?.(Math.round(e.loaded / e.total * 100))
  })
}

export const scanText = (text) =>
  api.post('/scan/text', { text })

export const proposeRedactions = (file, onProgress) => {
  const fd = new FormData(); fd.append('file', file)
  return api.post('/review/propose', fd, {
    onUploadProgress: e => onProgress?.(Math.round(e.loaded / e.total * 100))
  })
}

export const applyRedactions = (sessionToken, approvedBoxes) =>
  api.post('/review/apply', { session_token: sessionToken, approved_boxes: approvedBoxes })

export const checkHealth    = ()      => api.get('/health')
export const getLLMConfig   = ()      => api.get('/config/llm')
export const setLLMConfig   = (key)   => api.post('/config/llm', { gemini_api_key: key })
export const downloadUrl    = (file)  => `/download/${file}`
