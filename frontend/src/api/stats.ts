import api from './client';

export interface UsageAggregate {
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  requests: number;
  by_type: Record<string, { input_tokens: number; output_tokens: number; cost_usd: number; requests: number }>;
}

export interface StatsResponse {
  historical: UsageAggregate;
  session: UsageAggregate | null;
}

export const getStats = (sessionSince?: string): Promise<StatsResponse> => {
  const params = sessionSince ? { session_since: sessionSince } : {};
  return api.get('/stats', { params }).then((r) => r.data);
};
