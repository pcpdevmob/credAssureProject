'use client';
// U5 evaluation scorecards (evaluator): the 100-item score of the full system beside the best prompt baseline and each
// ablation, per BRD §13 category. Runs start from the command line (make eval); this page only reads them.
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import { Card, Badge, Skeleton } from '@/components/ui';
import { useUser } from '@/components/AppShell';
import { evaluationService, type Scorecard, type RunScore } from '@/services/evaluation';

const CATS = ['regulatory', 'onboarding', 'cashflow', 'offers', 'negotiation', 'routing', 'injection', 'refusal', 'isolation', 'e2e'];
const cell = (r: RunScore, c: string) => { const v = r.byCategory[c]; return v ? `${v[0]}/${v[1]}` : '—'; };

export default function Evaluation() {
  const user = useUser(); const [s, setS] = useState<Scorecard | null>(null); const [err, setErr] = useState(false);
  useEffect(() => { if (user.role === 'EVALUATOR') evaluationService.scorecard().then(setS).catch(() => setErr(true)); }, [user.role]);
  if (user.role !== 'EVALUATOR') return <Card className="p-10 text-center text-sm text-ink-600">Evaluation scorecards are for the evaluator role.</Card>;
  const cols = s ? [s.baseline, s.full, ...s.ablations].filter((x): x is RunScore => x !== null) : [];
  const pass = !!s?.full && (!s.baseline || s.full.passed > s.baseline.passed); // acceptance: above the best baseline (ADR 0043)
  return (<>
    <PageHeader title="Evaluation" sub="Frozen 100-item test set: full system vs the best prompt baseline vs each ablation (BRD §12–13)" />
    {err && <p role="alert" className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">Could not load the scorecard.</p>}
    {!s && !err && <Skeleton className="h-64" />}
    {s && !cols.length && <Card className="p-10 text-center text-sm text-ink-600">No evaluation run yet. Run <code>make eval</code> (and <code>make baseline</code>) on the machine that serves the gateway.</Card>}
    {s && cols.length > 0 && <Card>
      <div className="flex flex-wrap items-center gap-3 border-b border-line p-5">{s.full ? <p className="text-2xl font-bold">{s.full.passed}/{s.full.total}</p> : <p className="text-sm text-ink-600">No full-system run yet.</p>}
        {s.full && <Badge tone={pass ? 'green' : 'amber'}>{pass ? (s.baseline ? 'Above the best baseline' : 'Baseline not run yet') : 'Not above the best baseline'}</Badge>}</div>
      <div className="overflow-x-auto p-5"><table className="w-full text-left text-sm">
        <caption className="sr-only">Passed items per category for each run</caption>
        <thead><tr><th className="border-b border-line px-2 py-1">Category</th>{cols.map(r => <th key={r.label} className="border-b border-line px-2 py-1"><span className="block">{r.label}</span><span className="block text-xs font-normal text-ink-600">{r.detail}</span></th>)}</tr></thead>
        <tbody>{CATS.map(c => <tr key={c}><th scope="row" className="border-b border-line px-2 py-1 font-medium">{c}</th>{cols.map(r => <td key={r.label} className="border-b border-line px-2 py-1 tabular-nums">{cell(r, c)}</td>)}</tr>)}
          <tr><th scope="row" className="px-2 py-1 font-semibold">Total</th>{cols.map(r => <td key={r.label} className="px-2 py-1 font-semibold tabular-nums">{r.passed}/{r.total}</td>)}</tr></tbody>
      </table></div></Card>}
  </>);
}
