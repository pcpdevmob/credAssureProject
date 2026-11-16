// LendWise comparison and the single negotiation round (LW-09..14). Everything shown is a stored fact computed by the
// gateway; `source: "preview"` means audit and pricing only, with no affordability check and no ranking.
import type { CaseRecord, Negotiation, OfferView } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { fig, type Fig, type Money } from '@/lib/money';

type NegResp = { target_offer: string | null; competing_fee_pct?: string | null; competing_fee?: Money | null; concession_counts: boolean; message: string; status: string | null;
  revised: { version: number; comparable: boolean; flags: string[]; apr_pct: string | null; total_cost: Money | null } | null };
type OfferResp = { source: 'ledger' | 'preview'; ranking: string[]; negotiation?: NegResp;
  offers: { offer_id: string; version: number; flags: string[]; comparable: boolean; affordable: boolean | null; rank: number | null; apr_pct: string | null; cheapest_headline_rate?: boolean;
    amount_received: Money | null; total_repayment: Money | null; total_cost: Money | null }[] };

const pct = (v: string | null, key: string): Fig | null => (v === null ? null : { display: `${v}%`, key });

export function mapNegotiation(n: NegResp): Negotiation {
  const fee = n.competing_fee ? fig(n.competing_fee, 'lw.negotiation.competing_fee') : pct(n.competing_fee_pct ?? null, 'lw.negotiation.competing_fee');
  const r = n.revised;
  return { target: n.target_offer, competingFee: fee, countsAsConcession: n.concession_counts, message: n.message, status: n.status,
    revised: r && { version: r.version, comparable: r.comparable, flags: r.flags, apr: pct(r.apr_pct, 'lw.negotiation.revised.apr'),
      totalCost: r.total_cost ? fig(r.total_cost, 'lw.negotiation.revised.total_cost') : null } };
}

export function mapOffers(caseId: string, r: OfferResp): OfferView | null {
  if (!r.offers.length) return null;
  return { caseId, source: r.source, ranking: r.ranking, negotiation: r.negotiation ? mapNegotiation(r.negotiation) : null,
    offers: r.offers.map(o => { const k = (f: string) => `lw.${o.offer_id}.v${o.version}.${f}`; const m = (v: Money | null, f: string) => (v ? fig(v, k(f)) : null);
      return { id: o.offer_id, version: o.version, flags: o.flags, comparable: o.comparable, affordable: o.affordable, rank: o.rank, cheapest: o.cheapest_headline_rate === true, aprPct: o.apr_pct,
        apr: pct(o.apr_pct, k('apr')), amountReceived: m(o.amount_received, 'amount_received'), totalRepayment: m(o.total_repayment, 'total_repayment'), totalCost: m(o.total_cost, 'total_cost') }; }) };
}

export interface LendWiseService {
  compare(c: CaseRecord): Promise<OfferView | null>;
  negotiate(c: CaseRecord): Promise<Negotiation>;
  /** Approver evidence (APR-04, BR-09): `negotiation_in_progress`, `revised_offer_not_reaudited`. */
  warnings(c: CaseRecord): Promise<string[]>;
}
export const lendWiseService: LendWiseService = {
  async compare(c) { return mapOffers(c.id, await ok(gw.GET('/v1/cases/{case_id}/offers', { params: { path: { case_id: c.id } } })) as unknown as OfferResp); },
  async negotiate(c) { return mapNegotiation(await ok(gw.POST('/v1/agents/lendwise/cases/{case_id}/negotiate', { params: { path: { case_id: c.id } } })) as unknown as NegResp); },
  async warnings(c) { return (await ok(gw.GET('/v1/cases/{case_id}/inbox', { params: { path: { case_id: c.id } } })) as unknown as { warnings: string[] }).warnings; },
};
