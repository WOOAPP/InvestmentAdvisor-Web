import api from './client';

export interface CalendarEvent {
  date: string;
  time: string;
  flag: string;
  country: string;
  event: string;
  impact_icon: string;
  impact_label: string;
  impact_raw: string;
  forecast: string;
  previous: string;
  significance: string;
}

export interface CalendarResponse {
  events: CalendarEvent[];
  error: string | null;
}

export const getCalendar = (): Promise<CalendarResponse> =>
  api.get('/calendar').then((r) => r.data);

export const analyzeCalendarEvent = (ev: CalendarEvent): Promise<{ analysis: string }> =>
  api.post('/calendar/analyze', {
    event: ev.event,
    country: ev.country,
    date: ev.date,
    time: ev.time,
    impact_raw: ev.impact_raw,
    forecast: ev.forecast,
    previous: ev.previous,
    significance: ev.significance,
  }).then((r) => r.data);

export const searchInstruments = (q: string): Promise<{
  symbol: string;
  name: string;
  type: string;
  exchange: string;
}[]> =>
  api.get('/market/search', { params: { q } }).then((r) => r.data).catch(() => []);
