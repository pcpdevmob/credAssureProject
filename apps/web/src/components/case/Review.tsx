'use client';
import { useState } from 'react';
import type { CaseRecord, ApprovalDecision, User } from '@/types';
import { Card, CardHeader, Button, Textarea, Badge, StageBadge } from '../ui';
import { approvalService, supervisorService, type ReturnStage } from '@/services';
import { inr, inrShort } from '@/lib/format';
import { CheckCircle2, XCircle, Undo2, Send, ShieldCheck, PauseCircle, Lock } from 'lucide-react';

const APPROVER = { VP_FINANCE: 'VP, Finance', DIRECTOR_FINANCE: 'Director, Finance', HELD_PENDING_POLICY: 'a human decision' } as const;

export default function Review({ c, need, user, onChange }: { c: CaseRecord; need?: number; user: User; onChange: () => void }) {
  const [comment, setComment] = useState(''); const [back, setBack] = useState<ReturnStage>('working_capital');
  const [busy, setBusy] = useState(''); const [err, setErr] = useState('');
  const can = approvalService.canDecide(c, user);
  const act = async (d: ApprovalDecision['decision']) => { setErr(''); setBusy(d); try { await approvalService.decide(c, d, comment, back); setComment(''); onChange(); } catch (e) { setErr((e as Error).message); } setBusy(''); };
  const run = async () => { setErr(''); setBusy('run'); try { await supervisorService.run(c.id); onChange(); } catch (e) { setErr((e as Error).message); } setBusy(''); };
  return (<div className="grid gap-6 lg:grid-cols-3">
    <div className="space-y-6 lg:col-span-2">
      <Card><CardHeader title="Proposal summary" sub="Numbers come from the fact ledger; the gateway routes by code" icon={<ShieldCheck className="h-4 w-4" />} />
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Order</p><p className="mt-1 text-sm"><b>{c.msmeName}</b> · {c.orderRef} ({inrShort(c.orderValue)}), due {c.customerDueDate}</p></div>
          <div className="rounded-xl bg-slate-50 p-4"><p className="text-xs uppercase text-slate-500">Validated funding need</p><p className="num mt-1 text-xl font-bold">{need !== undefined ? inr(need) : '—'}</p><p className="text-xs text-slate-500">indicative request {inrShort(c.requestedAmount)}</p></div>
        </div>
        {c.nextAction && <p className="border-t border-slate-100 p-5 text-sm text-slate-600">{c.nextAction}</p>}
      </Card>
      <Card className="p-5 text-sm text-slate-600">Decision history is recorded in the append-only audit log (evaluator view). Approval is an internal sign-off on this proposal only: it is not loan acceptance, and the MSME chooses its lender outside the system.</Card>
    </div>
    <div className="space-y-6">
      <Card className="p-5"><p className="text-sm text-slate-500">Status</p><p className="mt-1"><StageBadge s={c.stage} /></p>
        {c.routedTo && <p className="mt-3 text-sm text-slate-600">Routed to <Badge tone="blue">{APPROVER[c.routedTo]}</Badge></p>}</Card>
      {c.stage === 'ROUTING_HELD' && <Card className="p-5 ring-1 ring-violet-200"><p className="flex items-center gap-2 font-semibold text-violet-800"><PauseCircle className="h-5 w-5" />Routing held</p><p className="mt-2 text-sm text-slate-600">The validated amount is exactly ₹1.5 crore, so the configured rule holds it for a human decision (APR-03).</p></Card>}
      {user.role === 'PREPARER' && !['AWAITING_APPROVAL', 'ROUTING_HELD', 'APPROVED', 'REJECTED'].includes(c.stage) && <Card className="p-5"><p className="font-semibold">Run the workflow</p><p className="mt-1 text-sm text-slate-500">Runs every stage that is not yet GO. It pauses with one question if data is missing.</p><Button className="mt-4 w-full" onClick={run} loading={busy === 'run'}><Send className="h-4 w-4" />Run</Button></Card>}
      {c.stage === 'AWAITING_APPROVAL' && (can ? (
        <Card className="p-5 ring-2 ring-brand-500/40"><p className="font-semibold">Your decision</p><p className="mt-1 text-xs text-slate-500">Approving does not accept a loan or bind the MSME to any lender.</p>
          <Textarea className="mt-3" placeholder="Comments (required to reject or return)" value={comment} onChange={e => setComment(e.target.value)} />
          <label className="mt-3 block text-xs text-slate-500">If returning, reopen stage
            <select value={back} onChange={e => setBack(e.target.value as ReturnStage)} className="mt-1 h-9 w-full rounded-lg border border-slate-200 bg-white px-2 text-sm"><option value="onboarding">Onboarding</option><option value="working_capital">Working capital</option><option value="lendwise">LendWise</option></select></label>
          {err && <p role="alert" className="mt-2 text-sm text-rose-600">{err}</p>}
          <div className="mt-3 grid gap-2"><Button variant="success" onClick={() => act('APPROVED')} loading={busy === 'APPROVED'}><CheckCircle2 className="h-4 w-4" />Approve</Button>
            <div className="grid grid-cols-2 gap-2"><Button variant="outline" onClick={() => act('RETURNED')} loading={busy === 'RETURNED'}><Undo2 className="h-4 w-4" />Return</Button><Button variant="danger" onClick={() => act('REJECTED')} loading={busy === 'REJECTED'}><XCircle className="h-4 w-4" />Reject</Button></div></div>
        </Card>) : <Card className="p-5 text-sm text-slate-500"><Lock className="mb-2 h-5 w-5 text-slate-400" />Awaiting decision from <Badge tone="blue">{c.routedTo ? APPROVER[c.routedTo] : 'the routed approver'}</Badge>. {user.role === 'PREPARER' ? 'Preparers cannot approve.' : 'This case is routed to a different approver.'}</Card>)}
      {err && c.stage !== 'AWAITING_APPROVAL' && <p role="alert" className="text-sm text-rose-600">{err}</p>}
    </div>
  </div>);
}
