'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { formatCurrency, formatPct } from '@/lib/format'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { BarChart2 } from 'lucide-react'

export default function ForecastsPage() {
  const { datasetId } = useDataset()
  const [horizon, setHorizon] = useState(30)
  const [forecast, setForecast] = useState<any>(null)
  const [trend, setTrend] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    Promise.all([
      api.forecasts(datasetId, horizon),
      api.spendTrend(datasetId, 'daily'),
    ]).then(([f, t]) => { setForecast(f); setTrend(t) })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [datasetId, horizon])

  const trendData = trend?.data_points?.slice(-30) || []
  const points = forecast?.points || []

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1400 }}>
        <PageHeader
          title="Spend Forecast"
          subtitle="Machine learning forecasting with temporal split validation"
          actions={<DatasetSelector />}
        />

        <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          <div className="input-group">
            <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Horizon:</label>
            <select id="horizon-select" value={horizon} onChange={e => setHorizon(Number(e.target.value))}>
              <option value={7}>7 Days</option>
              <option value={14}>14 Days</option>
              <option value={30}>30 Days</option>
              <option value={60}>60 Days</option>
              <option value={90}>90 Days</option>
            </select>
          </div>
        </div>

        {forecast && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
            <div className="metric-card">
              <div className="metric-label">Model Method</div>
              <div className="metric-value" style={{ fontSize: 20 }}>{forecast.method}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">WAPE Error</div>
              <div className="metric-value" style={{ fontSize: 20 }}>{formatPct((forecast.metrics?.wape || 0) * 100)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">MAE</div>
              <div className="metric-value" style={{ fontSize: 20 }}>{formatCurrency(forecast.metrics?.mae)}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">RMSE</div>
              <div className="metric-value" style={{ fontSize: 20 }}>{formatCurrency(forecast.metrics?.rmse)}</div>
            </div>
          </div>
        )}

        <div className="card" style={{ padding: 24 }}>
          {loading && <div className="skeleton" style={{ height: 300, borderRadius: 8 }} />}
          {!loading && points.length > 0 && (
            <ResponsiveContainer width="100%" height={320}>
              <AreaChart data={[...trendData, ...points.map((p: any) => ({ ...p, is_forecast: true }))]}>
                <defs>
                  <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradFc" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={d => d?.slice(5)} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                  formatter={(v: any) => [formatCurrency(Number(v)), 'Cost']}
                />
                <Area type="monotone" dataKey="billed_cost" stroke="#6366f1" fill="url(#gradActual)" strokeWidth={2} name="Historical" />
                <Area type="monotone" dataKey="predicted_cost" stroke="#8b5cf6" fill="url(#gradFc)" strokeWidth={2} strokeDasharray="4 2" name="Forecast" />
              </AreaChart>
            </ResponsiveContainer>
          )}
          {!loading && points.length === 0 && (
            <div className="empty-state" style={{ padding: 64 }}>
              <BarChart2 size={32} />
              <span>No forecast available</span>
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
