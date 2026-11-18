// U6 budget: initial JS per exported route, gzip, must stay ≤ 250 kB (plan v3.4 §6). Run after `next build`.
// Initial = every module <script src> in the route's HTML (lazy chunks such as the 3D hero and the cash chart are not counted).
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { join, relative } from 'node:path';

const OUT = new URL('../out/', import.meta.url).pathname;
const LIMIT_KB = Number(process.env.JS_BUDGET_KB || 250);
const pages = [];
(function walk(d) { for (const f of readdirSync(d)) { const p = join(d, f); if (statSync(p).isDirectory()) { if (f !== '_next') walk(p); } else if (f === 'index.html') pages.push(p); } })(OUT);
const size = new Map();
const gz = src => { if (!size.has(src)) size.set(src, gzipSync(readFileSync(join(OUT, src.replace(/^\//, '')))).length); return size.get(src); };
let worst = 0; const rows = [];
for (const p of pages) {
  const srcs = [...new Set([...readFileSync(p, 'utf8').matchAll(/<script([^>]*)>/g)].filter(m => !/\bnoModule\b/i.test(m[1])) // polyfills load only in pre-module browsers
    .map(m => /src="([^"]+\.js)"/.exec(m[1])?.[1]).filter(s => s?.startsWith('/_next/')))];
  const kb = srcs.reduce((n, s) => n + gz(s), 0) / 1024;
  worst = Math.max(worst, kb);
  rows.push(`${('/' + relative(OUT, p).replace(/index\.html$/, '')).padEnd(22)} ${kb.toFixed(1).padStart(7)} kB  (${srcs.length} scripts)`);
}
console.log(rows.sort().join('\n'));
if (!pages.length) { console.error('no exported pages in out/; run next build first'); process.exit(2); }
console.log(`initial JS budget ${LIMIT_KB} kB gzip: worst route ${worst.toFixed(1)} kB → ${worst <= LIMIT_KB ? 'PASS' : 'FAIL'}`);
process.exit(worst <= LIMIT_KB ? 0 : 1);
