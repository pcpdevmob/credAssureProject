// Prints the e2e-report HTML to PDF with Playwright's Chromium: node scripts/e2e_report_pdf.cjs <in.html> <out.pdf>
// Uses branded Chrome when installed (as the e2e specs do), else Playwright's own Chromium
// (npx playwright install chromium); PW_CHROMIUM=<path> picks another executable.
const { chromium } = require('@playwright/test');
const { pathToFileURL } = require('node:url');
const [input, output] = process.argv.slice(2);
(async () => {
  const tries = process.env.PW_CHROMIUM ? [{ executablePath: process.env.PW_CHROMIUM }] : [{ channel: 'chrome' }, {}];
  let browser, last;
  for (const opts of tries) {
    try { browser = await chromium.launch(opts); break; } catch (e) { last = e; }
  }
  if (!browser) { console.error(String(last).split('\n')[0]); process.exit(1); }
  const page = await browser.newPage();
  await page.goto(pathToFileURL(input).href);
  await page.pdf({ path: output, format: 'A4', printBackground: true, margin: { top: '12mm', bottom: '12mm', left: '10mm', right: '10mm' } });
  await browser.close();
})().catch(e => { console.error(String(e).split('\n')[0]); process.exit(1); });
