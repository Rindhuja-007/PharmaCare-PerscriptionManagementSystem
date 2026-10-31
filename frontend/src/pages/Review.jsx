import {useCallback,useEffect,useMemo,useState} from 'react'
import {Link,useParams} from 'react-router-dom'
import {ArrowLeft,CheckCircle2,Circle,Plus,Wand2,ZoomIn,AlertTriangle} from 'lucide-react'
import {createWorker} from 'tesseract.js'
import {api,errText} from '../api'
import {Badge,Confirm,Empty,Field,Modal,PageHead,RX_LABEL,RX_TONE,fmtDate,money,useToast} from '../ui'
import ReceiptModal from './Receipt'
const suggestQty = (f, d) => {
  const m = (f || '').match(/(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)/)
  const per = m ? +m[1] + +m[2] + +m[3] : ({OD: 1, BD: 2, TID: 3, QID: 4, HS: 1}[(f || '').toUpperCase()] || 0)
  const n = (d || '').match(/(\d+)\s*(day|week|month)/i), days = n ? +n[1] * ({day: 1, week: 7, month: 30}[n[2].toLowerCase()]) : 0
  return per && days ? Math.ceil(per * days) : ''
}
const mkDec = i => ({status: i.verification_status || 'PENDING', medicine_id: i.medicine_id || '', quantity: i.quantity || suggestQty(i.frequency, i.duration), dosage: i.dosage || '', frequency: i.frequency || '', duration: i.duration || ''})
const LEVEL = {HIGH: 'green', MEDIUM: 'amber', LOW: 'neutral'}
function Scan({id, processed}) {
  const [w, setW] = useState('original'), [src, setSrc] = useState(null), [zoom, setZoom] = useState(100), [err, setErr] = useState(false)
  useEffect(() => { let u; setErr(false); api.get(`/prescriptions/${id}/image?which=${w}`, {responseType: 'blob'}).then(r => { u = URL.createObjectURL(r.data); setSrc(u) }).catch(() => setErr(true)); return () => u && URL.revokeObjectURL(u) }, [id, w, processed])
  return <div className="panel"><div className="ph"><h3>Scan</h3>{processed && <div className="seg"><button className={'v' + (w === 'original' ? ' on' : '')} onClick={() => setW('original')}>Original</button><button className={'v' + (w === 'processed' ? ' on' : '')} onClick={() => setW('processed')}>Cleaned</button></div>}</div>
    <div className="viewer">{err ? <div className="empty">Image could not be loaded.</div> : src ? <img src={src} alt="Prescription scan" style={{width: zoom + '%'}}/> : <div className="loading">Loading…</div>}</div>
    <label className="small muted" style={{display: 'flex', gap: 8, alignItems: 'center', marginTop: 10}}><ZoomIn size={16}/>Zoom<input type="range" min="100" max="300" value={zoom} onChange={e => setZoom(+e.target.value)} style={{padding: 0}}/></label></div>
}
function Slip({item, d, set, m, meds, locked, problem}) {
  const med = meds.find(x => x.id === +d.medicine_id), q = +d.quantity || 0, low = d.status === 'VERIFIED' && med && q > med.usable_stock
  const toggle = s => set({status: d.status === s ? 'PENDING' : s})
  return <div className={`slip ${d.status.toLowerCase()}${problem ? ' bad' : ''}`}>
    <div className="slip-head"><div><b>{item.extracted_medicine_name}</b><div className="small muted">{[item.dosage, item.frequency, item.duration].filter(Boolean).join(', ') || 'No dosage details read'}</div></div>
      <div style={{display: 'flex', gap: 8, alignItems: 'center'}}>{item.confidence_score != null && <Badge tone={item.confidence_score >= 90 ? 'green' : item.confidence_score >= 70 ? 'amber' : 'neutral'}>{Math.round(item.confidence_score)}% match</Badge>}
        <div className="seg" role="group" aria-label="Decision"><button className={'v' + (d.status === 'VERIFIED' ? ' on' : '')} disabled={locked} onClick={() => toggle('VERIFIED')}>Verify</button><button className={'r' + (d.status === 'REJECTED' ? ' on' : '')} disabled={locked} onClick={() => toggle('REJECTED')}>Reject</button></div></div></div>
    {m && !locked && <div className="match-panel">
      <b>Catalogue matches</b>
      {m.candidates.length > 0 ? <div className="match-grid">{m.candidates.slice(0, 3).map(c => <button key={c.medicine_id} className="match-option" onClick={() => set({medicine_id: c.medicine_id})}><span>{c.name}</span><Badge tone={LEVEL[c.level]}>{c.score}%</Badge></button>)}</div> : <span className="small muted">No close catalogue match found.</span>}
      {m.substitutes.length > 0 && <div className="small muted" style={{marginTop: 8}}>Same ingredient</div>}
      {m.substitutes.slice(0, 3).map(c => <button key={'s' + c.medicine_id} className="match-option substitute" onClick={() => set({medicine_id: c.medicine_id})}><span>{c.name}</span><Badge tone={c.is_available ? 'green' : 'rose'}>{c.is_available ? c.stock + ' in stock' : 'out of stock'}</Badge></button>)}</div>}
    <div className="form dispense-fields">
      <Field label="Medicine to dispense" cls="c2"><select disabled={locked} value={d.medicine_id} onChange={e => set({medicine_id: e.target.value})}><option value="">Select from catalogue…</option>{meds.map(x => <option key={x.id} value={x.id}>{x.medicine_name} ({x.usable_stock} in stock)</option>)}</select></Field>
      <Field label="Quantity (units)"><input disabled={locked} type="number" min="1" value={d.quantity} onChange={e => set({quantity: e.target.value})}/></Field></div>
    {low && <div className="note warn" style={{marginTop: 10}}><AlertTriangle size={14} style={{verticalAlign: -2}}/> Only {med.usable_stock} usable units are in stock. Reduce the quantity or choose an available substitute.</div>}
    {problem && <div className="note err" style={{marginTop: 10}}>{problem}</div>}</div>
}
function AddModal({pid, meds, onClose, onAdded}) {
  const toast = useToast(), [f, setF] = useState({medicine_id: '', quantity: '', dosage: '', frequency: '', duration: ''}), [search, setSearch] = useState(''), s = k => e => setF({...f, [k]: e.target.value})
  const filteredMeds = meds.filter(m => `${m.medicine_name} ${m.generic_name || ''}`.toLowerCase().includes(search.trim().toLowerCase()))
  const go = async e => { e.preventDefault(); const med = meds.find(x => x.id === +f.medicine_id)
    if (!med) return toast('Choose a medicine from the catalogue.', 'err')
    try { await api.post(`/prescriptions/${pid}/items`, {extracted_medicine_name: med.medicine_name, medicine_id: med.id, quantity: +f.quantity || null, dosage: f.dosage || null, frequency: f.frequency || null, duration: f.duration || null}); toast('Medicine added'); onAdded() } catch (x) { toast(errText(x), 'err') } }
  return <Modal title="Add a medicine from catalogue" onClose={onClose}><form onSubmit={go} className="form"><Field label="Search medicine" cls="full"><input autoFocus value={search} onChange={e => setSearch(e.target.value)} placeholder="Search brand or generic name…"/></Field><Field label="Medicine" cls="full"><select required value={f.medicine_id} onChange={s('medicine_id')}><option value="">Select…</option>{filteredMeds.map(x => <option key={x.id} value={x.id}>{x.medicine_name} ({x.usable_stock} in stock)</option>)}</select>{!filteredMeds.length && <div className="small muted" style={{marginTop: 6}}>No catalogue medicine matches that search.</div>}</Field>
    <Field label="Quantity"><input type="number" min="1" required value={f.quantity} onChange={s('quantity')}/></Field><Field label="Dosage"><input value={f.dosage} onChange={s('dosage')}/></Field><Field label="Frequency"><input value={f.frequency} onChange={s('frequency')} placeholder="1-0-1"/></Field><Field label="Duration"><input value={f.duration} onChange={s('duration')} placeholder="5 days"/></Field>
    <div className="foot full"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">Add medicine</button></div></form></Modal>
}
function Dispense({p, onDone}) {
  const toast = useToast(), [av, setAv] = useState(null), [disc, setDisc] = useState('0'), [tax, setTax] = useState('0'), [ask, setAsk] = useState(false), [busy, setBusy] = useState(false)
  useEffect(() => { api.post(`/prescriptions/${p.id}/availability`).then(r => setAv(r.data)).catch(e => toast(errText(e), 'err')) }, [p.id]) // eslint-disable-line
  const plan = useMemo(() => (av || []).map(a => { let need = a.needed; const lines = []; for (const b of a.batches) { if (!need) break; const n = Math.min(b.quantity, need); lines.push({...b, take: n, amount: n * b.selling_price}); need -= n } return {...a, lines} }), [av])
  const sub = plan.reduce((s, a) => s + a.lines.reduce((x, l) => x + l.amount, 0), 0), short = plan.some(a => a.shortage > 0), d = +disc || 0, t = +tax || 0, bad = d < 0 || t < 0 || d > sub
  const go = async () => { setBusy(true); try { const {data} = await api.post('/transactions', {prescription_id: p.id, confirmed_dispensing: true, discount: d, tax: t}); setAsk(false); onDone(data) } catch (e) { setAsk(false); toast(errText(e), 'err') } finally { setBusy(false) } }
  return <section className="panel"><h2>Check stock and dispense</h2>
    {!av ? <div className="loading">Checking stock…</div> : <>
      {plan.map(a => <div key={a.item_id} style={{marginBottom: 12}}><div className="ph"><b>{a.medicine}: {a.needed} units</b>{a.shortage > 0 ? <Badge tone="rose">Short by {a.shortage}</Badge> : <Badge tone="green">Covered</Badge>}</div>
        <div className="scroll"><table><thead><tr><th>Batch (earliest expiry first)</th><th>Expires</th><th className="right">Take</th><th className="right">Price</th></tr></thead><tbody>{a.lines.map(l => <tr key={l.batch_id}><td>{l.batch_number}</td><td>{fmtDate(l.expiry_date)}</td><td className="right">{l.take}</td><td className="right">{money(l.selling_price)}</td></tr>)}{a.lines.length === 0 && <tr><td colSpan="4" className="muted">No usable batches</td></tr>}</tbody></table></div></div>)}
      {short && <div className="note err">Some medicines do not have enough usable stock. Go back to the lines above, reduce the quantity or choose a substitute, then save the verification again.</div>}
      <div className="form" style={{margin: '12px 0', maxWidth: 420}}><Field label="Discount (₹)"><input type="number" min="0" step="0.01" value={disc} onChange={e => setDisc(e.target.value)}/></Field><Field label="Tax (₹)"><input type="number" min="0" step="0.01" value={tax} onChange={e => setTax(e.target.value)}/></Field></div>
      {d > sub && <div className="note err" style={{marginBottom: 8}}>The discount cannot exceed the subtotal.</div>}
      <div style={{maxWidth: 300}}><div className="sumline"><span>Subtotal</span><span>{money(sub)}</span></div><div className="sumline tot"><span>Total</span><span>{money(sub - d + t)}</span></div></div>
      <div className="foot"><button className="btn primary" disabled={short || bad || plan.length === 0} onClick={() => setAsk(true)}>Review and dispense</button></div></>}
    {ask && <Confirm title="Dispense this prescription?" label="Confirm and dispense" busy={busy} onYes={go} onNo={() => setAsk(false)}><p>Stock will be deducted now, oldest expiry first. This cannot be undone.</p></Confirm>}</section>
}
export default function Review() {
  const {id} = useParams(), toast = useToast()
  const [p, setP] = useState(null), [err, setErr] = useState(''), [meds, setMeds] = useState([]), [match, setMatch] = useState({}), [dec, setDec] = useState({}), [busy, setBusy] = useState(''), [probs, setProbs] = useState({}), [adding, setAdding] = useState(false), [receipt, setReceipt] = useState(null)
  const load = useCallback(async () => { try { const {data} = await api.get('/prescriptions/' + id); setP(data); setDec(prev => Object.fromEntries(data.items.map(i => [i.id, prev[i.id] || mkDec(i)]))) } catch (e) { setErr(errText(e)) } }, [id])
  const loadMeds = useCallback(() => api.get('/medicines').then(r => setMeds(r.data)).catch(() => {}), [])
  useEffect(() => { load(); loadMeds() }, [load, loadMeds])
  const run = async (path, label, notify = true) => { setBusy(label); try { const r = await api.post(`/prescriptions/${id}/${path}`); await load(); return r.data } catch (e) { if (notify) toast(errText(e), 'err'); throw e } finally { setBusy('') } }
  const runBrowserOcr = async () => {
    let worker
    try {
      const {data: image} = await api.get(`/prescriptions/${id}/image?which=${p.processed_image_path ? 'processed' : 'original'}`, {responseType: 'blob'})
      worker = await createWorker('eng')
      await worker.setParameters({tessedit_pageseg_mode: '6', preserve_interword_spaces: '1'})
      const result = await worker.recognize(image)
      const text = result.data.text.trim()
      if (!text) throw new Error('No readable text was found in the image.')
      await api.post(`/prescriptions/${id}/process-text`, {extracted_text: text, confidence_score: result.data.confidence || 0})
      await load()
      return text
    } finally {
      if (worker) await worker.terminate()
    }
  }
  const runOcrWithFallback = async () => {
    try {
      return await run('process', 'Reading with RapidOCR', false)
    } catch {
      toast('RapidOCR is unavailable. Reading in the browser instead.', 'warn')
      setBusy('Reading in browser')
      try {
        return await runBrowserOcr()
      } catch (e) {
        toast(e?.response ? errText(e) : (e?.message || 'Browser OCR failed. Try a clearer image.'), 'err')
        throw e
      } finally {
        setBusy('')
      }
    }
  }
  const doMatch = async () => { const d = await run('match', 'Matching catalogue'); setMatch(Object.fromEntries(d.map(x => [x.item_id, x])))
    setDec(prev => { const n = {...prev}; d.forEach(x => { const c = x.candidates[0]; if (c && c.score >= 90 && n[x.item_id] && !n[x.item_id].medicine_id) n[x.item_id] = {...n[x.item_id], medicine_id: c.medicine_id} }); return n }) }
  const findAndMatch = async () => { try { const it = await run('extract', 'Finding medicines'); if (it.length) await doMatch(); else toast('No medicine lines were found. Add them manually.', 'warn') } catch { /* toast shown */ } }
  const runAll = async () => { try { await run('preprocess', 'Cleaning image'); await runOcrWithFallback(); await findAndMatch() } catch { /* toast shown */ } }
  const set = iid => patch => setDec(d => ({...d, [iid]: {...d[iid], ...patch}}))
  const save = async () => {
    const bad = {}; p.items.forEach(i => { const d = dec[i.id]; if (d.status === 'PENDING') bad[i.id] = 'Choose Verify or Reject for this line.'; else if (d.status === 'VERIFIED') { if (!d.medicine_id) bad[i.id] = 'Select the catalogue medicine to dispense.'; else if (!(+d.quantity > 0)) bad[i.id] = 'Enter a quantity greater than zero.' } })
    setProbs(bad); if (Object.keys(bad).length) return toast('Fix the highlighted lines before saving.', 'err')
    setBusy('Saving')
    try { const {data} = await api.put(`/prescriptions/${id}/verify`, {items: p.items.map(i => { const d = dec[i.id]; return {item_id: i.id, verification_status: d.status, medicine_id: d.medicine_id ? +d.medicine_id : null, quantity: d.quantity ? +d.quantity : null, dosage: d.dosage, frequency: d.frequency, duration: d.duration} })})
      setP(data); toast(data.status === 'VERIFIED' ? 'Prescription verified' : 'Prescription rejected') } catch (e) { toast(errText(e), 'err') } finally { setBusy('') }
  }
  const viewReceipt = async () => { try { setReceipt((await api.get(`/prescriptions/${id}/receipt`)).data) } catch (e) { toast(errText(e), 'err') } }
  if (err) return <Empty title="Prescription unavailable" hint={err}><Link className="btn" to="/prescriptions">Back to prescriptions</Link></Empty>
  if (!p) return <div className="loading">Loading prescription…</div>
  const locked = p.status === 'DISPENSED', steps = [['Uploaded', true], ['Image cleaned', !!p.processed_image_path], ['Text read', p.extracted_text != null], ['Lines found', p.items.length > 0], ['Verified', ['VERIFIED', 'DISPENSED'].includes(p.status)], ['Dispensed', locked]], cur = steps.findIndex(s => !s[1])
  const cnt = s => p.items.filter(i => dec[i.id]?.status === s).length
  return <>
    <Link to="/prescriptions" className="back"><ArrowLeft size={16}/>All prescriptions</Link>
    <PageHead title={p.prescription_number} sub={[p.patient_reference, p.doctor_name && 'Dr. ' + p.doctor_name.replace(/^dr\.?\s*/i, ''), fmtDate(p.created_at, true)].filter(Boolean).join(', ')}><Badge tone={RX_TONE[p.status]}>{RX_LABEL[p.status]}</Badge></PageHead>
    <ol className="stepper">{steps.map(([l, done], i) => <li key={l} className={done ? 'done' : i === cur ? 'cur' : ''}>{done ? <CheckCircle2 size={16}/> : <Circle size={16}/>}{l}</li>)}</ol>
    <div className="desk">
      <aside className="scan"><Scan id={p.id} processed={!!p.processed_image_path}/>
        <div className="panel detected"><h3>Medicines detected</h3>{p.items.length ? <ol>{p.items.map(i => <li key={i.id}><b>{i.extracted_medicine_name}</b><span>{[i.dosage, i.frequency, i.duration, i.quantity && `Qty ${i.quantity}`].filter(Boolean).join(' · ') || 'Dosage not read'}</span></li>)}</ol> : <p className="small muted">Run “Find medicines” to list the prescription items.</p>}</div>
      </aside>
      <section>
        {!locked && <div className="panel"><div className="actions"><button className="btn primary" disabled={!!busy} onClick={() => runAll()}><Wand2 size={16}/>Read prescription automatically</button>
          <button className="btn sm" disabled={!!busy} onClick={() => run('preprocess', 'Cleaning image').catch(() => {})}>Clean image</button><button className="btn sm" disabled={!!busy} onClick={() => runOcrWithFallback().catch(() => {})}>Run OCR</button>
          <button className="btn sm" disabled={!!busy} onClick={findAndMatch}>Find medicines</button><button className="btn sm" disabled={!!busy || !p.items.length} onClick={() => doMatch().catch(() => {})}>Match catalogue</button>
          {busy && <span className="muted small"><span className="spin"/> {busy}…</span>}</div>
          <p className="small muted" style={{margin: '10px 0 0'}}>These steps only suggest. Nothing is approved and no stock moves until you verify and dispense.</p></div>}
        <div className="ph" style={{margin: '4px 0 10px'}}><h2>Medicines on this prescription</h2>{!locked && <button className="btn sm" onClick={() => setAdding(true)}><Plus size={14}/>Add medicine</button>}</div>
        {p.items.length === 0 ? <div className="panel"><Empty title="No medicines yet" hint="OCR is only a suggestion. Search the catalogue and add each medicine manually for reliable dispensing."/></div> :
          p.items.map(i => <Slip key={i.id} item={i} d={dec[i.id] || mkDec(i)} set={set(i.id)} m={match[i.id]} meds={meds} locked={locked} problem={probs[i.id]}/>)}
        {!locked && p.items.length > 0 && <div className="sticky-save"><span className="muted small">{cnt('VERIFIED')} to dispense, {cnt('REJECTED')} rejected, {cnt('PENDING')} undecided</span><button className="btn primary" disabled={!!busy} onClick={save}>Save verification</button></div>}
        {p.status === 'REJECTED' && <div className="note warn">Every line was rejected, so there is nothing to dispense. Change a decision and save again if this was a mistake.</div>}
        {p.status === 'VERIFIED' && <Dispense p={p} onDone={r => { setReceipt(r); load(); loadMeds() }}/>}
        {locked && <div className="panel"><div className="ph"><div><h3>Dispensed</h3><span className="muted small">Stock was deducted and the receipt recorded.</span></div><button className="btn" onClick={viewReceipt}>View receipt</button></div></div>}
      </section></div>
    {adding && <AddModal pid={p.id} meds={meds} onClose={() => setAdding(false)} onAdded={() => { setAdding(false); load() }}/>}
    {receipt && <ReceiptModal tx={receipt} onClose={() => setReceipt(null)}/>}</>
}
