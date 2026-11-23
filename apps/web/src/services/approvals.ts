// Decision capture (UI-07, APR-04..06). Approval is internal only; the MSME chooses its lender outside the system.
import type { ApprovalDecision, CaseRecord, User } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { ApiProblem } from '@/lib/problem';

export interface InboxItem { caseId: string; msmeName: string; status: string; route: string | null; held: boolean }
export type ReturnStage = 'onboarding' | 'working_capital' | 'lendwise';
export interface ApprovalService { decide(c: CaseRecord, decision: ApprovalDecision['decision'], comment: string, returnStage?: ReturnStage, password?: string, reportVersion?: number | null, attested?: boolean, mfaCode?: string): Promise<void>; canDecide(c: CaseRecord, u: User): boolean }
const WIRE = { APPROVED: 'approve', REJECTED: 'reject', RETURNED: 'return' } as const;

export const approvalService: ApprovalService & { inbox(): Promise<InboxItem[]> } = {
  /** The gateway filters by the signed-in role; the browser shows exactly what it returns (UI-07). */
  async inbox() {
    const r = await ok(gw.GET('/v1/inbox')) as unknown as { items: { case_id: string; msme_name: string; status: string; route: string | null }[] };
    return r.items.map(i => ({ caseId: i.case_id, msmeName: i.msme_name, status: i.status, route: i.route, held: i.status === 'HELD' }));
  },
  // UX hint only; the server enforces the role (APR-05). A case held at exactly ₹1.5 crore (APR-03, rule "hold") is the VP's to decide (BRD §5.1).
  canDecide: (c, u) => (c.stage === 'AWAITING_APPROVAL' && c.routedTo === u.role) || (c.stage === 'ROUTING_HELD' && u.role === 'VP_FINANCE'),
  async decide(c, decision, comment, returnStage, password, reportVersion, attested, mfaCode) {
    if (decision !== 'APPROVED' && !comment.trim()) throw new Error('A comment is required to reject or return a proposal.');
    try { await ok(gw.POST('/v1/cases/{case_id}/decision', { params: { path: { case_id: c.id } }, body: { decision: WIRE[decision], return_stage: decision === 'RETURNED' ? returnStage ?? 'working_capital' : null, comment, expected_version: c.rowVersion ?? 0, attested: decision === 'APPROVED' && attested === true, ...(password ? { password } : {}), ...(mfaCode ? { mfa_code: mfaCode } : {}), ...(decision === 'APPROVED' && reportVersion != null ? { report_version: reportVersion } : {}) } as never })); }
    catch (e) { // APR-05: say why, in plain words (the gateway's detail is generic)
      if (e instanceof ApiProblem && e.status === 403 && e.code !== 'STEP_UP_REQUIRED') throw new ApiProblem(403, e.code, { what: 'You cannot decide this case.', fix: `${e.banner.what}. The person who prepared a proposal cannot approve it, and only the routed approver can decide.` }, []);
      throw e;
    }
  },
};
