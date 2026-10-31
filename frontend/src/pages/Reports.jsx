import {useState} from 'react'
import {api} from '../api'
import {Badge,PageHead,RX_LABEL,money,useLoad} from '../ui'
export default function Reports() {
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10))
  const s = useLoad(() => api.get('/reports/sales?report_date=' + day), [day]), r = useLoad(() => api.get('/reports/prescriptions')), i = useLoad(() => api.get('/reports/inventory'))
  const sd = s.data || {}, rx = r.data || {}, total = Object.values(rx).reduce((a, b) => a + b, 0) || 1
  return <><PageHead title="Reports" sub="Sales, prescription throughput and inventory health."/>
    <div className="panel"><div className="ph"><h2>Sales</h2><input type="date" value={day} onChange={e => e.target.value && setDay(e.target.value)} style={{width: 'auto'}} aria-label="Report date"/></div>
      <div className="strip" style={{marginBottom: 0}}>{[['Receipts', sd.count], ['Subtotal', money(sd.subtotal)], ['Discounts', money(sd.discount)], ['Tax', money(sd.tax)], ['Total', money(sd.total)]].map(([k, v]) => <div key={k}><b>{v ?? '–'}</b><span>{k}</span></div>)}</div></div>
    <div className="cols"><div className="panel"><h2>Prescriptions by status</h2>{Object.keys(rx).length === 0 ? <p className="muted">No prescriptions yet.</p> : Object.entries(rx).map(([k, v]) => <div key={k} style={{marginBottom: 10}}><div className="sumline"><span>{RX_LABEL[k] || k}</span><b>{v}</b></div><div className="bar"><i style={{width: v / total * 100 + '%'}}/></div></div>)}</div>
      <div className="panel"><h2>Inventory health</h2><div className="scroll"><table><thead><tr><th>Medicine</th><th className="right">Usable</th><th className="right">Reorder at</th><th/></tr></thead><tbody>{(i.data || []).map(m => <tr key={m.medicine_id}><td>{m.name}</td><td className="right">{m.usable}</td><td className="right">{m.reorder_level}</td><td>{m.usable === 0 ? <Badge tone="rose">Out</Badge> : m.low ? <Badge tone="amber">Low</Badge> : null}</td></tr>)}</tbody></table></div></div></div></>
}
