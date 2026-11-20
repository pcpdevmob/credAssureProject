// LendWise comparison and the negotiation rounds (LW-09..15, ADR 0037). Everything shown is a stored fact computed by the
// gateway; `source: "preview"` means audit and pricing only, with no affordability check and no ranking.
import type { CaseRecord, Negotiation, NegotiationMove, NegotiationRound, OfferView, Revised } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { fig, type Fig, type Money } from '@/lib/money';

type RevisedResp = { version: number; comparable: boolean; flags: string[]; apr_pct: string | null; total_cost: Money | null };
type ReplyResp = { round: number; text: string; injection_flags: string[] };
type RoundResp = { round: number; move: NegotiationMove; target_offer: string; status: string; cited: Record<string, string>;
  message: string; concession_counts: boolean; revised: RevisedResp | null; reply: ReplyResp | null };
type NegResp = { target_offer: string | null; competing_fee_pct?: string | null; competing_fee?: Money | null; concession_counts: boolean; message: string; status: string | null;
  revised: RevisedResp | null; reply?: ReplyResp | null; rounds?: RoundResp[]; complete?: boolean };
type OfferResp = { source: 'ledger' | 'preview' | 'stale'; message?: string; ranking: string[]; negotiation?: NegResp;
  offers: { offer_id: string; version: number; flags: string[]; comparable: boolean; affordable: boolean | null; rank: number | null; apr_pct: string | null; cheapest_headline_rate?: boolean;
    amount_received: Money | null; total_repayment: Money | null; total_cost: Money | null }[] };

const pct = (v: string | null, key: string): Fig | null => (v === null ? null : { display: `${v}%`, key });

// Where each move keeps its facts (ADR 0037): the fee waiver under the original keys.
const PREFIX: Record<NegotiationMove, string> = { fee_waiver_v1: 'lw.negotiation.', rate_match_v1: 'lw.negotiation.rate_match.', tenor_change_v1: 'lw.negotiation.tenor_change.' };
const CITED: Record<string, string> = { current_fee: 'Current fee', competing_fee: 'Competing fee', current_rate: 'Current rate', competing_rate: 'Competing rate',
  competing_offer: 'Competing offer', current_first_repayment: 'First repayment now', requested_first_repayment: 'First repayment asked',
  cash_low_week_start: 'Cash lowest from', extra_months: 'Extra months' };

const mapRevised = (r: RevisedResp | null, p: string): Revised | null => r && { version: r.version, comparable: r.comparable, flags: r.flags,
  apr: pct(r.apr_pct, `${p}revised.apr`), totalCost: r.total_cost ? fig(r.total_cost, `${p}revised.total_cost`) : null };
const mapReply = (r: ReplyResp | null | undefined) => (r ? { round: r.round, text: r.text, injectionFlags: r.injection_flags } : null);
function mapRound(r: RoundResp): NegotiationRound {
  const p = PREFIX[r.move];
  const cited = Object.entries(r.cited ?? {}).map(([k, v]) => ({ label: CITED[k] ?? k, value: v }));
  return { round: r.round, move: r.move, target: r.target_offer, status: r.status, cited, message: r.message, countsAsConcession: r.concession_counts,
    revised: mapRevised(r.revised, p), reply: mapReply(r.reply) };
}

export function mapNegotiation(n: NegResp): Negotiation {
  const fee = n.competing_fee ? fig(n.competing_fee, 'lw.negotiation.competing_fee') : pct(n.competing_fee_pct ?? null, 'lw.negotiation.competing_fee');
  const revised = mapRevised(n.revised, PREFIX.fee_waiver_v1), reply = mapReply(n.reply);
  // An API from before ADR 0037 sends no `rounds`: its single fee-waiver round stands in for the list.
  const rounds = n.rounds ? n.rounds.map(mapRound) : n.target_offer && (n.status === 'sent' || n.status === 'blocked')
    ? [{ round: 1, move: 'fee_waiver_v1' as const, target: n.target_offer, status: n.status, cited: fee ? [{ label: 'Competing fee', value: fee.display }] : [],
      message: n.message, countsAsConcession: n.concession_counts, revised, reply }] : [];
  return { target: n.target_offer, competingFee: fee, countsAsConcession: n.concession_counts, message: n.message, status: n.status,
    revised, reply, rounds, complete: n.complete === true };
}

export function mapOffers(caseId: string, r: OfferResp): OfferView | null {
  // scope #6: an offer or KFS re-upload after the last LendWise run; the gateway withholds the old comparison.
  if (r.source === 'stale') return { caseId, source: 'stale', message: r.message, offers: [], ranking: [], negotiation: r.negotiation ? mapNegotiation(r.negotiation) : null };
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
  /** Plus the report version on screen, which approve echoes back (#6). */
  warnings(c: CaseRecord): Promise<{ warnings: string[]; reportVersion: number | null }>;
}
export const lendWiseService: LendWiseService = {
  async compare(c) { return mapOffers(c.id, await ok(gw.GET('/v1/cases/{case_id}/offers', { params: { path: { case_id: c.id } } })) as unknown as OfferResp); },
  async negotiate(c) { return mapNegotiation(await ok(gw.POST('/v1/agents/lendwise/cases/{case_id}/negotiate', { params: { path: { case_id: c.id } } })) as unknown as NegResp); },
  async warnings(c) { const r = await ok(gw.GET('/v1/cases/{case_id}/inbox', { params: { path: { case_id: c.id } } })) as unknown as { warnings: string[]; report_version: number | null }; return { warnings: r.warnings, reportVersion: r.report_version }; },
};
