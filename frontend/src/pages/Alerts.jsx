import {useEffect,useState} from 'react'
import {RefreshCw} from 'lucide-react'
import {api,errText} from '../api'
import {Badge,Empty,PageHead,fmtDate,useLoad,useToast} from '../ui'
const TONE = {CRITICAL: 'rose', WARNING: 'amber', INFO: 'sky'}
export default function Alerts({onChange}) {
  const l = useLoad(() => api.get('/alerts')), toast = useToast(), [all, setAll] = useState(false), [busy, setBusy] = useState(false)
  const rows = (l.data || []).filter(a => all || !a.is_read), after = () => { l.reload(); onChange && onChange() }
  const scan = async () => { setBusy(true); try { await api.post('/alerts/refresh'); after(); toast('Stock and expiry dates checked') } catch (e) { toast(errText(e), 'err') } finally { setBusy(false) } }
  useEffect(() => { api.post('/alerts/refresh').then(after).catch(() => {}) }, []) // eslint-disable-line
  const read = async a => { try { await api.put(`/alerts/${a.id}/read`); after() } catch (e) { toast(errText(e), 'err') } }
  const readAll = async () => { try { await Promise.all(rows.filter(a => !a.is_read).map(a => api.put(`/alerts/${a.id}/read`))); after() } catch (e) { toast(errText(e), 'err') } }
  return <><PageHead title="Alerts" sub="Low stock, out of stock and expiry warnings."><button className="btn" onClick={readAll}>Mark all read</button><button className="btn primary" disabled={busy} onClick={scan}><RefreshCw size={16}/>Scan now</button></PageHead>
    <div className="chips" style={{marginBottom: 14}}><button className={'chip' + (!all ? ' on' : '')} onClick={() => setAll(false)}>Unread</button><button className={'chip' + (all ? ' on' : '')} onClick={() => setAll(true)}>All</button></div>
    <div className="panel">{l.loading ? <div className="loading">Loading…</div> : rows.length === 0 ? <Empty title="All clear" hint="No alerts in this view."/> :
      rows.map(a => <div className="row" key={a.id} style={{opacity: a.is_read ? .55 : 1}}><div><Badge tone={TONE[a.severity]}>{a.alert_type.replace(/_/g, ' ').toLowerCase()}</Badge> <span style={{marginLeft: 8}}>{a.message}</span><div className="small muted">{fmtDate(a.created_at, true)}</div></div>{!a.is_read && <button className="btn sm" onClick={() => read(a)}>Mark read</button>}</div>)}</div></>
}
