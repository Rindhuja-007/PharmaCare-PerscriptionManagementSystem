import {useRef,useState} from 'react'
import {Download,Pencil,Plus,Trash2,Upload} from 'lucide-react'
import {api,errText} from '../api'
import {Badge,Confirm,Empty,Field,Modal,PageHead,download,money,useLoad,useToast} from '../ui'
const FORMS = ['Tablet', 'Capsule', 'Syrup', 'Injection', 'Drops', 'Ointment', 'Other']
const BLANK = {medicine_name: '', generic_name: '', brand_name: '', composition: '', strength: '', dosage_form: 'Tablet', category: '', rack_location: '', shelf_number: '', reorder_level: 15, mrp: '', prescription_required: true}
function MedForm({med, onClose, onSaved}) {
  const toast = useToast(), [f, setF] = useState(med ? {...BLANK, ...Object.fromEntries(Object.entries(med).filter(([, v]) => v != null))} : BLANK), s = k => e => setF({...f, [k]: e.target.value})
  const go = async e => { e.preventDefault(); const b = {...f, reorder_level: +f.reorder_level || 0, mrp: f.mrp === '' ? null : +f.mrp}; ['generic_name', 'brand_name', 'composition', 'strength', 'category', 'rack_location', 'shelf_number'].forEach(k => { if (b[k] === '') b[k] = null })
    try { med ? await api.put('/medicines/' + med.id, b) : await api.post('/medicines', b); toast(med ? 'Medicine updated' : 'Medicine added'); onSaved() } catch (x) { toast(errText(x), 'err') } }
  return <Modal title={med ? 'Edit medicine' : 'Add medicine'} onClose={onClose} wide><form className="form" onSubmit={go}>
    <Field label="Medicine name" cls="full"><input required value={f.medicine_name} onChange={s('medicine_name')}/></Field>
    <Field label="Generic name (active ingredient)"><input value={f.generic_name} onChange={s('generic_name')}/></Field><Field label="Brand"><input value={f.brand_name} onChange={s('brand_name')}/></Field>
    <Field label="Composition" cls="full"><input value={f.composition} onChange={s('composition')} placeholder="Paracetamol (500mg)"/></Field>
    <Field label="Strength"><input value={f.strength} onChange={s('strength')} placeholder="500 mg"/></Field><Field label="Form"><select value={f.dosage_form} onChange={s('dosage_form')}>{FORMS.map(x => <option key={x}>{x}</option>)}</select></Field>
    <Field label="Category"><input value={f.category} onChange={s('category')}/></Field><Field label="MRP (₹)"><input type="number" min="0" step="0.01" value={f.mrp} onChange={s('mrp')}/></Field>
    <Field label="Rack"><input value={f.rack_location} onChange={s('rack_location')} placeholder="Rack A-02"/></Field><Field label="Shelf"><input value={f.shelf_number} onChange={s('shelf_number')}/></Field>
    <Field label="Reorder level" hint="Warn when usable stock falls to this."><input type="number" min="0" value={f.reorder_level} onChange={s('reorder_level')}/></Field>
    <label className="small" style={{alignSelf: 'end'}}><input type="checkbox" checked={f.prescription_required} onChange={e => setF({...f, prescription_required: e.target.checked})}/> Prescription required</label>
    <div className="foot full"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">{med ? 'Save changes' : 'Add medicine'}</button></div></form></Modal>
}
export default function Medicines({user}) {
  const l = useLoad(() => api.get('/medicines')), toast = useToast(), file = useRef(), [q, setQ] = useState(''), [edit, setEdit] = useState(null), [del, setDel] = useState(null), admin = user.role === 'ADMIN'
  const rows = (l.data || []).filter(m => `${m.medicine_name} ${m.generic_name || ''} ${m.brand_name || ''}`.toLowerCase().includes(q.toLowerCase()))
  const imp = async e => { const f = e.target.files[0]; e.target.value = ''; if (!f) return; const fd = new FormData(); fd.append('file', f)
    try { const {data} = await api.post('/medicines/import-csv', fd); toast(`Imported: ${data.created} new, ${data.updated} updated, ${data.batches} batches`); l.reload() } catch (x) { toast(errText(x), 'err') } }
  const sample = async () => { try { download((await api.get('/medicines/sample-csv', {responseType: 'blob'})).data, 'medicines-sample.csv') } catch (x) { toast(errText(x), 'err') } }
  const rm = async () => { try { await api.delete('/medicines/' + del.id); toast('Medicine deleted'); setDel(null); l.reload() } catch (x) { toast(errText(x), 'err'); setDel(null) } }
  return <>
    <PageHead title="Medicines" sub="The catalogue, with where each one lives on the shelf."><button className="btn" onClick={sample}><Download size={16}/>Sample CSV</button><button className="btn" onClick={() => file.current.click()}><Upload size={16}/>Import CSV</button><button className="btn primary" onClick={() => setEdit({})}><Plus size={16}/>Add medicine</button></PageHead>
    <input ref={file} type="file" accept=".csv" hidden onChange={imp}/>
    <div className="panel"><input placeholder="Search by name, generic or brand" value={q} onChange={e => setQ(e.target.value)} style={{maxWidth: 360, marginBottom: 12}} aria-label="Search medicines"/>
      {l.loading ? <div className="loading">Loading…</div> : l.error ? <div className="note err">{l.error}</div> : rows.length === 0 ? <Empty title="No medicines found" hint="Add one, or import a CSV file."/> :
        <div className="scroll"><table><thead><tr><th>Medicine</th><th>Form</th><th>Location</th><th className="right">MRP</th><th className="right">Usable stock</th><th/></tr></thead><tbody>
          {rows.map(m => <tr key={m.id}><td><b>{m.medicine_name}</b><div className="small muted">{m.generic_name}{m.prescription_required ? '' : ', over the counter'}</div></td><td>{m.dosage_form}{m.strength ? ' ' + m.strength : ''}</td><td>{[m.rack_location, m.shelf_number].filter(Boolean).join(', ') || '–'}</td><td className="right">{m.mrp != null ? money(m.mrp) : '–'}</td>
            <td className="right">{m.usable_stock} <Badge tone={m.usable_stock === 0 ? 'rose' : m.usable_stock <= m.reorder_level ? 'amber' : 'green'}>{m.usable_stock === 0 ? 'Out' : m.usable_stock <= m.reorder_level ? 'Low' : 'OK'}</Badge></td>
            <td className="right nowrap">{admin && <><button className="icon" aria-label={'Edit ' + m.medicine_name} onClick={() => setEdit(m)}><Pencil size={16}/></button><button className="icon" aria-label={'Delete ' + m.medicine_name} onClick={() => setDel(m)}><Trash2 size={16}/></button></>}</td></tr>)}</tbody></table></div>}</div>
    {edit && <MedForm med={edit.id ? edit : null} onClose={() => setEdit(null)} onSaved={() => { setEdit(null); l.reload() }}/>}
    {del && <Confirm title="Delete medicine?" danger label="Delete" onYes={rm} onNo={() => setDel(null)}><p>Delete <b>{del.medicine_name}</b> from the catalogue? This is blocked if it has stock or sales history.</p></Confirm>}</>
}
