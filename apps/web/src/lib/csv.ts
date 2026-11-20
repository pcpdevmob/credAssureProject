// CSV export cells (ADR 0030 §6, OWASP CSV injection): a cell that starts with = + - @ (or a tab or
// carriage return) is prefixed with an apostrophe so a spreadsheet shows it as text and never runs
// it as a formula. Every cell is quoted and inner quotes are doubled.
const FORMULA_START = /^[=+\-@\t\r]/;

export function csvCell(value: unknown): string {
  let s = String(value ?? '');
  if (FORMULA_START.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
}

export function toCsv(rows: unknown[][]): string {
  return rows.map(r => r.map(csvCell).join(',')).join('\n');
}
