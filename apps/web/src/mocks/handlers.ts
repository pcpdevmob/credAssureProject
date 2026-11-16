// MSW handlers for unit tests (msw/node). Errors are RFC 9457 problem+json exactly as the gateway sends them at run time.
import { http, HttpResponse } from 'msw';
import { CASE_ID, LINEAGE, caseSummary, caseTotals } from './fixtures';

export const API = 'http://localhost:8000';
export const problem = (status: number, code: string, detail: string, errors?: unknown[]) =>
  HttpResponse.json({ type: `https://credassure.local/problems/${code.toLowerCase().replace(/_/g, '-')}`, title: 'Error', status, detail, code, instance: '/v1', ...(errors ? { errors } : {}) },
    { status, headers: { 'Content-Type': 'application/problem+json' } });

export const handlers = [
  http.post(`${API}/v1/auth/token`, () => HttpResponse.json({ access_token: 'test-token', token_type: 'bearer', expires_in: 1800 })),
  http.get(`${API}/v1/me`, () => HttpResponse.json({ user_id: 'u-1', username: 'demo.preparer', role: 'preparer' })),
  http.get(`${API}/v1/cases`, () => HttpResponse.json({ items: [caseSummary], totals: caseTotals })),
  http.get(`${API}/v1/cases/:id`, ({ params }) => params.id === CASE_ID ? HttpResponse.json(caseSummary) : problem(404, 'NOT_FOUND', 'Case not found.')),
  http.get(`${API}/v1/cases/:id/facts/:key/lineage`, ({ params }) => {
    const l = LINEAGE[String(params.key)];
    return params.id === CASE_ID && l ? HttpResponse.json(l) : problem(404, 'NOT_FOUND', `No fact ${String(params.key)} on this case.`);
  }),
];
