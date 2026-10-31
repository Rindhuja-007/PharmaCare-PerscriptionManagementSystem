import {useState} from 'react'
import {api} from '../api'
import {Empty,PageHead,fmtDate,money,useLoad} from '../ui'
import ReceiptModal from './Receipt'
export default function Transactions() {
  const l = useLoad(() => api.get('/transactions?limit=100')), [sel, setSel] = useState(null)
  return <><PageHead title="Transactions" sub="Every dispense, with the pharmacist who did it."/>
    <div className="panel">{l.loading ? <div className="loading">Loading…</div> : l.error ? <div className="note err">{l.error}</div> : (l.data || []).length === 0 ? <Empty title="Nothing dispensed yet" hint="Receipts appear here after a prescription is dispensed."/> :
      <div className="scroll"><table><thead><tr><th>Receipt</th><th>Prescription</th><th>Patient</th><th>Pharmacist</th><th>Date</th><th className="right">Total</th></tr></thead><tbody>
        {l.data.map(t => <tr key={t.id} onClick={() => setSel(t)} style={{cursor: 'pointer'}}><td><b>#{t.id}</b></td><td>{t.prescription_number || '–'}</td><td>{t.patient_reference || '–'}</td><td>{t.pharmacist}</td><td className="nowrap">{fmtDate(t.created_at, true)}</td><td className="right">{money(t.total_amount)}</td></tr>)}</tbody></table></div>}</div>
    {sel && <ReceiptModal tx={sel} onClose={() => setSel(null)}/>}</>
}
