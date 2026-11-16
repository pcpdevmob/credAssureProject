// Funding view from the gateway: recommended amount and ledger facts. The 26-week cash table arrives in Phase 9b (501 today).
import type { CaseRecord, FundingAssessment } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { factFig, fig, type Fig, type Money } from '@/lib/money';

export interface WorkingCapitalService { assess(c: CaseRecord): Promise<FundingAssessment | null> }
type Fact = { key: string; value: string; unit: string; version: number };
type Funding = { recommended_amount: Money | null; indicative_amount: Money; facts: Fact[] };
const NONE: Fig = { display: '—' };

export const workingCapitalService: WorkingCapitalService = {
  async assess(c) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/funding', { params: { path: { case_id: c.id } } })) as unknown as Funding;
    if (!r.recommended_amount) return null;
    const f = (k: string) => factFig(r.facts, k) ?? NONE;
    return { caseId: c.id, requestedAmount: fig(r.indicative_amount), minCashBuffer: f('wc.min_buffer'),
      peakShortfall: f('wc.peak_shortfall'), peakPeriod: `week ${r.facts.find(x => x.key === 'wc.peak_week')?.value ?? '—'}`, existingFacility: f('wc.undrawn_limits'),
      recommendedAmount: fig(r.recommended_amount, 'wc.recommended_amount'),
      drivers: r.facts.filter(x => x.key.startsWith('wc.bridge.')).map(x => ({ label: x.key.slice('wc.bridge.'.length).replace(/_/g, ' '), amount: f(x.key) })),
      decision: 'GO' };
  },
};
