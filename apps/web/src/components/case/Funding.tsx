'use client';
import type { FundingAssessment } from '@/types';
import { Card, CardHeader, GateBadge } from '../ui';
import { Figure } from '../Figure';
import CashChart from './CashChart';
import { LineChart } from 'lucide-react';

// Every figure is a ledger fact from the gateway (BR-05); this view only displays it. The bridge sums to the recommendation in code.
const BRIDGE: [string, string][] = [
  ['indicative_request', 'Indicative request'], ['peak_shortfall_vs_request', 'Peak shortfall compared with the request'],
  ['undrawn_credit_limits', 'Less: undrawn credit limits'], ['min_cash_buffer', 'Plus: minimum cash buffer'],
  ['confirmed_mitigations', 'Less: confirmed mitigations'], ['round_up_to_lakh', 'Rounding up to the next lakh'], ['floor_at_zero', 'Floor at zero'],
];
const label = (code: string) => BRIDGE.find(([c]) => c === code)?.[1] ?? code.replace(/_/g, ' ');
const rank = (code: string) => { const i = BRIDGE.findIndex(([c]) => c === code); return i < 0 ? BRIDGE.length : i; };

export default function Funding({ a }: { a: FundingAssessment }) {
  const row = (text: string, f: FundingAssessment['peakShortfall']) => (
    <div className="flex justify-between gap-3"><span className="text-ink-600">{text}</span><Figure value={f} label={text} caseId={a.caseId} /></div>
  );
  const bridge = [...a.bridge].sort((x, y) => rank(x.code) - rank(y.code));
  return (<div className="space-y-6">
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="p-5"><p className="text-sm text-ink-600">Requested (indicative, entered by the preparer)</p>
        <Figure className="mt-1 text-2xl font-semibold text-ink-600" value={a.requestedAmount} label="Requested amount" caseId={a.caseId} showApprox /></Card>
      <Card className="p-5 ring-2 ring-brand-600"><p className="text-sm text-brand-700">Validated funding need (calculated from weekly cash flows)</p>
        <Figure className="mt-1 text-2xl font-bold text-ink-950" value={a.recommendedAmount} label="Validated funding need" caseId={a.caseId} showApprox />
        <div className="mt-2"><GateBadge d={a.decision} /></div></Card>
    </div>
    <div className="grid gap-6 xl:grid-cols-3">
      <Card className="xl:col-span-2"><CardHeader title="26-week cash position" sub={a.peakWeek === null ? 'Cumulative cash by week' : `Peak shortfall in week ${a.peakWeek}${a.shortfallWeeks === null ? '' : `; ${a.shortfallWeeks} weeks below zero`}`} icon={<LineChart className="h-4 w-4" />} />
        <div className="p-5">{a.cash ? <CashChart cash={a.cash} peakDisplay={a.peakShortfall.display} /> : <p className="text-sm text-ink-600">The weekly table is not available yet.</p>}</div>
      </Card>
      <Card><CardHeader title="How the need is calculated" sub="Deterministic, reproducible" />
        <div className="space-y-2 p-5 text-sm">
          {row(`Peak cash shortfall${a.peakWeek === null ? '' : ` (week ${a.peakWeek})`}`, a.peakShortfall)}
          {row('Plus: minimum cash buffer', a.minCashBuffer)}
          {row('Less: undrawn credit limits', a.existingFacility)}
          <div className="flex justify-between gap-3 border-t border-line pt-2 font-semibold"><span>Recommended facility</span><Figure value={a.recommendedAmount} label="Recommended facility" caseId={a.caseId} /></div>
        </div>
        {bridge.length > 0 && <div className="border-t border-line p-5 text-sm"><h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-600">Bridge from the request</h3>
          <ul className="space-y-1">{bridge.map(d => <li key={d.code} className="flex justify-between gap-3"><span className="text-ink-700">{label(d.code)}</span><Figure value={d.amount} label={`Bridge: ${label(d.code)}`} caseId={a.caseId} /></li>)}</ul>
          <div className="mt-2 flex justify-between gap-3 border-t border-line pt-2 font-semibold"><span>Recommended facility</span><Figure value={a.recommendedAmount} label="Bridge result: recommended facility" caseId={a.caseId} /></div></div>}
      </Card>
    </div>
  </div>);
}
