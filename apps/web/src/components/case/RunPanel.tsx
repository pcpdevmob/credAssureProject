// Run / resume with live progress (SSE, ADR 0007) and the stage's one question (SUP-06, design-plan principle 2).
// The question is answered in the form for the file it names (or by uploading that file); Resume re-runs only the
// blocked stage (the server decides). Progress and questions are worded for a non-technical preparer (lib/plain.ts).
// A lender-comparison question (a missing offer, KFS or schedule of charges) is answered by adding the lender's file,
// so the card shows that upload and names the file, not the case-data forms.
import { useEffect, useState } from 'react';
import { HelpCircle, Play, RotateCcw, Loader2 } from 'lucide-react';
import { Button, Card } from '../ui';
import ErrorBanner from '../ErrorBanner';
import dynamic from 'next/dynamic';
import { LenderUpload, SLOTS, UploadSlot } from './Documents';
// The form loads only when a stage asks a question (U6 budget).
const DataEditor = dynamic(() => import('./DataEditor'), { ssr: false });
import { STAGES, gate, supervisorService, type EndEvent } from '@/services/supervisor';
import { caseFiles, type StoredFile } from '@/services/documents';
import { plainText } from '@/lib/caseForms';
import { gateWord } from '@/lib/plain';
import type { CaseRecord, WorkflowGate } from '@/types';

/** active: a run is streaming. After it ends the log stays on screen as "Last run" (fast stages finish in under a second). */
export type Live = { active: boolean; running: string | null; done: Record<string, string>; log: string[] };
const NAME: Record<string, string> = Object.fromEntries(STAGES.map(s => [s.id, s.name]));
const LOCKED = ['AWAITING_APPROVAL', 'ROUTING_HELD', 'APPROVED', 'REJECTED'];
const KINDS = SLOTS.map(s => s.kind as string);
const FILE_RE = new RegExp(`\\b(${KINDS.join('|')})\\.(json|csv)\\b`, 'g');

/** The case file a stage question asks for, from the file name it mentions. */
export const fileAskedFor = (q?: string | null) => { const m = q ? new RegExp(FILE_RE.source).exec(q) : null; return m ? m[1] : null; };
/** The lender's file a lender-comparison question asks for: its file name when the question names a document
 *  ("…schedule of charges KFS-OF-07-A-v1-SCH…" → "KFS-OF-07-A-v1-SCH.md"), '' when it asks for lender files in
 *  general, null when the question is about case data. */
export const lenderFileAskedFor = (q?: string | null): string | null => {
  if (!q || fileAskedFor(q)) return null;
  const doc = /\bKFS-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b/.exec(q);
  if (doc) return `${doc[0]}.md`;
  return /\b(lender offers?|schedule of charges|key facts statement)\b/i.test(q) ? '' : null;
};
/** The question with file and field names replaced by the names on the form. */
export const plainQuestion = plainText;

/** Gate list with the live job's progress laid over the last saved state. */
export const overlay = (gates: WorkflowGate[], live: Live | null): WorkflowGate[] => !live?.active ? gates : gates.map(g =>
  live.done[g.id] ? { ...g, decision: gate(live.done[g.id]) } : live.running === g.id ? { ...g, decision: 'RUNNING' } : g);

function Elapsed() {
  const [s, setS] = useState(0);
  useEffect(() => { const t = setInterval(() => setS(x => x + 1), 1000); return () => clearInterval(t); }, []);
  return <span className="tabular-nums">{Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}</span>;
}

export default function RunPanel({ c, gates, canRun, live, setLive, onDone }: {
  c: CaseRecord; gates: WorkflowGate[]; canRun: boolean; live: Live | null; setLive: (l: Live | null) => void; onDone: () => void;
}) {
  const asked = fileAskedFor(c.question); const lenderFile = lenderFileAskedFor(c.question);
  const [err, setErr] = useState<unknown>(); const [kind, setKind] = useState<string>(asked ?? 'opening_position');
  const [stored, setStored] = useState<StoredFile[] | null>(null);
  useEffect(() => { if (asked) setKind(asked); }, [asked]);
  const showQuestion = canRun && !LOCKED.includes(c.stage) && !!c.question && !live?.active;
  useEffect(() => { if (showQuestion && lenderFile === null) caseFiles.list(c.id).then(r => setStored(r.files), () => setStored([])); }, [showQuestion, lenderFile, c.id]);
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
          state = { active: true, running: next, done: { ...state.done, [e.stage]: e.decision ?? 'PENDING' }, log: [...state.log, `${NAME[e.stage] ?? e.stage}: ${gateWord(e.decision).toLowerCase()}${next ? ` · now ${NAME[next]?.toLowerCase()}` : ''}`] };
          setLive(state);
        });
      }
    } catch (e) { setErr(e); state = { ...state, log: [...state.log, 'Stopped: see the message below.'] }; }
    setLive({ ...state, active: false, running: null }); onDone();
  };
  const slot = SLOTS.find(s => s.kind === kind) ?? SLOTS[1];
  const file = stored?.find(f => f.kind === slot.kind);
  return (<div className="mb-6 space-y-4">
    {showQuestion && (
      <Card className="p-5 ring-2 ring-gold-500/50">
        <p className="flex items-center gap-2 text-sm font-semibold text-gold-800"><HelpCircle aria-hidden className="h-5 w-5" />{blocked ? `${blocked.name} needs one thing from you` : 'One question'}</p>
        <p className="mt-2 text-lg text-ink-950" data-testid="stage-question">{plainQuestion(c.question!)}</p>
        <p className="mt-1 text-sm text-ink-600">{lenderFile !== null ? 'Add the lender\u2019s file below, then press Continue.' : 'Correct it below and save, then press Continue.'} Only the step that stopped runs again; finished steps are kept.</p>
        <div className="mt-4 space-y-4">
          {lenderFile !== null ? <div className="rounded-2xl p-4 ring-1 ring-line" data-testid="lender-file-needed"><h4 className="mb-1 font-medium text-ink-950">Documents from lenders</h4>
            <p className="mb-3 text-sm text-ink-700">{lenderFile ? <>File needed: <span className="font-mono">{lenderFile}</span>, the lender&apos;s schedule of charges or Key Facts Statement for that offer. </> : null}Each offer needs three files from the lender: the offer (.json), its Key Facts Statement (.md) and its schedule of charges (.md, name ending in -SCH). They are also listed on the Case data tab under “Documents from lenders”.</p>
            <LenderUpload caseId={c.id} id="upload-lender-file" label="Choose the lender’s file or files (.json, .md)" /></div>
          : <>{!asked && <label className="block text-sm text-ink-700">Section to correct
            <select value={kind} onChange={e => setKind(e.target.value)} className="ml-2 h-9 rounded-lg border border-ink-400 bg-white px-2 text-sm">{SLOTS.map(s => <option key={s.kind} value={s.kind}>{s.label}</option>)}</select>
          </label>}
          <div className="rounded-2xl p-4 ring-1 ring-line"><h4 className="mb-3 font-medium text-ink-950">{slot.label}</h4>
            {stored === null ? <p className="flex items-center gap-2 text-sm text-ink-600"><Loader2 aria-hidden className="h-4 w-4 animate-spin" />Loading what you entered…</p>
              : <DataEditor key={slot.kind} caseId={c.id} kind={slot.kind} stored={file?.data} canEdit />}
            <div className="mt-4 border-t border-line pt-3"><UploadSlot key={slot.kind} caseId={c.id} slot={slot} canEdit /></div></div></>}
          <Button onClick={start}><RotateCcw className="h-4 w-4" />Continue</Button>
        </div>
      </Card>)}
    {!locked && !c.question && !live?.active && <Card className="flex flex-wrap items-center justify-between gap-3 p-5">
      <div><p className="font-semibold text-ink-950">{blocked ? 'Run again' : 'Run the checks'}</p><p className="text-sm text-ink-600">Runs every step that has not passed yet, in order. If something is missing it stops and asks you one question.</p></div>
      <Button onClick={start}><Play className="h-4 w-4" />Run</Button></Card>}
    <div aria-live="polite" className={live ? 'rounded-2xl bg-ink-50 p-4 text-sm ring-1 ring-line' : 'sr-only'}>
      {live && <><p className="flex items-center gap-2 font-semibold text-ink-950">{live.active ? <><Loader2 aria-hidden className="h-4 w-4 animate-spin" />Working… <span className="font-normal text-ink-600">(<Elapsed />; steps that write text can take a minute)</span></> : 'Last run'}</p>
        <ul className="mt-1 space-y-0.5 text-ink-700" data-testid="live-progress">{live.log.map((l, i) => <li key={i}>{l}</li>)}</ul></>}
    </div>
    {err !== undefined && <ErrorBanner error={err} />}
  </div>);
}
