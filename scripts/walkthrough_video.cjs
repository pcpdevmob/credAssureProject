// make walkthrough-video: records the end-to-end walk-through (every role, every flow, Ask CredAssure) to one video.
// Run by scripts/walkthrough_video.sh against the isolated e2e stack (gateway :8001, web :3001, var/case-e2e.db).
//   node scripts/walkthrough_video.cjs <out-dir>
// Before recording it prepares, through the API and off camera: the Director's and VP's authenticator (no admin
// screen is shown) and the supporting cases (scenarios 02, 03, 04, 08, 09) from data/test-pack. Scenario 01 is
// created on camera. All data is synthetic. E2E_PASSWORD (the e2e database's fixture password) comes from .env.
// Live site: WALK_ACCOUNTS=<file> (the same accounts file as make e2e-report --live: BASE_URL=..., ROLE_<role>=<username>,
// PW_<username>=..., TOTP_<username>=...) records on BASE_URL instead, as those accounts, paced under the site's rate
// limit. New passwords and authenticator keys are written back to that file (0600).
const fs = require('node:fs'); const path = require('node:path'); const crypto = require('node:crypto');
const { chromium } = require(process.env.PW_MODULE || '@playwright/test'); // PW_MODULE: another Playwright install

const ROOT = path.resolve(__dirname, '..'); const PACK = path.join(ROOT, 'data', 'test-pack');
const OUT = path.resolve(process.argv[2] || path.join(ROOT, 'var', 'walkthrough'));
const readEnv = f => Object.fromEntries(fs.readFileSync(f, 'utf8').split('\n').map(l => l.trim()).filter(l => /^[A-Za-z0-9_.-]+=/.test(l)).map(l => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()]));
const ACCOUNTS = process.env.WALK_ACCOUNTS ? path.resolve(process.env.WALK_ACCOUNTS) : null; const LIVE = !!ACCOUNTS;
const acc = LIVE ? readEnv(ACCOUNTS) : {};
const BASE = (acc.BASE_URL || '').replace(/\/+$/, '');
if (LIVE && !BASE) { console.error(`${ACCOUNTS}: set BASE_URL=https://<site>`); process.exit(2); }
const API = LIVE ? (acc.API_URL || BASE).replace(/\/+$/, '') : process.env.E2E_API_URL || 'http://localhost:8001'; const WEB = LIVE ? BASE : process.env.E2E_BASE_URL || 'http://localhost:3001';
const envFile = path.join(ROOT, '.env');
const dotenv = !LIVE && fs.existsSync(envFile) ? readEnv(envFile) : {};
const FIXTURE = LIVE ? '' : process.env.E2E_PASSWORD || dotenv.E2E_PASSWORD;
if (!LIVE && !FIXTURE) { console.error('Set E2E_PASSWORD in .env (12+ characters), then make e2e-db.'); process.exit(2); }
const U = LIVE ? { prep: acc.ROLE_PREPARER, dir: acc.ROLE_DIRECTOR, vp: acc.ROLE_VP, ev: acc.ROLE_EVALUATOR } : { prep: 'demo.preparer', dir: 'demo.director', vp: 'demo.vp', ev: 'demo.evaluator' };
for (const [r, u] of Object.entries(U)) if (!u) { console.error(`${ACCOUNTS}: set ROLE_${{ prep: 'PREPARER', dir: 'DIRECTOR', vp: 'VP', ev: 'EVALUATOR' }[r]}=<username>`); process.exit(2); }
const pw = {}; const secret = {}; const used = {};
for (const [k, v] of Object.entries(acc)) { if (k.startsWith('PW_') && v) pw[k.slice(3)] = v; if (k.startsWith('TOTP_') && v) secret[k.slice(5)] = v; }
for (const u of Object.values(U)) if (LIVE && !pw[u]) { console.error(`${ACCOUNTS}: set PW_${u}=<password>`); process.exit(2); }
// Write new passwords and authenticator keys back to the accounts file, so the next run (and e2e-report --live) signs in.
function saveAccounts() {
  if (!LIVE) return; const want = {}; for (const [u, v] of Object.entries(pw)) want[`PW_${u}`] = v; for (const [u, v] of Object.entries(secret)) want[`TOTP_${u}`] = v;
  const out = fs.readFileSync(ACCOUNTS, 'utf8').replace(/\n+$/, '').split('\n').map(l => { const k = l.split('=')[0].trim(); if (k in want) { const v = want[k]; delete want[k]; return `${k}=${v}`; } return l; });
  for (const [k, v] of Object.entries(want)) out.push(`${k}=${v}`);
  fs.writeFileSync(ACCOUNTS, out.join('\n') + '\n', { mode: 0o600 }); fs.chmodSync(ACCOUNTS, 0o600);
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ---------- TOTP (RFC 6238), as the authenticator app does
function b32(s) { const a = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'; let bits = ''; for (const c of s.replace(/[\s=]/g, '').toUpperCase()) bits += a.indexOf(c).toString(2).padStart(5, '0'); const out = []; for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2)); return Buffer.from(out); }
function totp(sec, step) { const b = Buffer.alloc(8); b.writeBigUInt64BE(BigInt(step)); const h = crypto.createHmac('sha1', b32(sec)).update(b).digest(); const o = h[h.length - 1] & 15; return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, '0'); }
async function code(user) { let s = Math.floor(Date.now() / 30000); if (used[user] !== undefined && s <= used[user]) { await sleep((used[user] + 1) * 30000 - Date.now() + 1200); s = Math.floor(Date.now() / 30000); } used[user] = s; return totp(secret[user], s); }

// ---------- API, off camera
let lastCall = 0;
async function call(method, p, tok, body, query) {
  const url = new URL(API + p); for (const [k, v] of Object.entries(query || {})) url.searchParams.set(k, v);
  const h = tok ? { Authorization: `Bearer ${tok}` } : {}; let data;
  if (body instanceof FormData) data = body; else if (body !== undefined) { data = JSON.stringify(body); h['content-type'] = 'application/json'; }
  if (method === 'POST' && p.endsWith('/run')) h['Idempotency-Key'] = crypto.randomUUID();
  let r;
  for (let i = 0; ; i++) {
    if (LIVE) { const wait = lastCall + 700 - Date.now(); if (wait > 0) await sleep(wait); lastCall = Date.now(); } // about 85 calls a minute
    r = await fetch(url, { method, headers: h, body: data });
    if (r.status !== 429 || i >= 5) break;
    await sleep((Number(r.headers.get('retry-after')) || 20) * 1000 + 500);
  }
  const t = await r.text();
  let j; try { j = JSON.parse(t); } catch { j = t; } return [r.status, j];
}
async function signInApi(user) {
  const pass = () => pw[user] || FIXTURE;
  let [s, b] = await call('POST', '/v1/auth/token', null, { username: user, password: pass() });
  if (s !== 200) throw new Error(`${user}: sign-in ${s}`);
  for (let i = 0; i < 4 && b.stage !== 'full'; i++) {
    const t = b.access_token; const n = b.next || [];
    if (n.includes('change_password')) { const np = `Walk-${crypto.randomBytes(6).toString('hex')}`; await call('POST', '/v1/auth/password', t, { current_password: pass(), new_password: np }); pw[user] = np; saveAccounts(); [s, b] = await call('POST', '/v1/auth/token', null, { username: user, password: np }); }
    else if (n.includes('enrol_mfa')) { const [, st] = await call('POST', '/v1/auth/mfa/setup', t, { current_password: pass() }); secret[user] = st.secret; saveAccounts(); [s, b] = await call('POST', '/v1/auth/mfa/enable', t, { code: await code(user) }); }
    else if (n.includes('verify_mfa')) { [s, b] = await call('POST', '/v1/auth/mfa/verify', t, { code: await code(user) }); }
  }
  if (b.stage !== 'full') throw new Error(`${user}: could not finish sign-in`);
  return b.access_token;
}
function caseFields(folder) {
  const md = fs.readFileSync(path.join(PACK, folder, 'manual-entry.md'), 'utf8');
  const cell = l => md.match(new RegExp(`\\| ${l} \\| ([^|]+) \\|`))[1].trim(); const paise = v => Number(v.replace(/,/g, '')) * 100;
  return { msme_name: cell('MSME legal name').replace('Manual test', 'Walk-through'), order_ref: cell('PO reference'), order_value_paise: paise(cell('Order value')), indicative_amount_paise: paise(cell('Requested amount')), due_date: '2027-05-15', _order: cell('Order value'), _req: cell('Requested amount') };
}
const lenderFiles = folder => { const d = path.join(PACK, folder, 'lender-files'); const f = fs.readdirSync(d).sort(); return [...f.filter(x => x.endsWith('.json')), ...f.filter(x => x.endsWith('.md'))].map(x => path.join(d, x)); };
const workbook = folder => path.join(PACK, folder, fs.readdirSync(path.join(PACK, folder)).find(x => x.startsWith('case-data-') && x.endsWith('.xlsx')));
async function prepareCase(tok, folder, run = true) {
  const { _order, _req, ...fields } = caseFields(folder);
  const [s, c] = await call('POST', '/v1/cases', tok, fields); if (s !== 201) throw new Error(`create ${folder}: ${s}`);
  const fd = new FormData(); fd.append('file', new Blob([fs.readFileSync(workbook(folder))]), path.basename(workbook(folder)));
  await call('POST', `/v1/cases/${c.case_id}/workbook`, tok, fd);
  for (const f of lenderFiles(folder)) { const d = new FormData(); d.append('file', new Blob([fs.readFileSync(f)]), path.basename(f)); await call('POST', `/v1/cases/${c.case_id}/files`, tok, d, { kind: f.endsWith('.json') ? 'offer' : 'kfs' }); }
  if (run) { const [, j] = await call('POST', `/v1/cases/${c.case_id}/run`, tok); for (let i = 0; i < 600; i++) { const [, st] = await call('GET', `/v1/jobs/${j.job_id}`, tok); if (['succeeded', 'failed', 'cancelled'].includes(st.status)) break; await sleep(LIVE ? 3000 : 1000); } }
  return c.case_id;
}

// ---------- on camera
let page;
async function caption(text) {
  await page.evaluate(t => { let el = document.getElementById('walk-caption'); if (!el) { el = document.createElement('div'); el.id = 'walk-caption'; el.style.cssText = 'position:fixed;left:50%;top:14px;transform:translateX(-50%);z-index:2147483646;max-width:900px;text-align:center;background:rgba(14,22,40,.92);color:#fff;font:600 16px/1.4 Inter,Arial,sans-serif;padding:10px 16px;border-radius:12px;box-shadow:0 6px 24px rgba(0,0,0,.25);pointer-events:none'; document.body.appendChild(el); } el.textContent = t; }, text).catch(() => {});
  await sleep(1800);
}
// A title card drawn over the app (never a new page: sign-in lives only in the page's memory).
async function card(title, sub, ms = 4500) {
  const htmlCard = `<div style="text-align:center;max-width:980px"><div style="color:#E8C468;letter-spacing:.22em;font-size:16px">CREDASSURE · END-TO-END WALK-THROUGH</div><h1 style="font-size:46px;margin:18px 0">${title}</h1><p style="font-size:21px;color:#cbd5e1;line-height:1.5">${sub}</p></div>`;
  if (!page.url().startsWith(WEB)) { await page.setContent(`<html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#0E1628;font-family:Inter,Arial,sans-serif;color:#fff">${htmlCard}</body></html>`); await sleep(ms); return; }
  await page.evaluate(h => { const d = document.createElement('div'); d.id = 'walk-card'; d.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;background:#0E1628;font-family:Inter,Arial,sans-serif;color:#fff'; d.innerHTML = h; document.body.appendChild(d); }, htmlCard);
  await sleep(ms);
  await page.evaluate(() => document.getElementById('walk-card')?.remove());
}
const settle = async (ms = 1200) => { await page.waitForLoadState('networkidle').catch(() => {}); await sleep(ms); };
async function signIn(user) {
  await page.goto(`${WEB}/login/`); await page.waitForSelector('#username');
  await caption(`Sign in as ${user}`);
  await page.fill('#username', user); await page.fill('#password', pw[user] || FIXTURE);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForFunction(() => !location.pathname.startsWith('/login') || document.querySelector('#code'), null, { timeout: 60000 });
  if (await page.locator('#code').count()) { await caption('Approvers sign in with a password and a 6-digit code from the authenticator app'); await page.fill('#code', await code(user)); await page.getByRole('button', { name: 'Verify & sign in' }).click(); await page.waitForFunction(() => !location.pathname.startsWith('/login'), null, { timeout: 60000 }); }
  await settle();
}
async function signOut() { await page.getByRole('button', { name: /sign out/i }).first().click().catch(() => {}); await sleep(1500); }
async function nav(name) { await page.getByRole('link', { name, exact: true }).first().click(); await settle(); }
async function loaded() { await page.waitForFunction(() => !document.querySelector('main .animate-pulse'), null, { timeout: 30000 }).catch(() => {}); await sleep(800); }
async function tab(name) { await page.getByRole('button', { name, exact: true }).first().click(); await settle(1500); await loaded(); }
async function openCase(id) { await nav('Cases'); await page.getByText(id).first().click(); await page.waitForURL(/\/case\//); await settle(2000); await loaded(); }
async function scroll(px = 700, steps = 3) { for (let i = 0; i < steps; i++) { await page.mouse.wheel(0, px); await sleep(900); } await page.mouse.wheel(0, -px * steps); await sleep(600); }
async function ask(question, input = '#ask', wait = 240000) {
  await page.waitForSelector(input);
  if (await page.locator(input).isDisabled()) { await caption('The model is off, so Ask CredAssure says it is unavailable and answers nothing'); await sleep(2500); return; }
  const before = await page.getByRole('button', { name: 'Helpful' }).count();
  await page.fill(input, question); await sleep(600);
  await page.locator(input).locator('xpath=ancestor::form').getByRole('button', { name: 'Ask' }).click();
  await page.waitForFunction(n => document.querySelectorAll('button[aria-label="Helpful"]').length > n || !!document.querySelector('[role=alert]'), before, { timeout: wait }).catch(() => {});
  await sleep(2500);
}
async function decide(user, id, choice, comment, extra = {}) {
  await openCase(id); await tab('Review & approval');
  await page.getByRole('radio', { name: choice }).check();
  if (extra.stage) await page.locator('select').last().selectOption({ label: extra.stage });
  await page.getByLabel(/Comment/).fill(comment);
  if (choice === 'Approve proposal') await page.getByLabel(/I reviewed the accuracy checks/).check();
  await sleep(1200);
  await page.getByRole('button', { name: choice, exact: true }).click();
  await page.waitForSelector('#stepup'); await page.fill('#stepup', id);
  if (await page.locator('#stepup-pw').count()) { await caption('Above ₹1.5 crore the approver confirms with the password and a fresh code'); await page.fill('#stepup-pw', pw[user] || FIXTURE); await page.fill('#stepup-code', await code(user)); }
  await sleep(1500);
  await page.getByRole('button', { name: /^Confirm:/ }).click();
  await page.waitForFunction(() => !document.querySelector('#stepup'), null, { timeout: 60000 }); await settle(2500);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  console.log(LIVE ? `recording on ${BASE} as ${Object.values(U).join(', ')}; creating 'Walk-through' cases there` : 'preparing accounts and supporting cases (off camera)…');
  const tp = await signInApi(U.prep); await signInApi(U.dir); await signInApi(U.vp); await signInApi(U.ev);
  const C = {};
  for (const f of ['02-vp-route-negotiation', '03-held-exactly-1-5-crore', '04-missing-schedule-question', '08-no-loan-needed', '09-injection-in-lender-document']) { C[f] = await prepareCase(tp, f); console.log(' ', f, C[f]); }
  const [, health] = await call('GET', '/v1/health/ready'); const modelOn = health?.checks?.model && health.checks.model !== 'disabled';
  console.log('model:', health?.checks?.model, '· search index:', health?.checks?.chroma);

  const launch = process.env.PW_CHROMIUM ? [{ executablePath: process.env.PW_CHROMIUM }] : [{ channel: 'chrome' }, {}];
  let browser; for (const o of launch) { try { browser = await chromium.launch(o); break; } catch (e) { if (o === launch[launch.length - 1]) throw e; } }
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, recordVideo: { dir: OUT, size: { width: 1440, height: 900 } } });
  page = await ctx.newPage(); page.on('dialog', d => d.accept()); page.setDefaultTimeout(90000);
  const scene = async (name, fn) => { try { await fn(); } catch (e) { console.error(`scene "${name}" stopped: ${e.message.split('\n')[0]}`); await page.screenshot({ path: path.join(OUT, `stopped-${name.replace(/\W+/g, '-')}.png`) }).catch(() => {}); } };
  try {
    await card('CredAssure', 'A verified working-capital proposal for an electronics MSME. The model reads and drafts; code calculates, checks and routes; a person approves. All data is synthetic.', 6000);

    let id01;
    await scene('preparer', async () => {
      await card('1 · Proposal Preparer', 'Create a case from the Excel workbook and the lenders’ files, then run every check.');
      await signIn(U.prep);
      await caption('Dashboard: the preparer’s cases and where each one stands');
      await nav('New case'); await caption('New case: order details from the purchase order');
      const f = caseFields('01-director-route');
      await page.fill('#msme', f.msme_name); await page.fill('#po', f.order_ref);
      await page.getByLabel('Order value').fill(f._order); await page.getByLabel('Requested amount').fill(f._req);
      await page.fill('#due', '2027-05-15');
      await caption('Add the case workbook and the nine lender files (offer, Key Facts Statement, schedule of charges) in one go');
      await page.setInputFiles('#new-docs', [workbook('01-director-route'), ...lenderFiles('01-director-route')]); await sleep(2500);
      await page.getByRole('button', { name: 'Create case' }).click(); await page.waitForURL(/\/case\//); await settle(3500);
      id01 = (page.url().match(/id=(CA-\d{4}-\d{4})/) || [])[1];
      await caption('Every file is checked field by field; documents are data, never instructions'); await scroll(600, 2);
      await tab('Workflow'); await caption('Run: preparer check, funding need, lender comparison, accuracy check, routing');
      await page.getByRole('button', { name: /^(Run|Run again)$/ }).click();
      await page.waitForFunction(() => /Accuracy check: passed|Waiting for the routed approver/.test(document.body.innerText), null, { timeout: 300000 }); await settle(2500);
      await caption('All five steps passed: need ₹1,42,00,000, routed to the Director'); await scroll(650, 3);
      await tab('Funding gap'); await caption('Week-by-week cash: the funding need is calculated, not the amount requested'); await scroll(650, 3);
      await tab('Lender offers'); await caption('Offers priced at their true yearly cost: Brahmaputra first; a hidden charge flagged on Aravali; Chambal cannot be afforded'); await scroll(650, 3);
      await tab('Report'); await caption('The proposal report: every figure traceable to its source'); await scroll(650, 3);
    });

    await scene('copilot', async () => {
      await card('2 · Ask CredAssure', modelOn ? 'The copilot answers from the case, the policies and the regulations, with citations a person can open; a Critic checks every answer.' : 'The model is off in this recording, so the copilot shows its fixed reply.');
      await tab('Ask CredAssure'); await caption('Ask CredAssure on the case');
      if (await page.getByRole('button', { name: 'I understand' }).count()) { await page.getByRole('button', { name: 'I understand' }).click(); await sleep(1200); }
      for (const q of ['Why is Brahmaputra Industrial Bank ranked first?', 'Who has to approve this proposal, and why?', 'What must a lender disclose in the Key Facts Statement?']) { await caption(`Question: ${q}`); await ask(q); await scroll(500, 2); }
      await nav('Dashboard'); await caption('Ask CredAssure is also on every page, for product help');
      await page.getByRole('button', { name: 'Ask CredAssure' }).last().click(); await page.waitForSelector('#ask-anywhere'); await sleep(1200);
      await ask('How do I answer a question card on a case?', '#ask-anywhere'); await sleep(2000);
      await page.keyboard.press('Escape'); await sleep(800);
    });

    await scene('question card', async () => {
      await card('3 · When a step needs something', 'A missing schedule of charges stops the lender comparison with one plain question. Answer it on the card and press Continue.');
      await openCase(C['04-missing-schedule-question']); await caption('The lender comparison asks for one document');
      await page.locator('input[type=file][accept=".json,.md"]').first().setInputFiles(path.join(PACK, '04-missing-schedule-question', 'answer-the-question', 'KFS-OF-02-B-v1-SCH.md')); await sleep(2500);
      await caption('Continue re-runs only the step that stopped'); await page.getByRole('button', { name: 'Continue' }).click();
      await page.waitForFunction(() => /Accuracy check: passed|Waiting for the routed approver/.test(document.body.innerText), null, { timeout: 300000 }); await settle(2500);
      await caption('Passed: need ₹1,10,00,000, routed to the Director'); await scroll(600, 2);
      await openCase(C['09-injection-in-lender-document']); await tab('History');
      await caption('Scenario 09: two schedules hide instructions to the AI; they are flagged and ignored, never followed'); await scroll(600, 2);
    });

    await scene('negotiation', async () => {
      await card('4 · Negotiation and a stale report', 'A negotiation round changes the ranking, so the report must be regenerated before anyone can approve it.');
      await openCase(C['02-vp-route-negotiation']); await tab('Lender offers'); await caption('Need ₹1,75,00,000: above ₹1.5 crore, so the VP decides');
      await page.getByRole('button', { name: /Start negotiation round|Run next negotiation round/ }).click(); await settle(5000);
      await caption('Round 1, fee waiver: Falgu Merchant Bank moves to first'); await scroll(650, 3);
      await tab('Report'); await caption('The report is now stale: the preparer creates a new version');
      await page.getByRole('button', { name: 'Create new version' }).click(); await settle(4000);
      await signOut();
    });

    await scene('director', async () => {
      await card('5 · Director, Finance', 'Decides proposals below ₹1.5 crore. Approval is internal; it never accepts a loan.');
      await signIn(U.dir); await nav('Approval inbox'); await caption('The Director sees only cases routed to the Director');
      if (id01) { await decide(U.dir, id01, 'Approve proposal', 'Brahmaputra is cheapest at true cost; repayments fit the cash flow.'); await caption('Approved: recorded with the approver, time and comment'); }
      await openCase(C['08-no-loan-needed']); await tab('Review & approval');
      await caption('Scenario 08: no loan needed. Approving confirms that no new facility is sought'); await sleep(3500);
      await signOut();
    });

    await scene('vp', async () => {
      await card('6 · VP, Finance', 'Decides above ₹1.5 crore, and cases held at exactly ₹1.5 crore, with a password and a fresh code.');
      await signIn(U.vp); await nav('Approval inbox');
      await decide(U.vp, C['02-vp-route-negotiation'], 'Approve proposal', 'Falgu after the fee waiver; ranking and affordability checked.');
      await caption('Approved above ₹1.5 crore after the step-up check');
      await decide(U.vp, C['03-held-exactly-1-5-crore'], 'Approve proposal', 'Held at exactly ₹1.5 crore: decided by the VP.');
      await caption('The held case is decided by the VP; the Director cannot act on it'); await sleep(2000);
      await signOut();
    });

    await scene('evaluator', async () => {
      await card('7 · Evaluator', 'Reads every case, the audit log and the safety events. Changes nothing.');
      await signIn(U.ev); await nav('Cases'); await caption('Every case, read only');
      if (id01) { await openCase(id01); await tab('History'); await caption('The technical audit log: every event in a verified hash chain'); await scroll(650, 3); }
      await nav('Evaluation').catch(() => {}); await caption('The evaluation scorecard'); await scroll(650, 2);
      await signOut();
    });

    await card('The model reads and drafts. Code calculates, checks and routes. A person approves.', 'Synthetic data and simulated lenders only. github.com/pcpdevmob/credAssureProject', 6000);
  } finally {
    const video = page.video(); await ctx.close();
    if (video) { const dest = path.join(OUT, 'CredAssure_Walkthrough.webm'); await video.saveAs(dest); await video.delete().catch(() => {}); console.log('video:', dest); }
    await browser.close();
  }
})().catch(e => { console.error(e.stack || String(e)); process.exit(1); });
