// Funding view from the gateway: recommended amount and ledger facts. The 26-week cash table arrives in Phase 9b (501 today).
import type { CaseRecord, FundingAssessment } from '@/types';
import { gw, ok } from '@/lib/gateway';

export interface WorkingCapitalService { assess(c: CaseRecord): Promise<FundingAssessment | null> }
type Fact = { key: string; value: string; unit: string; version: number };
type Funding = { recommended_amount: { paise: number } | null; indicative_amount: { paise: number }; facts: Fact[] };
const num = (f: Fact[], k: string) => { const v = f.find(x => x.key === k)?.value; return v === undefined ? 0 : Number(v); };

export const workingCapitalService: WorkingCapitalService = {
  async assess(c) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/funding', { params: { path: { case_id: c.id } } })) as unknown as Funding;
    if (!r.recommended_amount) return null;
    return { caseId: c.id, requestedAmount: r.indicative_amount.paise / 100, horizonMonths: 6, minCashBuffer: num(r.facts, 'wc.min_buffer'), periods: [],
      peakShortfall: num(r.facts, 'wc.peak_shortfall'), peakPeriod: `week ${num(r.facts, 'wc.peak_week')}`, existingFacility: num(r.facts, 'wc.undrawn_limits'),
      recommendedAmount: r.recommended_amount.paise / 100,
      drivers: r.facts.filter(f => f.key.startsWith('wc.bridge.')).map(f => ({ label: f.key.slice('wc.bridge.'.length).replace(/_/g, ' '), amount: Number(f.value) })),
      assumptions: [], warnings: [], decision: 'GO' };
  },
};
