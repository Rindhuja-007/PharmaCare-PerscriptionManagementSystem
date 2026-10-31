import {useCallback,useEffect,useState} from 'react'
import {NavLink,Navigate,Route,Routes,useLocation} from 'react-router-dom'
import {LayoutDashboard,FileText,Pill,Boxes,Receipt,Bell,BarChart3,Users,LogOut,KeyRound,Menu,Cross} from 'lucide-react'
import {api,errText} from './api'
import {Field,Modal,ToastProvider,useToast} from './ui'
import Auth from './Auth'
import Dashboard from './pages/Dashboard'
import Prescriptions from './pages/Prescriptions'
import Review from './pages/Review'
import Medicines from './pages/Medicines'
import Inventory from './pages/Inventory'
import Transactions from './pages/Transactions'
import Alerts from './pages/Alerts'
import Reports from './pages/Reports'
import Staff from './pages/Staff'
const NAV = [['/dashboard', 'Dashboard', LayoutDashboard], ['/prescriptions', 'Prescriptions', FileText], ['/medicines', 'Medicines', Pill], ['/inventory', 'Inventory', Boxes], ['/transactions', 'Transactions', Receipt], ['/alerts', 'Alerts', Bell], ['/reports', 'Reports', BarChart3], ['/staff', 'Staff', Users, true]]
function Password({onClose}) {
  const toast = useToast(), [f, setF] = useState({current_password: '', new_password: ''}), [err, setErr] = useState('')
  const go = async e => { e.preventDefault(); try { await api.post('/auth/change-password', f); toast('Password updated'); onClose() } catch (x) { setErr(errText(x)) } }
  return <Modal title="Change password" onClose={onClose}><form onSubmit={go} className="form" style={{gridTemplateColumns: '1fr'}}>{err && <div className="note err">{err}</div>}
    <Field label="Current password"><input required type="password" autoComplete="current-password" value={f.current_password} onChange={e => setF({...f, current_password: e.target.value})}/></Field>
    <Field label="New password" hint="At least 8 characters."><input required minLength={8} type="password" autoComplete="new-password" value={f.new_password} onChange={e => setF({...f, new_password: e.target.value})}/></Field>
    <div className="foot"><button type="button" className="btn" onClick={onClose}>Cancel</button><button className="btn primary">Update password</button></div></form></Modal>
}
function Shell({user, onLogout}) {
  const [open, setOpen] = useState(false), [unread, setUnread] = useState(0), [pw, setPw] = useState(false), loc = useLocation()
  const refresh = useCallback(() => api.get('/alerts?unread_only=true').then(r => setUnread(r.data.length)).catch(() => {}), [])
  useEffect(() => { refresh(); const t = setInterval(refresh, 60000); return () => clearInterval(t) }, [refresh])
  useEffect(() => { setOpen(false); refresh() }, [loc.pathname, refresh])
  const admin = user.role === 'ADMIN'
  return <div className="app">
    <div className="topbar"><button className="icon" onClick={() => setOpen(!open)} aria-label="Menu"><Menu size={22}/></button><b style={{fontFamily: 'Fraunces,serif'}}>PharmaCare</b></div>
    <nav className={'side' + (open ? ' open' : '')} aria-label="Main"><div className="brand"><Cross size={22}/>PharmaCare</div>
      {NAV.filter(n => !n[3] || admin).map(([to, label, Icon]) => <NavLink key={to} to={to}><Icon size={18}/>{label}{to === '/alerts' && unread > 0 && <span className="count">{unread}</span>}</NavLink>)}
      <div className="me"><div><b>{user.name}</b>{admin ? 'Administrator' : 'Pharmacist'}</div>
        <button onClick={() => setPw(true)}><KeyRound size={15}/>Change password</button><button onClick={onLogout}><LogOut size={15}/>Sign out</button></div></nav>
    <main className="main"><Routes>
      <Route path="/dashboard" element={<Dashboard user={user}/>}/><Route path="/prescriptions" element={<Prescriptions/>}/><Route path="/prescriptions/:id" element={<Review/>}/>
      <Route path="/medicines" element={<Medicines user={user}/>}/><Route path="/inventory" element={<Inventory/>}/><Route path="/transactions" element={<Transactions/>}/>
      <Route path="/alerts" element={<Alerts onChange={refresh}/>}/><Route path="/reports" element={<Reports/>}/>
      <Route path="/staff" element={admin ? <Staff user={user}/> : <Navigate to="/dashboard" replace/>}/><Route path="*" element={<Navigate to="/dashboard" replace/>}/></Routes></main>
    {pw && <Password onClose={() => setPw(false)}/>}</div>
}
function Root() {
  const [user, setUser] = useState(null), [boot, setBoot] = useState(!!localStorage.getItem('pc_token'))
  const logout = useCallback(() => { localStorage.removeItem('pc_token'); setUser(null) }, [])
  useEffect(() => { if (boot) api.get('/auth/me').then(r => setUser(r.data)).catch(() => localStorage.removeItem('pc_token')).finally(() => setBoot(false)) }, []) // eslint-disable-line
  useEffect(() => { window.addEventListener('pc-logout', logout); return () => window.removeEventListener('pc-logout', logout) }, [logout])
  if (boot) return <div className="loading">Loading…</div>
  return user ? <Shell user={user} onLogout={logout}/> : <Auth onLogin={u => { window.location.hash = '#/dashboard'; setUser(u) }}/>
}
export default function App() { return <ToastProvider><Root/></ToastProvider> }
