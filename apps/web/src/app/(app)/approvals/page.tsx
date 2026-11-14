'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Inbox, PauseCircle, ArrowRight } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardHeader, Badge, StageBadge, Button } from '@/components/ui';
import { caseService } from '@/services';
import type { CaseRecord } from '@/types';
import { ROLE_LABEL } from '@/types';
import { inr, d } from '@/lib/format';
export default function Approvals() {
  const u = useUser(); const [cases, setCases] = useState<CaseRecord[]>([]);
  useEffect(() => { caseService.list().then(setCases); }, []);
  const mine = cases.filter(c => c.stage === 'AWAITING_APPROVAL' && (u.role === 'PREPARER' ? c.preparerId === u.id : c.routedTo === u.role));
  const held = cases.filter(c => c.stage === 'ROUTING_HELD');
  const decided = cases.filter(c => ['APPROVED', 'REJECTED', 'RETURNED'].includes(c.stage));
  const Row = ({ c }: { c: CaseRecord }) => (
    <Link href={`/case/?id=${c.id}&tab=review`} className="flex flex-wrap items-center gap-3 px-5 py-4 transition hover:bg-brand-50/40">
      <div className="min-w-0 flex-1"><p className="font-mono text-xs text-brand-700">{c.id}</p><p className="font-medium text-slate-900">{c.msmeName}</p><p className="text-xs text-slate-500">{c.preparerName} · updated {d(c.updatedAt)}</p></div>
      <p className="num font-semibold">{inr(c.recommendedAmount ?? c.requestedAmount)}</p><StageBadge s={c.stage} /><ArrowRight className="h-4 w-4 text-slate-300" />
    </Link>);
  return (<>
    <PageHeader title="Approval inbox" sub={u.role === 'PREPARER' ? 'Your submitted proposals awaiting a decision' : <>Proposals routed to you as <Badge tone="blue">{ROLE_LABEL[u.role]}</Badge></>} />
    <div className="space-y-6">
      <Card><CardHeader title={u.role === 'PREPARER' ? 'Awaiting decision' : 'Needs your decision'} icon={<Inbox className="h-4 w-4" />} right={<Badge tone="amber">{mine.length}</Badge>} />
        {mine.length ? <div className="divide-y divide-slate-50">{mine.map(c => <Row key={c.id} c={c} />)}</div> : <div className="p-10 text-center text-sm text-slate-400">Inbox zero.</div>}
      </Card>
      {held.length > 0 && <Card><CardHeader title="Held — policy decision required" sub="Exactly ₹1.5 crore; approver not defined in BRD (Q-01)" icon={<PauseCircle className="h-4 w-4" />} /><div className="divide-y divide-slate-50">{held.map(c => <Row key={c.id} c={c} />)}</div></Card>}
      <Card><CardHeader title="Recently decided" /><div className="divide-y divide-slate-50">{decided.map(c => <Row key={c.id} c={c} />)}</div></Card>
    </div>
    {u.role === 'PREPARER' && <p className="mt-6 text-center text-sm text-slate-500">Only VP, Finance and Director, Finance can approve. <Link href="/cases/"><Button variant="ghost" size="sm">Go to cases</Button></Link></p>}
  </>);
}
