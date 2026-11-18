// MSW handlers for unit tests (msw/node). Errors are RFC 9457 problem+json exactly as the gateway sends them at run time.
import { http, HttpResponse } from 'msw';
import { CASE_ID, LINEAGE, caseSummary, caseTotals } from './fixtures';

export const API = 'http://localhost:8000';
export const problem = (status: number, code: string, detail: string, errors?: unknown[]) =>
  HttpResponse.json({ type: `https://credassure.local/problems/${code.toLowerCase().replace(/_/g, '-')}`, title: 'Error', status, detail, code, instance: '/v1', ...(errors ? { errors } : {}) },
    { status, headers: { 'Content-Type': 'application/problem+json' } });

export const reply = (o: Record<string, unknown> = {}) => ({ answer: 'A Key Facts Statement discloses the all-in cost of a loan [1].', citations: [{ chunk_id: 'R-RBI-02-c12', doc_id: 'R-RBI-02', title: 'Responsible Business Conduct Directions, 2025', section: 'Annex XIII', effective_from: '2025-11-28' }],
  refused: false, abstained: false, refusal_code: null, injection_flagged: false, pii_redacted: false, intent: 'copilot_question', trace_id: 't-1', fact_key: null, ...o });
export const passage = (o: Record<string, unknown> = {}) => ({ chunk_id: 'R-RBI-02-c12', doc_id: 'R-RBI-02', title: 'Responsible Business Conduct Directions, 2025', section: 'Annex XIII',
  effective_from: '2025-11-28', legal_basis: 'L4', source_url: 'https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140', text: 'The Key Facts Statement shall disclose the annual percentage rate.',
  text_format: 'plain', truncated: false, injection_flagged: false, injection_flags: [], ...o });
// Same wording as the gateway's CHAT_NOTICE (supervisor_service.py); the UI shows whatever GET /v1/me/chat-notice returns.
export const NOTICE = "Ask CredAssure drafts answers with a language model from cited sources (product help, regulations, policies) and the open case's verified figures. It is general information, not legal, tax or credit advice, and it never approves, accepts or signs anything. Do not enter personal identifiers.";
/** CP-12: the gateway's stream for one reply: stage events, the checked text in deltas, then the full reply. */
export const sse = (r: Record<string, unknown>) => {
  const answer = String(r.answer ?? ''); const words = answer.match(/\S+\s*/g) ?? [];
  const ev = (e: string, d: unknown) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`;
  const body = ['routing', 'retrieving', 'drafting', 'checking'].map(s => ev('stage', { stage: s })).join('')
    + words.map(w => ev('delta', { text: w })).join('') + ev('final', r);
  return new HttpResponse(body, { headers: { 'Content-Type': 'text/event-stream' } });
};

export const handlers = [
  http.get(`${API}/v1/cases/:id/citations/:chunk`, () => HttpResponse.json(passage())),
  http.post(`${API}/v1/cases/:id/chat`, () => HttpResponse.json(reply({ notice: 'Answers come from public sources and this case. Do not enter personal data.' }))),
  http.post(`${API}/v1/copilot/chat/stream`, () => sse(reply({ followups: ['What is the status of this case?', 'How does CredAssure handle personal data?'] }))),
  http.get(`${API}/v1/cases/:id/chat`, ({ params }) => HttpResponse.json({ case_id: String(params.id), messages: [] })),
  http.post(`${API}/v1/cases/:id/chat/reset`, ({ params }) => HttpResponse.json({ case_id: String(params.id), messages: [] })),
  http.post(`${API}/v1/copilot/feedback`, () => HttpResponse.json({ trace_id: 't-1', rating: 'up', recorded: true })),
  http.get(`${API}/v1/citations/:chunk`, () => HttpResponse.json(passage())),
  http.get(`${API}/v1/cases/:id/safety`, ({ params }) => HttpResponse.json({ case_id: String(params.id), counts: {}, events: [] })),
  http.get(`${API}/v1/eval/scorecard`, () => HttpResponse.json({ baseline: null, full: null, ablations: {}, target: 92 })),
  http.get(`${API}/v1/health/ready`, () => HttpResponse.json({ status: 'ok', checks: { db: 'ok', model: 'closed' } })),
  http.get(`${API}/v1/inbox`, () => HttpResponse.json({ items: [{ case_id: 'CA-2026-0016', msme_name: 'Demo Electronics', status: 'AWAITING_APPROVAL', route: 'director_finance' }, { case_id: 'CA-2026-0030', msme_name: 'Boundary Works', status: 'HELD', route: 'HELD' }] })),
  http.post(`${API}/v1/cases/:id/decision`, () => HttpResponse.json({ status: 'APPROVED', approval_id: 1 })),
  http.get(`${API}/v1/cases/:id/report`, ({ request }) => new URL(request.url).searchParams.get('fmt') === 'json'
    ? HttpResponse.json({ case_id: 'CA-2026-0016', version: 1, latest_version: 1, stale: false, reasons: [], sections: [
        { title: 'Case summary', text: 'Demo <script>x</script>. Validated need: ₹1,42,00,000.', figures: [{ key: 'wc.recommended_amount', version: 1, start: 41, end: 53, display: '₹1,42,00,000' }] }] })
    : new HttpResponse('# Proposal CA-2026-0016\n\n<script>x</script>\n', { headers: { 'Content-Type': 'text/markdown' } })),
  http.get(`${API}/v1/me/chat-notice`, () => HttpResponse.json({ text: NOTICE, version: 'abc123def456', acknowledged_at: null })),
  http.post(`${API}/v1/me/chat-notice/ack`, () => HttpResponse.json({ text: NOTICE, version: 'abc123def456', acknowledged_at: '2026-11-17T08:00:00+00:00' })),
  http.post(`${API}/v1/cases/:id/report`, () => HttpResponse.json({ version: 2, stale: false, reasons: [] }, { status: 201 })),
  http.post(`${API}/v1/auth/token`, () => HttpResponse.json({ access_token: 'test-token', token_type: 'bearer', expires_in: 1800 })),
  http.get(`${API}/v1/me`, () => HttpResponse.json({ user_id: 'u-1', username: 'demo.preparer', role: 'preparer' })),
  http.get(`${API}/v1/cases`, () => HttpResponse.json({ items: [caseSummary], totals: caseTotals })),
  http.get(`${API}/v1/cases/:id`, ({ params }) => params.id === CASE_ID ? HttpResponse.json(caseSummary) : problem(404, 'NOT_FOUND', 'Case not found.')),
  http.get(`${API}/v1/cases/:id/facts/:key/lineage`, ({ params }) => {
    const l = LINEAGE[String(params.key)];
    return params.id === CASE_ID && l ? HttpResponse.json(l) : problem(404, 'NOT_FOUND', `No fact ${String(params.key)} on this case.`);
  }),
];
