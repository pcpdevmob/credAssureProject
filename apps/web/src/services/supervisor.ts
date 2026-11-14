// Supervisor: stage gates come from the gateway's stage results; the run itself is a 202 job.
import type { CaseRecord, WorkflowGate, GateDecision } from '@/types';
import { gw, ok } from '@/lib/gateway';
import type { Raw, RawStage } from './cases';

export interface SupervisorService { gates(c: CaseRecord): Promise<WorkflowGate[]>; run(caseId: string): Promise<void> }
const STAGES = [
  { id: 'onboarding', name: 'Employee readiness', agent: 'Employee Onboarding Agent', next: 'Upload case data' },
  { id: 'working_capital', name: 'Funding need', agent: 'Working Capital Advisory Agent', next: 'Compare lenders' },
  { id: 'lendwise', name: 'Lender comparison', agent: 'LendWise Agent', next: 'Verify' },
  { id: 'critic', name: 'Verification', agent: 'Verification Critic', next: 'Route for approval' },
] as const;
const gate = (d: string | null | undefined): GateDecision => d === 'GO' ? 'GO' : d === 'NEEDS_INPUT' ? 'NEEDS_INPUT' : d === 'NO_GO' || d === 'ERROR' ? 'NO_GO' : 'PENDING';

export const supervisorService: SupervisorService = {
  async gates(c) {
    const raw = await ok(gw.GET('/v1/cases/{case_id}', { params: { path: { case_id: c.id } } })) as unknown as Raw;
    const by = new Map<string, RawStage>((raw.stages ?? []).map(s => [s.stage, s]));
    const g: WorkflowGate[] = STAGES.map(s => {
      const r = by.get(s.id);
      return { id: s.id, name: s.name, agent: s.agent, decision: gate(r?.decision), evidence: r?.narrative ?? (r ? `Attempt ${r.attempt}` : 'Not run yet'), blockers: (r?.blockers ?? []).map(b => b.message ?? b.code ?? 'Blocked'), at: undefined, next: r?.question ?? s.next };
    });
    const held = c.stage === 'ROUTING_HELD';
    g.push({ id: 'routing', name: 'Approval routing', agent: 'Supervisor (code)', decision: held ? 'HELD' : ['AWAITING_APPROVAL', 'APPROVED', 'REJECTED'].includes(c.stage) ? 'GO' : 'PENDING', evidence: c.routedTo ? `Routed to ${c.routedTo.replace(/_/g, ' ').toLowerCase()}` : '—', blockers: held ? ['Exactly ₹1.5 crore: held for a human decision (APR-03)'] : [], next: 'Human decision' });
    return g;
  },
  async run(caseId) { await ok(gw.POST('/v1/cases/{case_id}/run', { params: { path: { case_id: caseId }, header: { 'Idempotency-Key': crypto.randomUUID() } } as never })); },
};
