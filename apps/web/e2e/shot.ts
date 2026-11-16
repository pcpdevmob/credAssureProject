// Screenshots in light, dark and 360 px, each checked with axe (WCAG 2.2 AA, no serious or critical violations).
import { expect, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { join } from 'node:path';

const MODES = [
  { name: 'light', width: 1280, height: 860, scheme: 'light' as const },
  { name: 'dark', width: 1280, height: 860, scheme: 'dark' as const },
  { name: '360', width: 360, height: 780, scheme: 'light' as const },
];

export async function capture(page: Page, dir: string, screen: string, fullPage = true) {
  for (const m of MODES) {
    await page.setViewportSize({ width: m.width, height: m.height });
    await page.emulateMedia({ colorScheme: m.scheme, reducedMotion: 'reduce' });
    await page.waitForTimeout(700); // shell fade-in and drawer slide settle
    await page.screenshot({ path: join(__dirname, '__screenshots__', dir, `${screen}-${m.name}.png`), fullPage });
    const { violations } = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    const bad = violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
      .map(v => `${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map(n => n.target.join(' ')).join(' | ')}`);
    expect.soft(bad, `axe on ${screen}-${m.name}`).toEqual([]);
  }
  await page.setViewportSize({ width: 1280, height: 860 });
}

export async function signIn(page: Page, username: string, password: string) {
  await page.goto('/login/');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('**/dashboard/');
}
