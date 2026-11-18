// U6 (P9): the evaluator's view of the demo story (audit chain badge, safety panel, scorecard, help centre) on the
// live e2e stack, axe-checked in light, dark and 360 px, plus reduced motion. Lighthouse runs separately (make lighthouse).
import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { DEMO_FILE, e2ePassword } from './credentials';
import { capture as shot, signIn } from './shot';

const capture = (page: Page, screen: string) => shot(page, 'u6', screen);
const EVALUATOR = process.env.E2E_EVALUATOR || 'demo.evaluator';

test('U6 evaluator story: audit, safety, scorecard, help', async ({ page }) => {
  const { caseId } = JSON.parse(readFileSync(DEMO_FILE, 'utf8')) as { caseId: string };
  const problems: string[] = [];
  page.on('console', m => { if (m.type() === 'error') problems.push(`console: ${m.text()}`); });
  page.on('response', r => { if (r.status() >= 400) problems.push(`${r.status()} ${r.url()}`); });
  await page.setViewportSize({ width: 1280, height: 860 });
  await signIn(page, EVALUATOR, e2ePassword(EVALUATOR));

  // --- The demo case: safety panel (counts and codes only), then its audit log with the hash-chain badge
  await page.goto(`/case/?id=${caseId}`);
  await page.getByRole('button', { name: 'Review & approval' }).click();
  await expect(page.getByText('Safety events').first()).toBeVisible();
  await capture(page, 'safety');
  await page.getByRole('button', { name: 'Audit', exact: true }).click();
  await expect(page.getByText(/^Hash chain verified/)).toBeVisible();
  await capture(page, 'audit');

  // --- Evaluation scorecard (an empty state is fine before `make eval` has run)
  await page.getByRole('link', { name: 'Evaluation', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Evaluation' })).toBeVisible();
  await expect(page.getByText(/No evaluation run yet|Meets ≥ 92|Target ≥ 92/).first()).toBeVisible();
  await capture(page, 'evaluation');

  // --- Help centre from docs/help
  await page.getByRole('link', { name: 'Help', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Help centre' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Help pages' }).getByRole('link').first()).toBeVisible();
  await capture(page, 'help');

  expect(problems, problems.join('\n')).toEqual([]);
});

test('U6 reduced motion stops animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/login/');
  const longest = await page.evaluate(() => Math.max(0, ...[...document.querySelectorAll('*')].map(el => {
    const s = getComputedStyle(el);
    return s.animationName === 'none' ? 0 : parseFloat(s.animationDuration) * (s.animationIterationCount === 'infinite' ? 1e6 : 1);
  })));
  expect(longest).toBeLessThan(0.01); // seconds: globals.css collapses every animation under reduce
});
