// The only money formatting in the web app (design-plan §8, BR-05). Integer paise only, never floats.
// The API's `display` string is the exact figure; this module only renders it, or groups paise the same way the gateway's
// format_inr does (Indian grouping, "-₹" sign, paise digits only when non-zero), and adds the labelled "≈" short form.

/** Money as the gateway sends it. */
export type Money = { paise: number; display: string };
/** A figure on screen: the exact display string, its paise when known, and the ledger key that explains it. */
export type Fig = { display: string; paise?: number; key?: string; version?: number };

const LAKH = 100_000n * 100n; // in paise
const CRORE = 100n * LAKH;

function group(digits: string): string {
  if (digits.length <= 3) return digits;
  return `${digits.slice(0, -3).replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${digits.slice(-3)}`;
}

/** ₹ with Indian grouping from integer paise, e.g. 1420000000 → "₹1,42,00,000", 105 → "₹1.05". */
export function inrFromPaise(paise: number | bigint): string {
  let p = BigInt(paise);
  const sign = p < 0n ? '-' : '';
  if (p < 0n) p = -p;
  const frac = p % 100n;
  return `${sign}₹${group((p / 100n).toString())}${frac ? `.${frac.toString().padStart(2, '0')}` : ''}`;
}

/** Decimal rupee text from the ledger ("14200000", "1234.5", "-10.05") → paise, half-up past two places. Null if not a number. */
export function paiseFromText(text: string): bigint | null {
  const m = /^\s*(-?)(\d+)(?:\.(\d+))?\s*$/.exec(text);
  if (!m) return null;
  const frac = (m[3] ?? '').padEnd(3, '0');
  let p = BigInt(m[2]) * 100n + BigInt(frac.slice(0, 2)) + (Number(frac[2]) >= 5 ? 1n : 0n);
  if (m[1] && p !== 0n) p = -p;
  return p;
}

const UNIT: Record<string, bigint> = { '': 1n, l: 100_000n, lac: 100_000n, lakh: 100_000n, lakhs: 100_000n, cr: 10_000_000n, crore: 10_000_000n, crores: 10_000_000n };
const INPUT = /^(?:₹|rs\.?)?\s*(\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?\s*([a-z]*)\s*(?:\/-)?$/;

/**
 * What a person types in a money field → exact paise, or null. The one conversion every form uses (no `* 100` on a float).
 * Accepts ₹ / Rs., Indian or western grouping, a "/-" suffix and lakh / L / crore / Cr; rejects anything that would leave a
 * fraction of a paisa, negatives and exponents. 1420000000 paise = ₹1,42,00,000 = 142 lakh = 1.42 crore.
 */
export function paiseFromInput(text: string): bigint | null {
  const m = INPUT.exec(text.trim().toLowerCase());
  if (!m || !Object.hasOwn(UNIT, m[3])) return null;
  const frac = m[2] ?? '';
  const scale = 10n ** BigInt(frac.length);
  const num = (BigInt(m[1].replace(/,/g, '') + frac)) * UNIT[m[3]] * 100n; // paise × scale
  return num % scale === 0n ? num / scale : null;
}

/** "≈ ₹1.42 Cr" / "≈ ₹42.50 L", half-up to two places; null below ₹1 lakh. Only ever shown beside the exact amount. */
export function approx(paise: number | bigint): string | null {
  let p = BigInt(paise);
  const sign = p < 0n ? '-' : '';
  if (p < 0n) p = -p;
  const [unit, label] = p >= CRORE ? [CRORE, 'Cr'] : p >= LAKH ? [LAKH, 'L'] : [0n, ''];
  if (!unit) return null;
  const hundredths = (p * 100n + unit / 2n) / unit;
  return `≈ ${sign}₹${group((hundredths / 100n).toString())}.${(hundredths % 100n).toString().padStart(2, '0')} ${label}`;
}

/** A Fig from a gateway Money object. */
export const fig = (m: Money, key?: string): Fig => ({ display: m.display, paise: m.paise, key });

/** A Fig from a ledger fact's value text (rupees); the display string is built from paise, not from a float. */
export function factFig(facts: { key: string; value: string }[], key: string): Fig | undefined {
  const f = facts.find(x => x.key === key);
  if (!f) return undefined;
  const p = paiseFromText(f.value);
  return p === null ? { display: f.value, key } : { display: inrFromPaise(p), paise: Number(p), key };
}
