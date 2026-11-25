// Case-data forms (UI-02, UI thread 20 Nov): the seven case files as forms and tables a person fills in, so nobody edits
// CSV or JSON by hand. The form writes exactly the file the upload endpoint already accepts and the gateway validates it
// field by field as before (packages/core schemas are the authority). Nothing here calculates a figure: money text is
// converted to exact rupees with the same parser as every money field (lib/money.ts), and a percentage is a decimal shift.
import { inrFromPaise, paiseFromInput, paiseFromText } from './money';

export type FieldType = 'text' | 'money' | 'int' | 'date' | 'select' | 'bool' | 'percent' | 'intlist';
export type Field = {
  name: string; label: string; type: FieldType; help?: string;
  /** required: the upload is refused without it. needed: the funding check stops and asks for it. */
  need?: 'required' | 'needed'; options?: [string, string][]; placeholder?: string;
};
export type Table = { name: string; label: string; help: string; fields: Field[] };
export type FormDef =
  | { kind: 'order' | 'opening_position'; shape: 'form'; title: string; intro: string; fields: Field[]; tables: Table[] }
  | { kind: 'costs' | 'receipts' | 'receivables' | 'payables' | 'inventory'; shape: 'table'; title: string; intro: string; fields: Field[] };
export type Values = Record<string, string>;
export type Rows = Values[];
export type FormState = { values: Values; tables: Record<string, Rows> };

const WEEK: Field = { name: 'week', label: 'Week', type: 'int', need: 'required', help: 'Week number from the start of the plan (1 = first week).', placeholder: '1' };
const yes: [string, string][] = [['true', 'Yes'], ['false', 'No']];

export const FORMS: Record<string, FormDef> = {
  order: {
    kind: 'order', shape: 'form', title: 'Customer order', intro: 'The confirmed customer order this loan will fund.',
    fields: [
      { name: 'order_ref', label: 'Purchase order number', type: 'text', need: 'needed', placeholder: 'PO-2026-0001' },
      { name: 'customer_name', label: 'Customer name', type: 'text', need: 'required' },
      { name: 'order_value', label: 'Order value', type: 'money', need: 'needed', placeholder: '₹3,20,00,000 or 3.2 crore' },
      { name: 'po_date', label: 'Order date', type: 'date', need: 'needed' },
      { name: 'delivery_weeks', label: 'Delivery weeks', type: 'intlist', need: 'needed', help: 'The weeks in which goods are delivered, separated by commas.', placeholder: '3, 6, 9' },
      { name: 'payment_terms_days', label: 'Customer pays within (days)', type: 'int', need: 'needed', placeholder: '45' },
      { name: 'advance_pct', label: 'Advance paid by the customer (%)', type: 'percent', need: 'required', help: 'Share of the order value paid up front. Enter 10 for 10%.', placeholder: '10' },
      { name: 'enterprise_class', label: 'Business size (MSME class)', type: 'select', need: 'needed', options: [['micro', 'Micro'], ['small', 'Small'], ['medium', 'Medium']] },
      { name: 'investment', label: 'Investment in plant and machinery', type: 'money', need: 'required' },
      { name: 'turnover', label: 'Annual turnover', type: 'money', need: 'required' },
      { name: 'home_state', label: 'Home state', type: 'select', help: 'Used to pick the state rules that apply.', options: [['IN-MH', 'Maharashtra'], ['IN-GJ', 'Gujarat'], ['IN-KA', 'Karnataka'], ['IN-TN', 'Tamil Nadu'], ['IN-UP', 'Uttar Pradesh'], ['IN-TS', 'Telangana'], ['IN-DL', 'Delhi'], ['IN-HR', 'Haryana'], ['IN-WB', 'West Bengal']] },
    ],
    tables: [],
  },
  opening_position: {
    kind: 'opening_position', shape: 'form', title: 'Opening cash and credit lines', intro: 'Where the business stands at the start of the plan.',
    fields: [
      { name: 'as_of_week_start', label: 'Plan starts on', type: 'date', need: 'needed', help: 'The first day of week 1.' },
      { name: 'opening_cash', label: 'Cash in hand and in bank', type: 'money', need: 'needed' },
      { name: 'min_cash_buffer', label: 'Minimum cash to keep at all times', type: 'money', need: 'needed', help: 'Your company policy. The funding need includes it.' },
    ],
    tables: [
      { name: 'credit_lines', label: 'Existing credit lines', help: 'Loans and overdrafts the business already has. Unused overdraft reduces the new loan needed.', fields: [
        { name: 'lender', label: 'Lender', type: 'text', need: 'required' },
        { name: 'type', label: 'Type', type: 'select', need: 'required', options: [['overdraft', 'Overdraft'], ['cash_credit', 'Cash credit'], ['term_loan', 'Term loan']] },
        { name: 'sanctioned', label: 'Limit sanctioned', type: 'money', need: 'required' },
        { name: 'drawn', label: 'Amount used', type: 'money', need: 'required' },
      ] },
      { name: 'confirmed_mitigations', label: 'Confirmed extra funds (optional)', help: 'Money already promised for the order, such as owner funds. Each needs a reference to its evidence.', fields: [
        { name: 'type', label: 'What it is', type: 'select', need: 'required', options: [['promoter_infusion', 'Owner / promoter funds'], ['asset_sale', 'Asset sale'], ['other', 'Other']] },
        { name: 'amount', label: 'Amount', type: 'money', need: 'required' },
        { name: 'week', label: 'Arrives in week', type: 'int', need: 'required' },
        { name: 'evidence_ref', label: 'Evidence reference', type: 'text', need: 'required', placeholder: 'Board resolution 12/2026' },
      ] },
    ],
  },
  costs: {
    kind: 'costs', shape: 'table', title: 'Weekly costs', intro: 'What the business pays out for this order, week by week.',
    fields: [WEEK, { name: 'category', label: 'Cost type', type: 'select', need: 'required', options: [['components', 'Components'], ['labour', 'Labour'], ['testing', 'Testing'], ['packaging', 'Packaging'], ['logistics', 'Logistics'], ['overheads', 'Overheads']] },
      { name: 'amount', label: 'Amount', type: 'money', need: 'required' }],
  },
  receipts: {
    kind: 'receipts', shape: 'table', title: 'Expected receipts', intro: 'Money the business expects to receive. Only confirmed receipts count towards the plan.',
    fields: [WEEK, { name: 'source', label: 'From', type: 'select', need: 'required', options: [['order_advance', 'Order advance'], ['order_milestone', 'Order milestone payment'], ['other_customer', 'Another customer']] },
      { name: 'amount', label: 'Amount', type: 'money', need: 'required' }, { name: 'confirmed', label: 'Confirmed?', type: 'bool', need: 'required', options: yes }],
  },
  receivables: {
    kind: 'receivables', shape: 'table', title: 'Customer invoices due', intro: 'Invoices already raised that customers still have to pay.',
    fields: [{ name: 'invoice_id', label: 'Invoice number', type: 'text', need: 'required' }, { name: 'customer', label: 'Customer', type: 'text', need: 'required' },
      { name: 'amount', label: 'Amount', type: 'money', need: 'required' }, { name: 'due_week', label: 'Due in week', type: 'int', need: 'required' },
      { name: 'expected_week', label: 'Expected in week', type: 'int', need: 'required', help: 'When you realistically expect the money.' }],
  },
  payables: {
    kind: 'payables', shape: 'table', title: 'Supplier bills', intro: 'Bills the business has to pay suppliers.',
    fields: [{ name: 'bill_id', label: 'Bill number', type: 'text', need: 'required' }, { name: 'supplier', label: 'Supplier', type: 'text', need: 'required' },
      { name: 'amount', label: 'Amount', type: 'money', need: 'required' }, { name: 'bill_week', label: 'Billed in week', type: 'int' },
      { name: 'due_week', label: 'Due in week', type: 'int', need: 'required' }, { name: 'msme_supplier', label: 'Supplier is a micro or small business?', type: 'bool', need: 'required', options: yes, help: 'By law these must be paid within 45 days.' }],
  },
  inventory: {
    kind: 'inventory', shape: 'table', title: 'Stock movement', intro: 'The value of stock held, bought and used each week.',
    fields: [WEEK, { name: 'opening_value', label: 'Opening stock', type: 'money', need: 'required' }, { name: 'purchases', label: 'Bought', type: 'money', need: 'required' },
      { name: 'consumption', label: 'Used', type: 'money', need: 'required' }, { name: 'closing_value', label: 'Closing stock', type: 'money', need: 'required' }],
  },
};

// ---- conversion: stored payload → what the person sees ----
/** "0.1" → "10"; "0.125" → "12.5". String decimal shift, no float arithmetic. */
export function percentFromFraction(text: string): string {
  const m = /^(-?)(\d*)(?:\.(\d*))?$/.exec(text.trim()); if (!m) return text;
  const f = (m[3] ?? '').padEnd(2, '0');
  const int = ((m[2] || '0') + f.slice(0, 2)).replace(/^0+(?=\d)/, ''); const frac = f.slice(2).replace(/0+$/, '');
  return `${m[1]}${int}${frac ? '.' + frac : ''}`;
}
/** "10" → "0.1"; "12.5" → "0.125". Null when it is not a plain number. */
export function fractionFromPercent(text: string): string | null {
  const m = /^\s*(\d+)(?:\.(\d+))?\s*%?\s*$/.exec(text); if (!m) return null;
  const whole = m[1].padStart(3, '0'); const frac = (m[2] ?? '');
  const out = `${whole.slice(0, -2).replace(/^0+(?=\d)/, '')}.${whole.slice(-2)}${frac}`.replace(/\.?0+$/, '');
  return out || '0';
}
const shown = (f: Field, v: unknown): string => {
  if (v === null || v === undefined) return '';
  if (f.type === 'money') { const p = paiseFromText(String(v)); return p === null ? String(v) : inrFromPaise(p); }
  if (f.type === 'percent') return percentFromFraction(String(v));
  if (f.type === 'intlist') return Array.isArray(v) ? v.join(', ') : String(v);
  if (f.type === 'bool') return String(v) === 'true' || v === true ? 'true' : 'false';
  return String(v);
};
export function stateFromStored(def: FormDef, data: unknown): FormState {
  const rowOf = (fields: Field[], o: Record<string, unknown>) => Object.fromEntries(fields.map(f => [f.name, shown(f, o[f.name])]));
  if (def.shape === 'table') return { values: {}, tables: { rows: Array.isArray(data) ? data.map(r => rowOf(def.fields, r as Record<string, unknown>)) : [] } };
  const o = (data && typeof data === 'object' ? data : {}) as Record<string, unknown>;
  return {
    values: rowOf(def.fields, o),
    tables: Object.fromEntries(def.tables.map(t => [t.name, Array.isArray(o[t.name]) ? (o[t.name] as Record<string, unknown>[]).map(r => rowOf(t.fields, r)) : []])),
  };
}
export const emptyRow = (fields: Field[]): Values => Object.fromEntries(fields.map(f => [f.name, f.type === 'select' && f.need === 'required' && f.options ? f.options[0][0] : '']));
export function blankState(def: FormDef): FormState {
  if (def.shape === 'table') return { values: {}, tables: { rows: [emptyRow(def.fields)] } };
  return { values: Object.fromEntries(def.fields.map(f => [f.name, f.name === 'home_state' ? 'IN-MH' : ''])), tables: Object.fromEntries(def.tables.map(t => [t.name, []])) };
}

// ---- conversion: what the person typed → the file the gateway validates ----
export type Problem = { path: string; row?: number; field: string; reason: string };
const rupees = (p: bigint) => `${p / 100n}${p % 100n ? '.' + (p % 100n).toString().padStart(2, '0') : ''}`;

function value(f: Field, raw: string): { v?: unknown; err?: string } {
  const t = (raw ?? '').trim();
  if (!t) return f.need === 'required' ? { err: 'Please fill this in' } : {};
  switch (f.type) {
    case 'money': { const p = paiseFromInput(t); return p === null ? { err: 'Not a valid amount (try 1,42,00,000 or 1.42 crore)' } : { v: rupees(p) }; }
    case 'int': return /^\d+$/.test(t) ? { v: Number(t) } : { err: 'Use a whole number' };
    case 'percent': { const x = fractionFromPercent(t); return x === null ? { err: 'Use a number such as 10 for 10%' } : { v: x }; }
    case 'intlist': { const parts = t.split(/[\s,;]+/).filter(Boolean); return parts.every(p => /^\d+$/.test(p)) ? { v: parts.map(Number) } : { err: 'Use week numbers separated by commas' }; }
    case 'bool': return { v: t === 'true' };
    case 'date': return /^\d{4}-\d{2}-\d{2}$/.test(t) ? { v: t } : { err: 'Pick a date' };
    default: return { v: t };
  }
}
function rowObject(fields: Field[], row: Values, path: string, n: number | undefined, problems: Problem[]) {
  const out: Record<string, unknown> = {};
  for (const f of fields) { const r = value(f, row[f.name]); if (r.err) problems.push({ path, row: n, field: f.name, reason: r.err }); else if (r.v !== undefined) out[f.name] = r.v; }
  return out;
}
/**
 * A row nobody has typed in: every field empty, or a required choice still on the option a new row starts with
 * (emptyRow). Such a row is ignored on save and replaced by pasted rows, so the starting row never blocks a save.
 */
export const isBlankRow = (fields: Field[], row: Values): boolean => {
  const start = emptyRow(fields);
  return fields.every(f => { const v = String(row[f.name] ?? '').trim(); return !v || (f.type === 'select' && v === start[f.name]); });
};
const csvQuote = (v: unknown) => { const s = String(v ?? ''); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };

/** The file text to upload, or the problems to fix first. Blank table rows are ignored. */
export function build(def: FormDef, s: FormState): { text?: string; name: string; problems: Problem[] } {
  const problems: Problem[] = [];
  if (def.shape === 'table') {
    const rows = s.tables.rows.filter(r => !isBlankRow(def.fields, r));
    const objs = rows.map((r, i) => rowObject(def.fields, r, 'rows', i + 1, problems));
    if (!rows.length) problems.push({ path: 'rows', field: '', reason: 'Add at least one row' });
    const head = def.fields.map(f => f.name);
    const text = [head.join(','), ...objs.map(o => head.map(h => csvQuote(o[h])).join(','))].join('\n') + '\n';
    return { text: problems.length ? undefined : text, name: `${def.kind}.csv`, problems };
  }
  const out: Record<string, unknown> = { schema_version: '1.0', ...(def.kind === 'order' ? { currency: 'INR' } : {}) };
  Object.assign(out, rowObject(def.fields, s.values, '', undefined, problems));
  for (const t of def.tables) out[t.name] = (s.tables[t.name] ?? []).filter(r => !isBlankRow(t.fields, r)).map((r, i) => rowObject(t.fields, r, t.name, i + 1, problems));
  return { text: problems.length ? undefined : JSON.stringify(out, null, 2), name: `${def.kind}.json`, problems };
}

/**
 * Where a gateway field error belongs on the form. CSV: row n (1-based) and the column name. JSON: "credit_lines.0.sanctioned"
 * → table credit_lines, row 1, field sanctioned; "advance_pct" → the form field.
 */
export function placeServerError(def: FormDef, e: { field?: string | null; row?: number | null; reason: string }): Problem {
  const field = e.field ?? '';
  if (def.shape === 'table') return { path: 'rows', row: e.row ?? undefined, field, reason: e.reason };
  const m = /^(\w+)\.(\d+)\.(\w+)/.exec(field);
  if (m) return { path: m[1], row: Number(m[2]) + 1, field: m[3], reason: e.reason };
  return { path: '', field: field.split('.')[0], reason: e.reason };
}

/** Rows pasted from a spreadsheet (tab-separated, as Excel and Google Sheets copy them), in column order. A header row is skipped. */
export function rowsFromPaste(fields: Field[], text: string): Values[] {
  const lines = text.replace(/\r/g, '').split('\n').filter(l => l.trim());
  const cells = lines.map(l => (l.includes('\t') ? l.split('\t') : l.split(',')).map(c => c.trim()));
  const isHeader = (c: string[]) => c.some(x => fields.some(f => f.name === x.toLowerCase() || f.label.toLowerCase() === x.toLowerCase()));
  return cells.filter((c, i) => !(i === 0 && isHeader(c))).map(c => Object.fromEntries(fields.map((f, i) => {
    let v = c[i] ?? '';
    if (f.type === 'bool') v = /^(y|yes|true|1)$/i.test(v) ? 'true' : /^(n|no|false|0)$/i.test(v) ? 'false' : v;
    if (f.type === 'select' && f.options) v = f.options.find(([k, l]) => k === v || l.toLowerCase() === v.toLowerCase())?.[0] ?? v;
    return [f.name, v];
  })));
}

// A file name ("receipts.csv") anywhere, or a bare kind only when it cannot be an ordinary word ("opening_position").
const KIND_RE = new RegExp(`\\b(?:(${Object.keys(FORMS).join('|')})\\.(?:json|csv)|(opening_position))\\b`, 'g');
/**
 * Gateway text (stage questions, blockers, narratives) with file and field names replaced by the names on the forms:
 * "min_cash_buffer is missing from opening_position." → "minimum cash to keep at all times is missing from “Opening cash and credit lines”."
 */
export function plainText(text: string): string {
  let out = text.replace(/Please upload (\w+)\.(?:json|csv) with it filled in\.?/g, (_, k: string) => `Please add it in “${FORMS[k]?.title ?? k}”.`)
    .replace(/upload a corrected (\w+)\.(?:json|csv)/gi, (_, k: string) => `correct “${FORMS[k]?.title ?? k}”`)
    .replace(/\bmin cash buffer\b/gi, 'minimum cash buffer');
  for (const def of Object.values(FORMS)) for (const f of [...def.fields, ...(def.shape === 'form' ? def.tables : [])])
    if (f.name.includes('_')) out = out.replace(new RegExp(`\\b${f.name}\\b`, 'g'), f.label.toLowerCase());
  return out.replace(KIND_RE, (_, a?: string, b?: string) => `“${FORMS[(a ?? b)!].title}”`);
}

/** Pydantic and upload messages in plain words; anything unknown is shown as the server wrote it. */
export function plainReason(reason: string): string {
  const r = reason.toLowerCase();
  if (r.includes('field required') || r === 'missing column') return 'This is required';
  if (r.includes('valid integer')) return 'Use a whole number';
  if (r.includes('valid decimal') || r.includes('valid number')) return 'Use an amount such as 1,42,000 or 1.42 lakh';
  if (r.includes('valid boolean')) return 'Choose Yes or No';
  if (r.includes('valid date')) return 'Use a date such as 2026-11-16';
  if (r.startsWith('input should be ')) return 'Choose one of the listed options';
  if (r.includes('string should match pattern')) return 'Not in the expected format';
  if (r.includes('personal identifier') || r.includes('number not allowed')) return 'Remove the personal ID number (PAN, Aadhaar or bank account); it is never stored';
  if (r.includes('may not start with')) return 'Text may not start with = + - or @';
  return reason;
}

