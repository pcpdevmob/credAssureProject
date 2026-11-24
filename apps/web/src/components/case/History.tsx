'use client';
// The case's history in plain words for every case member (GET /v1/cases/{id}/history). Key moments are shown by default;
// the system's detailed steps (figures written, tools called) are one click away. Evaluators also get the raw audit log.
import { useEffect, useMemo, useState } from 'react';
import { CheckCircle2, CircleAlert, FileUp, FolderPlus, Gavel, History as HistoryIcon, Route, ShieldAlert, ShieldCheck, Cog, Download } from 'lucide-react';
import type { HistoryEvent } from '@/types';
import { auditService } from '@/services';
import { Card, CardHeader, Skeleton, Button } from '../ui';
import ErrorBanner from '../ErrorBanner';
import AuditList from '../AuditList';
import { dt } from '@/lib/format';
import { toCsv } from '@/lib/csv';
import { DECISION_LABEL, ROLE_LABEL, ROUTE_LABEL, STATUS_LABEL, factLabel, fileLabel, gateWord, humanise, stepName } from '@/lib/plain';
import { cn } from '@/lib/utils';

type Line = { icon: typeof CheckCircle2; tone: 'ok' | 'warn' | 'bad' | 'plain'; text: string; note?: string; key: boolean };

const who = (e: HistoryEvent) => e.actorRole ? `${e.actorName ?? 'A user'} (${ROLE_LABEL[e.actorRole] ?? humanise(e.actorRole)})` : 'CredAssure';
const s = (v: unknown) => (v === null || v === undefined ? '' : String(v));

/** One event in words. Unknown types are shown with their name, never hidden. */
export function describe(e: HistoryEvent): Line {
  const x = e.details;
  switch (e.type) {
    case 'CASE_CREATED': return { icon: FolderPlus, tone: 'plain', key: true, text: `${who(e)} created the case${x.order_ref ? ` for order ${s(x.order_ref)}` : ''}.` };
    case 'PDF_DRAFTED': { const doc = ({ offer: 'an offer letter', kfs: 'a Key Facts Statement', schedule: 'a schedule of charges' } as Record<string, string>)[s(x.doc)] ?? 'a PDF';
      return { icon: FileUp, tone: 'plain', key: false, text: `${who(e)} read ${doc} from a PDF${s(x.model) === 'used' ? `; the AI suggested ${s(x.drafted)} value(s) for review` : ''}. Nothing is saved until the person checks it.` }; }
    case 'FILE_UPLOADED': return { icon: FileUp, tone: 'plain', key: true, text: `${who(e)} provided “${fileLabel(s(x.kind))}”.` };
    case 'INJECTION_FLAGGED': {
      const flags = Array.isArray(x.flags) ? x.flags.map(String) : [];
      const other = flags.length > 0 && flags.every(f => f === 'KFS_CASE_MISMATCH');
      return { icon: ShieldAlert, tone: 'warn', key: true, text: other ? `A ${fileLabel(s(x.kind)).toLowerCase()} names a different case number. It was kept and flagged for review.` : `A ${fileLabel(s(x.kind)).toLowerCase()} contained text that looks like instructions to the system. It was kept as data and ignored.` };
    }
    case 'STAGE_COMPLETED': {
      const dec = s(x.decision); const tone = dec === 'GO' ? 'ok' : dec === 'NEEDS_INPUT' ? 'warn' : 'bad';
      return { icon: dec === 'GO' ? CheckCircle2 : CircleAlert, tone, key: true, text: `${stepName(s(x.stage))}: ${gateWord(dec).toLowerCase()}.`, note: Number(x.attempt) > 1 ? `Run ${s(x.attempt)}` : undefined };
    }
    case 'STATE_CHANGED': return { icon: Cog, tone: 'plain', key: x.status === 'PAUSED' || x.status === 'FAILED', text: `Case status: ${(STATUS_LABEL[s(x.status)] ?? humanise(s(x.status))).toLowerCase()}${x.current_stage ? ` (at ${stepName(s(x.current_stage)).toLowerCase()})` : ''}.` };
    case 'ROUTED': return { icon: Route, tone: x.route === 'HELD' ? 'warn' : 'plain', key: true, text: x.route === 'HELD' ? 'The validated amount is exactly ₹1.5 crore, so the proposal is on hold for a human decision.' : `Sent for approval to the ${ROUTE_LABEL[s(x.route)] ?? humanise(s(x.route))}.` };
    case 'DECISION_RECORDED': {
      const dec = DECISION_LABEL[s(x.decision)] ?? s(x.decision);
      return { icon: Gavel, tone: x.decision === 'approve' ? 'ok' : 'bad', key: true, text: `${who(e)} ${dec} the proposal${x.return_stage ? `, returning it to ${stepName(s(x.return_stage)).toLowerCase()}` : ''}.`, note: x.comment ? `Comment: “${s(x.comment)}”` : undefined };
    }
    case 'EXTRA_INVOCATION': return { icon: Route, tone: 'plain', key: true, text: x.name === 'negotiate' ? 'A negotiation round was sent to a lender (see Lender offers for the reply).' : `${stepName(s(x.stage))} ran an extra step (${humanise(s(x.name)).toLowerCase()}).` };
    case 'STAGE_RETRY_REQUESTED': return { icon: Cog, tone: 'plain', key: true, text: `${who(e)} asked to retry ${stepName(s(x.stage)).toLowerCase()}.` };
    case 'GATE_OVERRIDE': return { icon: ShieldAlert, tone: 'bad', key: true, text: `The double-check of ${stepName(s(x.stage)).toLowerCase()} disagreed with the result, so the step was stopped.` };
    case 'CRITIC_BLOCKED': return { icon: ShieldCheck, tone: 'warn', key: false, text: `The accuracy check held back a draft text${x.stage ? ` in ${stepName(s(x.stage)).toLowerCase()}` : ''} because a figure or source did not match.` };
    case 'CRITIC_FALLBACK': return { icon: ShieldCheck, tone: 'plain', key: false, text: `A fixed, pre-approved wording was used${x.stage ? ` in ${stepName(s(x.stage)).toLowerCase()}` : ''} instead of an AI draft.` };
    case 'CRITIC_REROUTE': return { icon: ShieldCheck, tone: 'warn', key: true, text: `The accuracy check sent ${stepName(s(x.stage)).toLowerCase()} back to be redone.` };
    case 'LLM_FALLBACK': return { icon: Cog, tone: 'plain', key: false, text: 'The AI assistant was unavailable, so a fixed wording was used. Figures are unaffected.' };
    case 'GUARDRAIL_EVENT': return { icon: ShieldAlert, tone: x.action === 'block' ? 'bad' : 'warn', key: x.action === 'block', text: x.action === 'block' ? 'Something was refused by a safety rule (for example a personal ID number in a file).' : x.action === 'redact' ? 'Personal details were hidden before storage.' : 'A safety rule flagged something for review.' };
    case 'FACT_WRITTEN': return { icon: Cog, tone: 'plain', key: false, text: `Recorded: ${factLabel(s(x.key))}${x.version && Number(x.version) > 1 ? ` (version ${s(x.version)})` : ''}.` };
    case 'TOOL_CALLED': return { icon: Cog, tone: 'plain', key: false, text: `Ran a calculation step (${humanise(s(x.tool)).toLowerCase()}).` };
    case 'STEP_UP_VERIFIED': return { icon: ShieldCheck, tone: 'plain', key: false, text: `${who(e)} confirmed their identity for a decision.` };
    case 'STEP_UP_FAILED': return { icon: ShieldAlert, tone: 'warn', key: true, text: `${who(e)} failed an identity confirmation for a decision.` };
    case 'CASE_DELETED': return { icon: ShieldAlert, tone: 'bad', key: true, text: `${who(e)} deleted the case content. This record is kept.` };
    default: return { icon: Cog, tone: 'plain', key: false, text: humanise(e.type) + '.' };
  }
}

const TONE = { ok: 'bg-emerald-50 text-emerald-700', warn: 'bg-amber-50 text-amber-700', bad: 'bg-rose-50 text-rose-700', plain: 'bg-ink-50 text-ink-600' };

export default function History({ caseId, technical }: { caseId: string; technical: boolean }) {
  const [state, setState] = useState<{ events: HistoryEvent[]; chainOk: boolean } | null>(null); const [err, setErr] = useState<unknown>();
  const [all, setAll] = useState(false); const [raw, setRaw] = useState(false);
  useEffect(() => { let live = true; auditService.history(caseId).then(v => live && setState(v), e => live && setErr(e)); return () => { live = false; }; }, [caseId]);
  const lines = useMemo(() => (state?.events ?? []).map(e => ({ e, l: describe(e) })).reverse(), [state]);
  const shown = all ? lines : lines.filter(x => x.l.key);
  const csv = () => {
    const rows = [['When', 'Who', 'What', 'Note'], ...shown.map(({ e, l }) => [dt(e.ts), who(e), l.text, l.note ?? ''])];
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([toCsv(rows)], { type: 'text/csv' })); a.download = `history-${caseId}.csv`; a.click();
  };
  if (raw) return <div className="space-y-3"><Button variant="outline" size="sm" onClick={() => setRaw(false)}>Back to the case history</Button><AuditList caseId={caseId} /></div>;
  return (<Card>
    <CardHeader title="Case history" sub="Everything that happened on this case, newest first. Nothing here can be edited or removed." icon={<HistoryIcon className="h-4 w-4" />}
      right={<div className="flex flex-wrap gap-2">{technical && <Button size="sm" variant="outline" onClick={() => setRaw(true)}>Technical audit log</Button>}<Button size="sm" variant="outline" onClick={csv} disabled={!state}><Download aria-hidden className="h-4 w-4" />Download</Button></div>} />
    {err !== undefined ? <ErrorBanner className="m-5" error={err} /> : !state ? <div className="space-y-3 p-5"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div> : <>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
        <p role="status" className={cn('flex items-center gap-2 text-sm font-medium', state.chainOk ? 'text-emerald-800' : 'text-rose-800')}><ShieldCheck aria-hidden className="h-4 w-4" />{state.chainOk ? 'Record intact: no entry has been changed or removed.' : 'Warning: the record has been tampered with. Tell your administrator now.'}</p>
        <label className="flex items-center gap-2 text-sm text-ink-700"><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} />Show every system step ({lines.length})</label>
      </div>
      <ol className="divide-y divide-line">{shown.map(({ e, l }) => { const I = l.icon; return (
        <li key={e.seq} className="flex gap-3 px-5 py-3.5">
          <span className={cn('grid h-9 w-9 shrink-0 place-items-center rounded-xl', TONE[l.tone])}><I aria-hidden className="h-4 w-4" /></span>
          <div className="min-w-0 flex-1"><p className="text-sm text-ink-900">{l.text}</p>{l.note && <p className="mt-0.5 text-sm text-ink-700">{l.note}</p>}<p className="mt-0.5 text-xs text-ink-500">{dt(e.ts)}</p></div>
        </li>); })}
        {!shown.length && <li className="p-10 text-center text-sm text-ink-500">Nothing has happened on this case yet.</li>}</ol>
    </>}
  </Card>);
}
