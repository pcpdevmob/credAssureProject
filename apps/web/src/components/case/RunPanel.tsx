// Run / resume with live progress (SSE, ADR 0007) and the stage's one question (SUP-06, design-plan principle 2).
// The question is answered by uploading the corrected file; Resume re-runs only the blocked stage (the server decides).
import { useState } from 'react';
import { HelpCircle, Play, RotateCcw } from 'lucide-react';
import { Button, Card } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { SLOTS, UploadSlot } from './Documents';
import { STAGES, gate, supervisorService, type EndEvent } from '@/services/supervisor';
import type { CaseRecord, WorkflowGate } from '@/types';

/** active: a run is streaming. After it ends the log stays on screen as "Last run" (fast stages finish in under a second). */
export type Live = { active: boolean; running: string | null; done: Record<string, string>; log: string[] };
const NAME: Record<string, string> = Object.fromEntries(STAGES.map(s => [s.id, s.name]));
const LOCKED = ['AWAITING_APPROVAL', 'ROUTING_HELD', 'APPROVED', 'REJECTED'];

/** Gate list with the live job's progress laid over the last saved state. */
export const overlay = (gates: WorkflowGate[], live: Live | null): WorkflowGate[] => !live?.active ? gates : gates.map(g =>
  live.done[g.id] ? { ...g, decision: gate(live.done[g.id]) } : live.running === g.id ? { ...g, decision: 'RUNNING' } : g);

export default function RunPanel({ c, gates, canRun, live, setLive, onDone }: {
  c: CaseRecord; gates: WorkflowGate[]; canRun: boolean; live: Live | null; setLive: (l: Live | null) => void; onDone: () => void;
}) {
  const [err, setErr] = useState<unknown>(); const [kind, setKind] = useState<string>('opening_position');
  const locked = !canRun || LOCKED.includes(c.stage); // no Run or Resume, but the last run's log stays
  if (locked && !live) return null;
  const blocked = gates.find(g => g.decision === 'NEEDS_INPUT' || g.decision === 'NO_GO' || g.decision === 'ERROR');
  const start = async () => {
    setErr(undefined);
    const first = gates.find(g => g.decision !== 'GO')?.id ?? null;
    let state: Live = { active: true, running: first, done: {}, log: [first ? `Starting: ${NAME[first] ?? first}` : 'Starting'] };
    setLive(state);
    try {
      const job = await supervisorService.run(c.id);
      let end: EndEvent = { status: 'timeout', outcome: null };
      for (let tries = 0; tries < 5 && ['timeout', 'disconnected'].includes(end.status); tries++) { // the stream is capped server-side; reconnect
        end = await supervisorService.watch(job.job_id, e => {
          const i = STAGES.findIndex(s => s.id === e.stage);
          const next = e.decision === 'GO' && i >= 0 ? STAGES[i + 1]?.id ?? null : null;
          state = { active: true, running: next, done: { ...state.done, [e.stage]: e.decision ?? 'PENDING' }, log: [...state.log, `${NAME[e.stage] ?? e.stage}: ${e.decision ?? 'done'}${next ? ` · now ${NAME[next]}` : ''}`] };
          setLive(state);
        });
      }
    } catch (e) { setErr(e); state = { ...state, log: [...state.log, 'Stopped: see the message below.'] }; }
    setLive({ ...state, active: false, running: null }); onDone();
  };
  const slot = SLOTS.find(s => s.kind === kind) ?? SLOTS[1];
  return (<div className="mb-6 space-y-4">
    {!locked && c.question && !live?.active && (
      <Card className="p-5 ring-2 ring-gold-500/50">
        <p className="flex items-center gap-2 text-sm font-semibold text-gold-800"><HelpCircle aria-hidden className="h-5 w-5" />One question {blocked ? `from ${blocked.name}` : ''}</p>
        <p className="mt-2 text-lg text-ink-950" data-testid="stage-question">{c.question}</p>
        <p className="mt-1 text-sm text-ink-600">Upload the corrected file, then resume. Only the blocked stage runs again; finished stages are kept.</p>
        <div className="mt-4 space-y-3">
          <label className="block text-sm text-ink-700">File to correct
            <select value={kind} onChange={e => setKind(e.target.value)} className="ml-2 h-9 rounded-lg border border-ink-400 bg-white px-2 text-sm">{SLOTS.map(s => <option key={s.kind} value={s.kind}>{s.label}</option>)}</select>
          </label>
          <ul><UploadSlot key={slot.kind} caseId={c.id} slot={slot} canEdit /></ul>
          <Button onClick={start}><RotateCcw className="h-4 w-4" />Resume</Button>
        </div>
      </Card>)}
    {!locked && !c.question && !live?.active && <Card className="flex flex-wrap items-center justify-between gap-3 p-5">
      <div><p className="font-semibold text-ink-950">Run the workflow</p><p className="text-sm text-ink-600">Runs every stage that is not yet GO, in order. It stops with one question if data is missing.</p></div>
      <Button onClick={start}><Play className="h-4 w-4" />Run</Button></Card>}
    <div aria-live="polite" className={live ? 'rounded-2xl bg-ink-50 p-4 text-sm ring-1 ring-line' : 'sr-only'}>
      {live && <><p className="font-semibold text-ink-950">{live.active ? 'Live progress' : 'Last run'}</p><ul className="mt-1 space-y-0.5 text-ink-700" data-testid="live-progress">{live.log.map((l, i) => <li key={i}>{l}</li>)}</ul></>}
    </div>
    {err !== undefined && <ErrorBanner error={err} />}
  </div>);
}
