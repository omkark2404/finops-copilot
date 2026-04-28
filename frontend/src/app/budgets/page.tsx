'use client'
import { useEffect, useState } from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/format'
import { DollarSign, Plus } from 'lucide-react'

export default function BudgetsPage() {
  const [budgets, setBudgets] = useState<any[]>([])
  const [name, setName] = useState('')
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.budgets().then(setBudgets).catch(console.error)
  }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name || !amount) return
    setLoading(true)
    try {
      await api.createBudget({
        name,
        entity_type: 'total',
        entity_value: 'all',
        period_type: 'monthly',
        period_start: '2024-01-01',
        period_end: '2024-12-31',
        budget_amount: Number(amount),
        currency: 'USD',
      })
      setName('')
      setAmount('')
      api.budgets().then(setBudgets)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Layout>
      <div style={{ padding: '28px 32px', maxWidth: 1000 }}>
        <PageHeader title="Budgets & Variance" subtitle="Track spend against allocated cloud budgets" />

        {/* Create Budget */}
        <div className="card" style={{ padding: 24, marginBottom: 24 }}>
          <div className="section-title" style={{ marginBottom: 16 }}>Create Budget</div>
          <form onSubmit={handleCreate} style={{ display: 'flex', gap: 12, alignItems: 'flex-end' }}>
            <div style={{ flex: 1 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Budget Name</label>
              <input
                id="budget-name"
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="e.g. Monthly Total Cloud Budget"
                required
                style={{ width: '100%' }}
              />
            </div>
            <div style={{ width: 160 }}>
              <label style={{ fontSize: 12, color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>Amount ($)</label>
              <input
                id="budget-amount"
                type="number"
                value={amount}
                onChange={e => setAmount(e.target.value)}
                placeholder="50000"
                required
                style={{ width: '100%' }}
              />
            </div>
            <button id="create-budget-btn" type="submit" disabled={loading} className="btn btn-primary">
              <Plus size={14} /> Create
            </button>
          </form>
        </div>

        {/* Budget List */}
        <div className="card" style={{ padding: 24 }}>
          <div className="section-title" style={{ marginBottom: 16 }}>Configured Budgets ({budgets.length})</div>
          {budgets.length === 0 ? (
            <div className="empty-state" style={{ padding: 32 }}>
              <DollarSign size={24} />
              <span>No budgets configured yet</span>
            </div>
          ) : (
            <table className="table">
              <thead><tr><th>Budget Name</th><th>Amount</th><th>Period</th><th>Currency</th></tr></thead>
              <tbody>
                {budgets.map(b => (
                  <tr key={b.id}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{b.name}</td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{formatCurrency(b.budget_amount)}</td>
                    <td style={{ color: 'var(--text-muted)' }}>{b.period_type}</td>
                    <td>{b.currency}</td>
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
