'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { Settings, Upload, CheckCircle, Database, Trash2, AlertTriangle } from 'lucide-react'

export default function SettingsPage() {
  const [health, setHealth] = useState<any>(null)
  const [datasets, setDatasets] = useState<any[]>([])
  const [datasetName, setDatasetName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  // Delete modal state
  const [deletingDataset, setDeletingDataset] = useState<any | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { datasetId, setDatasetId } = useDataset()

  const refreshDatasets = async () => {
    try {
      const list = await api.listDatasets()
      setDatasets(list)
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    api.health().then(setHealth).catch(console.error)
    refreshDatasets()
  }, [])

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !datasetName) return
    setUploading(true)
    setMsg(null)
    try {
      const res = await api.ingestDataset(file, datasetName)
      const rows = res.row_count ?? '?'
      const status = res.validation_status ?? res.status ?? 'unknown'
      const name = res.dataset_name ?? datasetName
      setMsg(`Dataset "${name}" ingested successfully: ${rows} rows. Status: ${status}`)
      setDatasetName('')
      setFile(null)
      await refreshDatasets()
      if (res.dataset_id) {
        setDatasetId(res.dataset_id)
      }
    } catch (err: any) {
      setMsg(`Error: ${err.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async () => {
    if (!deletingDataset) return
    setDeleting(true)
    try {
      await api.deleteDataset(deletingDataset.id)
      setMsg(`Dataset '${deletingDataset.name}' was permanently deleted.`)
      
      const updatedList = await api.listDatasets()
      setDatasets(updatedList)

      // Reset active selection if deleted dataset was selected
      if (datasetId === deletingDataset.id) {
        if (updatedList.length > 0) {
          setDatasetId(updatedList[0].id)
        } else {
          if (typeof window !== 'undefined') {
            localStorage.removeItem('cs_dataset_id')
          }
          setDatasetId('')
        }
      }
    } catch (err: any) {
      setMsg(`Failed to delete dataset: ${err.message}`)
    } finally {
      setDeleting(false)
      setDeletingDataset(null)
    }
  }

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1000 }}>
        <PageHeader title="Settings & Datasets" subtitle="System configuration and FOCUS billing data management" />

        {/* System Health */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <div className="section-title" style={{ marginBottom: 16 }}>System Health</div>
          {health ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Status</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--success)' }}>{health.status}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Database</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--success)' }}>{health.database}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>LLM Provider</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)' }}>{health.llm_provider}</div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Version</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>v{health.version}</div>
              </div>
            </div>
          ) : <div>Checking system health…</div>}
        </div>

        {/* Upload FOCUS Dataset */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <div className="section-title" style={{ marginBottom: 8 }}>Ingest Real FOCUS Billing Data</div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
            Upload CSV or Parquet files conforming to FOCUS 1.0 / 1.0.1 specifications.
          </p>

          <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Dataset Name</label>
              <input
                id="dataset-name-input"
                type="text"
                value={datasetName}
                onChange={e => setDatasetName(e.target.value)}
                placeholder="e.g. AWS Focus Q1 2024"
                required
                style={{ width: '100%', maxWidth: 400 }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Billing File (CSV / Parquet)</label>
              <input
                id="file-input"
                type="file"
                accept=".csv,.parquet,.pq"
                onChange={e => setFile(e.target.files?.[0] || null)}
                required
              />
            </div>
            <button id="upload-btn" type="submit" disabled={uploading} className="btn btn-primary" style={{ width: 'fit-content' }}>
              <Upload size={14} />
              {uploading ? 'Ingesting…' : 'Ingest Dataset'}
            </button>
          </form>

          {msg && (
            <div style={{ marginTop: 16, padding: 12, background: 'var(--bg-elevated)', borderRadius: 8, fontSize: 13 }}>
              {msg}
            </div>
          )}
        </div>

        {/* Installed Datasets */}
        <div className="card" style={{ padding: 24 }}>
          <div className="section-title" style={{ marginBottom: 16 }}>Ingested Datasets ({datasets.length})</div>
          {datasets.length === 0 ? (
            <div className="empty-state" style={{ padding: 32 }}>
              <Database size={24} />
              <span>No datasets ingested yet</span>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Rows</th>
                  <th>FOCUS Version</th>
                  <th>Status</th>
                  <th>Currency</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {datasets.map(d => (
                  <tr key={d.id}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{d.name}</td>
                    <td>{d.row_count?.toLocaleString()}</td>
                    <td>{d.focus_version}</td>
                    <td><span className={`badge badge-${d.validation_status?.toLowerCase()}`}>{d.validation_status}</span></td>
                    <td>{d.currency}</td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        className="btn btn-danger"
                        style={{ fontSize: 12, padding: '4px 8px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.2)' }}
                        onClick={() => setDeletingDataset(d)}
                      >
                        <Trash2 size={12} style={{ marginRight: 4 }} />
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Confirmation Modal */}
        {deletingDataset && (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.6)', backdropFilter: 'blur(4px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
          }}>
            <div className="card" style={{ maxWidth: 460, width: '100%', padding: 24, borderRadius: 12, border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: '#ef4444', marginBottom: 16 }}>
                <AlertTriangle size={24} />
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Delete dataset &apos;{deletingDataset.name}&apos;?</h3>
              </div>
              <p style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.5, marginBottom: 20 }}>
                This will permanently remove:
              </p>
              <ul style={{ fontSize: 13, color: 'var(--text-muted)', paddingLeft: 20, marginBottom: 24, display: 'flex', flexDirection: 'column', gap: 6 }}>
                <li>Dataset metadata from database</li>
                <li>Uploaded raw billing file and Parquet analytics storage</li>
                <li>DuckDB analytical tables</li>
                <li>Associated anomalies, forecasts, recommendations, and agent pipeline runs</li>
              </ul>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                <button
                  className="btn"
                  onClick={() => setDeletingDataset(null)}
                  disabled={deleting}
                  style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)' }}
                >
                  Cancel
                </button>
                <button
                  className="btn"
                  onClick={handleDelete}
                  disabled={deleting}
                  style={{ background: '#ef4444', color: '#ffffff' }}
                >
                  {deleting ? 'Deleting…' : 'Permanently Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  )
}
