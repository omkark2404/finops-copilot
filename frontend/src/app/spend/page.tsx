'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { formatCurrency } from '@/lib/format'
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell
} from 'recharts'

const DIMS = ['service', 'provider', 'account', 'region', 'category']
const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#818cf8', '#4f46e5', '#7c3aed', '#9333ea']

export default function SpendPage() {
  const { datasetId } = useDataset()
  const [dimension, setDimension] = useState('service')
  const [granularity, setGranularity] = useState('daily')
  const [trend, setTrend] = useState<any>(null)
  const [breakdown, setBreakdown] = useState<any[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    Promise.all([
      api.spendTrend(datasetId, granularity),
      api.spendBreakdown(datasetId, dimension, undefined, undefined, 15),
      api.spendSummary(datasetId),
    ]).then(([t, b, s]) => { setTrend(t); setBreakdown(b); setSummary(s) })
      .finally(() => setLoading(false))
  }, [datasetId, granularity, dimension])

  const trendData = trend?.data_points || []
  const breakdownData = breakdown.map(b => ({ name: b.value, cost: b.billed_cost }))

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1400 }}>
        <PageHeader
          title="Spend Explorer"
          subtitle="Analyze cloud spend across dimensions and time periods"
          actions={<DatasetSelector />}
        />

        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          <div className="input-group">
            <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Granularity:</label>
            <select id="granularity-select" value={granularity} onChange={e => setGranularity(e.target.value)}>
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
          <div className="input-group">
            <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Breakdown by:</label>
            <select id="dimension-select" value={dimension} onChange={e => setDimension(e.target.value)}>
              {DIMS.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
        </div>

        {loading && <div className="skeleton" style={{ height: 300, borderRadius: 12 }} />}

        {!loading && (
          <>
            {/* Trend Chart */}
            <div className="card" style={{ padding: 24, marginBottom: 16 }}>
              <div className="section-header">
                <div className="section-title">Spend Trend ({granularity})</div>
                {summary && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Total: <strong style={{ color: 'var(--text-primary)' }}>{formatCurrency(summary.total_billed_cost)}</strong></span>}
              </div>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trendData}>
                  <defs>
                    <linearGradient id="grad1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={d => d?.slice(5)} />
                  <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    formatter={(v: any) => [formatCurrency(Number(v)), 'Billed Cost']}
                  />
                  <Area type="monotone" dataKey="billed_cost" stroke="#6366f1" fill="url(#grad1)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Breakdown */}
            <div className="card" style={{ padding: 24 }}>
              <div className="section-header">
                <div className="section-title">By {dimension}</div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={breakdownData} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} tickFormatter={v => `$${(v / 1000).toFixed(0)}K`} />
                    <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text-muted)', fontSize: 10 }} width={120} />
                    <Tooltip
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                      formatter={(v: any) => [formatCurrency(Number(v)), 'Cost']}
                    />
                    <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                      {breakdownData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <table className="table">
                  <thead><tr><th>{dimension}</th><th>Cost</th><th>Share</th></tr></thead>
                  <tbody>
                    {breakdownData.map((item, i) => {
                      const total = breakdownData.reduce((s, d) => s + d.cost, 0)
                      return (
                        <tr key={i}>
                          <td style={{ color: 'var(--text-primary)' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ width: 8, height: 8, borderRadius: '50%', background: COLORS[i % COLORS.length], flexShrink: 0 }} />
                              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>{item.name}</span>
                            </div>
                          </td>
                          <td>{formatCurrency(item.cost)}</td>
                          <td style={{ color: 'var(--text-muted)' }}>{total > 0 ? (item.cost / total * 100).toFixed(1) : 0}%</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </Layout>
  )
}
