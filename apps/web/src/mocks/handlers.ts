// MSW handlers for unit tests (msw/node). Errors are RFC 9457 problem+json exactly as the gateway sends them at run time.
import { http, HttpResponse } from 'msw';
import { CASE_ID, LINEAGE, caseSummary, caseTotals } from './fixtures';

export const API = 'http://localhost:8000';
export const problem = (status: number, code: string, detail: string, errors?: unknown[]) =>
  HttpResponse.json({ type: `https://credassure.local/problems/${code.toLowerCase().replace(/_/g, '-')}`, title: 'Error', status, detail, code, instance: '/v1', ...(errors ? { errors } : {}) },
    { status, headers: { 'Content-Type': 'application/problem+json' } });

export const reply = (o: Record<string, unknown> = {}) => ({ answer: 'A Key Facts Statement discloses the all-in cost of a loan [1].', citations: [{ chunk_id: 'R-RBI-02-c12', doc_id: 'R-RBI-02', title: 'Responsible Business Conduct Directions, 2025', section: 'Annex XIII', effective_from: '2025-11-28' }],
  refused: false, abstained: false, refusal_code: null, injection_flagged: false, pii_redacted: false, intent: 'copilot_question', trace_id: 't-1', fact_key: null, ...o });
export const handlers = [
  http.post(`${API}/v1/cases/:id/chat`, () => HttpResponse.json(reply({ notice: 'Answers come from public sources and this case. Do not enter personal data.' }))),
  http.get(`${API}/v1/health/ready`, () => HttpResponse.json({ status: 'ok', checks: { db: 'ok', model: 'closed' } })),
  http.get(`${API}/v1/inbox`, () => HttpResponse.json({ items: [{ case_id: 'CA-2026-0016', msme_name: 'Demo Electronics', status: 'AWAITING_APPROVAL', route: 'director_finance' }, { case_id: 'CA-2026-0030', msme_name: 'Boundary Works', status: 'HELD', route: 'HELD' }] })),
  http.post(`${API}/v1/cases/:id/decision`, () => HttpResponse.json({ status: 'APPROVED', approval_id: 1 })),
  http.get(`${API}/v1/cases/:id/report`, () => new HttpResponse('# Proposal CA-2026-0016\n\n<script>x</script>\n', { headers: { 'Content-Type': 'text/markdown' } })),
  http.post(`${API}/v1/auth/token`, () => HttpResponse.json({ access_token: 'test-token', token_type: 'bearer', expires_in: 1800 })),
  http.get(`${API}/v1/me`, () => HttpResponse.json({ user_id: 'u-1', username: 'demo.preparer', role: 'preparer' })),
  http.get(`${API}/v1/cases`, () => HttpResponse.json({ items: [caseSummary], totals: caseTotals })),
  http.get(`${API}/v1/cases/:id`, ({ params }) => params.id === CASE_ID ? HttpResponse.json(caseSummary) : problem(404, 'NOT_FOUND', 'Case not found.')),
  http.get(`${API}/v1/cases/:id/facts/:key/lineage`, ({ params }) => {
    const l = LINEAGE[String(params.key)];
    return params.id === CASE_ID && l ? HttpResponse.json(l) : problem(404, 'NOT_FOUND', `No fact ${String(params.key)} on this case.`);
  }),
];
