import { describe, expect, it } from 'vitest';
import { approx, factFig, inrFromPaise, paiseFromText } from '@/lib/money';

describe('inrFromPaise matches the gateway format_inr', () => {
  it.each([
    [1420000000, '₹1,42,00,000'], [0, '₹0'], [99900, '₹999'], [100000, '₹1,000'], [10000000, '₹1,00,000'],
    [105, '₹1.05'], [1050, '₹10.50'], [-1000000000, '-₹1,00,00,000'], [123456789012, '₹1,23,45,67,890.12'],
  ])('%i paise → %s', (p, s) => expect(inrFromPaise(p)).toBe(s));
  it('handles amounts beyond float precision', () => expect(inrFromPaise(9007199254740993n)).toBe('₹9,00,71,99,25,47,409.93'));
});

describe('approx: labelled lakh/crore reading, half-up', () => {
  it.each([
    [1420000000, '≈ ₹1.42 Cr'], [1424999900, '≈ ₹1.42 Cr'], [1425000000, '≈ ₹1.43 Cr'], [1000000000, '≈ ₹1.00 Cr'],
    [999999900, '≈ ₹100.00 L'], [425000000, '≈ ₹42.50 L'], [10000000, '≈ ₹1.00 L'], [-1420000000, '≈ -₹1.42 Cr'],
    [1234500000000, '≈ ₹1,234.50 Cr'],
  ])('%i → %s', (p, s) => expect(approx(p)).toBe(s));
  it('is null below ₹1 lakh', () => expect(approx(9999999)).toBeNull());
});

describe('paiseFromText reads ledger decimal text without floats', () => {
  it.each([['14200000', 1420000000n], ['1234.5', 123450n], ['0.105', 11n], ['0.104', 10n], ['-10.05', -1005n], [' 7 ', 700n]])('%s', (t, p) => expect(paiseFromText(t)).toBe(p));
  it.each(['', 'abc', '1e5', '1,000', '₹10'])('rejects %j', t => expect(paiseFromText(t)).toBeNull());
});

it('factFig keeps the ledger key and falls back to the raw text', () => {
  const facts = [{ key: 'wc.peak_shortfall', value: '16200000' }, { key: 'wc.peak_week', value: 'nine' }];
  expect(factFig(facts, 'wc.peak_shortfall')).toEqual({ display: '₹1,62,00,000', paise: 1620000000, key: 'wc.peak_shortfall' });
  expect(factFig(facts, 'wc.peak_week')).toEqual({ display: 'nine', key: 'wc.peak_week' });
  expect(factFig(facts, 'missing')).toBeUndefined();
});
