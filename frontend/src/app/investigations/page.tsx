'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { Search, AlertTriangle, ArrowRight } from 'lucide-react'

export default function InvestigationsPage() {
  const { datasetId } = useDataset()
  const [anomalies, setAnomalies] = useState<any>(null)

  useEffect(() => {
    if (!datasetId) return
    api.anomalies(datasetId).then(setAnomalies).catch(console.error)
  }, [datasetId])

  const anomalyList = anomalies?.anomalies || []

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1200 }}>
        <PageHeader
          title="Investigation Workspace"
          subtitle="Flagship workflow: What happened? Why? What changed? Evidence? Recommended Actions?"
          actions={<DatasetSelector />}
        />

        {anomalyList.length === 0 ? (
          <div className="empty-state card" style={{ padding: 64 }}>
            <Search size={32} />
            <span>Select a dataset to begin investigation</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {anomalyList.slice(0, 5).map((a: any) => (
              <div key={a.id} className="card" style={{ padding: 24 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                  <div>
                    <span className={`badge badge-${a.severity}`} style={{ marginBottom: 8 }}>
                      {a.severity} Severity Spike
                    </span>
                    <h3 style={{ fontSize: 16, color: 'var(--text-primary)', fontWeight: 600 }}>
                      {a.entity_value} ({a.entity_type}) cost spike on {a.detected_at?.slice(0, 10)}
                    </h3>
                  </div>
                  <a href="/agents" className="btn btn-ghost" style={{ height: 'fit-content' }}>
                    Run Agent Investigation <ArrowRight size={13} />
                  </a>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, background: 'var(--bg-elevated)', padding: 16, borderRadius: 8, marginBottom: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Actual Cost</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--danger)' }}>${a.actual_cost?.toLocaleString()}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Expected Cost</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>${a.expected_cost?.toLocaleString()}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Deviation</div>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--danger)' }}>+{a.deviation_pct?.toFixed(1)}%</div>
                  </div>
                </div>

                <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  <strong>Detection Evidence:</strong>
                  <ul style={{ paddingLeft: 16, marginTop: 4 }}>
                    {a.supporting_evidence?.map((e: string, i: number) => <li key={i}>{e}</li>)}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
