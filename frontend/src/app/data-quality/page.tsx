'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { Shield, CheckCircle, AlertTriangle, XCircle } from 'lucide-react'

export default function DataQualityPage() {
  const { datasetId } = useDataset()
  const [report, setReport] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!datasetId) return
    setLoading(true)
    api.dataQuality(datasetId)
      .then(setReport)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [datasetId])

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1200 }}>
        <PageHeader
          title="Data Quality Report"
          subtitle="Validation status, field metrics, and provenance for ingested FOCUS dataset"
          actions={<DatasetSelector />}
        />

        {loading && <div className="skeleton" style={{ height: 300, borderRadius: 12 }} />}

        {!loading && report && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 24 }}>
              <div className="metric-card">
                <div className="metric-label">Status</div>
                <div style={{ marginTop: 4 }}>
                  <span className={`badge badge-${report.overall_status?.toLowerCase()}`} style={{ fontSize: 14, padding: '4px 12px' }}>
                    {report.overall_status}
                  </span>
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Total Rows</div>
                <div className="metric-value">{report.total_rows?.toLocaleString()}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Valid Rows</div>
                <div className="metric-value" style={{ color: 'var(--success)' }}>{report.valid_rows?.toLocaleString()}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Duplicate Rows</div>
                <div className="metric-value">{report.duplicate_rows?.toLocaleString()}</div>
              </div>
            </div>

            {report.issues?.length > 0 && (
              <div className="card" style={{ padding: 20, marginBottom: 16, borderColor: 'rgba(239,68,68,0.3)' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--danger)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <XCircle size={15} /> Issues Detected ({report.issues.length})
                </div>
                <ul style={{ paddingLeft: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
                  {report.issues.map((issue: string, i: number) => <li key={i}>{issue}</li>)}
                </ul>
              </div>
            )}

            {report.warnings?.length > 0 && (
              <div className="card" style={{ padding: 20, marginBottom: 24, borderColor: 'rgba(245,158,11,0.3)' }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--warning)', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <AlertTriangle size={15} /> Warnings ({report.warnings.length})
                </div>
                <ul style={{ paddingLeft: 20, fontSize: 13, color: 'var(--text-secondary)' }}>
                  {report.warnings.map((warn: string, i: number) => <li key={i}>{warn}</li>)}
                </ul>
              </div>
            )}
          </>
        )}

        {!loading && !report && (
          <div className="empty-state card" style={{ padding: 64 }}>
            <Shield size={32} />
            <span>No data quality report available for this dataset</span>
          </div>
        )}
      </div>
    </Layout>
  )
}
