// Typed fixtures for MSW handlers, unit tests and the /__gallery route. Shapes come from openapi.json via the api-client.
// Values mirror the demo case (CA-2026-0001, BRD App. A); they are display data only, never used for calculation.
import type { Lineage } from '@/services/lineage';

export const CASE_ID = 'CA-2026-0001';
export const TRACE = '7f3c9a2e5b1d4c8e9a0f6b2d3e4c5a1b';

export const lineageFull: Lineage = {
  case_id: CASE_ID, key: 'wc.recommended_amount', version: 2, latest_version: 2, superseded_by: null,
  value: { text: '14200000', paise: 1420000000, display: '₹1,42,00,000' }, unit: 'INR',
  created_at: '2026-11-16T09:30:00Z', source_type: 'engine', source_ref: 'file:order@3a9f0c1d2e4b fact:wc.peak_shortfall',
  engine: { name: 'engines.cashflow', version: '1' }, input_hash: 'b'.repeat(64),
  files: [{ kind: 'order', name: 'order', sha256: '3a9f0c1d2e4b' + 'c'.repeat(52), uploaded_at: '2026-11-16T09:12:00Z' }],
  inputs: [{ kind: 'fact', ref: 'fact:wc.peak_shortfall', fact_key: 'wc.peak_shortfall' }, { kind: 'ref', ref: 'policy:WC-POL-v3', fact_key: null }],
  passages: [{ doc_id: 'R-RBI-04', title: 'Master Direction – Lending to MSME Sector', section: '4.2 Working capital assessment', chunk_id: 'R-RBI-04#s4.2-c1' }],
  producer: { agent: 'working_capital', stage: 'working_capital', trace_id: TRACE },
  audit: { seq: 412, actor: 'supervisor', ts: '2026-11-16T09:30:01Z' },
};

/** A fact written before provenance tracking: no producer, no passages, no audit link, an older version. */
export const lineageLegacy: Lineage = {
  ...lineageFull, key: 'wc.peak_shortfall', version: 1, latest_version: 2, superseded_by: 2,
  value: { text: '16200000', paise: 1620000000, display: '₹1,62,00,000' },
  engine: { name: 'engines.cashflow', version: null }, inputs: [], passages: [],
  producer: { agent: null, stage: null, trace_id: null }, audit: null,
};

/** A reference-rate fact: cites a corpus doc id only (no title, section or chunk), producer partly recorded. */
export const lineageRefRate: Lineage = {
  ...lineageFull, key: 'lw.reference.eblr', version: 1, latest_version: 1,
  value: { text: '8.15', paise: null, display: '8.15%' }, unit: 'pct', files: [], inputs: [],
  passages: [{ doc_id: 'R-RATE-02-SBI', title: null, section: null, chunk_id: null }],
  producer: { agent: 'lendwise', stage: null, trace_id: null },
};

export const LINEAGE: Record<string, Lineage> = { [lineageFull.key]: lineageFull, [lineageLegacy.key]: lineageLegacy, [lineageRefRate.key]: lineageRefRate };

const money = (paise: number, display: string) => ({ paise, display });
export const caseSummary = {
  case_id: CASE_ID, msme_name: 'Demo Electronics Pvt Ltd', order_ref: 'PO-CA-2026-0001', status: 'AWAITING_APPROVAL', current_stage: 'approval',
  route: 'director_finance', row_version: 7, order_value: money(3200000000, '₹3,20,00,000'), indicative_amount: money(2000000000, '₹2,00,00,000'),
  recommended_amount: money(1420000000, '₹1,42,00,000'),
  due_date: '2027-05-15', question: null, next_action: 'Awaiting the Director, Finance decision.', stages: [],
};
// GET /v1/cases totals: summed by the gateway in paise (the browser never adds money).
export const caseTotals = {
  validated_cases: 1, validated_need: money(1420000000, '₹1,42,00,000'), requested_for_validated: money(2000000000, '₹2,00,00,000'),
  over_borrowing_avoided: money(580000000, '₹58,00,000'),
};
