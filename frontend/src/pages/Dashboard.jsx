import {Link} from 'react-router-dom'
import {api} from '../api'
import {Badge,Empty,PageHead,RX_LABEL,RX_TONE,fmtDate,money,useLoad} from '../ui'
const TONE = {CRITICAL: 'rose', WARNING: 'amber', INFO: 'sky'}
export default function Dashboard({user}) {
  const d = useLoad(() => api.get('/reports/dashboard')), al = useLoad(() => api.get('/alerts?unread_only=true')), rx = useLoad(() => api.get('/prescriptions'))
  const h = new Date().getHours(), hi = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening', s = d.data || {}
  const queue = (rx.data || []).filter(r => ['UPLOADED', 'PROCESSED', 'VERIFIED'].includes(r.status)).slice(0, 8), alerts = (al.data || []).slice(0, 7)
  return <>
    <PageHead title={`${hi}, ${user.name.split(' ')[0]}`} sub="Here is what needs a pharmacist today."><Link className="btn primary" to="/prescriptions?upload=1">Upload prescription</Link></PageHead>
    {d.error && <div className="note err" style={{marginBottom: 14}}>{d.error}</div>}
    <div className="strip">{[['Awaiting review', s.pending_review], ['Ready to dispense', s.ready_to_dispense], ['Medicines out of stock', s.out_of_stock], ['Batches expiring within 90 days', s.expiring_batches], ["Today's sales", s.todays_sales == null ? null : money(s.todays_sales)]].map(([k, v]) => <div key={k}><b>{v ?? '–'}</b><span>{k}</span></div>)}</div>
    <div className="cols">
      <section className="panel"><div className="ph"><h2>Prescription queue</h2><Link to="/prescriptions" className="small">View all</Link></div>
        {rx.loading ? <div className="loading">Loading…</div> : queue.length === 0 ? <Empty title="The queue is clear" hint="Upload a prescription to start a new review."/> :
          queue.map(r => <div className="row" key={r.id}><div><b>{r.prescription_number}</b><div className="small muted">{r.patient_reference || 'No patient reference'}, {fmtDate(r.created_at)}</div></div>
            <div style={{display: 'flex', gap: 10, alignItems: 'center'}}><Badge tone={RX_TONE[r.status]}>{RX_LABEL[r.status]}</Badge><Link className="btn sm" to={`/prescriptions/${r.id}`}>Open</Link></div></div>)}</section>
      <section className="panel"><div className="ph"><h2>Needs attention</h2><Link to="/alerts" className="small">All alerts</Link></div>
        {al.loading ? <div className="loading">Loading…</div> : alerts.length === 0 ? <Empty title="Nothing needs attention" hint="Stock levels and expiry dates look healthy."/> :
          alerts.map(a => <div className="row" key={a.id}><span>{a.message}</span><Badge tone={TONE[a.severity]}>{a.alert_type.replace(/_/g, ' ').toLowerCase()}</Badge></div>)}</section>
    </div></>
}
