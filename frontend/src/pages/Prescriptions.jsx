import {useRef,useState} from 'react'
import {Link,useNavigate,useSearchParams} from 'react-router-dom'
import {Upload,Plus} from 'lucide-react'
import {api,errText,shrinkImage} from '../api'
import {Badge,Empty,Field,Modal,PageHead,RX_LABEL,RX_TONE,fmtDate,useLoad,useToast} from '../ui'
function UploadModal({onClose}) {
  const nav = useNavigate(), toast = useToast(), ref = useRef(), [file, setFile] = useState(null), [prev, setPrev] = useState(''), [drag, setDrag] = useState(false), [busy, setBusy] = useState(false)
  const [pat, setPat] = useState(''), [doc, setDoc] = useState('')
  const pick = f => { if (!f) return; if (!/^image\/(jpeg|png)$/.test(f.type)) return toast('Please choose a JPG or PNG photo.', 'err'); setFile(f); setPrev(URL.createObjectURL(f)) }
  const go = async () => {
    setBusy(true)
    try { const fd = new FormData(); fd.append('file', await shrinkImage(file), 'prescription.jpg'); if (pat) fd.append('patient_reference', pat); if (doc) fd.append('doctor_name', doc)
      const {data} = await api.post('/prescriptions/upload', fd); toast('Prescription uploaded'); nav(`/prescriptions/${data.id}`) } catch (e) { toast(errText(e), 'err'); setBusy(false) }
  }
  return <Modal title="Upload prescription" onClose={onClose}>
    <div className={'drop' + (drag ? ' over' : '')} role="button" tabIndex={0} onClick={() => ref.current.click()} onKeyDown={e => e.key === 'Enter' && ref.current.click()}
      onDragOver={e => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)} onDrop={e => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]) }}>
      {prev ? <img src={prev} alt="Selected prescription"/> : <><Upload size={28}/><p style={{margin: '8px 0 0'}}>Drop a photo here or click to choose<br/><span className="small">JPG or PNG, a clear straight-on photo reads best</span></p></>}</div>
    <input ref={ref} type="file" accept="image/jpeg,image/png" hidden onChange={e => pick(e.target.files[0])}/>
    <div className="form" style={{marginTop: 14}}><Field label="Patient name, phone or MRN"><input value={pat} onChange={e => setPat(e.target.value)}/></Field><Field label="Doctor"><input value={doc} onChange={e => setDoc(e.target.value)}/></Field></div>
    <div className="foot"><button className="btn" onClick={onClose}>Cancel</button><button className="btn primary" disabled={!file || busy} onClick={go}>{busy ? 'Uploading…' : 'Upload and open'}</button></div></Modal>
}
export default function Prescriptions() {
  const l = useLoad(() => api.get('/prescriptions')), [sp, setSp] = useSearchParams(), [f, setF] = useState('ALL')
  const rows = (l.data || []).filter(r => f === 'ALL' || r.status === f)
  return <>
    <PageHead title="Prescriptions" sub="Upload, review and dispense."><button className="btn primary" onClick={() => setSp({upload: 1})}><Plus size={16}/>Upload prescription</button></PageHead>
    <div className="chips" style={{marginBottom: 14}}>{['ALL', 'UPLOADED', 'PROCESSED', 'VERIFIED', 'REJECTED', 'DISPENSED'].map(s => <button key={s} className={'chip' + (f === s ? ' on' : '')} onClick={() => setF(s)}>{s === 'ALL' ? 'All' : RX_LABEL[s]}</button>)}</div>
    <div className="panel scroll">{l.loading ? <div className="loading">Loading…</div> : l.error ? <div className="note err">{l.error}</div> : rows.length === 0 ? <Empty title="No prescriptions here" hint={f === 'ALL' ? 'Upload your first prescription to begin.' : 'Try another filter.'}/> :
      <table><thead><tr><th>Number</th><th>Patient</th><th>Doctor</th><th>Status</th><th className="right">Lines</th><th>Uploaded</th><th/></tr></thead><tbody>
        {rows.map(r => <tr key={r.id}><td><b>{r.prescription_number}</b></td><td>{r.patient_reference || '–'}</td><td>{r.doctor_name || '–'}</td><td><Badge tone={RX_TONE[r.status]}>{RX_LABEL[r.status]}</Badge></td><td className="right">{r.item_count}</td><td className="nowrap">{fmtDate(r.created_at)}</td><td className="right"><Link className="btn sm" to={`/prescriptions/${r.id}`}>Open</Link></td></tr>)}</tbody></table>}</div>
    {sp.get('upload') && <UploadModal onClose={() => setSp({})}/>}</>
}
