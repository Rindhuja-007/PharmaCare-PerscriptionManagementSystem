import {useState} from 'react'
import {Plus} from 'lucide-react'
import {api,errText} from '../api'
import {Badge,Confirm,Empty,Field,Modal,PageHead,fmtDate,useLoad,useToast} from '../ui'
function AddStaff({onClose, onSaved}) {
  const toast = useToast(), [f, setF] = useState({name: '', username: '', email: '', password: '', role: 'PHARMACIST'}), s = k => e => setF({...f, [k]: e.target.value})
  const go = async e => { e.preventDefault(); try { await api.post('/auth/staff', f); toast('Account created'); onSaved() } catch (x) { toast(errText(x), 'err') } }
  return <Modal title="Add staff account" onClose={onClose}><form className="form" onSubmit={go}><Field label="Full name" cls="full"><input required minLength={2} value={f.name} onChange={s('name')}/></Field><Field label="Username"><input required minLength={3} value={f.username} onChange={s('username')}/></Field>
    <Field label="Role"><select value={f.role} onChange={s('role')}><option value="PHARMACIST">Pharmacist</option><option value="ADMIN">Administrator</option></select></Field><Field label="Email" cls="full"><input required type="email" value={f.email} onChange={s('email')}/></Field>
    <Field label="Temporary password" hint="At least 8 characters. They can change it after signing in." cls="full"><input required minLength={8} type="password" value={f.password} onChange={s('password')}/></Field>
    <div className="foot full"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">Create account</button></div></form></Modal>
}
export default function Staff({user}) {
  const l = useLoad(() => api.get('/auth/staff')), toast = useToast(), [add, setAdd] = useState(false), [ask, setAsk] = useState(null)
  const rows = l.data || [], pending = rows.filter(u => !u.is_approved), active = rows.filter(u => u.is_approved)
  const act = async (fn, msg) => { try { await fn(); toast(msg); l.reload() } catch (e) { toast(errText(e), 'err') } setAsk(null) }
  return <><PageHead title="Staff" sub="Who can sign in, and what they can do."><button className="btn primary" onClick={() => setAdd(true)}><Plus size={16}/>Add staff</button></PageHead>
    {pending.length > 0 && <div className="panel" style={{borderColor: '#e3c36b'}}><h2>Waiting for approval ({pending.length})</h2>{pending.map(u => <div className="row" key={u.id}><div><b>{u.name}</b> <Badge tone="amber">{u.role === 'ADMIN' ? 'Administrator' : 'Pharmacist'}</Badge><div className="small muted">{u.username}, {u.email}</div></div>
      <div style={{display: 'flex', gap: 8}}><button className="btn primary sm" onClick={() => act(() => api.post(`/auth/approve-admin/${u.id}`), 'Approved')}>Approve</button><button className="btn danger sm" onClick={() => setAsk(u)}>Reject</button></div></div>)}</div>}
    <div className="panel">{l.loading ? <div className="loading">Loading…</div> : active.length === 0 ? <Empty title="No staff yet"/> : <div className="scroll"><table><thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Status</th><th>Joined</th><th/></tr></thead><tbody>
      {active.map(u => <tr key={u.id}><td><b>{u.name}</b><div className="small muted">{u.email}</div></td><td>{u.username}</td><td>{u.role === 'ADMIN' ? 'Administrator' : 'Pharmacist'}</td><td>{u.is_active ? <Badge tone="green">Active</Badge> : <Badge tone="neutral">Deactivated</Badge>}</td><td>{fmtDate(u.created_at)}</td>
        <td className="right">{u.id !== user.id && (u.is_active ? <button className="btn danger sm" onClick={() => act(() => api.delete('/auth/staff/' + u.id), 'Account deactivated')}>Deactivate</button> : <button className="btn sm" onClick={() => act(() => api.post(`/auth/staff/${u.id}/activate`), 'Account reactivated')}>Reactivate</button>)}</td></tr>)}</tbody></table></div>}</div>
    {add && <AddStaff onClose={() => setAdd(false)} onSaved={() => { setAdd(false); l.reload() }}/>}
    {ask && <Confirm title="Reject request?" danger label="Reject and remove" onYes={() => act(() => api.post(`/auth/reject-admin/${ask.id}`), 'Request rejected')} onNo={() => setAsk(null)}><p>Remove the request from <b>{ask.name}</b>? They will need to submit a new request.</p></Confirm>}</>
}
