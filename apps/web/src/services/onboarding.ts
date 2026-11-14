// Onboarding result = the stage result the Supervisor stored (rule table arrives with Phase 9a).
import type { CaseRecord, ReadinessResult } from '@/types';
import { gw, ok } from '@/lib/gateway';
import type { Raw } from './cases';

export interface OnboardingService { checkReadiness(c: CaseRecord): Promise<ReadinessResult> }
export const onboardingService: OnboardingService = {
  async checkReadiness(c) {
    const raw = await ok(gw.GET('/v1/cases/{case_id}', { params: { path: { case_id: c.id } } })) as unknown as Raw;
    const s = raw.stages?.find(x => x.stage === 'onboarding');
    return { employeeId: '—', employeeName: '—', role: '—', buddy: '—', manager: '—', prerequisites: [],
      decision: !s ? 'PENDING' : s.decision === 'GO' ? 'GO' : s.decision === 'NEEDS_INPUT' ? 'NEEDS_INPUT' : 'NO_GO',
      blockers: (s?.blockers ?? []).map(b => b.message ?? b.code ?? 'Blocked'), checkedAt: '' };
  },
};
