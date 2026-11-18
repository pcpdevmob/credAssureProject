'use client';
import { toCsv } from '@/lib/csv';
import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import type { AuditEvent } from '@/types';
import { auditService } from '@/services';
import { Card, Badge, Input } from './ui';
import { dt } from '@/lib/format';
import { User, Bot, ShieldCheck, Cog, Search, Download } from 'lucide-react';
import { cn } from '@/lib/utils';
const ICON = { HUMAN: User, AGENT: Bot, SUPERVISOR: ShieldCheck, SYSTEM: Cog };
export default function AuditList({ caseId }: { caseId?: string }) {
  const [ev, setEv] = useState<AuditEvent[]>([]); const [q, setQ] = useState(''); const [t, setT] = useState('ALL');
  useEffect(() => { auditService.list(caseId).then(setEv); }, [caseId]);
  const list = useMemo(() => ev.filter(e => (t === 'ALL' || e.actorType === t) && (e.action + e.detail + e.actor + e.caseId).toLowerCase().includes(q.toLowerCase())), [ev, q, t]);
  const csv = () => { const rows = [['at', 'caseId', 'actorType', 'actor', 'action', 'detail', 'severity'], ...list.map(e => [e.at, e.caseId, e.actorType, e.actor, e.action, e.detail, e.severity])]; const b = new Blob([toCsv(rows)], { type: 'text/csv' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = `audit${caseId ? '-' + caseId : ''}.csv`; a.click(); };
  return (<Card>
    <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center">
      <div className="relative flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><Input className="pl-9" placeholder="Search events…" value={q} onChange={e => setQ(e.target.value)} /></div>
      <div className="flex gap-1 overflow-x-auto">{['ALL', 'HUMAN', 'AGENT', 'SUPERVISOR'].map(x => <button key={x} onClick={() => setT(x)} className={cn('shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium', t === x ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100')}>{x}</button>)}</div>
      <button onClick={csv} className="inline-flex items-center gap-1 text-sm font-medium text-brand-600"><Download className="h-4 w-4" />CSV</button>
    </div>
    <ol className="divide-y divide-slate-50">{list.map(e => { const I = ICON[e.actorType]; return (
      <li key={e.id} className="flex gap-3 px-5 py-3.5">
        <div className={cn('grid h-9 w-9 shrink-0 place-items-center rounded-xl', e.severity === 'critical' ? 'bg-rose-50 text-rose-600' : e.severity === 'warn' ? 'bg-amber-50 text-amber-600' : 'bg-slate-100 text-slate-500')}><I className="h-4 w-4" /></div>
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-[11px] font-semibold text-slate-700">{e.action}</span>{!caseId && <Link href={`/case/?id=${e.caseId}&tab=audit`} className="font-mono text-[11px] text-brand-600">{e.caseId}</Link>}{e.severity !== 'info' && <Badge tone={e.severity === 'critical' ? 'red' : 'amber'}>{e.severity}</Badge>}</div>
          <p className="text-sm text-slate-700">{e.detail}</p><p className="text-xs text-slate-400">{e.actor} · {dt(e.at)}</p></div>
      </li>); })}{!list.length && <li className="p-10 text-center text-sm text-slate-400">No events.</li>}</ol>
  </Card>);
}
