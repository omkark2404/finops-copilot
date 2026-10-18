'use client'
import {useEffect,useState} from 'react'
import {usePathname,useRouter} from 'next/navigation'
import Link from 'next/link'
import {api} from '@/lib/api'
import {clearDataset,useDataset} from '@/lib/useDataset'
const NAV=[['/dashboard','Overview'],['/spend','Spend Explorer'],['/anomalies','Anomalies'],
['/investigations','Investigations'],['/recommendations','Recommendations'],['/forecasts','Forecast'],
['/budgets','Budgets'],['/agents','Analysis Runs'],['/data-quality','Data Quality'],['/settings','Settings']]
export default function Layout({children}:{children:React.ReactNode}){
  const pathname=usePathname();const router=useRouter();const {datasetId}=useDataset()
  const [ready,setReady]=useState(false);const [error,setError]=useState<string|null>(null)
  useEffect(()=>{
    let active=true
    api.me().then(()=>{if(active)setReady(true)}).catch(()=>router.replace('/login'))
    const listener=(event:Event)=>setError((event as CustomEvent<string>).detail)
    const expired=()=>router.replace('/login')
    window.addEventListener('finops:unauthorized',expired)
    window.addEventListener('finops:error',listener)
    return ()=>{active=false;window.removeEventListener('finops:unauthorized',expired);window.removeEventListener('finops:error',listener)}
  },[router])
  useEffect(()=>setError(null),[pathname,datasetId])
  async function logout(){
    try{await api.logout();clearDataset();router.replace('/login')}catch(e){setError((e as Error).message)}
  }
  if(!ready)return <main className="session-loading" role="status">Checking session…</main>
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="app-sidebar">
      <div className="app-brand"><span className="brand-mark" aria-label="FinOps Copilot">FC</span><div><strong>FinOps Copilot</strong><small>Omkar · Portfolio prototype</small></div></div>
      <nav aria-label="Main navigation">{NAV.map(([href,label])=><Link key={href} href={href} aria-current={pathname===href?'page':undefined}>{label}</Link>)}</nav>
      <button className="btn btn-ghost" onClick={logout}>Sign out</button>
      <a href="https://github.com/omkark2404/finops-copilot" className="source-link">Source and limitations</a>
    </aside>
    <main id="main-content" className="app-main">
      {error && <div className="request-error" role="alert"><strong>Request failed.</strong> {error} Results may be unavailable. <button className="btn btn-ghost" onClick={()=>window.location.reload()}>Retry</button></div>}
      {children}
    </main>
  </div>
}
