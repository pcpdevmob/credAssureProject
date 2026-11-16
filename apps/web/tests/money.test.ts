import { describe, expect, it } from 'vitest';
import { approx, factFig, inrFromPaise, paiseFromInput, paiseFromText } from '@/lib/money';

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

describe('paiseFromInput: the one rupees → paise conversion for every money field', () => {
  it.each([
    ['₹1,42,00,000', 1420000000n], ['1,42,00,000/-', 1420000000n], ['₹ 1,42,00,000 /-', 1420000000n], ['14200000', 1420000000n],
    ['14,200,000', 1420000000n], ['142 lakh', 1420000000n], ['142L', 1420000000n], ['Rs. 142L', 1420000000n], ['1.42 crore', 1420000000n],
    ['1.42 Cr', 1420000000n], ['2 crore', 2000000000n], ['₹3,20,00,000', 3200000000n], ['14200000.50', 1420000050n], ['0.5 lakh', 5000000n],
    ['1.2345678 crore', 1234567800n], ['10 Lakhs', 100000000n], ['rs 1,000', 100000n],
  ])('%s → %s paise', (t, p) => expect(paiseFromInput(t)).toBe(p));
  it.each(['', 'abc', '-5', '1e7', '1.234', '1.2345678901 crore', '1,4,2', '₹', '12 lakh crore', '1.42.0'])('rejects %j', t => expect(paiseFromInput(t)).toBeNull());
  it('round-trips the display string', () => { for (const p of [0n, 105n, 1420000000n, 123456789012n]) expect(paiseFromInput(inrFromPaise(p))).toBe(p); });
});
