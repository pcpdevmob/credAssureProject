'use client';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Search, PlusCircle } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import { Card, Input, Button, Skeleton } from '@/components/ui';
import CaseTable from '@/components/CaseTable';
import { caseService } from '@/services';
import type { CaseRecord } from '@/types';
import { cn } from '@/lib/utils';
const F = [['all', 'All'], ['active', 'In progress'], ['approval', 'Awaiting approval'], ['closed', 'Closed']] as const;
export default function Cases() {
  const u = useUser(); const [cases, setCases] = useState<CaseRecord[] | null>(null); const [q, setQ] = useState(''); const [f, setF] = useState<string>('all');
  useEffect(() => { caseService.list().then(setCases); }, []);
  const list = useMemo(() => (cases ?? []).filter(c => (c.msmeName + c.id + c.orderRef).toLowerCase().includes(q.toLowerCase())).filter(c =>
    f === 'all' || (f === 'approval' ? ['AWAITING_APPROVAL', 'ROUTING_HELD'].includes(c.stage) : f === 'closed' ? ['APPROVED', 'REJECTED', 'RETURNED'].includes(c.stage) : !['APPROVED', 'REJECTED', 'RETURNED', 'AWAITING_APPROVAL', 'ROUTING_HELD'].includes(c.stage))), [cases, q, f]);
  return (<>
    <PageHeader title="Cases" sub="Working-capital financing proposals" right={u.role === 'PREPARER' && <Link href="/cases/new/"><Button><PlusCircle className="h-4 w-4" />New case</Button></Link>} />
    <Card>
      <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative sm:w-72"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input className="pl-9" placeholder="Search MSME, case, PO…" value={q} onChange={e => setQ(e.target.value)} /></div>
        <div className="flex gap-1 overflow-x-auto">{F.map(([k, l]) => <button key={k} onClick={() => setF(k)} className={cn('shrink-0 rounded-lg px-3 py-1.5 text-sm', f === k ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100')}>{l}</button>)}</div>
      </div>
      {cases ? list.length ? <CaseTable cases={list} /> : <p className="p-10 text-center text-slate-400">No cases match.</p> : <Skeleton className="m-4 h-40" />}
    </Card>
  </>);
}
