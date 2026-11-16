// Funding view from the gateway: recommended amount, ledger facts and the weekly cash table (WC-03/04).
// The table is requested only after a GO run, so the browser never makes the expected 404.
import type { CaseRecord, CashTable, FundingAssessment } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { factFig, fig, type Fig, type Money } from '@/lib/money';

export interface WorkingCapitalService { assess(c: CaseRecord): Promise<FundingAssessment | null> }
type Fact = { key: string; value: string; unit: string; version: number };
type Funding = { recommended_amount: Money | null; indicative_amount: Money; facts: Fact[] };
type CashResp = { buffer: Money | null; peak_week: number | null; rows: { week: number; inflow: Money; outflow: Money; cumulative: Money; shortfall: boolean; below_buffer: boolean | null }[] };
const NONE: Fig = { display: '—' };

export function mapCash(r: CashResp): CashTable {
  return { buffer: r.buffer ? fig(r.buffer, 'wc.min_buffer') : null, peakWeek: r.peak_week,
    rows: r.rows.map(x => ({ week: x.week, inflow: fig(x.inflow), outflow: fig(x.outflow), cumulative: fig(x.cumulative), shortfall: x.shortfall, belowBuffer: x.below_buffer })) };
}

export const workingCapitalService: WorkingCapitalService = {
  async assess(c) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/funding', { params: { path: { case_id: c.id } } })) as unknown as Funding;
    if (!r.recommended_amount) return null;
    const f = (k: string) => factFig(r.facts, k) ?? NONE;
    const num = (k: string) => { const v = r.facts.find(x => x.key === k)?.value; return v === undefined ? null : Number(v); };
    const cash = await ok(gw.GET('/v1/agents/working-capital/cases/{case_id}/cash-table', { params: { path: { case_id: c.id } } })) as unknown as CashResp;
    return { caseId: c.id, requestedAmount: fig(r.indicative_amount), minCashBuffer: f('wc.min_buffer'),
      peakShortfall: f('wc.peak_shortfall'), peakWeek: num('wc.peak_week'), shortfallWeeks: num('wc.shortfall_weeks'), existingFacility: f('wc.undrawn_limits'),
      recommendedAmount: fig(r.recommended_amount, 'wc.recommended_amount'),
      bridge: r.facts.filter(x => x.key.startsWith('wc.bridge.')).map(x => ({ code: x.key.slice('wc.bridge.'.length), amount: f(x.key) })),
      decision: 'GO', cash: mapCash(cash) };
  },
};
