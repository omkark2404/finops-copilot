import type {Metadata} from 'next'
import './globals.css'
export const metadata:Metadata={
  title:{default:'FinOps Copilot | Omkar',template:'%s | FinOps Copilot'},
  description:'FOCUS billing analytics prototype with statistical anomaly detection, forecasting, and optional Gemini explanations.',
  openGraph:{title:'FinOps Copilot | Omkar',description:'A portfolio prototype for investigating cloud billing data.',type:'website'},
  twitter:{card:'summary',title:'FinOps Copilot | Omkar'},
  icons:{icon:'/icon.svg'},
}
export default function RootLayout({children}:{children:React.ReactNode}){
  return <html lang="en"><body>{children}</body></html>
}
