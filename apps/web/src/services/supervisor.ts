// Supervisor: stage gates come from the gateway's stage results; the run itself is a 202 job.
import type { CaseRecord, WorkflowGate, GateDecision } from '@/types';
import { gw, ok } from '@/lib/gateway';
import { toProblem } from '@/lib/problem';
import { parseSse, type SseEvent } from '@/lib/sse';
import type { Raw, RawStage } from './cases';
import { STEP } from '@/lib/plain';
import { plainText as formText } from '@/lib/caseForms';
import { FLAG_TEXT } from '@/lib/flags';
/** Form names for file and field names, and flag codes in words ("OF-04-C: LW_RATE_MAY_RESET" → "OF-04-C: floating rate: it may reset"). */
const plainText = (t: string) => formText(t).replace(/\bLW_[A-Z_]+\b/g, c => FLAG_TEXT[c] ? FLAG_TEXT[c].replace(/\.$/, '').replace(/^./, x => x.toLowerCase()) : c);

export type Job = { job_id: string; status: string; outcome: string | null };
export type StageEvent = { stage: string; decision: string | null; attempt: number };
export type EndEvent = { status: string; outcome: string | null };
export interface SupervisorService {
  gates(c: CaseRecord): Promise<WorkflowGate[]>;
  run(caseId: string): Promise<Job>;
  /** Live progress (SSE) until the job ends; resolves with the end event. */
  watch(jobId: string, onStage: (e: StageEvent) => void, signal?: AbortSignal): Promise<EndEvent>;
}
/** The steps in plain words; `agent` is what the step does (the agent's name is kept in `by` for evaluators). */
export const STAGES = [
  { id: 'onboarding', name: STEP.onboarding.name, agent: STEP.onboarding.does, by: 'Employee Onboarding Agent', next: 'Work out the funding need' },
  { id: 'working_capital', name: STEP.working_capital.name, agent: STEP.working_capital.does, by: 'Working Capital Advisory Agent', next: 'Compare the lender offers' },
  { id: 'lendwise', name: STEP.lendwise.name, agent: STEP.lendwise.does, by: 'LendWise Agent', next: 'Check every figure and source' },
  { id: 'critic', name: STEP.critic.name, agent: STEP.critic.does, by: 'Verification Critic', next: 'Send for approval' },
] as const;
export const gate = (d: string | null | undefined): GateDecision => d === 'GO' ? 'GO' : d === 'NEEDS_INPUT' ? 'NEEDS_INPUT' : d === 'ERROR' ? 'ERROR' : d === 'NO_GO' ? 'NO_GO' : 'PENDING';

export const supervisorService: SupervisorService = {
  async gates(c) {
    const raw = await ok(gw.GET('/v1/cases/{case_id}', { params: { path: { case_id: c.id } } })) as unknown as Raw;
    const by = new Map<string, RawStage>((raw.stages ?? []).map(s => [s.stage, s]));
    const g: WorkflowGate[] = STAGES.map(s => {
      const r = by.get(s.id);
      return { id: s.id, name: s.name, agent: s.agent, decision: gate(r?.decision), evidence: r?.narrative ? plainText(r.narrative) : (r ? (r.decision === 'GO' ? 'Done.' : '') : 'Not run yet.'), blockers: (r?.blockers ?? []).map(b => plainText(b.message ?? b.code ?? 'Blocked')), at: undefined, next: r?.decision === 'GO' ? s.next : r?.question ? plainText(r.question) : (r ? 'Fix what is listed above, then press Run again.' : s.next), aiDrafted: r?.narrative_source === 'model', by: s.by, blockerActions: (r?.blockers ?? []).map(b => b.next_action ?? '').filter(Boolean) };
    });
    const held = c.stage === 'ROUTING_HELD';
    const to = c.routedTo === 'VP_FINANCE' ? 'VP, Finance' : c.routedTo === 'DIRECTOR_FINANCE' ? 'Director, Finance' : null;
    g.push({ id: 'routing', name: STEP.routing.name, agent: STEP.routing.does, by: 'Supervisor (fixed rules)', decision: held ? 'HELD' : ['AWAITING_APPROVAL', 'APPROVED', 'REJECTED'].includes(c.stage) ? 'GO' : 'PENDING', evidence: to ? `Sent to the ${to}.` : held ? '' : 'Not sent yet.', blockers: held ? ['The validated amount is exactly ₹1.5 crore. Company policy holds it for a person to decide who approves.'] : [], next: held ? 'The VP, Finance decides' : 'The approver decides on the Review & approval tab' });
    return g;
  },
  async run(caseId) { return await ok(gw.POST('/v1/cases/{case_id}/run', { params: { path: { case_id: caseId }, header: { 'Idempotency-Key': crypto.randomUUID() } } as never })) as unknown as Job; },
  async watch(jobId, onStage, signal) {
    const { response } = await gw.GET('/v1/jobs/{job_id}/events', { params: { path: { job_id: jobId } }, parseAs: 'stream', signal } as never);
    if (!response.ok || !response.body) throw toProblem(response.status, undefined);
    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) return { status: 'disconnected', outcome: null }; // the caller reloads the case and decides
      const { events, rest } = parseSse(buf + value); buf = rest;
      for (const e of events as SseEvent[]) {
        if (e.event === 'stage') onStage(e.data as StageEvent);
        if (e.event === 'end') { await reader.cancel(); return e.data as EndEvent; }
      }
    }
  },
};
