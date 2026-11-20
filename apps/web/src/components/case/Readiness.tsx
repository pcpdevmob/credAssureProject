'use client';
// Gate 1 in plain words: who is preparing the case, and each readiness rule with the HR record behind it. The gateway sends
// the rule outcomes the Onboarding stage recorded; this view only words them (lib/plain.ts).
import type { ReadinessResult, ReadinessRule } from '@/types';
import { Card, CardHeader, GateBadge } from '../ui';
import { UserCheck, CheckCircle2, XCircle, HelpCircle, Clock } from 'lucide-react';
import { d, dt } from '@/lib/format';
import { ROLE_LABEL, RULE_LABEL, STEP, humanise } from '@/lib/plain';

const initials = (n: string) => n.split(/[\s-]+/).filter(Boolean).slice(0, 2).map(s => s[0]?.toUpperCase()).join('');

function evidence(r: ReadinessRule): string {
  if (r.kind === 'role') return r.role ? `HR role: ${ROLE_LABEL[r.role] ?? humanise(r.role)}` : 'No HR role on record';
  if (r.kind === 'policy') return r.policyAck ? `Accepted version ${r.policyAck.version}${r.policyAck.acknowledged_on ? ` on ${d(r.policyAck.acknowledged_on)}` : ''}` : 'No acceptance on record';
  const t = r.training;
  if (!t) return 'HR has no record of this training';
  const status = t.status === 'completed' ? 'Completed' : t.status === 'in_progress' ? 'Still in progress' : humanise(t.status);
  return [status, t.completed_on && `on ${d(t.completed_on)}`, t.expires_on && `· valid until ${d(t.expires_on)}`].filter(Boolean).join(' ');
}

export default function Readiness({ r }: { r: ReadinessResult }) {
  const passed = r.rules.filter(x => x.outcome === 'PASS').length;
  const notRun = r.decision === 'PENDING';
  return (<div className="grid gap-6 lg:grid-cols-3">
    <Card className="p-5">
      <p className="text-sm text-ink-600">Proposal prepared by</p>
      {r.preparer ? <div className="mt-3 flex items-center gap-3">
        <div aria-hidden className="grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-violet-500 font-semibold text-white">{initials(r.preparer.name)}</div>
        <div><p className="font-semibold text-ink-950">{r.preparer.name}</p><p className="text-xs text-ink-600">{ROLE_LABEL[r.preparer.role] ?? humanise(r.preparer.role)}{r.preparer.department ? ` · ${r.preparer.department}` : ''}</p><p className="text-xs text-ink-500">Employee ID {r.preparer.empId}</p></div>
      </div> : <p className="mt-2 text-sm text-ink-700">No HR record is linked to the preparer of this case. Ask HR to add the employee record.</p>}
      <dl className="mt-4 space-y-2 text-sm"><div className="flex justify-between gap-3"><dt className="text-ink-600">Last checked</dt><dd>{r.checkedAt ? dt(r.checkedAt) : 'Not checked yet'}</dd></div></dl>
      <div className="mt-5 rounded-2xl bg-sunken p-4 text-center">
        <p className="text-sm font-medium text-ink-700">Result</p><div className="mt-2 flex justify-center"><GateBadge d={r.decision} /></div>
        {r.rules.length > 0 && <>
          <div className="mx-auto mt-3 h-2 w-full overflow-hidden rounded-full bg-ink-100" role="img" aria-label={`${passed} of ${r.rules.length} checks passed`}><div className={`h-full rounded-full ${passed === r.rules.length ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{ width: `${(passed / r.rules.length) * 100}%` }} /></div>
          <p className="mt-2 text-sm text-ink-700">{passed} of {r.rules.length} checks passed</p></>}
      </div>
      {r.blockers.length > 0 && <div role="alert" className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-800 ring-1 ring-rose-200"><p className="font-semibold">The rest of the case is on hold until this is fixed</p>
        <ul className="mt-2 space-y-2">{r.blockers.map((b, i) => <li key={i}><p>{(b.message ?? 'Blocked').replace(/\s*\[[^\]]+\]/, '')}</p>{b.nextAction && <p className="text-xs text-rose-700">What to do: {b.nextAction}</p>}</li>)}</ul></div>}
    </Card>
    <Card className="lg:col-span-2"><CardHeader title="Preparer check" sub={STEP.onboarding.does} icon={<UserCheck className="h-4 w-4" />} />
      {notRun || r.rules.length === 0 ? <div className="flex items-start gap-3 p-6 text-sm text-ink-700"><Clock aria-hidden className="mt-0.5 h-5 w-5 text-ink-400" />
        <p>{notRun ? 'Not checked yet. It runs first when you start the workflow on the Workflow tab.' : 'The check ran but recorded no rules. Run the workflow again.'}</p></div>
      : <ul className="divide-y divide-line">{r.rules.map(p => (
        <li key={p.rule} className="flex items-start gap-3 px-5 py-3.5">
          {p.outcome === 'PASS' ? <CheckCircle2 aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" /> : p.outcome === 'UNKNOWN' ? <HelpCircle aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" /> : <XCircle aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />}
          <div className="min-w-0 flex-1"><p className="font-medium text-ink-950">{RULE_LABEL[p.rule] ?? humanise(p.rule)} <span className="sr-only">: {p.outcome === 'PASS' ? 'passed' : p.outcome === 'UNKNOWN' ? 'no record' : 'failed'}</span></p>
            <p className="mt-0.5 text-xs text-ink-600">{evidence(p)}</p></div>
          <span className={`shrink-0 text-xs font-semibold ${p.outcome === 'PASS' ? 'text-emerald-700' : p.outcome === 'UNKNOWN' ? 'text-amber-700' : 'text-rose-700'}`} aria-hidden>{p.outcome === 'PASS' ? 'Passed' : p.outcome === 'UNKNOWN' ? 'No record' : 'Failed'}</span>
        </li>))}</ul>}
      <p className="border-t border-line p-4 text-xs text-ink-600">Read from HR records only. CredAssure never marks a training as complete; HR updates the records.</p>
    </Card>
  </div>);
}
