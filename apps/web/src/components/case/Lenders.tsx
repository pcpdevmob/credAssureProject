'use client';
import type { CaseRecord, OfferRow, OfferView } from '@/types';
import { Card, CardHeader, Badge } from '../ui';
import { Figure } from '../Figure';
import Negotiation from './Negotiation';
import { BLOCKING, flagText } from '@/lib/flags';
import { Trophy, AlertTriangle, OctagonX, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

// Offers, APR, flags and rank are computed by the gateway (LendWise engines, BR-06..08). This view only displays them.
// "Cheapest" below is a display sort over the API's own APR strings; rank and affordability are never derived here.
const apr = (o: OfferRow) => (o.aprPct === null ? Infinity : Number(o.aprPct));

export default function Lenders({ c, view, canNegotiate, onChange }: { c: CaseRecord; view: OfferView; canNegotiate: boolean; onChange: () => void }) {
  const preview = view.source === 'preview';
  const cheapest = view.offers.reduce<OfferRow | null>((m, o) => (apr(o) < (m ? apr(m) : Infinity) ? o : m), null);
  const unusable = (o: OfferRow) => !preview && (o.affordable === false || !o.comparable || o.flags.some(f => BLOCKING.has(f)));
  const trap = !preview && cheapest && unusable(cheapest) ? cheapest : null;
  return (<div className="space-y-6">
    {preview && <p role="note" className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200"><Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Read-only preview: affordability and ranking not yet checked. Run the case to check them.</p>}
    {trap && <p role="alert" className="flex gap-2 rounded-xl bg-rose-700 p-4 text-sm font-semibold text-white"><OctagonX aria-hidden className="mt-0.5 h-5 w-5 shrink-0" />
      <span>Offer {trap.id} has the lowest APR ({trap.aprPct}%) but it is not recommended: {trap.affordable === false ? 'its repayments push cash below the minimum buffer' : 'it cannot be compared'}. It is not ranked.</span></p>}
    <Card><CardHeader title="Lender offers" sub={`${view.offers.length} simulated offers · ${preview ? 'not ranked yet' : 'ranked by APR among comparable, affordable offers'}`} icon={<Trophy className="h-4 w-4" />} />
      <ul className="grid gap-4 p-5 md:grid-cols-2 xl:grid-cols-3">{view.offers.map(o => {
        const bad = unusable(o); const k = (l: string, f: OfferRow['apr'], strong?: boolean) => f && <div className="flex justify-between gap-3"><dt className="text-ink-600">{l}</dt><dd className={cn(strong && 'font-semibold')}><Figure value={f} label={`Offer ${o.id} ${l}`} caseId={c.id} /></dd></div>;
        return (<li key={o.id} aria-label={`Offer ${o.id}`} className={cn('rounded-2xl border p-4', bad ? 'border-2 border-rose-700 bg-rose-50' : 'border-line bg-white')}>
          <div className="flex flex-wrap items-center justify-between gap-2"><h4 className="font-semibold text-ink-950">Offer {o.id}</h4>
            {preview ? <Badge>Not yet checked</Badge>
              : bad ? <span className="inline-flex items-center gap-1 rounded-full bg-rose-700 px-2.5 py-0.5 text-xs font-semibold text-white"><OctagonX aria-hidden className="h-3.5 w-3.5" />NOT RANKED</span>
              : o.rank !== null ? <Badge tone="green"><Trophy aria-hidden className="h-3.5 w-3.5" />Rank {o.rank}</Badge> : <Badge>Not ranked</Badge>}</div>
          {cheapest?.id === o.id && <p className="mt-1 text-xs font-medium text-ink-700">▼ Lowest APR of these offers</p>}
          <dl className="mt-3 space-y-1.5 text-sm">{k('APR', o.apr, true)}{k('Total cost', o.totalCost)}{k('Amount received', o.amountReceived)}{k('Total repayment', o.totalRepayment)}
            <div className="flex justify-between gap-3"><dt className="text-ink-600">Affordable</dt><dd>{o.affordable === null ? 'Not yet checked' : o.affordable ? 'Yes' : <b className="text-rose-700">No</b>}</dd></div>
            <div className="flex justify-between gap-3"><dt className="text-ink-600">Comparable</dt><dd>{o.comparable ? 'Yes' : <b className="text-rose-700">No</b>}</dd></div></dl>
          {o.flags.length > 0 && <ul className="mt-3 space-y-1 border-t border-line pt-2">{o.flags.map(f => <li key={f} className={cn('flex gap-1.5 text-xs', BLOCKING.has(f) ? 'font-semibold text-rose-700' : 'text-ink-700')}><AlertTriangle aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" /><span>{flagText(f)}</span></li>)}</ul>}
        </li>);
      })}</ul>
      <p className="border-t border-line p-4 text-xs text-ink-600">The system never accepts an offer. The MSME chooses its lender outside CredAssure.</p></Card>
    <Negotiation c={c} n={view.negotiation} canStart={canNegotiate && !preview} onChange={onChange} />
  </div>);
}
