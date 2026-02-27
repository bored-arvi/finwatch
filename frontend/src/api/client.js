import axios from 'axios'

const api = axios.create({ baseURL: '/' })

export const scanImage = (file, onProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/scan/image', fd, {
    onUploadProgress: e => onProgress?.(Math.round(e.loaded / e.total * 100))
  })
}

export const scanAudio = (file, onProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/scan/audio', fd, {
    onUploadProgress: e => onProgress?.(Math.round(e.loaded / e.total * 100))
  })
}

export const scanText = (text) =>
  api.post('/scan/text', { text })

export const checkHealth = () =>
  api.get('/health')

export const downloadUrl = (filename) =>
  `/download/${filename}`
