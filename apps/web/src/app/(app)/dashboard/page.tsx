'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion, useReducedMotion } from 'framer-motion';
import { FolderKanban, Inbox, IndianRupee, TrendingDown, PlusCircle, ArrowRight, ChevronDown, ChevronRight, Wallet, MapPin, Landmark } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { Card, Stat, Button, Skeleton, Badge, StageBadge } from '@/components/ui';
import { caseService } from '@/services';
import type { CaseTotals } from '@/services/cases';
import type { CaseRecord } from '@/types';
import { ROLE_LABEL } from '@/types';
import { fig } from '@/lib/money';
import { Figure } from '@/components/Figure';
// Money totals come summed from the gateway (GET /v1/cases totals); the browser only renders them (BR-05).
const pa = (f?: { paise?: number }) => f?.paise ?? 0; // bar height only, never a displayed number
import { CountUp } from '@/components/fx/motion';
import { cn } from '@/lib/utils';


/** "Financing tracker": lollipop chart of validated need per assessed case (Twisty "Income Tracker" layout). */
function FinancingTracker({ cases, totals }: { cases: CaseRecord[]; totals: CaseTotals }) {
  const reduce = useReducedMotion();
  const data = cases.filter(c => c.recommendedAmount).slice(0, 7);
  const max = Math.max(...data.map(c => pa(c.recommendedAmount)), 1);
  const [sel, setSel] = useState(0);
  return (
    <Card className="p-6 sm:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-xl bg-ink-50 text-ink-800 ring-1 ring-line"><Wallet className="h-5 w-5" /></span><h2 className="font-display text-3xl font-light tracking-tight text-ink-950 sm:text-4xl">Financing <span className="font-semibold">Tracker</span></h2></div>
        <span className="rounded-full px-4 py-1.5 text-sm text-ink-700 ring-1 ring-ink-200">Assessed cases</span>
      </div>
      <p className="mt-3 max-w-md text-sm text-ink-500">Validated funding need for each assessed case, after the Working Capital agent nets off buffers and unused limits.</p>
      <div className="mt-6 grid gap-6 md:grid-cols-[minmax(0,13rem)_1fr] md:items-end">
        <div className="order-2 md:order-1">
          <Figure className="font-display text-3xl font-light tracking-tight text-ink-950" value={fig(totals.over_borrowing_avoided)} label="Over-borrowing avoided, all assessed cases" showApprox />
          <p className="mt-1 text-sm text-ink-500">less than requested across {totals.validated_cases} assessed cases (<span className="num">{totals.validated_need.display}</span> validated of <span className="num">{totals.requested_for_validated.display}</span> requested)</p>
        </div>
        <div className="order-1 flex h-64 items-end justify-between gap-1 md:order-2" role="list" aria-label="Validated need by case">
          {data.map((c, i) => { const h = 18 + (pa(c.recommendedAmount) / max) * 72; const on = i === sel; return (
            <button key={c.id} role="listitem" onClick={() => setSel(i)} onMouseEnter={() => setSel(i)} aria-label={`${c.msmeName}: ${c.recommendedAmount?.display}`}
              className={cn('relative h-full flex-1 flex-col items-center justify-end rounded-full pb-1 pt-10 transition', i > 4 ? 'hidden sm:flex' : 'flex', on && 'bg-gradient-to-b from-ink-50 to-ink-100')}>
              {on && <span className="absolute top-1 whitespace-nowrap rounded-full bg-ink-950 px-2.5 py-1 text-[11px] font-medium text-white">{c.recommendedAmount?.display}</span>}
              <motion.span initial={reduce ? false : { height: 0 }} animate={{ height: `${h}%` }} transition={{ duration: .8, delay: i * .06 }} className="relative w-px bg-ink-200">
                <i className={cn('absolute -left-[5px] -top-[5px] h-[11px] w-[11px] rounded-full', on ? 'bg-brand-600' : 'bg-brand-400')} /></motion.span>
              <span className={cn('mt-3 grid h-9 w-9 place-items-center rounded-full text-[10px] font-semibold', on ? 'bg-ink-950 text-white' : 'bg-ink-100 text-ink-700')}>{c.id.slice(-3)}</span>
            </button>); })}
        </div>
      </div>
    </Card>
  );
}

function RecentCases({ cases }: { cases: CaseRecord[] }) {
  const [open, setOpen] = useState<string | undefined>(cases[0]?.id);
  return (
    <div>
      <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-xl text-ink-950">Your recent cases</h2><Link href="/cases/" className="underline-link border-b border-ink-300 text-sm text-ink-700 hover:text-ink-950">See all cases</Link></div>
      <ul className="divide-y divide-line">
        {cases.map((c, i) => { const o = open === c.id; return (
          <li key={c.id} className="py-4">
            <div className="flex items-center gap-3">
              <span className={cn('grid h-10 w-10 shrink-0 place-items-center rounded-xl font-display text-xs font-semibold', ['bg-brand-700 text-white', 'bg-ink-900 text-gold-200', 'bg-gold-100 text-gold-800', 'bg-ink-100 text-ink-800', 'bg-brand-100 text-brand-800'][i % 5])}>{c.msmeName.split(' ').slice(0, 2).map(w => w[0]).join('')}</span>
              <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2 text-sm font-medium text-ink-950"><Link href={`/case/?id=${c.id}`} className="truncate hover:underline">{c.msmeName}</Link><StageBadge s={c.stage} /></div><p className="text-xs text-ink-500">{c.id} · {(c.recommendedAmount ?? c.requestedAmount).display}{c.recommendedAmount ? ' validated' : ' requested'}</p></div>
              <button aria-label={o ? 'Collapse' : 'Expand'} onClick={() => setOpen(o ? undefined : c.id)} className="grid h-9 w-9 place-items-center rounded-full bg-ink-100 text-ink-700 hover:bg-ink-200"><ChevronDown className={cn('h-4 w-4 transition', o && 'rotate-180')} /></button>
            </div>
            {o && <div className="mt-3 pl-[3.25rem] text-sm text-ink-600">
              <div className="flex flex-wrap gap-2"><span className="rounded-full bg-ink-100 px-3 py-1 text-xs text-ink-700">{c.sector}</span>{c.routedTo && <span className="rounded-full bg-ink-100 px-3 py-1 text-xs text-ink-700">{c.routedTo === 'HELD_PENDING_POLICY' ? 'Held at ₹1.5 Cr' : `Routed to ${ROLE_LABEL[c.routedTo as keyof typeof ROLE_LABEL] ?? c.routedTo}`}</span>}</div>
              <p className="mt-2">Order {c.orderRef}, {c.orderValue.display}. Requested {c.requestedAmount.display}.</p>
              {c.city && <p className="mt-2 flex items-center gap-1 text-xs text-ink-500"><MapPin className="h-3.5 w-3.5" />{c.city}</p>}
            </div>}
          </li>); })}
      </ul>
    </div>
  );
}

function Pipeline({ cases }: { cases: CaseRecord[] }) {
  const cols = [['In progress', cases.filter(c => !['AWAITING_APPROVAL', 'ROUTING_HELD', 'APPROVED', 'REJECTED', 'RETURNED'].includes(c.stage)).length, 'bg-ink-300', 'border-ink-300'], ['Awaiting approval', cases.filter(c => ['AWAITING_APPROVAL', 'ROUTING_HELD'].includes(c.stage)).length, 'bg-gold-500', 'border-gold-500'], ['Decided', cases.filter(c => ['APPROVED', 'REJECTED', 'RETURNED'].includes(c.stage)).length, 'bg-ink-900', 'border-ink-900']] as const;
  return (
    <Card className="p-6">
      <div className="flex items-center justify-between"><h2 className="font-display text-xl text-ink-950">Case pipeline</h2><span className="text-xs text-ink-500">{cases.length} cases</span></div>
      <div className="mt-5 grid grid-cols-3 gap-3">
        {cols.map(([l, n, bar, bd]) => <div key={l} className={cn('border-l-2 pl-3', bd)}><p className="text-xs text-ink-500">{l}</p><p className="mt-1 font-display text-3xl text-ink-950 num">{n}</p>
          <div className="mt-4 flex h-12 items-end gap-[5px]" aria-hidden>{Array.from({ length: 9 }, (_, i) => <i key={i} className={cn('w-[2px] flex-1 rounded-full', i < Math.max(1, Math.round(n / Math.max(cases.length, 1) * 18)) ? bar : 'bg-ink-100')} style={{ height: '100%' }} />)}</div></div>)}
      </div>
    </Card>
  );
}


export default function Dashboard() {
  const u = useUser(); const [data, setData] = useState<{ items: CaseRecord[]; totals: CaseTotals } | null>(null);
  useEffect(() => { caseService.summary().then(setData); }, []);
  if (!data) return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-32" />)}</div>;
  const { items: cases, totals } = data;
  const active = cases.filter(c => !['APPROVED', 'REJECTED'].includes(c.stage));
  const mine = cases.filter(c => c.stage === 'AWAITING_APPROVAL' && c.routedTo === u.role);
  const queue = u.role === 'PREPARER' ? cases.filter(c => c.stage === 'AWAITING_APPROVAL') : mine;
  return (<>
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="font-display text-3xl tracking-tight text-ink-950 sm:text-4xl"><span className="font-light">Good day,</span> <span className="font-semibold">{u.name.split(' ')[0]}</span></h1><p className="mt-1.5 text-ink-500">Signed in as <Badge tone="blue">{ROLE_LABEL[u.role]}</Badge></p></div>
      {u.role === 'PREPARER' ? <Link href="/cases/new/"><Button><PlusCircle className="h-4 w-4" />New case</Button></Link> : <Link href="/approvals/"><Button><Inbox className="h-4 w-4" />Open inbox ({mine.length})</Button></Link>}
    </div>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Stat label="Active cases" value={<CountUp value={active.length} />} sub={`${cases.length} total`} icon={<FolderKanban className="h-5 w-5" />} />
      <Stat label={u.role === 'PREPARER' ? 'Awaiting approval' : 'Awaiting your decision'} value={<CountUp value={queue.length} />} sub="Routed by ₹1.5 Cr threshold" icon={<Inbox className="h-5 w-5" />} tone="amber" />
      <Stat label="Validated funding need" value={<Figure className="text-2xl" value={fig(totals.validated_need)} label="Validated funding need, all assessed cases" showApprox />} sub={`across ${totals.validated_cases} assessed cases`} icon={<IndianRupee className="h-5 w-5" />} tone="violet" />
      <Stat label="Over-borrowing avoided" value={<Figure className="text-2xl" value={fig(totals.over_borrowing_avoided)} label="Over-borrowing avoided, all assessed cases" showApprox />} sub="Requested − validated need, by the gateway" icon={<TrendingDown className="h-5 w-5" />} tone="green" />
    </div>
    <div className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_1fr]">
      <div className="space-y-6">
        <FinancingTracker cases={cases} totals={totals} />
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-xl text-ink-950">{u.role === 'PREPARER' ? 'Awaiting approval' : 'Your approvals'}</h2><Link href="/approvals/" className="underline-link border-b border-ink-300 text-sm text-ink-700 hover:text-ink-950">See all</Link></div>
            <ul className="space-y-3">{queue.slice(0, 3).map(c => <li key={c.id}><Link href={`/case/?id=${c.id}`} className="flex items-center gap-3 rounded-full bg-white p-2 pr-3 ring-1 ring-line hover:ring-ink-300"><span className="grid h-10 w-10 place-items-center rounded-full bg-ink-900 text-[11px] font-semibold text-gold-200">{c.id.slice(-3)}</span><div className="min-w-0 flex-1"><p className="flex items-center gap-2 truncate text-sm font-medium text-ink-950">{c.msmeName.split(' ').slice(0, 2).join(' ')}<span className="rounded-full bg-gold-700 px-2 py-0.5 text-[10px] text-white">{(c.recommendedAmount ?? c.requestedAmount).display}</span></p><p className="truncate text-xs text-ink-500">{c.routedTo ? ROLE_LABEL[c.routedTo as keyof typeof ROLE_LABEL] ?? c.routedTo : 'Unrouted'}</p></div><span className="grid h-8 w-8 place-items-center rounded-full bg-ink-50 ring-1 ring-line"><ChevronRight className="h-4 w-4" /></span></Link></li>)}
              {!queue.length && <li className="rounded-3xl bg-white p-4 text-sm text-ink-500 ring-1 ring-line">Nothing waiting right now.</li>}</ul>
          </div>
          <div className="keep-light relative overflow-hidden rounded-[24px] bg-ink-950 p-6 text-white">
            <div aria-hidden className="absolute -right-10 -top-10 h-48 w-48 rounded-full border-[18px] border-white/[.04]" /><div aria-hidden className="absolute -bottom-16 right-6 h-40 w-40 rounded-full border-[14px] border-brand-400/10" />
            <h2 className="relative font-display text-xl">{u.role === 'PREPARER' ? 'Start a new case' : 'Review with evidence'}</h2>
            <p className="relative mt-2 text-sm text-ink-300">{u.role === 'PREPARER' ? 'Agents check readiness, size the funding gap and negotiate with three lenders.' : 'Every gate, offer and comment is on the record before you decide.'}</p>
            <Link href={u.role === 'PREPARER' ? '/cases/new/' : '/approvals/'} className="relative mt-6 flex items-center justify-between rounded-full bg-white px-5 py-3 text-sm font-medium text-ink-950 hover:bg-ink-100">{u.role === 'PREPARER' ? 'Create case' : 'Open approval inbox'}<ArrowRight className="h-4 w-4" /></Link>
          </div>
        </div>
      </div>
      <div className="space-y-6">
        <Card className="p-6"><RecentCases cases={cases.slice(0, 4)} /></Card>
        <Pipeline cases={cases} />
      </div>
    </div>
  </>);
}
