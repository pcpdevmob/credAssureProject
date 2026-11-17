// U4: Ask CredAssure, the approval inbox and the decision screen against the live e2e gateway and the demo case that
// demo-case.setup.ts ran. Works with LLM_ENABLED true or false: the chat assertions branch on the banner the gateway's
// health check produces. The decision is never confirmed here, so the case stays pending for re-runs.
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { DEMO_FILE, e2ePassword } from './credentials';
import { capture as shot, signIn } from './shot';

const capture = (page: Page, screen: string) => shot(page, 'u4', screen);
const DIRECTOR = process.env.E2E_DIRECTOR || 'demo.director';

test('U4 chat, inbox, decision, report', async ({ page }) => {
  const { caseId } = JSON.parse(readFileSync(DEMO_FILE, 'utf8')) as { caseId: string };
  const problems: string[] = [];
  page.on('console', m => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', r => { if (r.status() >= 400) problems.push(`${r.status()} ${r.url()}`); });
  await page.setViewportSize({ width: 1280, height: 860 });
  await signIn(page, DIRECTOR, e2ePassword(DIRECTOR));

  // --- Inbox: filtered to the signed-in role
  await page.getByRole('link', { name: 'Approval inbox', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Approval inbox' })).toBeVisible();
  await expect(page.getByRole('link', { name: new RegExp(caseId) })).toBeVisible();
  await capture(page, 'inbox');

  // --- Chat
  await page.getByRole('link', { name: new RegExp(caseId) }).click();
  const ready = page.waitForResponse(r => r.url().includes('/v1/health/ready'));
  await page.getByRole('button', { name: 'Ask CredAssure' }).click();
  const model = ((await (await ready).json()) as { checks: { model: string } }).checks.model;
  const off = model === 'disabled';
  if (off) await expect(page.getByText(/copilot is unavailable/)).toBeVisible();
  if (off) {
    await expect(page.getByLabel('Your question')).toBeDisabled();
  } else {
    await page.getByLabel('Your question').fill('What is a Key Facts Statement?');
    await page.getByRole('button', { name: /Ask$/ }).click();
    // A live model can be slow. Any reply (cited answer, case-fact answer or the neutral abstention) appends one turn; an empty chat or an error banner is a failure.
    await expect(page.locator('[aria-live="polite"] > div').first()).toBeVisible({ timeout: 120_000 });
    await expect(page.getByText('What is a Key Facts Statement?')).toBeVisible();
  }
  await capture(page, 'chat');

  // --- Decision screen: step-up confirm and the internal-approval statement; never confirmed here
  await page.getByRole('button', { name: 'Review & approval' }).click();
  await expect(page.getByText('Approval is internal, not loan acceptance.').first()).toBeVisible();
  await page.getByRole('radio', { name: 'Return to stage' }).check();
  await expect(page.getByRole('button', { name: 'Return to stage' })).toBeDisabled(); // comment required
  await page.getByRole('radio', { name: 'Approve proposal' }).check();
  await capture(page, 'decision');
  await page.getByRole('button', { name: 'Approve proposal' }).click();
  await expect(page.getByRole('button', { name: /^Confirm/ })).toBeDisabled(); // type the case ID first
  await page.keyboard.press('Escape');

  // --- Report and figures
  await page.getByRole('button', { name: 'Report' }).click();
  await expect(page.getByRole('heading', { name: 'Proposal report' })).toBeVisible();
  await expect(page.getByRole('button', { name: /Validated funding need: ₹1,42,00,000, show source/ })).toBeVisible();
  await capture(page, 'report');
  expect(problems, problems.join('\n')).toEqual([]);
});
