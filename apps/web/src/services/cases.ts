// Cases (UI-01). Gateway summaries are mapped to the screen-facing CaseRecord; money is paise on the wire.
import type { CaseRecord, CaseStage, Approver, User } from '@/types';
import { gw, ok } from '@/lib/gateway';

export interface NewCaseInput { msmeName: string; orderRef: string; orderValue: number; customerDueDate: string; requestedAmount: number; sector?: string; gstinMasked?: string; customerName?: string }
export interface CaseService { list(): Promise<CaseRecord[]>; get(id: string): Promise<CaseRecord | undefined>; create(i: NewCaseInput, by: User): Promise<CaseRecord> }

type Money = { paise: number; display: string };
export type Raw = { case_id: string; msme_name: string; order_ref: string; status: string; current_stage: string; route?: string | null; row_version: number; order_value: Money; indicative_amount: Money; due_date: string; question?: string | null; next_action?: string; stages?: RawStage[] };
export type RawStage = { stage: string; decision: string | null; attempt: number; blockers: { code?: string; message?: string; next_action?: string }[]; question?: string | null; narrative?: string | null; trace_id?: string };

const BY_STAGE: Record<string, CaseStage> = { onboarding: 'READINESS', working_capital: 'FUNDING_ASSESSMENT', lendwise: 'LENDER_COMPARISON', critic: 'VERIFICATION', routing: 'VERIFICATION', approval: 'AWAITING_APPROVAL' };
const BY_STATUS: Record<string, CaseStage> = { CREATED: 'DRAFT', AWAITING_APPROVAL: 'AWAITING_APPROVAL', HELD: 'ROUTING_HELD', APPROVED: 'APPROVED', REJECTED: 'REJECTED', RETURNED: 'RETURNED' };
const routed = (r?: string | null): Approver | undefined => r === 'vp_finance' ? 'VP_FINANCE' : r === 'director_finance' ? 'DIRECTOR_FINANCE' : r === 'HELD' ? 'HELD_PENDING_POLICY' : undefined;

export const toCase = (r: Raw): CaseRecord => ({
  id: r.case_id, msmeName: r.msme_name, sector: '—', gstinMasked: '—', customerName: '—', orderValue: r.order_value.paise / 100, orderRef: r.order_ref, customerDueDate: r.due_date,
  currency: 'INR', requestedAmount: r.indicative_amount.paise / 100, preparerId: '', preparerName: '—', createdAt: '', updatedAt: '',
  stage: BY_STATUS[r.status] ?? BY_STAGE[r.current_stage] ?? 'READINESS', routedTo: routed(r.route), rowVersion: r.row_version, question: r.question, nextAction: r.next_action,
});

export const caseService: CaseService = {
  async list() { return (await ok(gw.GET('/v1/cases')) as unknown as { items: Raw[] }).items.map(toCase); },
  async get(id) {
    const { data, response } = await gw.GET('/v1/cases/{case_id}', { params: { path: { case_id: id } } });
    if (response.status === 404) return undefined;
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return toCase(data as unknown as Raw);
  },
  async create(i) {
    const r = await ok(gw.POST('/v1/cases', { body: { msme_name: i.msmeName, order_ref: i.orderRef, order_value_paise: Math.round(i.orderValue * 100), indicative_amount_paise: Math.round(i.requestedAmount * 100), due_date: i.customerDueDate } as never }));
    return toCase(r as unknown as Raw);
  },
};
