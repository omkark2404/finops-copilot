'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { Database } from 'lucide-react'

export default function DatasetSelector() {
  const [datasets, setDatasets] = useState<any[]>([])
  const { datasetId, setDatasetId } = useDataset()

  useEffect(() => {
    api.listDatasets()
      .then(ds => {
        setDatasets(ds)
        if (ds.length > 0) {
          const exists = ds.some(d => d.id === datasetId)
          if (!datasetId || !exists) {
            setDatasetId(ds[0].id)
          }
        } else {
          setDatasetId('')
        }
      })
      .catch(() => {})
  }, [datasetId])

  if (!datasets.length) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <Database size={13} style={{ color: 'var(--text-muted)' }} />
      <select
        id="dataset-selector"
        value={datasetId || ''}
        onChange={e => setDatasetId(e.target.value)}
        style={{ fontSize: 12, padding: '4px 8px', minWidth: 180 }}
      >
        {datasets.map(d => (
          <option key={d.id} value={d.id}>
            {d.name} ({d.row_count?.toLocaleString() || 0} rows)
          </option>
        ))}
      </select>
    </div>
  )
}
