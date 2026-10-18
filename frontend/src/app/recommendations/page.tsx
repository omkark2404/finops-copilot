'use client'
import {useEffect,useRef,useState} from 'react'
import Link from 'next/link'
import Layout from '@/components/Layout'
import DatasetSelector from '@/components/DatasetSelector'
import PageHeader from '@/components/PageHeader'
import {api} from '@/lib/api'
import {getSelectedDatasetId,useDataset} from '@/lib/useDataset'
import {formatCurrency} from '@/lib/format'
import type {Recommendation,Scenario} from '@/lib/types'
export default function RecommendationsPage(){
  const {datasetId}=useDataset()
  const [items,setItems]=useState<Recommendation[]>([])
  const [error,setError]=useState<string|null>(null)
  const [busy,setBusy]=useState<string|null>(null)
  const [scenario,setScenario]=useState<Scenario|null>(null)
  const scope=useRef<{id:string|null;active:boolean}|null>(null)
  const [loading,setLoading]=useState(false)
  useEffect(()=>{
    const request={id:datasetId,active:true}
    scope.current=request
    setItems([]);setError(null);setScenario(null);setBusy(null);setLoading(Boolean(datasetId))
    const current=()=>request.active&&scope.current===request&&getSelectedDatasetId()===request.id
    if(datasetId)api.recommendations(datasetId)
      .then(x=>{if(current())setItems(x)})
      .catch(e=>{if(current())setError(e.message)})
      .finally(()=>{if(current())setLoading(false)})
    return ()=>{request.active=false}
  },[datasetId])
  async function decide(id:string,decision:'approved'|'rejected'){
    const request=scope.current
    if(!request?.active||!request.id||request.id!==getSelectedDatasetId())return
    const current=()=>request.active&&scope.current===request&&getSelectedDatasetId()===request.id
    setBusy(id);setError(null)
    try{
      await api.decide(id,decision)
      if(!current())return
      const updated=await api.recommendations(request.id)
      if(current())setItems(updated)
    }catch(e){if(current())setError((e as Error).message)}
    finally{if(current())setBusy(null)}
  }
  async function simulate(id:string,percent:number){
    const request=scope.current
    if(!request?.active||!request.id||request.id!==getSelectedDatasetId())return
    const current=()=>request.active&&scope.current===request&&getSelectedDatasetId()===request.id
    if(!(percent>0&&percent<100)){setError('Enter a reduction strictly between 0 and 100%.');return}
    setBusy(id);setError(null)
    try{const result=await api.simulate(id,percent);if(current())setScenario(result)}
    catch(e){if(current())setError((e as Error).message)}
    finally{if(current())setBusy(null)}
  }
  return <Layout><div className="page-content">
    <PageHeader title="Investigation recommendations" subtitle="Saved billing investigations. Approval records human review and never changes cloud resources." actions={<DatasetSelector/>}/>
    {error&&<p role="alert" className="request-error">{error}</p>}
    {loading&&<p role="status">Loading recommendations…</p>}
    {!loading&&!items.length&&!error&&<div className="card empty-state">No saved recommendations. <Link href="/agents">Run the analysis workflow</Link></div>}
    {items.map(item=><section key={item.id} className="card recommendation">
      <h2>{item.title}</h2><p>{item.description}</p><p>Status: <strong>{item.status}</strong></p>
      <ul>{item.evidence.map((e,i)=><li key={i}>{e}</li>)}</ul>
      <div className="actions"><button disabled={busy!==null} className="btn btn-primary" onClick={()=>decide(item.id,'approved')}>Record approval</button>
      <button disabled={busy!==null} className="btn btn-ghost" onClick={()=>decide(item.id,'rejected')}>Record rejection</button></div>
      <details><summary>Hypothetical whole-dataset scenario</summary>
        <p>This applies your assumed reduction to the entire observed dataset. It is not a measured or recommendation-specific achievable saving. Scenarios overlap and must not be added together.</p>
        <form onSubmit={event=>{event.preventDefault();const form=new FormData(event.currentTarget);void simulate(item.id,Number(form.get("reduction_pct")))}}>
        <label htmlFor={'pct-'+item.id}>Assumed usage reduction (%)</label>
        <input id={'pct-'+item.id} type="number" min=".01" max="99.99" step=".01" name="reduction_pct" required/>
        <button className="btn btn-ghost" type="submit" disabled={busy!==null}>Simulate scenario</button></form>
      </details>
    </section>)}
    {scenario&&<section className="card recommendation" role="status"><h2>Hypothetical estimate</h2>
      <p>{scenario.scope}</p><p>{scenario.period_start} – {scenario.period_end}</p>
      <p>Baseline {formatCurrency(scenario.current_cost,scenario.currency)} → projected {formatCurrency(scenario.projected_cost,scenario.currency)}</p>
      <p>Estimated difference: {formatCurrency(scenario.estimated_savings,scenario.currency)}</p>
      <ul>{scenario.assumptions.map((a,i)=><li key={i}>{a}</li>)}</ul></section>}
  </div></Layout>
}
