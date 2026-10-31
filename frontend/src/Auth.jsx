import {useEffect,useState} from 'react'
import {ShieldCheck,Layers,ScrollText,Cross} from 'lucide-react'
import {api,errText} from './api'
import {Field} from './ui'
export default function Auth({onLogin}) {
  const [st, setSt] = useState(null), [mode, setMode] = useState('login'), [busy, setBusy] = useState(false), [err, setErr] = useState(''), [note, setNote] = useState('')
  const [asAdmin, setAsAdmin] = useState(false)
  const [f, setF] = useState({name: '', username: '', email: '', password: '', approval_code: ''})
  const set = k => e => setF({...f, [k]: e.target.value})
  useEffect(() => { api.get('/auth/status').then(r => { setSt(r.data); if (r.data.initial_setup_required) setMode('setup') }).catch(e => setErr(errText(e))) }, [])
  const signIn = async (username, password) => { const {data} = await api.post('/auth/login', {username, password}); localStorage.setItem('pc_token', data.access_token); onLogin(data.user) }
  async function submit(e) {
    e.preventDefault(); setErr(''); setNote(''); setBusy(true)
    try {
      if (mode === 'login') await signIn(f.username, f.password)
      else {
        const admin = mode === 'setup' || asAdmin
        const {data} = await api.post(admin ? '/auth/register-admin' : '/auth/register', {name: f.name, username: f.username, email: f.email, password: f.password, approval_code: asAdmin && f.approval_code ? f.approval_code : null})
        if (data.approved && mode === 'setup') await signIn(f.username, f.password)
        else if (data.approved) { setNote(data.detail + ' You can sign in now.'); setMode('login'); setSt(s => ({...s, initial_setup_required: false})) }
        else { setNote(data.detail); setMode('login') }
      }
    } catch (x) { setErr(errText(x)) } finally { setBusy(false) }
  }
  const demo = async () => { try { await api.post('/auth/seed-demo'); setSt(s => ({...s, initial_setup_required: false})); setMode('login'); setF(x => ({...x, username: 'admin', password: 'Admin@123'})); setNote('Demo data loaded. Sign in as admin / Admin@123 or pharmacist / Pharmacist@123.') } catch (x) { setErr(errText(x)) } }
  const setup = mode === 'setup'
  return <div className="auth">
    <div className="auth-art"><div className="brand"><Cross size={26}/>PharmaCare</div>
      <div><h1>Every dispense, double-checked.</h1><ul>
        <li><ShieldCheck size={20}/><span><b>A pharmacist decides</b>Reading a prescription never approves it or touches stock.</span></li>
        <li><Layers size={20}/><span><b>Oldest batch first</b>Stock is taken first-expired-first-out and expired units are never used.</span></li>
        <li><ScrollText size={20}/><span><b>Everything is on record</b>Each verification, dispense and change is logged with who did it.</span></li></ul></div>
      <span className="small">Pharmacist-assisted clinical dispensing and inventory</span></div>
    <div className="auth-form"><form className="auth-card" onSubmit={submit}>
      {setup ? <><h1>Set up PharmaCare</h1><p className="muted">Create the first administrator account to get started.</p></>
        : <><h1>{mode === 'login' ? 'Welcome back' : 'Request access'}</h1>
          <div className="tabs" role="tablist"><button type="button" className={mode === 'login' ? 'on' : ''} onClick={() => { setMode('login'); setErr('') }}>Sign in</button><button type="button" className={mode === 'request' ? 'on' : ''} onClick={() => { setMode('request'); setErr(''); setNote('') }}>Request access</button></div></>}
      {note && <div className="note ok" role="status">{note}</div>}{err && <div className="note err" role="alert">{err}</div>}
      {mode !== 'login' && <><Field label="Full name"><input required minLength={2} value={f.name} onChange={set('name')} autoComplete="name"/></Field>
        <Field label="Email"><input required type="email" value={f.email} onChange={set('email')} autoComplete="email"/></Field></>}
      <Field label="Username" hint={mode !== 'login' ? 'Letters, numbers, dot, dash or underscore. At least 3 characters.' : undefined}><input required minLength={3} value={f.username} onChange={set('username')} autoComplete="username" autoCapitalize="none"/></Field>
      <Field label="Password" hint={mode !== 'login' ? 'At least 8 characters.' : undefined}><input required minLength={mode === 'login' ? 1 : 8} type="password" value={f.password} onChange={set('password')} autoComplete={mode === 'login' ? 'current-password' : 'new-password'}/></Field>
      {mode === 'request' && <><label className="small"><input type="checkbox" checked={asAdmin} onChange={e => setAsAdmin(e.target.checked)}/> I am requesting an administrator account</label>
        {asAdmin && <Field label="Clinic approval code (optional)" hint="Leave empty to wait for an administrator to approve you."><input value={f.approval_code} onChange={set('approval_code')}/></Field>}</>}
      <button className="btn primary" disabled={busy || (!st && !err)} style={{justifyContent: 'center'}}>{busy ? 'Please wait…' : setup ? 'Create administrator' : mode === 'login' ? 'Sign in' : 'Send request'}</button>
      {setup && <button type="button" className="btn" onClick={demo}>Load demo data instead</button>}
    </form></div></div>
}
