'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { formatCurrency } from '@/lib/format'
import { Lightbulb, CheckCircle2, XCircle } from 'lucide-react'

export default function RecommendationsPage() {
  const { datasetId } = useDataset()
  const [opportunities, setOpportunities] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    api.opportunities(datasetId)
      .then(setOpportunities)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [datasetId])

  const opps = opportunities?.opportunities || []

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1200 }}>
        <PageHeader
          title="Optimization Recommendations"
          subtitle="Ranked actions to optimize cloud spend with auditable evidence"
          actions={<DatasetSelector />}
        />

        {opportunities && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 24 }}>
            <div className="metric-card">
              <div className="metric-label">Total Opportunities</div>
              <div className="metric-value">{opportunities.total_opportunities}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Potential Est. Savings</div>
              <div className="metric-value" style={{ color: 'var(--success)' }}>
                {formatCurrency(opportunities.total_potential_savings)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Status</div>
              <div className="metric-value" style={{ fontSize: 18 }}>Human Review Required</div>
            </div>
          </div>
        )}

        {loading && <div className="skeleton" style={{ height: 300, borderRadius: 12 }} />}

        {!loading && opps.length === 0 && (
          <div className="empty-state card" style={{ padding: 64 }}>
            <Lightbulb size={32} />
            <span>No recommendations found</span>
          </div>
        )}

        {!loading && opps.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {opps.map((o: any, i: number) => (
              <div key={o.id} className="card" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Rank #{i + 1} • {o.opportunity_type?.replace(/_/g, ' ')}
                    </div>
                    <h3 style={{ fontSize: 16, color: 'var(--text-primary)', fontWeight: 600, marginTop: 4 }}>
                      Investigate {o.entity}
                    </h3>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 18, color: 'var(--success)', fontWeight: 700 }}>
                      {formatCurrency(o.potential_savings_estimate)}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Estimated Savings</div>
                  </div>
                </div>

                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16, lineHeight: 1.6 }}>
                  {o.description}
                </p>

                {o.evidence?.length > 0 && (
                  <div style={{ background: 'var(--bg-elevated)', padding: 12, borderRadius: 8, marginBottom: 16 }}>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
                      Supporting Evidence
                    </div>
                    <ul style={{ paddingLeft: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
                      {o.evidence.map((e: string, idx: number) => (
                        <li key={idx} style={{ marginBottom: 2 }}>{e}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn btn-ghost">Simulate Scenario</button>
                  <button className="btn btn-primary">Approve Recommendation</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
