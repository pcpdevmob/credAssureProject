'use client';
import type { FundingAssessment } from '@/types';
import { Card, CardHeader, GateBadge } from '../ui';
import { Figure } from '../Figure';
import EmptyState from '../EmptyState';
import { LineChart } from 'lucide-react';

// Every figure is a ledger fact from the gateway (BR-05); this view only displays it. The 26-week chart and table are U3.
export default function Funding({ a }: { a: FundingAssessment }) {
  const row = (label: string, f: FundingAssessment['peakShortfall']) => (
    <div className="flex justify-between gap-3"><span className="text-ink-500">{label}</span><Figure value={f} label={label} caseId={a.caseId} /></div>
  );
  return (<div className="space-y-6">
    <div className="grid gap-4 md:grid-cols-2">
      <Card className="p-5"><p className="text-sm text-ink-500">Requested (indicative, entered by preparer)</p>
        <Figure className="mt-1 text-2xl font-semibold text-ink-500" value={a.requestedAmount} label="Requested amount" caseId={a.caseId} showApprox /></Card>
      <Card className="p-5 ring-2 ring-brand-600"><p className="text-sm text-brand-700">Validated funding need</p>
        <Figure className="mt-1 text-2xl font-bold text-ink-950" value={a.recommendedAmount} label="Validated funding need" caseId={a.caseId} showApprox />
        <div className="mt-2"><GateBadge d={a.decision} /></div></Card>
    </div>
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="xl:col-span-2"><EmptyState icon={LineChart} title="26-week cash position" hint={`Peak shortfall in ${a.peakPeriod}. The weekly chart and table arrive with the funding view (U3).`} /></div>
      <Card><CardHeader title="How the need is calculated" sub="Deterministic, reproducible" />
        <div className="space-y-2 p-5 text-sm">
          {row(`Peak cash shortfall (${a.peakPeriod})`, a.peakShortfall)}
          {row('+ Minimum cash buffer', a.minCashBuffer)}
          {row('− Undrawn credit limits', a.existingFacility)}
          <div className="flex justify-between gap-3 border-t border-line pt-2 font-semibold"><span>Recommended facility</span><Figure value={a.recommendedAmount} label="Recommended facility" caseId={a.caseId} /></div>
        </div>
        {a.drivers.length > 0 && <div className="border-t border-line p-5 text-sm"><p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">Bridge from the request</p>
          <ul className="space-y-1">{a.drivers.map(d => <li key={d.label} className="flex justify-between gap-3"><span className="text-ink-600">{d.label}</span><Figure value={d.amount} label={`Bridge: ${d.label}`} caseId={a.caseId} /></li>)}</ul></div>}
      </Card>
    </div>
  </div>);
}
