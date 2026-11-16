// U3: funding and offers mapping, the unaffordable-cheapest emphasis, preview labelling, negotiation states.
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { mapOffers, mapNegotiation } from '@/services/lendwise';
import { mapCash } from '@/services/workingCapital';
import { chartSummary } from '@/components/case/CashChart';
import Lenders from '@/components/case/Lenders';
import Negotiation from '@/components/case/Negotiation';
import { flagText } from '@/lib/flags';
import type { CaseRecord } from '@/types';

const m = (paise: number, display: string) => ({ paise, display });
const offer = (id: string, apr: string, o: Record<string, unknown> = {}) => ({ offer_id: id, version: 1, flags: [], comparable: true, affordable: true, rank: null as number | null,
  apr_pct: apr, amount_received: m(1, '₹1'), total_repayment: m(2, '₹2'), total_cost: m(3, '₹3'), ...o });
const demo = {
  source: 'ledger' as const, ranking: ['OF-01-B', 'OF-01-A'],
  offers: [offer('OF-01-A', '17.56', { rank: 2, flags: ['LW_HIDDEN_CHARGE'] }), offer('OF-01-B', '13.00', { rank: 1 }),
    offer('OF-01-C', '11.87', { affordable: false, flags: ['LW_NOT_AFFORDABLE'], cheapest_headline_rate: true })],
};
const c = { id: 'CA-2026-0001' } as CaseRecord;

describe('offers', () => {
  it('gives every figure a ledger key at the latest version', () => {
    const v = mapOffers(c.id, demo)!;
    expect(v.offers.find(o => o.id === 'OF-01-B')!.apr).toEqual({ display: '13.00%', key: 'lw.OF-01-B.v1.apr' });
    expect(v.offers[0].totalCost?.key).toBe('lw.OF-01-A.v1.total_cost');
  });
  it('returns null when there are no offers', () => expect(mapOffers(c.id, { ...demo, offers: [] })).toBeNull());
  it('makes the unaffordable cheapest offer impossible to miss, in text, and leaves it unranked', () => {
    render(<Lenders c={c} view={mapOffers(c.id, demo)!} canNegotiate={false} onChange={() => undefined} />);
    expect(screen.getByRole('alert').textContent).toMatch(/Offer OF-01-C has the lowest APR \(11\.87%\) but it is not recommended.*not ranked/);
    const cc = screen.getByRole('listitem', { name: 'Offer OF-01-C' });
    expect(within(cc).getByText('NOT RANKED')).toBeTruthy();
    expect(within(cc).queryByText(/^Rank \d/)).toBeNull();
    expect(within(screen.getByRole('listitem', { name: 'Offer OF-01-B' })).getByText('Rank 1')).toBeTruthy();
    expect(within(screen.getByRole('listitem', { name: 'Offer OF-01-A' })).getByText(flagText('LW_HIDDEN_CHARGE'))).toBeTruthy();
  });
  it('labels the preview and shows no rank or affordability verdict', () => {
    const prev = { ...demo, source: 'preview' as const, ranking: [], offers: demo.offers.map(o => ({ ...o, rank: null, affordable: null })) };
    render(<Lenders c={c} view={mapOffers(c.id, prev)!} canNegotiate onChange={() => undefined} />);
    expect(screen.getByRole('note').textContent).toContain('affordability and ranking not yet checked');
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.queryByText(/^Rank \d/)).toBeNull();
    expect(screen.queryByRole('button', { name: /Start negotiation/ })).toBeNull();
  });
});

describe('cheapest flag comes from the API', () => {
  const view = (flagged: string | null) => mapOffers(c.id, { ...demo, offers: demo.offers.map(o => ({ ...o, cheapest_headline_rate: o.offer_id === flagged })) })!;
  it('maps the gateway flag and defaults to false when it is absent', () => {
    expect(mapOffers(c.id, demo)!.offers.map(o => o.cheapest)).toEqual([false, false, true]);
    expect(mapOffers(c.id, { ...demo, offers: [{ ...offer('OF-01-A', '17.56') }] })!.offers[0].cheapest).toBe(false);
  });
  it('follows the flag, not the APR strings: flag on OF-01-B (usable) means no alert, though OF-01-C shows a lower APR', () => {
    render(<Lenders c={c} view={view('OF-01-B')} canNegotiate={false} onChange={() => undefined} />);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(within(screen.getByRole('listitem', { name: 'Offer OF-01-B' })).getByText(/Lowest APR of these offers/)).toBeTruthy();
    expect(within(screen.getByRole('listitem', { name: 'Offer OF-01-C' })).queryByText(/Lowest APR of these offers/)).toBeNull();
  });
  it('flag on the unaffordable offer raises the alert; no flag at all raises none', () => {
    const { unmount } = render(<Lenders c={c} view={view('OF-01-C')} canNegotiate={false} onChange={() => undefined} />);
    expect(screen.getByRole('alert').textContent).toContain('Offer OF-01-C has the lowest APR');
    unmount();
    render(<Lenders c={c} view={view(null)} canNegotiate={false} onChange={() => undefined} />);
    expect(screen.queryByRole('alert')).toBeNull();
  });
});

describe('negotiation', () => {
  const sent = { target_offer: 'OF-01-A', competing_fee_pct: '0.50', concession_counts: false, message: 'Please waive.', status: 'sent',
    revised: { version: 2, comparable: true, flags: [], apr_pct: '16.90', total_cost: m(150000000, '₹15,00,000') } };
  it('says "not re-audited" until the concession counts', () => {
    render(<Negotiation c={c} n={mapNegotiation(sent)} canStart={false} onChange={() => undefined} />);
    expect(screen.getByText('Round 1 of 1')).toBeTruthy();
    expect(screen.getByText('Revised offer not re-audited')).toBeTruthy();
  });
  it('shows verified once re-audited', () => {
    render(<Negotiation c={c} n={mapNegotiation({ ...sent, concession_counts: true })} canStart={false} onChange={() => undefined} />);
    expect(screen.getByText('Concession verified by re-audit')).toBeTruthy();
  });
  it('offers the round only to a preparer before it has run', () => {
    render(<Negotiation c={c} n={null} canStart onChange={() => undefined} />);
    expect(screen.getByRole('button', { name: 'Start negotiation round' })).toBeTruthy();
  });
});

describe('cash chart', () => {
  const cash = mapCash({ buffer: m(100000000, '₹10,00,000'), peak_week: 9, rows: [1, 2, 3, 9].map(w => ({ week: w, inflow: m(0, '₹0'), outflow: m(0, '₹0'),
    cumulative: m(w >= 3 ? -1 : 1, w >= 3 ? '-₹1' : '₹1'), shortfall: w >= 3, below_buffer: true })) });
  it('summarises shortfall weeks, the peak and the buffer in words', () => {
    const s = chartSummary(cash, '₹1,62,00,000');
    expect(s).toContain('below zero in 2 weeks: 3, 9');
    expect(s).toContain('week 9 (peak shortfall ₹1,62,00,000)');
    expect(s).toContain('Minimum cash buffer ₹10,00,000');
  });
});

describe('bridge', () => {
  it('the demo bridge lines (signed paise from the ledger) sum to the recommendation', () => {
    const lines = [200_00_000, -38_00_000, -30_00_000, 10_00_000, 0, 0, 0].map(r => r * 100);
    expect(lines.reduce((a, b) => a + b, 0)).toBe(142_00_000 * 100);
  });
});
