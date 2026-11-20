// Plain-language wording for codes the gateway returns (UI thread, 20 Nov: the operator is not technical).
// Words only: no decision, figure or rule is derived here. Unknown codes fall back to a readable form of the code.
import type { GateDecision } from '@/types';

export const GATE_WORD: Record<GateDecision, string> = {
  GO: 'Passed', NO_GO: 'Blocked', NEEDS_INPUT: 'Needs information', PENDING: 'Not started', RUNNING: 'In progress', HELD: 'On hold', ERROR: 'Problem',
};
export const gateWord = (d: string | null | undefined) => GATE_WORD[(d ?? 'PENDING') as GateDecision] ?? humanise(d ?? '');

/** The five steps as a finance team names them, with what each one does. */
export const STEP: Record<string, { name: string; does: string }> = {
  onboarding: { name: 'Preparer check', does: 'Confirms the person preparing this proposal holds an authorised role, has current mandatory training and has accepted the working-capital policy (from HR records).' },
  working_capital: { name: 'Funding need', does: 'Works out, week by week, how much money the business really needs to fulfil the order. The requested amount is not assumed.' },
  lendwise: { name: 'Lender comparison', does: 'Prices each lender offer at its true yearly cost (fees and GST included), checks the repayments fit the cash flow, and ranks them.' },
  critic: { name: 'Accuracy check', does: 'Checks that every figure and source in the proposal matches the calculated records before anyone sees it.' },
  routing: { name: 'Approval routing', does: 'Sends the proposal to the right approver by amount: above ₹1.5 crore to the VP, Finance; below to the Director, Finance.' },
  approval: { name: 'Approval', does: 'The routed approver approves, rejects or returns the proposal.' },
};
export const stepName = (id?: string | null) => (id && STEP[id]?.name) || humanise(id ?? '');

export const FILE_LABEL: Record<string, string> = {
  order: 'Customer order', opening_position: 'Opening cash and credit lines', costs: 'Weekly costs', receipts: 'Expected receipts',
  receivables: 'Customer invoices due', payables: 'Supplier bills', inventory: 'Stock movement', offer: 'Lender offer', kfs: 'Key Facts Statement',
};
export const fileLabel = (k?: string | null) => (k && FILE_LABEL[k]) || humanise(k ?? '');

export const ROUTE_LABEL: Record<string, string> = { vp_finance: 'VP, Finance', director_finance: 'Director, Finance', HELD: 'held for a human decision' };
export const STATUS_LABEL: Record<string, string> = {
  CREATED: 'Draft', PAUSED: 'Waiting for information', FAILED: 'Stopped with a problem', RETURNED: 'Returned for rework', AWAITING_APPROVAL: 'Awaiting approval',
  HELD: 'On hold at ₹1.5 crore', APPROVED: 'Approved', REJECTED: 'Rejected', RUNNING: 'Running', DELETED: 'Deleted',
};
export const ROLE_LABEL: Record<string, string> = {
  preparer: 'Preparer', director_finance: 'Director, Finance', vp_finance: 'VP, Finance', evaluator: 'Evaluator', user_admin: 'Administrator',
  credit_proposal_officer: 'Credit proposal officer', senior_finance_analyst: 'Senior finance analyst', finance_analyst: 'Finance analyst', accounts_executive: 'Accounts executive',
};
export const RULE_LABEL: Record<string, string> = {
  role: 'Authorised to prepare loan proposals', 'FIN-101': 'Credit policy training', 'AML-201': 'Anti-money-laundering and KYC training',
  'DPDP-101': 'Data protection training', policy_ack: 'Working-capital policy accepted',
};
export const DECISION_LABEL: Record<string, string> = { approve: 'approved', reject: 'rejected', return: 'returned' };

/** "senior_finance_analyst" → "Senior finance analyst"; codes stay readable when no label exists. */
export function humanise(code: string): string {
  const s = code.replace(/[._]+/g, ' ').trim().toLowerCase();
  return s ? s[0].toUpperCase() + s.slice(1) : '';
}

/** A ledger key a person can read: "wc.peak_shortfall" → "Peak shortfall"; offer keys name the offer. */
const FACT_LABEL: Record<string, string> = {
  'wc.recommended_amount': 'Validated funding need', 'wc.peak_shortfall': 'Peak cash shortfall', 'wc.peak_week': 'Week of the peak shortfall',
  'wc.shortfall_weeks': 'Weeks with a shortfall', 'wc.min_buffer': 'Minimum cash buffer', 'wc.undrawn_limits': 'Unused credit limits', 'wc.mitigations': 'Confirmed offsets',
  'wc.gate': 'Funding need result', 'onb.gate': 'Preparer check result', 'lw.gate': 'Lender comparison result', 'lw.ranking': 'Offer ranking', report: 'Proposal report',
};
const OFFER_PART: Record<string, string> = {
  apr: 'yearly cost (APR)', total_cost: 'total cost', total_repayment: 'total repayment', amount_received: 'amount received', rank: 'rank', flags: 'warnings',
  comparable: 'comparable', affordable: 'affordable', min_cash: 'lowest cash position',
};
export function factLabel(key: string): string {
  if (FACT_LABEL[key]) return FACT_LABEL[key];
  if (key.startsWith('onb.rule.')) return RULE_LABEL[key.slice(9)] ?? humanise(key.slice(9));
  const m = /^lw\.(OF-[\w-]+)\.v(\d+)\.(?:v\d+\.)?(\w+)$/.exec(key);
  if (m) return `Offer ${m[1]} ${OFFER_PART[m[3]] ?? humanise(m[3]).toLowerCase()}`;
  if (key.startsWith('lw.negotiation')) return 'Negotiation: ' + humanise(key.replace(/^lw\.negotiation\.?/, '') || 'status').toLowerCase();
  if (key.startsWith('wc.bridge.')) return 'Bridge: ' + humanise(key.slice(10)).toLowerCase();
  return humanise(key.replace(/^(wc|lw|onb|cp)\./, ''));
}

export const ENGINE_LABEL: Record<string, string> = {
  'engines.cashflow': 'Cash-flow calculator', 'engines.loancost': 'Loan cost calculator', 'engines.negotiation': 'Negotiation rules', 'engines.onboarding_rules': 'Readiness rules',
  'engines.ranking': 'Offer ranking rules', 'engines.affordability': 'Affordability check', 'engines.routing': 'Approval routing rules',
};
export const engineLabel = (name?: string | null) => (name && (ENGINE_LABEL[name] ?? ENGINE_LABEL[name.split('@')[0]])) || 'A fixed calculation';
