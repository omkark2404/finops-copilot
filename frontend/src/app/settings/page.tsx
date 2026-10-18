'use client'
import type {DatasetInfo,Health} from '@/lib/types'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { Upload, Database, Trash2 } from 'lucide-react'

export default function SettingsPage() {
  const [health, setHealth] = useState<Health | null>(null)
  const [datasets, setDatasets] = useState<DatasetInfo[]>([])
  const [uploading, setUploading] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  // Inline deletion confirmation
  const [deletingDataset, setDeletingDataset] = useState<DatasetInfo | null>(null)
  const [deleting, setDeleting] = useState(false)

  const { datasetId, setDatasetId } = useDataset()

  const refreshDatasets = async () => {
    try {
      const list = await api.listDatasets()
      setDatasets(list)
    } catch (e) {
      setMsg(`Could not load datasets: ${(e as Error).message}`)
    }
  }

  useEffect(() => {
    api.health().then(setHealth).catch(e => setMsg(e.message))
    refreshDatasets()
  }, [])

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    const form=e.currentTarget as HTMLFormElement
    const fields=new FormData(form)
    const file=fields.get('file') as File
    const datasetName=String(fields.get('dataset_name') || '').trim()
    if (!file || !file.size || !datasetName) return
    if (file.size > 20_000_000) {setMsg("Upload limit: 20 MB");return}
    setUploading(true)
    setMsg(null)
    try {
      const res = await api.ingestDataset(file, datasetName)
      const rows = res.row_count ?? '?'
      const status = res.validation_status ?? res.status ?? 'unknown'
      const name = res.dataset_name ?? datasetName
      setMsg(`Dataset "${name}" ingested successfully: ${rows} rows. Status: ${status}`)
      form.reset()
      await refreshDatasets()
      if (res.dataset_id) {
        setDatasetId(res.dataset_id)
      }
    } catch (err: unknown) { setMsg(`Error: ${(err as Error).message}`)
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

          setDatasetId('')
        }
      }
    } catch (err: unknown) { setMsg(`Failed to delete dataset: ${(err as Error).message}`)
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
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Status</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--success)' }}>{health.status}</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Database</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--success)' }}>{health.database}</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>LLM Provider</div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--accent)' }}>{health.llm_provider}</div>
              </div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Version</div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>v{health.version}</div>
              </div>
            </div>
          ) : <div>Checking system health…</div>}
        </div>

        {/* Upload FOCUS Dataset */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <div className="section-title" style={{ marginBottom: 8 }}>Ingest Billing Data</div>
          <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 20 }}>
            Upload CSV or Parquet files using the supported FOCUS-inspired column subset. This is not a full conformance certification.
          </p>

          <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <label htmlFor="dataset-name-input" style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Dataset Name</label>
              <input
                id="dataset-name-input"
                type="text"
                name="dataset_name"
                placeholder="e.g. AWS Focus Q1 2024"
                required
                style={{ width: '100%', maxWidth: 400 }}
              />
            </div>
            <div>
              <label htmlFor="file-input" style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Billing File (CSV / Parquet)</label>
              <input
                id="file-input"
                type="file"
                accept=".csv,.parquet,.pq"
                name="file"
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

        {deletingDataset && <section className="card recommendation" aria-label="Confirm dataset deletion">
          <h2>Delete {deletingDataset.name}?</h2><p>This permanently removes this dataset and its saved analysis. This cannot be undone.</p>
          <div className="actions"><button className="btn btn-ghost" onClick={() => setDeletingDataset(null)} disabled={deleting}>Cancel</button>
          <button className="btn btn-danger" onClick={handleDelete} disabled={deleting}>{deleting ? 'Deleting…' : 'Permanently delete'}</button></div>
        </section>}
      </div>
    </Layout>
  )
}
