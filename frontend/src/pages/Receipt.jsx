import {Printer} from 'lucide-react'
import {Modal,fmtDate,money} from '../ui'
export default function ReceiptModal({tx, onClose}) {
  return <Modal title={`Receipt #${tx.id}`} onClose={onClose} wide><div className="receipt">
    <h2>PharmaCare</h2><div className="meta">{fmtDate(tx.created_at, true)}<br/>Dispensed by {tx.pharmacist}{tx.prescription_number && ` against ${tx.prescription_number}`}{tx.patient_reference && ` for ${tx.patient_reference}`}</div>
    <div className="scroll"><table><thead><tr><th>Medicine</th><th>Batch</th><th className="right">Qty</th><th className="right">Price</th><th className="right">Amount</th></tr></thead>
      <tbody>{tx.items.map(i => <tr key={i.id}><td>{i.medicine}</td><td>{i.batch_number}</td><td className="right">{i.quantity}</td><td className="right">{money(i.unit_price)}</td><td className="right">{money(i.total_price)}</td></tr>)}</tbody></table></div>
    <div style={{maxWidth: 260, marginLeft: 'auto', marginTop: 12}}><div className="sumline"><span>Subtotal</span><span>{money(tx.subtotal)}</span></div><div className="sumline"><span>Discount</span><span>−{money(tx.discount)}</span></div>
      <div className="sumline"><span>Tax</span><span>{money(tx.tax)}</span></div><div className="sumline tot"><span>Total</span><span>{money(tx.total_amount)}</span></div></div></div>
    <div className="foot no-print"><button className="btn" onClick={() => window.print()}><Printer size={16}/>Print</button><button className="btn primary" onClick={onClose}>Done</button></div></Modal>
}
