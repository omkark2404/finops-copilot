'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import MetricCard from '@/components/MetricCard'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { formatCurrency, formatPct } from '@/lib/format'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer
} from 'recharts'
import { TrendingUp, AlertTriangle, Lightbulb, DollarSign, Activity, Shield } from 'lucide-react'

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#818cf8', '#4f46e5']

export default function DashboardPage() {
  const { datasetId } = useDataset()
  const [summary, setSummary] = useState<any>(null)
  const [trend, setTrend] = useState<any>(null)
  const [anomalies, setAnomalies] = useState<any>(null)
  const [opportunities, setOpportunities] = useState<any>(null)
  const [forecast, setForecast] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    setError(null)
    Promise.all([
      api.spendSummary(datasetId),
      api.spendTrend(datasetId, 'daily'),
      api.anomalies(datasetId).catch(() => null),
      api.opportunities(datasetId).catch(() => null),
      api.forecasts(datasetId, 30).catch(() => null),
    ]).then(([s, t, a, o, f]) => {
      setSummary(s); setTrend(t); setAnomalies(a); setOpportunities(o); setForecast(f)
    }).catch(e => setError(e.message)).finally(() => setLoading(false))
  }, [datasetId])

  const serviceData = summary ? Object.entries(summary.service_breakdown || {}).slice(0, 6).map(([k, v]) => ({ name: k, cost: v as number })) : []
  const trendData = trend?.data_points?.slice(-30) || []
  const forecastPoints = forecast?.points?.slice(0, 14) || []

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1400 }}>
        <PageHeader
          title="Overview"
          subtitle="Cloud cost intelligence across all providers and services"
          actions={<DatasetSelector />}
        />

        {!datasetId && (
          <div className="empty-state card" style={{ padding: 64 }}>
            <Shield size={40} style={{ color: 'var(--text-muted)' }} />
            <h3 style={{ color: 'var(--text-primary)', fontSize: 16 }}>No dataset loaded</h3>
            <p style={{ fontSize: 13 }}>Upload FOCUS billing data to get started.</p>
            <a href="/settings" className="btn btn-primary">Go to Settings →</a>
          </div>
        )}

        {datasetId && loading && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
            {[...Array(4)].map((_, i) => (
              <div key={i} className="skeleton" style={{ height: 100, borderRadius: 12 }} />
            ))}
          </div>
        )}

        {datasetId && !loading && summary && (
          <>
            {/* Metric Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
              <MetricCard
                label="Total Spend"
                value={formatCurrency(summary.total_billed_cost)}
                change={summary.mom_change_pct}
                changeLabel="MoM"
                icon={<DollarSign size={16} />}
              />
              <MetricCard
                label="Effective Spend"
                value={formatCurrency(summary.total_effective_cost)}
                icon={<Activity size={16} />}
              />
              <MetricCard
                label="Active Anomalies"
                value={String(anomalies?.total_anomalies ?? '—')}
                icon={<AlertTriangle size={16} />}
              />
              <MetricCard
                label="Opportunities"
                value={String(opportunities?.total_opportunities ?? '—')}
                icon={<Lightbulb size={16} />}
              />
            </div>

            {/* Second Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
              <MetricCard
                label="Est. Savings Available"
                value={formatCurrency(opportunities?.total_potential_savings)}
                icon={<TrendingUp size={16} />}
              />
              <MetricCard
                label="Critical Anomalies"
                value={String(anomalies?.critical_count ?? '—')}
                icon={<AlertTriangle size={16} />}
              />
              <MetricCard
                label="Data Coverage"
                value={summary.period_start && summary.period_end
                  ? `${summary.period_start?.slice(0, 10)} – ${summary.period_end?.slice(0, 10)}`
                  : '—'}
                icon={<Shield size={16} />}
              />
            </div>

            {/* Charts Row */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 16, marginBottom: 24 }}>
              {/* Spend Trend */}
              <div className="card" style={{ padding: 24 }}>
                <div className="section-header">
                  <div className="section-title">Daily Spend Trend</div>
                </div>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={trendData}>
                    <defs>
                      <linearGradient id="gradAccent" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                      tickFormatter={d => d?.slice(5)} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }}
                      tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                      formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Billed Cost']}
                    />
                    <Area type="monotone" dataKey="billed_cost" stroke="#6366f1" fill="url(#gradAccent)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Service Breakdown */}
              <div className="card" style={{ padding: 24 }}>
                <div className="section-header">
                  <div className="section-title">By Service</div>
                </div>
                {serviceData.length > 0 ? (
                  <div>
                    {serviceData.map((item, i) => {
                      const total = serviceData.reduce((s, d) => s + d.cost, 0)
                      const pct = total > 0 ? (item.cost / total * 100) : 0
                      return (
                        <div key={item.name} style={{ marginBottom: 12 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 12 }}>
                            <span style={{ color: 'var(--text-secondary)' }} title={item.name}>
                              {item.name.length > 28 ? item.name.slice(0, 28) + '…' : item.name}
                            </span>
                            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>
                              {formatCurrency(item.cost)}
                            </span>
                          </div>
                          <div style={{ height: 4, background: 'var(--bg-elevated)', borderRadius: 2 }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: COLORS[i % COLORS.length], borderRadius: 2, transition: 'width 0.5s' }} />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="empty-state" style={{ padding: 24 }}>No data</div>
                )}
              </div>
            </div>

            {/* Forecast Row */}
            {forecast && forecastPoints.length > 0 && (
              <div className="card" style={{ padding: 24, marginBottom: 24 }}>
                <div className="section-header">
                  <div className="section-title">30-Day Forecast</div>
                  <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-muted)' }}>
                    <span>Method: <strong style={{ color: 'var(--text-primary)' }}>{forecast.method}</strong></span>
                    {forecast.metrics?.wape !== undefined && (
                      <span>WAPE: <strong style={{ color: 'var(--text-primary)' }}>{formatPct(forecast.metrics.wape * 100)}</strong></span>
                    )}
                  </div>
                </div>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={[...trendData.slice(-14), ...forecastPoints.map((p: any) => ({ ...p, is_forecast: true }))]}>  
                    <defs>
                      <linearGradient id="gradForecast" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={d => d?.slice(5)} />
                    <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                      formatter={(v: any) => [`$${Number(v).toLocaleString()}`, 'Cost']}
                    />
                    <Area type="monotone" dataKey="billed_cost" stroke="#6366f1" fill="url(#gradAccent)" strokeWidth={2} />
                    <Area type="monotone" dataKey="predicted_cost" stroke="#8b5cf6" fill="url(#gradForecast)" strokeWidth={2} strokeDasharray="4 2" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Bottom Row: Anomalies + Opportunities */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              {/* Anomalies */}
              <div className="card" style={{ padding: 24 }}>
                <div className="section-header">
                  <div className="section-title">Recent Anomalies</div>
                  <a href="/anomalies" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>View all →</a>
                </div>
                {anomalies?.anomalies?.length > 0 ? (
                  <table className="table">
                    <thead><tr>
                      <th>Entity</th><th>Deviation</th><th>Severity</th>
                    </tr></thead>
                    <tbody>
                      {anomalies.anomalies.slice(0, 5).map((a: any) => (
                        <tr key={a.id}>
                          <td style={{ color: 'var(--text-primary)', maxWidth: 140 }}>
                            <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {a.entity_value}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.entity_type}</div>
                          </td>
                          <td style={{ color: a.deviation_pct > 0 ? 'var(--danger)' : 'var(--success)' }}>
                            {a.deviation_pct > 0 ? '+' : ''}{a.deviation_pct?.toFixed(1)}%
                          </td>
                          <td><span className={`badge badge-${a.severity}`}>{a.severity}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="empty-state" style={{ padding: 32 }}>
                    <AlertTriangle size={24} />
                    <span>No anomalies detected</span>
                  </div>
                )}
              </div>

              {/* Opportunities */}
              <div className="card" style={{ padding: 24 }}>
                <div className="section-header">
                  <div className="section-title">Top Opportunities</div>
                  <a href="/recommendations" style={{ fontSize: 12, color: 'var(--accent)', textDecoration: 'none' }}>View all →</a>
                </div>
                {opportunities?.opportunities?.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    {opportunities.opportunities.slice(0, 4).map((o: any) => (
                      <div key={o.id} className="card-elevated" style={{ padding: '12px 14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <span style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500 }}>
                            {o.entity?.slice(0, 40)}
                          </span>
                          <span style={{ fontSize: 12, color: 'var(--success)', fontWeight: 600 }}>
                            {formatCurrency(o.potential_savings_estimate)}
                          </span>
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {o.opportunity_type?.replace(/_/g, ' ')}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state" style={{ padding: 32 }}>
                    <Lightbulb size={24} />
                    <span>No opportunities found</span>
                  </div>
                )}
              </div>
            </div>
          </>
        )}
        {error && (
          <div style={{ padding: 16, background: 'var(--danger-muted)', borderRadius: 8, color: '#f87171', fontSize: 13, marginTop: 16 }}>
            Error: {error}
          </div>
        )}
      </div>
    </Layout>
  )
}
