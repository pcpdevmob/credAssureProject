'use client';
import Link from 'next/link';
import type { CaseRecord } from '@/types';
import { StageBadge, Badge } from './ui';
import { inrShort, d } from '@/lib/format';
import { ChevronRight } from 'lucide-react';
const RT = { VP_FINANCE: 'VP, Finance', DIRECTOR_FINANCE: 'Director, Finance', HELD_PENDING_POLICY: 'Held (₹1.5 Cr)' } as const;
export default function CaseTable({ cases }: { cases: CaseRecord[] }) {
  return (<>
    <div className="hidden overflow-x-auto md:block"><table className="w-full text-sm">
      <thead><tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500"><th className="px-5 py-3">Case</th><th className="px-3 py-3">MSME / order</th><th className="px-3 py-3 text-right">Requested</th><th className="px-3 py-3 text-right">Validated need</th><th className="px-3 py-3">Stage</th><th className="px-3 py-3">Approver</th><th className="px-3 py-3">Updated</th><th /></tr></thead>
      <tbody>{cases.map(c => (
        <tr key={c.id} className="group border-b border-slate-50 transition hover:bg-brand-50/40">
          <td className="whitespace-nowrap px-5 py-3.5 font-mono text-xs font-semibold text-brand-700"><Link href={`/case/?id=${c.id}`}>{c.id}</Link></td>
          <td className="px-3 py-3.5"><Link href={`/case/?id=${c.id}`} className="font-medium text-slate-900">{c.msmeName}</Link><p className="text-xs text-slate-500">{c.orderRef} · {c.preparerName}</p></td>
          <td className="num px-3 py-3.5 text-right text-slate-500">{inrShort(c.requestedAmount)}</td>
          <td className="num px-3 py-3.5 text-right font-semibold text-slate-900">{c.recommendedAmount ? inrShort(c.recommendedAmount) : '—'}</td>
          <td className="px-3 py-3.5"><StageBadge s={c.stage} /></td>
          <td className="px-3 py-3.5">{c.routedTo ? <Badge tone={c.routedTo === 'HELD_PENDING_POLICY' ? 'violet' : 'slate'}>{RT[c.routedTo]}</Badge> : <span className="text-slate-400">—</span>}</td>
          <td className="px-3 py-3.5 text-xs text-slate-500">{d(c.updatedAt)}</td>
          <td className="pr-4"><Link href={`/case/?id=${c.id}`}><ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-brand-600" /></Link></td>
        </tr>))}</tbody></table></div>
    <div className="divide-y divide-slate-100 md:hidden">{cases.map(c => (
      <Link key={c.id} href={`/case/?id=${c.id}`} className="block p-4 active:bg-slate-50">
        <div className="flex items-center justify-between"><span className="font-mono text-xs font-semibold text-brand-700">{c.id}</span><StageBadge s={c.stage} /></div>
        <p className="mt-1 font-medium text-slate-900">{c.msmeName}</p>
        <div className="mt-1 flex justify-between text-xs text-slate-500"><span>Req {inrShort(c.requestedAmount)}</span><span className="font-semibold text-slate-800">Need {c.recommendedAmount ? inrShort(c.recommendedAmount) : '—'}</span></div>
      </Link>))}</div>
  </>);
}
