// UI-07, APR-04..06: the routed approver decides with a step-up confirm (type the case ID; the password too when the
// gateway answers STEP_UP_REQUIRED, which it does for approvals above ₹1.5 crore, NFR-07). The server enforces the role
// and maker-checker; the UI only hides controls it would refuse. Approval is internal, never loan acceptance.
import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import type { CaseRecord, ApprovalDecision, User } from '@/types';
import { Card, CardHeader, Button, Textarea, Badge, StageBadge, Input } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { approvalService, lendWiseService, type ReturnStage } from '@/services';
import { reportService } from '@/services/report';
import { Figure } from '../Figure';
import { ApiProblem } from '@/lib/problem';
import type { Fig } from '@/lib/money';
import { ShieldCheck, PauseCircle, Lock, Info, Hourglass } from 'lucide-react';
import SafetyPanel from './SafetyPanel';
import { d } from '@/lib/format';

// APR-04, BR-09: what the approver must know about a negotiation round that is newer than the verified comparison.
const WARNING: Record<string, string> = {
  negotiation_in_progress: 'Negotiation in progress: a counted concession is not in the ranking yet. Reload before deciding.',
  revised_offer_not_reaudited: 'Revised offer did not pass re-audit: the lender replied, but no concession counts and the ranking is unchanged.',
  report_stale: 'Report stale: figures changed after this proposal was rendered. The preparer must regenerate it before it can be approved; reject and return still work.',
};

const APPROVER = { VP_FINANCE: 'VP, Finance', DIRECTOR_FINANCE: 'Director, Finance', HELD_PENDING_POLICY: 'VP, Finance (held at ₹1.5 crore)' } as const;
export const INTERNAL = 'Approval is internal, not loan acceptance.';
export const STALE_REASON = 'Approve is unavailable: the report is stale. Ask the preparer to regenerate it.';
const ACTION: Record<ApprovalDecision['decision'], string> = { APPROVED: 'Approve proposal', REJECTED: 'Reject proposal', RETURNED: 'Return to stage' };
const DONE: Record<ApprovalDecision['decision'], string> = { APPROVED: 'Proposal approved', REJECTED: 'Proposal rejected', RETURNED: 'Proposal returned' };
const STAGE_LABEL: Record<ReturnStage, string> = { onboarding: 'Preparer check', working_capital: 'Funding need (case data)', lendwise: 'Lender comparison' };

function Internal() {
  return <p className="flex gap-2 rounded-xl bg-ink-50 p-3 text-sm font-medium text-ink-900 ring-1 ring-line"><Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-ink-600" /><span>{INTERNAL} <span className="font-normal text-ink-600">The MSME chooses its lender outside CredAssure.</span></span></p>;
}

export default function Review({ c, need, user, onChange }: { c: CaseRecord; need?: Fig; user: User; onChange: () => void }) {
  const [choice, setChoice] = useState<ApprovalDecision['decision']>('APPROVED');
  const [comment, setComment] = useState(''); const [back, setBack] = useState<ReturnStage>('working_capital');
  const [open, setOpen] = useState(false); const [typed, setTyped] = useState(''); const [pw, setPw] = useState(''); const [pwNeeded, setPwNeeded] = useState(false); const [code, setCode] = useState('');
  // ADR 0038 AUTH-10: once the approver has MFA, the step-up above ₹1.5 crore also needs a current code from the app.
  const codeNeeded = pwNeeded && !!user.mfaEnabled;
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>(); const [done, setDone] = useState('');
  const [warnings, setWarnings] = useState<string[]>([]); const [shown, setShown] = useState<number | null>(null); const [warnErr, setWarnErr] = useState(false);
  const [attested, setAttested] = useState(false); const [tick, setTick] = useState(0); const [regen, setRegen] = useState(false); const [regenErr, setRegenErr] = useState<unknown>();
  useEffect(() => { lendWiseService.warnings(c).then(w => { setWarnings(w.warnings); setShown(w.reportVersion); setWarnErr(false); }).catch(() => setWarnErr(true)); }, [c.id, c.stage, tick]); // the decision is enforced server-side either way, but say so when the check fails
  // #6, ADR 0003 §3: the gateway refuses approve with REPORT_STALE; the UI explains it and offers the preparer the fix.
  const stale = warnings.includes('report_stale');
  const regenerate = async () => { setRegen(true); setRegenErr(undefined); try { await reportService.regenerate(c.id); setTick(t => t + 1); onChange(); } catch (e) { setRegenErr(e); } setRegen(false); };
  const blocked = choice === 'APPROVED' && stale;
  const unattested = choice === 'APPROVED' && !attested; // P9, ASI09: the approver attests before approving
  const can = approvalService.canDecide(c, user);
  const needsComment = choice !== 'APPROVED' && !comment.trim();
  const confirm = async () => {
    setBusy(true); setErr(undefined);
    try { await approvalService.decide(c, choice, comment, back, pwNeeded ? pw : undefined, shown, attested, codeNeeded ? code.replace(/\s/g, '') : undefined); setOpen(false); setPw(''); setCode(''); setDone(`${DONE[choice]}: ${c.id}.`); onChange(); }
    catch (e) { setErr(e); if (e instanceof ApiProblem && e.code === 'STEP_UP_REQUIRED') { setPwNeeded(true); setPw(''); setCode(''); } }
    setBusy(false);
  };
  return (<div className="grid gap-6 pb-24 lg:grid-cols-3 lg:pb-0">
    <div className="space-y-6 lg:col-span-2">
      {warnErr && <p role="alert" className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200"><Hourglass aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Could not check negotiation status. Reload before deciding.</p>}
      {warnings.length > 0 && <ul aria-label="Negotiation status" className="space-y-2">{warnings.map(w => <li key={w} className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200"><Hourglass aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />{WARNING[w] ?? w}</li>)}</ul>}
      <Card><CardHeader title="Proposal summary" sub="Every figure is calculated by fixed rules; the approver is chosen by amount" icon={<ShieldCheck className="h-4 w-4" />} />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <div className="rounded-xl bg-sunken p-4"><p className="text-xs uppercase text-ink-600">Order</p><p className="mt-1 text-sm"><b>{c.msmeName}</b> · {c.orderRef} (<Figure value={c.orderValue} label="Order value" caseId={c.id} />), due {d(c.customerDueDate)}</p></div>
          <div className="rounded-xl bg-sunken p-4"><p className="text-xs uppercase text-ink-600">Validated funding need</p>{need ? <Figure className="mt-1 text-xl font-bold" value={need} label="Validated funding need" caseId={c.id} showApprox /> : <p className="mt-1 text-xl font-bold">—</p>}<p className="text-xs text-ink-600">indicative request <Figure value={c.requestedAmount} label="Requested amount" caseId={c.id} /></p></div>
        </div>
        {c.nextAction && <p className="border-t border-line p-5 text-sm text-ink-700">{c.nextAction}</p>}
      </Card>
      <SafetyPanel caseId={c.id} />
      <Internal />
    </div>
    <div className="space-y-6">
      <Card className="p-5"><p className="text-sm text-ink-600">Status</p><p className="mt-1"><StageBadge s={c.stage} /></p>
        {c.routedTo && <p className="mt-3 text-sm text-ink-700">Routed to <Badge tone="blue">{APPROVER[c.routedTo]}</Badge></p>}
        {done && <p role="status" className="mt-3 text-sm font-medium text-brand-700">{done}</p>}</Card>
      {stale && user.role === 'PREPARER' && (c.stage === 'AWAITING_APPROVAL' || c.stage === 'ROUTING_HELD') && <Card className="p-5 ring-1 ring-amber-300">
        <p className="font-semibold text-ink-900">Report stale</p><p className="mt-1 text-sm text-ink-700">Figures changed after the report was made, so it cannot be approved. Regenerate it to make a new version from the current figures.</p>
        {regenErr !== undefined && <ErrorBanner className="mt-3" error={regenErr} />}
        <Button className="mt-3 w-full" loading={regen} onClick={regenerate}>Regenerate report</Button></Card>}
      {c.stage === 'ROUTING_HELD' && <Card className="p-5 ring-1 ring-ink-300"><p className="flex items-center gap-2 font-semibold text-ink-900"><PauseCircle className="h-5 w-5" />Held at exactly ₹1.5 crore</p><p className="mt-2 text-sm text-ink-700">The validated amount is exactly ₹1.5 crore, the boundary between the two approvers. Company policy holds such a case for the VP, Finance to decide.</p></Card>}
      {(c.stage === 'AWAITING_APPROVAL' || c.stage === 'ROUTING_HELD') && (can ? (
        <Card className="p-5 ring-2 ring-brand-500/40">
          <fieldset><legend className="font-semibold">Your decision</legend>
            <div className="mt-3 space-y-2 text-sm">{(Object.keys(ACTION) as ApprovalDecision['decision'][]).map(d =>
              <label key={d} className="flex items-center gap-2"><input type="radio" name="decision" checked={choice === d} onChange={() => setChoice(d)} />{ACTION[d]}</label>)}</div>
          </fieldset>
          {choice === 'RETURNED' && <label className="mt-3 block text-sm text-ink-700">Reopen stage
            <select value={back} onChange={e => setBack(e.target.value as ReturnStage)} className="mt-1 h-9 w-full rounded-lg border border-ink-400 bg-white px-2 text-sm">{(Object.keys(STAGE_LABEL) as ReturnStage[]).map(s => <option key={s} value={s}>{STAGE_LABEL[s]}</option>)}</select></label>}
          <label className="mt-3 block text-sm text-ink-700">Comment{choice !== 'APPROVED' && ' (required)'}<Textarea className="mt-1" value={comment} onChange={e => setComment(e.target.value)} /></label>
          {choice === 'APPROVED' && <label className="mt-3 flex items-start gap-2 rounded-lg bg-sunken p-3 text-sm text-ink-800"><input type="checkbox" className="mt-0.5" checked={attested} onChange={e => setAttested(e.target.checked)} /><span>I reviewed the accuracy checks and the safety checks for this case. AI-written text is only a draft; every figure was calculated by fixed rules.</span></label>}
          {err !== undefined && !open && <ErrorBanner className="mt-3" error={err} />}
          <div className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-card p-3 lg:static lg:mt-4 lg:border-0 lg:bg-transparent lg:p-0">
            {blocked && <p id="stale-reason" className="mb-2 text-sm font-medium text-amber-900">{STALE_REASON}</p>}
            <Button className="w-full" aria-describedby={blocked ? 'stale-reason' : undefined} variant={choice === 'REJECTED' ? 'danger' : choice === 'RETURNED' ? 'outline' : 'success'} disabled={needsComment || blocked || unattested} onClick={() => { setTyped(''); setErr(undefined); setOpen(true); }}>{ACTION[choice]}</Button>
          </div>
        </Card>) : <Card className="p-5 text-sm text-ink-600"><Lock className="mb-2 h-5 w-5 text-ink-400" />Awaiting decision from <Badge tone="blue">{c.stage === 'ROUTING_HELD' ? APPROVER.VP_FINANCE : c.routedTo ? APPROVER[c.routedTo] : 'the routed approver'}</Badge>. {user.role === 'PREPARER' ? 'Preparers cannot approve.' : 'This case is routed to a different approver.'}</Card>)}
    </div>
    <Dialog.Root open={open} onOpenChange={o => { setOpen(o); if (!o) setPw(''); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink-950/40" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl bg-card p-6 shadow-xl sm:inset-auto sm:left-1/2 sm:top-1/2 sm:w-[28rem] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl">
          <Dialog.Title className="font-display text-lg font-semibold text-ink-950">{ACTION[choice]} {c.id}?</Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-ink-700">{choice === 'RETURNED' ? `Reopens ${STAGE_LABEL[back]}. ` : ''}This is recorded with your name and time and cannot be edited.</Dialog.Description>
          {need && <p className="mt-3 text-sm">Validated need <Figure value={need} label="Validated funding need" caseId={c.id} /></p>}
          <div className="mt-3"><Internal /></div>
          <label htmlFor="stepup" className="mt-4 block text-sm font-medium text-ink-900">Type the case ID to confirm</label>
          <Input id="stepup" className="mt-1 font-mono" autoComplete="off" value={typed} onChange={e => setTyped(e.target.value)} placeholder={c.id} />
          {pwNeeded && <><label htmlFor="stepup-pw" className="mt-4 block text-sm font-medium text-ink-900">Your password</label>
            <Input id="stepup-pw" type="password" className="mt-1" autoComplete="current-password" value={pw} onChange={e => setPw(e.target.value)} /></>}
          {codeNeeded && <><label htmlFor="stepup-code" className="mt-4 block text-sm font-medium text-ink-900">Code from your authenticator app</label>
            <Input id="stepup-code" inputMode="numeric" autoComplete="one-time-code" maxLength={12} className="mt-1 font-mono tracking-[.3em]" placeholder="123456" value={code} onChange={e => setCode(e.target.value)} /></>}
          {err !== undefined && <ErrorBanner className="mt-3" error={err} />}
          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild><Button variant="outline">Cancel</Button></Dialog.Close>
            <Button variant={choice === 'REJECTED' ? 'danger' : 'success'} disabled={typed.trim() !== c.id || (pwNeeded && !pw) || (codeNeeded && !code.trim())} loading={busy} onClick={confirm}>Confirm: {ACTION[choice].toLowerCase()}</Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </div>);
}
