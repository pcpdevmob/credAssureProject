// Decision capture (UI-07, APR-04..06). Approval is internal only; the MSME chooses its lender outside the system.
import type { ApprovalDecision, CaseRecord, User } from '@/types';
import { gw, ok } from '@/lib/gateway';

export type ReturnStage = 'onboarding' | 'working_capital' | 'lendwise';
export interface ApprovalService { decide(c: CaseRecord, decision: ApprovalDecision['decision'], comment: string, returnStage?: ReturnStage): Promise<void>; canDecide(c: CaseRecord, u: User): boolean }
const WIRE = { APPROVED: 'approve', REJECTED: 'reject', RETURNED: 'return' } as const;

export const approvalService: ApprovalService = {
  canDecide: (c, u) => c.stage === 'AWAITING_APPROVAL' && c.routedTo === u.role, // UX hint only; the server enforces the role (APR-05)
  async decide(c, decision, comment, returnStage) {
    if (decision !== 'APPROVED' && !comment.trim()) throw new Error('A comment is required to reject or return a proposal.');
    await ok(gw.POST('/v1/cases/{case_id}/decision', { params: { path: { case_id: c.id } }, body: { decision: WIRE[decision], return_stage: decision === 'RETURNED' ? returnStage ?? 'working_capital' : null, comment, expected_version: c.rowVersion ?? 0 } as never }));
  },
};
