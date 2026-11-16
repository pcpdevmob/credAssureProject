'use client';
import type { LenderComparison } from '@/types';
import { Card, CardHeader, Badge } from '../ui';
import { Figure } from '../Figure';
import { Trophy, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

// Offers, APR, flags and rank are computed by the gateway (LendWise engines). This view only displays them.
export default function Lenders({ cmp }: { cmp: LenderComparison }) {
  return (<Card><CardHeader title="Lender offers" sub={`${cmp.offers.length} simulated offer(s) · ${cmp.roundsUsed}/${cmp.maxRounds} negotiation round(s) · ranked by APR among comparable, affordable offers`} icon={<Trophy className="h-4 w-4" />} />
    <ul className="divide-y divide-slate-50">{cmp.offers.map(o => {
      const bad = o.flags.some(f => /AFFORD|NON_COMPARABLE|LATE_OR_SHORT/.test(f));
      return (<li key={o.lenderId} className={cn('flex flex-wrap items-center gap-3 px-5 py-4', bad && 'bg-rose-50/60')}>
        <div className="min-w-0 flex-1"><p className="font-medium text-slate-900">{o.lenderName}{o.lenderId === cmp.bestLenderId && <Badge tone="green"> Ranked first</Badge>}</p>
          <p className="text-xs text-slate-500">Rate <Figure value={o.annualRate} label={`${o.lenderName} rate`} caseId={cmp.caseId} /> · APR <b><Figure value={o.apr} label={`${o.lenderName} APR`} caseId={cmp.caseId} /></b> · net disbursal <Figure value={o.netDisbursal} label={`${o.lenderName} net disbursal`} caseId={cmp.caseId} /> · total cost <Figure value={o.totalCost} label={`${o.lenderName} total cost`} caseId={cmp.caseId} /></p>
          {o.flags.map(f => <p key={f} className="mt-1 flex items-center gap-1 text-xs text-rose-700"><AlertTriangle className="h-3 w-3" />{f.replace(/_/g, ' ').toLowerCase()}</p>)}</div>
      </li>);
    })}</ul>
    <p className="border-t border-slate-100 p-4 text-xs text-slate-500">The system never accepts an offer. The MSME chooses its lender outside CredAssure.</p></Card>);
}
