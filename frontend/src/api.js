import axios from 'axios'
export const api = axios.create({ baseURL: import.meta.env.VITE_API || '/api' })
api.interceptors.request.use(c => { const t = localStorage.getItem('pc_token'); if (t) c.headers.Authorization = 'Bearer ' + t; return c })
api.interceptors.response.use(r => r, e => {
  if (e.response?.status === 401 && !String(e.config?.url).includes('/auth/login') && localStorage.getItem('pc_token')) { localStorage.removeItem('pc_token'); window.dispatchEvent(new Event('pc-logout')) }
  return Promise.reject(e)
})
export const errText = e => {
  const d = e?.response?.data?.detail
  if (Array.isArray(d)) return d.map(x => `${(x.loc || []).slice(-1)[0]}: ${x.msg}`).join('; ')
  if (d) return String(d)
  if (e?.response?.status >= 500) return 'The server had a problem. Please try again.'
  return e?.message === 'Network Error' ? 'Cannot reach the server. Check your connection.' : (e?.message || 'Something went wrong')
}
export const shrinkImage = f => new Promise(res => {
  const im = new Image(), url = URL.createObjectURL(f)
  im.onload = () => { const s = Math.min(1, 1600 / im.width), c = document.createElement('canvas'); c.width = im.width * s; c.height = im.height * s
    c.getContext('2d').drawImage(im, 0, 0, c.width, c.height); URL.revokeObjectURL(url); c.toBlob(b => res(b || f), 'image/jpeg', .85) }
  im.onerror = () => res(f); im.src = url
})
