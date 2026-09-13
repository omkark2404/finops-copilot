import axios from 'axios';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const client = axios.create({
  baseURL: BASE_URL,
});

export const api = {
  spendSummary: async (datasetId: string) => (await client.get(`/spend/summary?dataset_id=${datasetId}`)).data,
  spendTrend: async (datasetId: string, granularity: string) => (await client.get(`/spend/trend?dataset_id=${datasetId}&granularity=${granularity}`)).data,
  anomalies: async (datasetId: string) => (await client.get(`/anomalies?dataset_id=${datasetId}`)).data,
  opportunities: async (datasetId: string) => (await client.get(`/opportunities?dataset_id=${datasetId}`)).data,
  forecasts: async (datasetId: string, days: number) => (await client.get(`/forecasts?dataset_id=${datasetId}&horizon_days=${days}`)).data,
  datasets: async () => (await client.get('/datasets')).data,
  login: async (email: string, pass: string) => (await client.post('/auth/login', {email, password: pass})).data,
  agentRuns: async (datasetId: string) => {
    try {
        return (await client.get(`/agent-runs?dataset_id=${datasetId}`)).data;
    } catch { return []; }
  },
  runAgents: async (datasetId: string) => (await client.post(`/agent-runs?dataset_id=${datasetId}`)).data,
  dataQuality: async (datasetId: string) => (await client.get(`/data-quality?dataset_id=${datasetId}`)).data,
  deleteDataset: async (datasetId: string) => (await client.delete(`/datasets/${datasetId}`)).data,
  costDrivers: async (datasetId: string) => (await client.get(`/spend/breakdown?dataset_id=${datasetId}`)).data,
  investigateAnomaly: async (id: string) => (await client.post(`/anomalies/${id}/investigate`)).data,
  health: async () => (await client.get('/health')).data,
  budgets: async () => (await client.get('/budgets')).data
};
