'use client';
import type { ReadinessResult } from '@/types';
import { Card, CardHeader, GateBadge, Badge } from '../ui';
import { UserCheck, CheckCircle2, XCircle, HelpCircle, FileCheck2 } from 'lucide-react';
import { d } from '@/lib/format';
export default function Readiness({ r }: { r: ReadinessResult }) {
  const mand = r.prerequisites.filter(p => p.mandatory); const done = mand.filter(p => p.status === 'COMPLETE').length;
  return (<div className="grid gap-6 lg:grid-cols-3">
    <Card className="p-5"><div className="flex items-center gap-3"><div className="grid h-12 w-12 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-violet-500 font-semibold text-white">{r.employeeName.split(' ').map(s => s[0]).join('')}</div><div><p className="font-semibold">{r.employeeName}</p><p className="text-xs text-slate-500">{r.employeeId} · {r.role}</p></div></div>
      <dl className="mt-4 space-y-2 text-sm"><div className="flex justify-between"><dt className="text-slate-500">Manager</dt><dd>{r.manager}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Onboarding buddy</dt><dd>{r.buddy}</dd></div><div className="flex justify-between"><dt className="text-slate-500">Checked</dt><dd>{d(r.checkedAt)}</dd></div></dl>
      <div className="mt-5 rounded-2xl bg-slate-50 p-4 text-center"><p className="text-xs uppercase tracking-wide text-slate-500">Readiness gate</p><div className="mt-2 flex justify-center"><GateBadge d={r.decision} /></div>
        <div className="mx-auto mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-200"><div className={`h-full rounded-full ${r.decision === 'GO' ? 'bg-emerald-500' : 'bg-rose-500'}`} style={{ width: `${(done / mand.length) * 100}%` }} /></div>
        <p className="mt-2 text-sm text-slate-600">{done}/{mand.length} mandatory prerequisites evidenced</p></div>
      {r.blockers.length > 0 && <div className="mt-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700"><p className="font-semibold">Financial workflow blocked</p><ul className="mt-1 list-disc pl-4 text-xs">{r.blockers.map(b => <li key={b}>{b}</li>)}</ul></div>}
    </Card>
    <Card className="lg:col-span-2"><CardHeader title="Employee Onboarding Agent" sub="Evidence from simulated HR / LMS / IAM systems. Nothing is marked complete without evidence." icon={<UserCheck className="h-4 w-4" />} />
      <ul className="divide-y divide-slate-50">{r.prerequisites.map(p => (
        <li key={p.id} className="flex items-start gap-3 px-5 py-3.5">
          {p.status === 'COMPLETE' ? <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-500" /> : p.status === 'UNKNOWN' ? <HelpCircle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" /> : <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-500" />}
          <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-medium text-slate-900">{p.name}</p><Badge>{p.category}</Badge>{!p.mandatory && <Badge tone="slate">Optional</Badge>}</div>
            <p className="mt-0.5 flex items-center gap-1 text-xs text-slate-500">{p.evidence ? <><FileCheck2 className="h-3.5 w-3.5" />{p.evidence}{p.completedOn && ` · ${d(p.completedOn)}`}</> : p.status === 'UNKNOWN' ? 'Record unavailable — agent will not infer completion' : `Not completed · owner: ${p.owner}`}</p></div>
        </li>))}</ul></Card>
  </div>);
}
