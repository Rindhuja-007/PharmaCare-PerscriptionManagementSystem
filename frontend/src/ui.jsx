import {createContext,useCallback,useContext,useEffect,useState} from 'react'
import {X} from 'lucide-react'
import {errText} from './api'
const Ctx = createContext(() => {})
export const useToast = () => useContext(Ctx)
export function ToastProvider({children}) {
  const [l, setL] = useState([])
  const push = useCallback((msg, kind = 'ok') => { const id = Math.random(); setL(x => [...x, {id, msg, kind}]); setTimeout(() => setL(x => x.filter(t => t.id !== id)), 4800) }, [])
  return <Ctx.Provider value={push}>{children}<div className="toasts" role="status" aria-live="polite">{l.map(t => <div key={t.id} className={'toast ' + t.kind}>{t.msg}</div>)}</div></Ctx.Provider>
}
export function Modal({title, onClose, children, wide}) {
  useEffect(() => { const k = e => e.key === 'Escape' && onClose(); window.addEventListener('keydown', k); return () => window.removeEventListener('keydown', k) }, [onClose])
  return <div className="scrim" onMouseDown={onClose}><div className={'modal' + (wide ? ' wide' : '')} role="dialog" aria-modal="true" aria-label={title} onMouseDown={e => e.stopPropagation()}>
    <header className="no-print"><h2>{title}</h2><button className="icon" onClick={onClose} aria-label="Close"><X size={18}/></button></header>{children}</div></div>
}
export const Confirm = ({title, children, label = 'Confirm', danger, busy, onYes, onNo}) =>
  <Modal title={title} onClose={onNo}>{children}<div className="foot"><button className="btn" onClick={onNo}>Cancel</button><button className={'btn ' + (danger ? 'danger' : 'primary')} disabled={busy} onClick={onYes}>{busy ? 'Working…' : label}</button></div></Modal>
export const Badge = ({tone = 'neutral', children}) => <span className={'badge ' + tone}>{children}</span>
export const Empty = ({title, hint, children}) => <div className="empty"><h3>{title}</h3>{hint && <p>{hint}</p>}{children}</div>
export const PageHead = ({title, sub, children}) => <div className="head"><div><h1>{title}</h1>{sub && <p>{sub}</p>}</div><div className="head-actions">{children}</div></div>
export const Field = ({label, hint, children, cls = ''}) => <label className={'field ' + cls}><span>{label}</span>{children}{hint && <small>{hint}</small>}</label>
export function useLoad(fn, deps = []) {
  const [s, setS] = useState({data: null, loading: true, error: ''})
  const run = useCallback(() => fn().then(r => setS({data: r.data, loading: false, error: ''})).catch(e => setS(x => ({data: x.data, loading: false, error: errText(e)}))), deps) // eslint-disable-line
  useEffect(() => { run() }, [run])
  return {...s, reload: run}
}
export const money = n => new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'}).format(Number(n) || 0)
export const fmtDate = (d, time) => { if (!d) return '–'; const x = new Date(d); return isNaN(x) ? String(d) : x.toLocaleString('en-IN', time ? {dateStyle: 'medium', timeStyle: 'short'} : {dateStyle: 'medium'}) }
export const RX_TONE = {UPLOADED: 'neutral', PROCESSED: 'sky', VERIFIED: 'amber', REJECTED: 'rose', DISPENSED: 'green'}
export const RX_LABEL = {UPLOADED: 'Uploaded', PROCESSED: 'Needs review', VERIFIED: 'Ready to dispense', REJECTED: 'Rejected', DISPENSED: 'Dispensed'}
export const download = (blob, name) => { const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000) }
