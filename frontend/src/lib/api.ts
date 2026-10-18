import axios,{type AxiosRequestConfig} from 'axios'
import type {DatasetInfo,SpendSummary,SpendTrend,Breakdown,AnomalyReport,OpportunityReport,Forecast,QualityReport,Health,Pipeline,Recommendation,Budget,BudgetInput,Scenario} from './types'

// These requests render errors in their dataset-scoped component. Never bypass 401 handling.
const localErrors:AxiosRequestConfig&{localErrors:boolean}={localErrors:true}
const client=axios.create({
  baseURL:process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  withCredentials:true,
  timeout:120000,
  headers:{'X-FinOps-Client':'1'},
})
client.interceptors.response.use(response=>response,error=>{
  const detail=error.response?.data?.detail
  const message=typeof detail==='string' ? detail : error.message || 'Request failed'
  if(typeof window!=='undefined'){
    if(error.response?.status===401 && !window.location.pathname.startsWith('/login')){
      window.dispatchEvent(new Event('finops:unauthorized'))
    }else if(!error.config?.localErrors){
      window.dispatchEvent(new CustomEvent('finops:error',{detail:message}))
    }
  }
  return Promise.reject(new Error(message))
})
export const api={
  login:async(email:string,password:string)=> (await client.post<{access_token:string}>('/auth/login',{email,password})).data,
  me:async()=> (await client.get<{id:string;email:string;role:string}>('/auth/me')).data,
  logout:async()=> (await client.post('/auth/logout')).data,
  listDatasets:async()=> (await client.get<DatasetInfo[]>('/datasets')).data,
  ingestDataset:async(file:File,name:string)=>{
    const data=new FormData();data.append('file',file);data.append('dataset_name',name)
    return (await client.post<{dataset_id:string;dataset_name:string;row_count:number;validation_status:string;status:string}>('/datasets/ingest',data)).data
  },
  deleteDataset:async(id:string)=> (await client.delete('/datasets/'+encodeURIComponent(id))).data,
  spendSummary:async(id:string)=> (await client.get<SpendSummary>('/spend/summary',{params:{dataset_id:id}})).data,
  spendTrend:async(id:string,granularity:string)=> (await client.get<SpendTrend>('/spend/trend',{params:{dataset_id:id,granularity}})).data,
  spendBreakdown:async(id:string,dimension:string,start?:string,end?:string,limit=25)=> (await client.get<Breakdown[]>('/spend/breakdown',{params:{dataset_id:id,dimension,period_start:start,period_end:end,limit}})).data,
  anomalies:async(id:string,entity_type='service')=> (await client.get<AnomalyReport>('/anomalies',{params:{dataset_id:id,entity_type}})).data,
  opportunities:async(id:string)=> (await client.get<OpportunityReport>('/opportunities',{params:{dataset_id:id}})).data,
  forecasts:async(id:string,horizon_days:number)=> (await client.get<Forecast>('/forecasts',{params:{dataset_id:id,horizon_days}})).data,
  dataQuality:async(id:string)=> (await client.get<QualityReport>('/data-quality',{params:{dataset_id:id}})).data,
  health:async()=> (await client.get<Health>('/health')).data,
  budgets:async()=> (await client.get<Budget[]>('/budgets')).data,
  createBudget:async(body:BudgetInput)=> (await client.post('/budgets',body)).data,
  agentRuns:async(id:string)=> (await client.get<Pipeline[]>('/agent-runs',{params:{dataset_id:id}})).data,
  runPipeline:async(id:string)=> (await client.post<Pipeline>('/agent-runs',null,{params:{dataset_id:id}})).data,
  recommendations:async(id:string)=> (await client.get<Recommendation[]>('/recommendations',{...localErrors,params:{dataset_id:id}})).data,
  decide:async(id:string,decision:'approved'|'rejected')=> (await client.post('/recommendations/'+id+'/decision',{decision},localErrors)).data,
  simulate:async(id:string,reduction_pct:number)=> (await client.post<Scenario>('/recommendations/'+id+'/simulate',{reduction_pct},localErrors)).data,
}
