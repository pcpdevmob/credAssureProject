// U1 screenshots (light, dark, 360 px) and axe on the signed-in screens, against the live gateway and the demo case
// that demo-case.setup.ts just ran. The token lives in memory only, so the test signs in once and navigates by clicking.
import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { DEMO_FILE, E2E_USERNAME, e2ePassword } from './credentials';

const OUT = join(__dirname, '__screenshots__/u1');
const MODES = [
  { name: 'light', width: 1280, height: 860, scheme: 'light' as const },
  { name: 'dark', width: 1280, height: 860, scheme: 'dark' as const },
  { name: '360', width: 360, height: 780, scheme: 'light' as const },
];

async function capture(page: Page, screen: string, fullPage = true) {
  for (const m of MODES) {
    await page.setViewportSize({ width: m.width, height: m.height });
    await page.emulateMedia({ colorScheme: m.scheme, reducedMotion: 'reduce' });
    await page.waitForTimeout(700); // shell fade-in and drawer slide settle
    await page.screenshot({ path: join(OUT, `${screen}-${m.name}.png`), fullPage });
    const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    const bad = violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
      .map(v => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(' | ')}`);
    expect.soft(bad, `axe on ${screen}-${m.name}`).toEqual([]);
  }
  await page.setViewportSize({ width: 1280, height: 860 });
}

test('U1 signed-in screens', async ({ page }) => {
  const { caseId } = JSON.parse(readFileSync(DEMO_FILE, 'utf8')) as { caseId: string };
  await page.setViewportSize({ width: 1280, height: 860 });
  await page.goto('/login/');
  await expect(page).toHaveTitle(/Sign in · CredAssure/);
  await page.getByLabel('Username').fill(E2E_USERNAME);
  await page.getByLabel('Password').fill(e2ePassword());
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard/');
  await expect(page.getByText('CredAssure').first()).toBeVisible();
  await capture(page, 'dashboard');

  await page.getByRole('link', { name: 'Cases', exact: true }).click();
  await page.waitForURL('**/cases/');
  await page.getByRole('link', { name: caseId }).first().click();
  await page.waitForURL(`**/case/?id=${caseId}*`);
  await expect(page.getByRole('heading', { name: 'Demo Electronics Pvt Ltd' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Requested amount: ₹2,00,00,000, source not available yet' })).toBeVisible(); // BRD App. A
  await capture(page, 'case-workflow');

  await page.getByRole('button', { name: 'Funding gap' }).click();
  const need = page.getByRole('button', { name: 'Validated funding need: ₹1,42,00,000, show source' });
  await expect(need).toBeVisible();
  await capture(page, 'case-funding');

  await need.click();
  const drawer = page.getByRole('dialog');
  await expect(drawer.getByText('wc.recommended_amount · v')).toBeVisible();
  await expect(drawer.getByText('working_capital').first()).toBeVisible(); // producer recorded by the fresh run
  await capture(page, 'provenance-drawer', false);
  await page.keyboard.press('Escape');
  await expect(need).toBeFocused();

  await page.goto('/__gallery/');
  await expect(page.getByRole('heading', { name: 'Component gallery' })).toBeVisible();
  await capture(page, 'gallery');
});
