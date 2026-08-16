import { ArrowUpRight, ArrowDownRight } from 'lucide-react'

export default function MetricCard({
  label,
  value,
  change,
  changeLabel,
  icon,
  accent,
}: {
  label: string
  value: string
  change?: number
  changeLabel?: string
  icon?: React.ReactNode
  accent?: 'success' | 'danger' | 'warning' | 'accent'
}) {
  const isPositiveChange = change !== undefined && change > 0
  const changeColor = change === undefined ? undefined
    : isPositiveChange ? 'var(--danger)' : 'var(--success)'

  return (
    <div className="metric-card fade-in">
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
        <div className="metric-label">{label}</div>
        {icon && <div style={{ color: 'var(--text-muted)', opacity: 0.6 }}>{icon}</div>}
      </div>
      <div className="metric-value">{value}</div>
      {change !== undefined && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 8, fontSize: 12 }}>
          {isPositiveChange
            ? <ArrowUpRight size={12} style={{ color: changeColor }} />
            : <ArrowDownRight size={12} style={{ color: changeColor }} />}
          <span style={{ color: changeColor, fontWeight: 600 }}>{Math.abs(change).toFixed(1)}%</span>
          {changeLabel && <span style={{ color: 'var(--text-muted)' }}>{changeLabel}</span>}
        </div>
      )}
    </div>
  )
}
