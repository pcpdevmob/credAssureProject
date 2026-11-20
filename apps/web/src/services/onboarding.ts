// Readiness (Gate 1): GET /v1/cases/{id}/readiness, the rules the Onboarding stage recorded with the HR records behind them.
import type { CaseRecord, ReadinessResult } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { gate } from './supervisor';

type Raw = {
  decision: string | null; checked_at: string | null; attempt: number; question: string | null;
  preparer: { emp_id: string; name: string; role: string; department: string | null; active: boolean } | null;
  rules: { rule: string; outcome: string; kind: 'role' | 'training' | 'policy'; role?: string; training?: { status: string; completed_on: string | null; expires_on: string | null } | null; policy_ack?: { version: string; acknowledged_on: string | null } | null }[];
  blockers: { code?: string | null; message?: string | null; next_action?: string | null }[];
};

export interface OnboardingService { checkReadiness(c: CaseRecord): Promise<ReadinessResult> }
export const onboardingService: OnboardingService = {
  async checkReadiness(c) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/readiness', { params: { path: { case_id: c.id } } })) as unknown as Raw;
    return {
      decision: gate(r.decision), checkedAt: r.checked_at, attempt: r.attempt, question: r.question,
      preparer: r.preparer && { empId: r.preparer.emp_id, name: r.preparer.name, role: r.preparer.role, department: r.preparer.department, active: r.preparer.active },
      rules: r.rules.map(x => ({ rule: x.rule, outcome: x.outcome, kind: x.kind, role: x.role, training: x.training, policyAck: x.policy_ack })),
      blockers: r.blockers.map(b => ({ code: b.code, message: b.message, nextAction: b.next_action })),
    };
  },
};
