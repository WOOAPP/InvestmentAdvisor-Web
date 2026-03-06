import api from './client';

export interface Position {
  id: number;
  symbol: string;
  name: string;
  quantity: number;
  buy_price: number;
  buy_currency: string;
  buy_fx_to_usd: number;
  buy_price_usd: number;
  tab_type: string;
  created_at: string;
}

export interface PositionCreate {
  symbol: string;
  name?: string;
  quantity: number;
  buy_price: number;
  buy_currency?: string;
  buy_fx_to_usd?: number;
  tab_type?: string;
}

export const getPositions = (tabType: string): Promise<Position[]> =>
  api.get(`/portfolio?tab_type=${tabType}`).then((r) => r.data);

export const addPosition = (data: PositionCreate): Promise<Position> =>
  api.post('/portfolio', data).then((r) => r.data);

export const deletePosition = (id: number): Promise<void> =>
  api.delete(`/portfolio/${id}`).then(() => undefined);
