import api from './client';

export interface ReportSummary {
  id: number;
  created_at: string;
  provider: string | null;
  model: string | null;
  risk_level: number;
  preview: string | null;
}

export interface ReportDetail {
  id: number;
  created_at: string;
  provider: string | null;
  model: string | null;
  market_summary: string | null;
  analysis: string | null;
  risk_level: number;
  input_tokens: number;
  output_tokens: number;
}

export const getReports = (limit = 50): Promise<ReportSummary[]> =>
  api.get(`/reports?limit=${limit}`).then((r) => r.data);

export const getReport = (id: number): Promise<ReportDetail> =>
  api.get(`/reports/${id}`).then((r) => r.data);

export const runAnalysis = (provider?: string, model?: string): Promise<{ status: string }> =>
  api.post('/reports/run', provider ? { provider, model } : {}).then((r) => r.data);

export const deleteReport = (id: number): Promise<void> =>
  api.delete(`/reports/${id}`).then(() => undefined);
