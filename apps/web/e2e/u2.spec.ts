// U2: the preparer flow through the UI only, against the live gateway: create the demo case (BRD App. A) with typed money,
// upload its seven files (one first rejected with field/row/reason, opening_position first without min_cash_buffer),
// run with live progress, answer the stage's one question by re-uploading, resume, then the Director approves with the
// step-up confirm. The API is used only to read back the dashboard totals the screen must show.
import { expect, test, type Page } from '@playwright/test';
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { E2E_USERNAME, e2ePassword } from './credentials';
import { capture as shot, signIn } from './shot';

const API = process.env.E2E_API_URL || 'http://localhost:8000';
const FROZEN = join(__dirname, '../../../data/frozen/v1');
const CASE_DIR = join(FROZEN, 'cases/CA-2026-0001');
const DIRECTOR = process.env.E2E_DIRECTOR || 'demo.director';
const KINDS = ['order', 'opening_position', 'costs', 'receipts', 'receivables', 'payables', 'inventory'];
const capture = (page: Page, screen: string, fullPage = true) => shot(page, 'u2', screen, fullPage);
const file = (kind: string) => join(CASE_DIR, `${kind}.${kind === 'order' || kind === 'opening_position' ? 'json' : 'csv'}`);

test.setTimeout(30 * 60_000); // two live runs on the local 8B model

test('U2 preparer flow, question and resume, Director approval', async ({ page, request }, info) => {
  await page.setViewportSize({ width: 1280, height: 860 });
  await signIn(page, E2E_USERNAME, e2ePassword());

  // Create case: money typed as a person would, read back before submit.
  await page.getByRole('link', { name: 'New case' }).first().click();
  await page.waitForURL('**/cases/new/');
  await page.getByLabel('MSME legal name').fill('Demo Electronics Pvt Ltd');
  await page.getByLabel('PO reference').fill('PO-CA-2026-0001');
  await page.getByLabel('Order value').fill('₹3,20,00,000/-');
  await expect(page.getByText('Reads as ₹3,20,00,000')).toBeVisible();
  await page.getByLabel('Requested amount').fill('2 crore');
  await expect(page.getByText('Reads as ₹2,00,00,000')).toBeVisible();
  await page.getByLabel('Customer due date').fill('2027-05-15');
  await capture(page, 'create-case');
  await page.getByRole('button', { name: 'Create case' }).click();
  await page.waitForURL('**/case/?id=*&tab=documents');
  const caseId = new URL(page.url()).searchParams.get('id')!;
  expect(caseId).toMatch(/^CA-\d{4}-\d{4}$/);

  // A broken file is rejected with field, row and reason.
  await page.locator('#upload-costs').setInputFiles({ name: 'costs.csv', mimeType: 'text/csv', buffer: Buffer.from('week,category,amount\n1,components,not-a-number\n') });
  const rejected = page.getByRole('alert').filter({ hasText: 'costs.csv was rejected' });
  await expect(rejected).toBeVisible();
  await expect(rejected.getByRole('listitem').first()).toContainText(/Row \d+ · .*amount/);
  await capture(page, 'documents-rejected');

  // The seven files; opening_position deliberately without the minimum cash buffer.
  const opening = JSON.parse(readFileSync(file('opening_position'), 'utf8')); delete opening.min_cash_buffer;
  const noBuffer = info.outputPath('opening_position.json'); writeFileSync(noBuffer, JSON.stringify(opening));
  for (const kind of KINDS) {
    await page.locator(`#upload-${kind}`).setInputFiles(kind === 'opening_position' ? noBuffer : file(kind));
    await expect(page.getByText(new RegExp(`^${kind}\\.(json|csv) accepted`))).toBeVisible();
  }
  const offersDir = join(FROZEN, 'offers/CA-2026-0001');
  const offerFiles = readdirSync(offersDir).filter(f => f.endsWith('.v1.json')).sort().flatMap(f => {
    const doc: string = JSON.parse(readFileSync(join(offersDir, f), 'utf8')).kfs_doc_id;
    return [join(offersDir, f), join(FROZEN, 'kfs', `${doc}.md`), join(FROZEN, 'kfs', `${doc}-SCH.md`)];
  });
  await page.locator('#upload-offers').setInputFiles(offerFiles);
  await expect(page.getByText(/ accepted · /)).toHaveCount(KINDS.length + offerFiles.length, { timeout: 60_000 });
  await capture(page, 'documents');

  // Run with live progress until the stage asks its one question.
  await page.getByRole('button', { name: 'Workflow' }).click();
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await expect(page.getByTestId('live-progress')).toContainText('Starting');
  const question = page.getByTestId('stage-question');
  await expect(question).toContainText(/min(imum)? cash buffer/i, { timeout: 10 * 60_000 });
  // The streamed stage events stay on screen as the last run's log (fast stages end in well under a second).
  await expect(page.getByText('Last run')).toBeVisible();
  await expect(page.getByTestId('live-progress')).toContainText('Employee readiness: GO');
  await expect(page.getByTestId('live-progress')).toContainText('Funding need: NEEDS_INPUT');
  await expect(page.getByText('NEEDS INPUT')).toBeVisible();
  await capture(page, 'workflow-question');

  // Answer: upload the corrected file in the question card, then resume.
  await page.locator('#upload-opening_position').setInputFiles(file('opening_position'));
  await expect(page.getByText(/^opening_position\.json accepted/)).toBeVisible();
  await page.getByRole('button', { name: 'Resume' }).click();
  await expect(page.getByText('Awaiting approval').first()).toBeVisible({ timeout: 15 * 60_000 });
  await expect(page.getByTestId('live-progress')).toContainText('Funding need: GO');
  await expect(page.getByTestId('live-progress')).not.toContainText('Employee readiness'); // resume re-ran only the blocked stage onward
  await expect(page.getByRole('button', { name: 'Validated need: ₹1,42,00,000, show source' })).toBeVisible(); // BRD App. A
  await capture(page, 'workflow-done');

  // Director: inbox → review → step-up confirm.
  await page.getByRole('button', { name: 'Sign out' }).first().click();
  await page.waitForURL('**/login/');
  await signIn(page, DIRECTOR, e2ePassword(DIRECTOR));
  await page.getByRole('link', { name: 'Approval inbox', exact: true }).first().click();
  await page.getByRole('link', { name: new RegExp(caseId) }).first().click();
  await page.waitForURL(`**/case/?id=${caseId}&tab=review`);
  await expect(page.getByText('Approval is internal, not loan acceptance.').first()).toBeVisible();
  await expect(page.getByText('Director, Finance').first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Validated funding need: ₹1,42,00,000, show source' })).toBeVisible();
  await capture(page, 'review');
  await page.getByRole('button', { name: 'Approve proposal' }).click();
  const confirm = page.getByRole('dialog');
  await expect(confirm.getByText('Approval is internal, not loan acceptance.')).toBeVisible();
  await expect(confirm.getByRole('button', { name: /Confirm: approve proposal/ })).toBeDisabled();
  await confirm.getByLabel('Type the case ID to confirm').fill(caseId);
  await capture(page, 'step-up', false);
  await confirm.getByRole('button', { name: /Confirm: approve proposal/ }).click();
  await expect(page.getByRole('status').filter({ hasText: `Proposal approved: ${caseId}.` })).toBeVisible();
  await expect(page.getByText('Approved', { exact: true }).first()).toBeVisible();

  // Dashboard shows the gateway's own totals for this user.
  const tok = await request.post(`${API}/v1/auth/token`, { data: { username: DIRECTOR, password: e2ePassword(DIRECTOR) } });
  const { totals } = await (await request.get(`${API}/v1/cases`, { headers: { Authorization: `Bearer ${(await tok.json()).access_token}` } })).json();
  await page.getByRole('link', { name: 'Dashboard', exact: true }).first().click();
  await page.waitForURL('**/dashboard/');
  await expect(page.getByRole('button', { name: `Validated funding need, all assessed cases: ${totals.validated_need.display}, source not available yet` })).toBeVisible();
  await capture(page, 'dashboard');
});
