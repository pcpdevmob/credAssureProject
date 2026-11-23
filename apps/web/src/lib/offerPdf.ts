// ADR 0041: a lender offer read from PDFs. The gateway returns a draft (each value with the quote it came from);
// the person checks and corrects every field here, and this module turns the reviewed form into the offer JSON that
// goes through the ordinary upload check. No arithmetic on floats: money via paiseFromInput, rates by decimal shift.
import { paiseFromInput, paiseFromText, inrFromPaise } from './money';
import { fractionFromPercent, percentFromFraction } from './caseForms';

export type Quoted = { value: string | number; quote: string };
export type OfferDraft = { model: string; fields: Record<string, Quoted>; fees: (DraftFee & { quote: string })[]; dropped: number };
export type DraftFee = { name: string; timing: 'upfront' | 'monthly' | 'annual'; basis: 'fixed' | 'pct_of_principal'; value: string; gst_applicable: boolean };
export type ChargeRow = { name: string; timing: 'upfront' | 'monthly' | 'annual'; amount: string };

type Kind = 'text' | 'money' | 'percent' | 'int' | 'date' | 'select';
export type OfferField = { name: string; label: string; kind: Kind; material?: boolean; options?: [string, string][]; help?: string };

export const OFFER_FIELDS: OfferField[] = [
  { name: 'lender_name', label: 'Lender name', kind: 'text' },
  { name: 'principal', label: 'Loan amount', kind: 'money', material: true, help: 'e.g. 1.57 crore or 1,57,00,000' },
  { name: 'annual_rate', label: 'Interest rate (% a year)', kind: 'percent', material: true },
  { name: 'rate_type', label: 'Rate type', kind: 'select', material: true, options: [['', '—'], ['fixed', 'Fixed'], ['floating', 'Floating']] },
  { name: 'benchmark', label: 'Benchmark (floating rates)', kind: 'select', options: [['', 'None'], ['EBLR', 'EBLR / repo-linked'], ['MCLR', 'MCLR']] },
  { name: 'spread', label: 'Spread over benchmark (%)', kind: 'percent' },
  { name: 'tenure_months', label: 'Tenure (months)', kind: 'int', material: true },
  { name: 'moratorium_months', label: 'Moratorium (months)', kind: 'int' },
  { name: 'repayment_method', label: 'Repayment', kind: 'select', material: true, options: [['', '—'], ['emi', 'EMI (equal instalments)'], ['equal_principal', 'Equal principal']] },
  { name: 'stated_instalment', label: 'Instalment stated by the lender', kind: 'money' },
  { name: 'issue_date', label: 'Offer date', kind: 'date' },
  { name: 'disbursal_date', label: 'Disbursal date', kind: 'date', material: true },
  { name: 'first_repayment_date', label: 'First repayment date', kind: 'date', material: true },
  { name: 'insurance_premium', label: 'Insurance premium (if any)', kind: 'money' },
  { name: 'guarantee_fee', label: 'CGTMSE guarantee fee (% a year, if passed on)', kind: 'percent' },
  { name: 'prepayment_terms', label: 'Prepayment terms', kind: 'text' },
];

export type Review = {
  values: Record<string, string>;
  fees: { name: string; timing: DraftFee['timing']; basis: DraftFee['basis']; value: string; gst: boolean }[];
  insuranceFinanced: boolean; guaranteeGst: boolean; lenderType: string; noFees: boolean;
};

/** Draft (machine form) → what the person sees and edits. */
export function reviewFromDraft(d: OfferDraft | null): Review {
  const values: Record<string, string> = {};
  for (const f of OFFER_FIELDS) {
    const raw = d?.fields[f.name]?.value; if (raw === undefined || raw === null) { values[f.name] = ''; continue; }
    const s = String(raw);
    values[f.name] = f.kind === 'money' ? (paiseFromText(s) === null ? s : inrFromPaise(paiseFromText(s)!)) : f.kind === 'percent' ? percentFromFraction(s) : s;
  }
  if (!values.moratorium_months) values.moratorium_months = '0';
  const fees = (d?.fees ?? []).map(x => ({ name: x.name, timing: x.timing, basis: x.basis, gst: x.gst_applicable,
    value: x.basis === 'pct_of_principal' ? percentFromFraction(x.value) : (paiseFromText(x.value) === null ? x.value : inrFromPaise(paiseFromText(x.value)!)) }));
  return { values, fees, insuranceFinanced: false, guaranteeGst: false, lenderType: '', noFees: false };
}

const rupees = (p: bigint) => { const r = p / 100n, f = p % 100n; return f ? `${r}.${f.toString().padStart(2, '0')}` : `${r}`; };
const slug = (s: string) => s.replace(/\(.*?\)/g, '').trim().split(/[^A-Za-z0-9]+/).filter(Boolean).map(w => w[0]).join('').toUpperCase().slice(0, 8) || 'L';

export type Built = { json?: string; offerId: string; kfsDocId: string; problems: Record<string, string>; missing: string[] };

/** Reviewed form → offer JSON (schema 1.0). Problems are per field; missing material terms are allowed but listed:
 * the audit then marks the offer not comparable (LW-02, BR-06), which the person is told before saving. */
export function buildOffer(r: Review, id: string): Built {
  const offerId = `OF-${id}`, kfsDocId = `KFS-${offerId}-v1`, problems: Record<string, string> = {}, missing: string[] = [];
  const out: Record<string, unknown> = { schema_version: '1.0', lender_id: `${slug(r.values.lender_name ?? '')}-${id}`.slice(0, 40), offer_id: offerId, version: 1, product: 'wc_term_loan', kfs_doc_id: kfsDocId };
  const name = (r.values.lender_name ?? '').trim();
  if (!/^[A-Za-z][A-Za-z .,&()'-]{0,119}$/.test(name)) problems.lender_name = name ? 'Use letters and simple punctuation only' : 'Enter the lender name';
  else out.lender_name = name;
  for (const f of OFFER_FIELDS) {
    if (f.name === 'lender_name') continue;
    const v = (r.values[f.name] ?? '').trim();
    if (!v) { if (f.material) missing.push(f.label); continue; }
    let val: unknown = v;
    if (f.kind === 'money') { const p = paiseFromInput(v); if (p === null || p <= 0n) { problems[f.name] = 'Enter an amount like 1.57 crore or 1,57,00,000'; continue; } val = rupees(p); }
    if (f.kind === 'percent') { const x = fractionFromPercent(v); if (x === null) { problems[f.name] = 'Enter a percentage like 10.45'; continue; } val = x; }
    if (f.kind === 'int') { if (!/^\d{1,3}$/.test(v)) { problems[f.name] = 'Enter a whole number of months'; continue; } val = Number(v); }
    if (f.kind === 'date' && !/^\d{4}-\d{2}-\d{2}$/.test(v)) { problems[f.name] = 'Pick a date'; continue; }
    out[f.name] = val;
  }
  if (out.repayment_method) { out.repayment = { frequency: 'monthly', method: out.repayment_method }; delete out.repayment_method; }
  if (out.insurance_premium) { out.insurance = { premium: out.insurance_premium, financed: r.insuranceFinanced }; delete out.insurance_premium; }
  if (out.guarantee_fee) { out.guarantee = { scheme: 'CGTMSE', annual_fee_pct: out.guarantee_fee, basis: 'y1_guaranteed_then_outstanding', passed_to_borrower: true, gst_applicable: r.guaranteeGst }; delete out.guarantee_fee; }
  if (out.rate_type === 'fixed') { delete out.benchmark; delete out.spread; }
  if (r.lenderType) out.lender_type = r.lenderType;
  const fees: unknown[] = [];
  r.fees.forEach((x, i) => {
    const n = x.name.trim(); if (!n) { problems[`fee.${i}`] = 'Name the fee'; return; }
    const value = x.basis === 'pct_of_principal' ? fractionFromPercent(x.value) : (() => { const p = paiseFromInput(x.value); return p === null ? null : rupees(p); })();
    if (value === null) { problems[`fee.${i}`] = x.basis === 'pct_of_principal' ? 'Enter a percentage like 1.5' : 'Enter an amount like 25,000'; return; }
    fees.push({ name: n, basis: x.basis, value, timing: x.timing, gst_applicable: x.gst });
  });
  if (fees.length || r.noFees) out.fees = fees; // "no fees" only when the person says so; absent fees = missing term
  else if (!r.fees.length) missing.push('Fees');
  if (Object.keys(problems).length) return { offerId, kfsDocId, problems, missing };
  return { json: JSON.stringify(out, null, 2), offerId, kfsDocId, problems, missing };
}

/** Schedule rows as the person reviewed them; blank rows are dropped. */
export const cleanRows = (rows: ChargeRow[]) => rows.map(r => ({ ...r, name: r.name.trim(), amount: r.amount.trim() })).filter(r => r.name && r.amount);
