'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { formatCurrency } from '@/lib/format'
import { AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react'

export default function AnomaliesPage() {
  const { datasetId } = useDataset()
  const [report, setReport] = useState<any>(null)
  const [entityType, setEntityType] = useState('service')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    api.anomalies(datasetId, entityType)
      .then(setReport)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [datasetId, entityType])

  const anomalies = report?.anomalies || []

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1400 }}>
        <PageHeader
          title="Anomalies"
          subtitle="Statistically detected cost anomalies across your cloud footprint"
          actions={<DatasetSelector />}
        />

        {/* Summary Cards */}
        {report && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
            {[{ label: 'Total', val: report.total_anomalies, color: 'var(--text-primary)' },
              { label: 'Critical', val: report.critical_count, color: 'var(--danger)' },
              { label: 'High', val: report.high_count, color: 'var(--warning)' },
              { label: 'Period', val: `${report.period_start?.slice(0,10)} – ${report.period_end?.slice(0,10)}`, color: 'var(--text-muted)' },
            ].map(({ label, val, color }) => (
              <div key={label} className="metric-card">
                <div className="metric-label">{label}</div>
                <div className="metric-value" style={{ fontSize: 24, color }}>{val}</div>
              </div>
            ))}
          </div>
        )}

        {/* Controls */}
        <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
          <div className="input-group">
            <label style={{ fontSize: 12, color: 'var(--text-muted)' }}>Group by:</label>
            <select id="entity-type-select" value={entityType} onChange={e => setEntityType(e.target.value)}>
              {['service', 'provider', 'account', 'region'].map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        {/* Anomaly Table */}
        <div className="card">
          {loading && <div className="skeleton" style={{ height: 300, margin: 16, borderRadius: 8 }} />}
          {!loading && anomalies.length === 0 && (
            <div className="empty-state" style={{ padding: 64 }}>
              <AlertTriangle size={32} />
              <h3>No anomalies detected</h3>
              <p style={{ fontSize: 13 }}>The detection algorithms found no statistically significant cost anomalies.</p>
            </div>
          )}
          {!loading && anomalies.length > 0 && (
            <table className="table">
              <thead><tr>
                <th>Entity</th><th>Type</th><th>Date</th>
                <th>Actual</th><th>Expected</th><th>Deviation</th>
                <th>Severity</th><th>Method</th><th>Confidence</th>
              </tr></thead>
              <tbody>
                {anomalies.map((a: any) => (
                  <tr key={a.id}>
                    <td>
                      <div style={{ color: 'var(--text-primary)', fontWeight: 500, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {a.entity_value}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.entity_type}</div>
                    </td>
                    <td><span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.entity_type}</span></td>
                    <td style={{ fontSize: 12 }}>{a.detected_at?.slice(0, 10)}</td>
                    <td>{formatCurrency(a.actual_cost)}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{formatCurrency(a.expected_cost)}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: a.deviation_pct > 0 ? 'var(--danger)' : 'var(--success)' }}>
                        {a.deviation_pct > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                        {a.deviation_pct > 0 ? '+' : ''}{a.deviation_pct?.toFixed(1)}%
                      </div>
                    </td>
                    <td><span className={`badge badge-${a.severity}`}>{a.severity}</span></td>
                    <td style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.method?.replace(/_/g, ' ')}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{(a.confidence * 100).toFixed(0)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Layout>
  )
}
