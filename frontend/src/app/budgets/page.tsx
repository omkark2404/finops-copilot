'use client'
import {useEffect,useState} from 'react'
import Layout from '@/components/Layout'
import PageHeader from '@/components/PageHeader'
import {api} from '@/lib/api'
import {formatCurrency} from '@/lib/format'
import type {Budget} from '@/lib/types'
export default function BudgetsPage(){
  const today=new Date().toISOString().slice(0,10)
  const [budgets,setBudgets]=useState<Budget[]>([])
  const [busy,setBusy]=useState(false);const [error,setError]=useState<string|null>(null)
  useEffect(()=>{let active=true;api.budgets().then(x=>{if(active)setBudgets(x)}).catch(e=>{if(active)setError(e.message)});return ()=>{active=false}},[])
  async function create(event:React.FormEvent<HTMLFormElement>){
    event.preventDefault();const element=event.currentTarget;const form=new FormData(element)
    setBusy(true);setError(null)
    try{
      await api.createBudget({name:String(form.get('name')).trim(),budget_amount:Number(form.get('amount')),
        currency:String(form.get('currency')).toUpperCase(),period_start:String(form.get('start')),period_end:String(form.get('end')),
        entity_type:'total',entity_value:'all',period_type:'custom'})
      setBudgets(await api.budgets());element.reset()
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  return <Layout><div className="page-content"><PageHeader title="Budgets and observed variance" subtitle="Observed differences use exactly one matching-currency dataset to avoid overlapping exports; they do not certify complete billing coverage."/>
    {error&&<p role="alert" className="request-error">{error}</p>}
    <form onSubmit={create} className="card budget-form">
      <label htmlFor="budget-name">Budget name</label><input id="budget-name" name="name" required maxLength={120}/>
      <label htmlFor="budget-amount">Budget amount</label><input id="budget-amount" name="amount" type="number" min=".01" step=".01" required/>
      <label htmlFor="budget-currency">Billing currency (three letters)</label><input id="budget-currency" name="currency" pattern="[A-Za-z]{3}" maxLength={3} placeholder="Match your billing file" required/>
      <label htmlFor="budget-start">Period start</label><input id="budget-start" name="start" type="date" defaultValue={today} required/>
      <label htmlFor="budget-end">Period end</label><input id="budget-end" name="end" type="date" defaultValue={today} required/>
      <button className="btn btn-primary" disabled={busy}>Create budget</button>
    </form>
    <div className="table-scroll"><table className="table"><thead><tr><th>Name</th><th>Budget</th><th>Observed spend</th><th>Observed difference</th><th>Coverage</th></tr></thead>
      <tbody>{budgets.map(b=><tr key={b.id}><td>{b.name}</td><td>{formatCurrency(b.budget_amount,b.currency)}</td><td>{formatCurrency(b.actual_spend,b.currency)}</td><td>{formatCurrency(b.variance,b.currency)}</td><td>{b.note||b.period_start.slice(0,10)+' – '+b.period_end.slice(0,10)}</td></tr>)}</tbody></table></div>
  </div></Layout>
}
