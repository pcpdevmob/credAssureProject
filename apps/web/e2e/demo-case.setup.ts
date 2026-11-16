// Runs the demo case (CA-2026-0001 files, BRD App. A) through the live gateway API, as the e2e preparer.
// A fresh case is needed: an identical re-run writes no new fact version, so old facts would keep producer = null.
import { expect, test as setup } from '@playwright/test';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { DEMO_FILE, E2E_USERNAME, e2ePassword } from './credentials';

const API = process.env.E2E_API_URL || 'http://localhost:8001';
const FROZEN = join(__dirname, '../../../data/frozen/v1');
const CASE_DIR = join(FROZEN, 'cases/CA-2026-0001');

const KINDS = ['order', 'opening_position', 'costs', 'receipts', 'receivables', 'payables', 'inventory'];

setup('demo case runs to approval with recorded producers', async ({ request }) => {
  const tok = await request.post(`${API}/v1/auth/token`, { data: { username: E2E_USERNAME, password: e2ePassword() } });
  expect(tok.status(), 'gateway sign-in').toBe(200);
  const headers = { Authorization: `Bearer ${(await tok.json()).access_token}` };

  const created = await request.post(`${API}/v1/cases`, { headers, data: {
    // ₹3.2 crore order, ₹2 crore request (paise written with Indian grouping), as tests/e2e/test_demo_case.py
    msme_name: 'Demo Electronics Pvt Ltd', order_ref: 'PO-CA-2026-0001', order_value_paise: 3_20_00_000_00, indicative_amount_paise: 2_00_00_000_00, due_date: '2027-05-15',
  } });
  expect(created.status(), await created.text()).toBe(201);
  const caseId: string = (await created.json()).case_id;

  const upload = async (kind: string, path: string, mimeType: string) => {
    const name = path.split('/').pop()!;
    const r = await request.post(`${API}/v1/cases/${caseId}/files`, { headers, params: { kind }, multipart: { file: { name, mimeType, buffer: readFileSync(path) } } });
    expect(r.status(), `${kind} ${name}: ${await r.text()}`).toBe(201);
  };
  for (const kind of KINDS) {
    const json = kind === 'order' || kind === 'opening_position';
    await upload(kind, join(CASE_DIR, `${kind}.${json ? 'json' : 'csv'}`), json ? 'application/json' : 'text/csv');
  }
  const offersDir = join(FROZEN, 'offers/CA-2026-0001');
  for (const file of readdirSync(offersDir).filter(f => f.endsWith('.v1.json')).sort()) { // as tests/e2e/conftest.py upload_offers
    const path = join(offersDir, file);
    const doc: string = JSON.parse(readFileSync(path, 'utf8')).kfs_doc_id;
    await upload('offer', path, 'application/json');
    await upload('kfs', join(FROZEN, 'kfs', `${doc}.md`), 'text/markdown');
    await upload('kfs', join(FROZEN, 'kfs', `${doc}-SCH.md`), 'text/markdown');
  }

  const run = await request.post(`${API}/v1/cases/${caseId}/run`, { headers });
  expect(run.status(), await run.text()).toBe(202);
  const statusUrl = new URL((await run.json()).status_url, API).toString();
  let job: { status?: string; outcome?: string } = {};
  // Poll under uvicorn's 5 s keep-alive; a reset socket is retried on the next poll, not treated as a failed run.
  await expect.poll(async () => {
    try { job = await (await request.get(statusUrl, { headers })).json(); } catch { return 'poll-retry'; }
    return job.status;
  }, { timeout: 14 * 60_000, intervals: [2_000, 3_000] }).toMatch(/succeeded|failed/);
  expect(job, JSON.stringify(job)).toMatchObject({ status: 'succeeded', outcome: 'AWAITING_APPROVAL' });

  const lin = await (await request.get(`${API}/v1/cases/${caseId}/facts/wc.recommended_amount/lineage`, { headers })).json();
  expect(lin.value.display).toBe('₹1,42,00,000');
  expect(lin.producer.trace_id, 'producer recorded at write time').toBeTruthy();
  writeFileSync(DEMO_FILE, JSON.stringify({ caseId }));
});

