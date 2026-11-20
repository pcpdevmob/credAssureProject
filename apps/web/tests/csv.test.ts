import { describe, expect, it } from 'vitest';
import { csvCell, toCsv } from '@/lib/csv';

describe('CSV export escaping (ADR 0030 §6)', () => {
  it.each(['=1+1', '+SUM(A1)', '-2+3', '@cmd', '\t=x', '\r=x'])('neutralises formula start %s', v => {
    expect(csvCell(v).startsWith(`"'`)).toBe(true);
  });
  it('keeps ordinary values and doubles quotes', () => {
    expect(csvCell('₹1,42,00,000')).toBe('"₹1,42,00,000"');
    expect(csvCell('say "hi"')).toBe('"say ""hi"""');
    expect(csvCell(null)).toBe('""');
  });
  it('builds rows', () => {
    expect(toCsv([['a', '=b'], [1, 2]])).toBe(`"a","'=b"\n"1","2"`);
  });
});
