'use client'
import { useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import DatasetSelector from '@/components/DatasetSelector'
import { api } from '@/lib/api'
import { useDataset } from '@/lib/useDataset'
import { Bot, Play, CheckCircle, XCircle, Loader2, ChevronDown, ChevronUp } from 'lucide-react'

const AGENT_LABELS: Record<string, string> = {
  data_quality: '1. Data Quality',
  cost_attribution: '2. Cost Attribution',
  anomaly_investigation: '3. Anomaly Investigation',
  opportunity: '4. Opportunity',
  optimization: '5. Optimization',
  savings: '6. Savings',
  critic: '7. Critic / Validation',
}

export default function AgentsPage() {
  const { datasetId } = useDataset()
  const [result, setResult] = useState<any>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const runPipeline = async () => {
    if (!datasetId) return
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const res = await api.runPipeline(datasetId)
      setResult(res)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const agentRuns = result?.agent_runs || []
  const decision = result?.final_decision

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1200 }}>
        <PageHeader
          title="Agent Pipeline"
          subtitle="7-agent dependent analysis pipeline: Data Quality → Attribution → Anomaly → Opportunity → Optimization → Savings → Critic"
          actions={
            <div style={{ display: 'flex', gap: 8 }}>
              <DatasetSelector />
              <button
                id="run-pipeline-btn"
                className="btn btn-primary"
                onClick={runPipeline}
                disabled={running || !datasetId}
              >
                {running ? <Loader2 size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={13} />}
                {running ? 'Running Pipeline…' : 'Run Pipeline'}
              </button>
            </div>
          }
        />

        {/* Pipeline visualization */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <div className="section-title" style={{ marginBottom: 20 }}>Agent Dependency Graph</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 0, overflowX: 'auto', paddingBottom: 8 }}>
            {Object.entries(AGENT_LABELS).map(([key, label], i, arr) => {
              const run = agentRuns.find((r: any) => r.agent_type === key)
              const status = run?.status || (running ? 'queued' : 'idle')
              const color = status === 'succeeded' ? 'var(--success)'
                : status === 'failed' ? 'var(--danger)'
                : status === 'running' ? 'var(--accent)'
                : 'var(--border)'
              return (
                <div key={key} style={{ display: 'flex', alignItems: 'center' }}>
                  <div
                    onClick={() => setExpanded(expanded === key ? null : key)}
                    style={{
                      padding: '12px 16px',
                      borderRadius: 10,
                      border: `1px solid ${color}`,
                      background: status === 'succeeded' ? 'rgba(16,185,129,0.08)'
                        : status === 'failed' ? 'rgba(239,68,68,0.08)'
                        : 'var(--bg-elevated)',
                      cursor: 'pointer',
                      minWidth: 130,
                      transition: 'all 0.2s',
                    }}
                  >
                    <div style={{ fontSize: 11, fontWeight: 700, color, marginBottom: 4 }}>
                      {status === 'succeeded' ? '✓' : status === 'failed' ? '✗' : status === 'running' ? '⟳' : '○'}
                      {' '}{label.split('. ')[0]}.
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label.split('. ')[1]}</div>
                    {run?.confidence && (
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>
                        conf: {(run.confidence * 100).toFixed(0)}%
                      </div>
                    )}
                  </div>
                  {i < arr.length - 1 && (
                    <div style={{ width: 24, height: 1, background: 'var(--border)', flexShrink: 0 }} />
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Agent Details */}
        {agentRuns.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24 }}>
            {agentRuns.map((run: any) => (
              <div key={run.id} className="card" style={{ overflow: 'hidden' }}>
                <div
                  onClick={() => setExpanded(expanded === run.id ? null : run.id)}
                  style={{ padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 12, cursor: 'pointer' }}
                >
                  {run.status === 'succeeded' ? <CheckCircle size={16} style={{ color: 'var(--success)' }} />
                    : run.status === 'failed' ? <XCircle size={16} style={{ color: 'var(--danger)' }} />
                    : <Loader2 size={16} style={{ color: 'var(--accent)', animation: 'spin 1s linear infinite' }} />}
                  <div style={{ flex: 1 }}>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontSize: 13 }}>
                      {AGENT_LABELS[run.agent_type] || run.agent_type}
                    </span>
                    {run.duration_seconds && (
                      <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 12 }}>
                        {run.duration_seconds.toFixed(2)}s
                      </span>
                    )}
                  </div>
                  {run.confidence && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>conf: {(run.confidence * 100).toFixed(0)}%</span>}
                  {expanded === run.id ? <ChevronUp size={14} style={{ color: 'var(--text-muted)' }} /> : <ChevronDown size={14} style={{ color: 'var(--text-muted)' }} />}
                </div>
                {expanded === run.id && (
                  <div style={{ padding: '0 20px 16px', borderTop: '1px solid var(--border)' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 12 }}>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Input</div>
                        <pre style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-primary)', padding: 12, borderRadius: 6, overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(run.input_summary, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Output</div>
                        <pre style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-primary)', padding: 12, borderRadius: 6, overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(run.output_summary, null, 2)}
                        </pre>
                      </div>
                    </div>
                    {run.output_summary?.explanation && (
                      <div style={{ marginTop: 12 }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase' }}>LLM Explanation</div>
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', background: 'rgba(99,102,241,0.06)', padding: 12, borderRadius: 6, lineHeight: 1.6 }}>
                          {run.output_summary.explanation}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Final Decision */}
        {decision && (
          <div className="card" style={{ padding: 24, border: `1px solid ${decision.decision === 'APPROVE' ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}` }}>
            <div className="section-title" style={{ marginBottom: 16 }}>Final Decision</div>
            <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <span className={`badge badge-${decision.decision === 'APPROVE' ? 'pass' : decision.decision === 'REJECT' ? 'fail' : 'warn'}`} style={{ fontSize: 13, padding: '6px 14px' }}>
                {decision.decision}
              </span>
              <div>
                <p style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 8 }}>{decision.rationale}</p>
                <p style={{ fontSize: 12, color: 'var(--text-muted)' }}>Confidence: {(decision.confidence * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div style={{ padding: 16, background: 'var(--danger-muted)', borderRadius: 8, color: '#f87171', fontSize: 13 }}>
            Error: {error}
          </div>
        )}

        {!result && !running && !error && (
          <div className="empty-state card" style={{ padding: 64 }}>
            <Bot size={40} style={{ color: 'var(--text-muted)' }} />
            <h3 style={{ color: 'var(--text-primary)', fontSize: 16 }}>Ready to run agent pipeline</h3>
            <p style={{ fontSize: 13 }}>Select a dataset and click "Run Pipeline" to execute the 7-agent analysis.</p>
          </div>
        )}
      </div>
    </Layout>
  )
}
