import {useState} from 'react'
import {ChevronDown,ChevronRight,Pencil,Plus} from 'lucide-react'
import {api,errText} from '../api'
import {Badge,Empty,Field,Modal,PageHead,fmtDate,money,useLoad,useToast} from '../ui'
const today = () => new Date().toISOString().slice(0, 10)
function AddStock({meds, onClose, onSaved}) {
  const toast = useToast(), [f, setF] = useState({medicine_id: '', batch_number: '', quantity: '', expiry_date: '', purchase_price: '', selling_price: ''}), s = k => e => setF({...f, [k]: e.target.value})
  const go = async e => { e.preventDefault(); try { await api.post('/inventory/stock', {...f, medicine_id: +f.medicine_id, quantity: +f.quantity, purchase_price: +f.purchase_price, selling_price: +f.selling_price}); toast('Batch added'); onSaved() } catch (x) { toast(errText(x), 'err') } }
  return <Modal title="Add stock batch" onClose={onClose}><form className="form" onSubmit={go}><Field label="Medicine" cls="full"><select required value={f.medicine_id} onChange={s('medicine_id')}><option value="">Select…</option>{meds.map(m => <option key={m.id} value={m.id}>{m.medicine_name}</option>)}</select></Field>
    <Field label="Batch number"><input required value={f.batch_number} onChange={s('batch_number')}/></Field><Field label="Quantity (units)"><input required type="number" min="1" value={f.quantity} onChange={s('quantity')}/></Field>
    <Field label="Expiry date" hint="Expired batches are never dispensed."><input required type="date" value={f.expiry_date} onChange={s('expiry_date')}/></Field><span/>
    <Field label="Purchase price (₹)"><input required type="number" min="0" step="0.01" value={f.purchase_price} onChange={s('purchase_price')}/></Field><Field label="Selling price (₹)"><input required type="number" min="0" step="0.01" value={f.selling_price} onChange={s('selling_price')}/></Field>
    <div className="foot full"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">Add batch</button></div></form></Modal>
}
function EditBatch({b, onClose, onSaved}) {
  const toast = useToast(), [f, setF] = useState({quantity: b.quantity, expiry_date: b.expiry_date, purchase_price: b.purchase_price, selling_price: b.selling_price}), s = k => e => setF({...f, [k]: e.target.value})
  const go = async e => { e.preventDefault(); try { await api.put('/inventory/batch/' + b.id, {quantity: +f.quantity, expiry_date: f.expiry_date, purchase_price: +f.purchase_price, selling_price: +f.selling_price}); toast('Batch updated'); onSaved() } catch (x) { toast(errText(x), 'err') } }
  return <Modal title={`Edit batch ${b.batch_number}`} onClose={onClose}><form className="form" onSubmit={go}><Field label="Quantity"><input type="number" min="0" value={f.quantity} onChange={s('quantity')}/></Field><Field label="Expiry date"><input type="date" value={f.expiry_date} onChange={s('expiry_date')}/></Field>
    <Field label="Purchase price (₹)"><input type="number" min="0" step="0.01" value={f.purchase_price} onChange={s('purchase_price')}/></Field><Field label="Selling price (₹)"><input type="number" min="0" step="0.01" value={f.selling_price} onChange={s('selling_price')}/></Field>
    <div className="foot full"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">Save</button></div></form></Modal>
}
export default function Inventory() {
  const inv = useLoad(() => api.get('/inventory')), meds = useLoad(() => api.get('/medicines')), [open, setOpen] = useState({}), [add, setAdd] = useState(false), [edit, setEdit] = useState(null)
  const reload = () => { inv.reload(); meds.reload() }, t = today(), soon = new Date(Date.now() + 90 * 864e5).toISOString().slice(0, 10)
  const by = {}; (inv.data || []).forEach(b => (by[b.medicine_id] ||= []).push(b))
  const rows = (meds.data || []).map(m => { const bs = by[m.id] || [], live = bs.filter(b => b.quantity > 0 && b.expiry_date >= t); return {m, bs, live, next: live.map(b => b.expiry_date).sort()[0]} })
  return <>
    <PageHead title="Inventory" sub="Stock by medicine, with every batch and its expiry."><button className="btn primary" onClick={() => setAdd(true)}><Plus size={16}/>Add stock</button></PageHead>
    <div className="panel">{inv.loading || meds.loading ? <div className="loading">Loading…</div> : rows.length === 0 ? <Empty title="No medicines yet" hint="Add medicines first, then record stock batches."/> :
      <div className="scroll"><table><thead><tr><th/><th>Medicine</th><th className="right">Usable</th><th>Next expiry</th><th>Status</th></tr></thead><tbody>
        {rows.map(({m, bs, next}) => [<tr key={m.id}><td style={{width: 30}}><button className="icon" aria-label="Toggle batches" onClick={() => setOpen({...open, [m.id]: !open[m.id]})}>{open[m.id] ? <ChevronDown size={16}/> : <ChevronRight size={16}/>}</button></td>
          <td><b>{m.medicine_name}</b><div className="small muted">{bs.length} batch{bs.length === 1 ? '' : 'es'}</div></td><td className="right">{m.usable_stock}</td><td>{next ? fmtDate(next) : '–'}</td>
          <td>{m.usable_stock === 0 ? <Badge tone="rose">Out of stock</Badge> : m.usable_stock <= m.reorder_level ? <Badge tone="amber">Low stock</Badge> : next && next <= soon ? <Badge tone="amber">Expiring soon</Badge> : <Badge tone="green">Healthy</Badge>}</td></tr>,
          open[m.id] && <tr key={m.id + 'b'}><td/><td colSpan="4" style={{background: '#f8fbf9'}}>{bs.length === 0 ? <span className="muted">No batches recorded.</span> : <table><thead><tr><th>Batch</th><th className="right">Qty</th><th>Expiry</th><th className="right">Buy</th><th className="right">Sell</th><th/></tr></thead><tbody>
            {bs.map(b => <tr key={b.id}><td>{b.batch_number}</td><td className="right">{b.quantity}</td><td>{fmtDate(b.expiry_date)} {b.expiry_date < t ? <Badge tone="rose">Expired</Badge> : b.expiry_date <= soon && <Badge tone="amber">Soon</Badge>}</td><td className="right">{money(b.purchase_price)}</td><td className="right">{money(b.selling_price)}</td><td className="right"><button className="icon" aria-label="Edit batch" onClick={() => setEdit(b)}><Pencil size={15}/></button></td></tr>)}</tbody></table>}</td></tr>])}</tbody></table></div>}</div>
    {add && <AddStock meds={meds.data || []} onClose={() => setAdd(false)} onSaved={() => { setAdd(false); reload() }}/>}{edit && <EditBatch b={edit} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); reload() }}/>}</>
}
