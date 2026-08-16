'use client'
import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  LayoutDashboard, TrendingUp, AlertTriangle, Search,
  Lightbulb, BarChart2, DollarSign,
  Bot, Shield, Settings, LogOut
} from 'lucide-react'
import { clearAuthToken } from '@/lib/api'

const NAV = [
  { href: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { href: '/spend', label: 'Spend Explorer', icon: TrendingUp },
  { href: '/anomalies', label: 'Anomalies', icon: AlertTriangle },
  { href: '/investigations', label: 'Investigations', icon: Search },
  { href: '/recommendations', label: 'Recommendations', icon: Lightbulb },
  { href: '/forecasts', label: 'Forecast', icon: BarChart2 },
  { href: '/budgets', label: 'Budgets', icon: DollarSign },
  { href: '/agents', label: 'Agent Runs', icon: Bot },
  { href: '/data-quality', label: 'Data Quality', icon: Shield },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()

  const handleLogout = () => {
    clearAuthToken()
    router.push('/login')
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <aside style={{
        width: 220,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        position: 'sticky',
        top: 0,
        height: '100vh',
      }}>
        {/* Logo */}
        <div style={{
          padding: '20px 20px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          <div style={{
            width: 32, height: 32, background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
            borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <span style={{ color: '#fff', fontSize: 14, fontWeight: 700 }}>C</span>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.2 }}>CloudSpend</div>
            <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 500 }}>Intelligence</div>
          </div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '8px 8px', overflowY: 'auto' }}>
          {NAV.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== '/dashboard' && pathname?.startsWith(href))
            return (
              <Link key={href} href={href} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '8px 12px',
                borderRadius: 8,
                color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                background: active ? 'rgba(99,102,241,0.12)' : 'transparent',
                textDecoration: 'none',
                fontSize: 13,
                fontWeight: active ? 600 : 400,
                marginBottom: 2,
                transition: 'all 0.15s',
                borderLeft: active ? '2px solid var(--accent)' : '2px solid transparent',
              }}>
                <Icon size={15} style={{ flexShrink: 0 }} />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom */}
        <div style={{ padding: '12px 8px', borderTop: '1px solid var(--border)' }}>
          <button onClick={handleLogout} style={{
            display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
            borderRadius: 8, color: 'var(--text-muted)', background: 'transparent',
            border: 'none', cursor: 'pointer', fontSize: 13, width: '100%',
            transition: 'color 0.15s',
          }}>
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main style={{ flex: 1, overflowX: 'hidden' }}>
        {children}
      </main>
    </div>
  )
}
