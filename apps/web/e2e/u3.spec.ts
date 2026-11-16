// U3: funding need, offers and negotiation against the live e2e gateway (own database) and the demo case that
// demo-case.setup.ts just ran. Asserts the real figures (BRD Appendix A / gold), screenshots in three modes, axe,
// and that no screen logs a console error or a 4xx/5xx (guards the dev-overlay "Issues").
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { DEMO_FILE, E2E_USERNAME, e2ePassword } from './credentials';
import { capture as shot, signIn } from './shot';

const capture = (page: Page, screen: string) => shot(page, 'u3', screen);
// The bearer token lives in memory only, so a full page load signs out: reach every tab by clicking, as U1 does.
async function openCase(page: Page, caseId: string, tab: string) {
  if (!page.url().includes(`id=${caseId}`)) {
    await page.getByRole('link', { name: 'Cases', exact: true }).click();
    await page.waitForURL('**/cases/');
    await page.getByRole('link', { name: caseId }).first().click();
    await page.waitForURL(`**/case/?id=${caseId}*`);
  }
  await page.getByRole('button', { name: tab }).click();
}
const fig = (page: Page, name: string) => page.getByRole('button', { name }).first();

test('U3 funding, offers, negotiation', async ({ page }) => {
  const { caseId } = JSON.parse(readFileSync(DEMO_FILE, 'utf8')) as { caseId: string };
  const problems: string[] = [];
  page.on('console', m => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', r => { if (r.status() >= 400) problems.push(`${r.status()} ${r.url()}`); });
  await page.setViewportSize({ width: 1280, height: 860 });
  await signIn(page, E2E_USERNAME, e2ePassword());

  // --- Funding need
  await openCase(page, caseId, 'Funding gap');
  await expect(fig(page, 'Validated funding need: ₹1,42,00,000, show source')).toBeVisible();
  await expect(fig(page, 'Requested amount: ₹2,00,00,000, source not available yet')).toBeVisible();
  await expect(fig(page, 'Peak cash shortfall (week 9): ₹1,62,00,000, show source')).toBeVisible();
  await expect(fig(page, 'Plus: minimum cash buffer: ₹10,00,000, show source')).toBeVisible();
  await expect(fig(page, 'Less: undrawn credit limits: ₹30,00,000, show source')).toBeVisible();
  await expect(fig(page, 'Bridge: Indicative request: ₹2,00,00,000, show source')).toBeVisible();
  await expect(page.getByRole('img', { name: /Cash is below zero in 10 weeks.*Lowest point in week 9 \(peak shortfall ₹1,62,00,000\).*Minimum cash buffer ₹10,00,000/ })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Chart key' }).getByText('Minimum cash buffer ₹10,00,000')).toBeVisible();
  await expect(page.getByText('◆ Peak shortfall, week 9')).toBeVisible();
  await capture(page, 'funding');
  await page.getByText('Weekly cash table').click();
  await expect(page.getByRole('row', { name: /^9 .*-₹1,62,00,000.*◆ Peak shortfall/ })).toBeVisible();

  // --- Offers: the cheapest APR is unaffordable and must be impossible to miss
  await openCase(page, caseId, 'Lender offers');
  const c = page.getByRole('listitem', { name: 'Offer OF-01-C' });
  const b = page.getByRole('listitem', { name: 'Offer OF-01-B' });
  const a = page.getByRole('listitem', { name: 'Offer OF-01-A' });
  await expect(page.getByRole('alert').filter({ hasText: 'Offer OF-01-C has the lowest APR (11.87%)' })).toBeVisible();
  await expect(c.getByText('NOT RANKED')).toBeVisible();
  await expect(c.getByText('Not affordable: repayments push cash below the minimum buffer.')).toBeVisible();
  await expect(c.getByText(/^Rank \d/)).toHaveCount(0);
  await expect(b.getByText('Rank 1')).toBeVisible();
  await expect(b.getByRole('button', { name: /APR: 13\.00%/ })).toBeVisible();
  await expect(a.getByText('Rank 2')).toBeVisible();
  await expect(a.getByRole('button', { name: /APR: 17\.56%/ })).toBeVisible();
  await expect(a.getByText(/Hidden charge/)).toBeVisible();
  await capture(page, 'offers');

  // --- Negotiation: one round, then the revised offer is not re-audited until the stage re-runs
  await page.getByRole('button', { name: 'Start negotiation round' }).click();
  await expect(page.getByText('Round 1 of 1')).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText('Revised offer not re-audited').or(page.getByText('Concession verified by re-audit'))).toBeVisible();
  await capture(page, 'negotiation');

  expect(problems.filter(p => !/\/auth\/token/.test(p)), 'no console errors or failed requests on any U3 screen').toEqual([]);
});

test('U3 approver sees negotiation in progress', async ({ page }) => {
  const { caseId } = JSON.parse(readFileSync(DEMO_FILE, 'utf8')) as { caseId: string };
  await page.setViewportSize({ width: 1280, height: 860 });
  await signIn(page, process.env.E2E_DIRECTOR || 'demo.director', e2ePassword(process.env.E2E_DIRECTOR || 'demo.director'));
  await openCase(page, caseId, 'Review & approval');
  await expect(page.getByRole('list', { name: 'Negotiation status' }).getByText(/Negotiation in progress/)).toBeVisible();
  await expect(page.getByText('Approval is internal, not loan acceptance.').first()).toBeVisible();
  await shot(page, 'u3', 'approval-negotiation');
});
