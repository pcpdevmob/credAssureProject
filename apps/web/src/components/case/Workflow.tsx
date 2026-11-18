'use client';
import type { WorkflowGate } from '@/types';
import { Card, CardHeader, GateBadge, AiBadge } from '../ui';
import { cn } from '@/lib/utils';
import { GitBranch, AlertTriangle } from 'lucide-react';
import { motion } from 'framer-motion';
export default function Workflow({ gates }: { gates: WorkflowGate[] }) {
  return (<Card><CardHeader title="Workflow & Supervisor gates" sub="Each gate must return GO before the next agent runs" icon={<GitBranch className="h-4 w-4" />} />
    <ol className="relative p-5">{gates.map((g, i) => {
      const col = g.decision === 'GO' ? 'bg-gradient-to-br from-emerald-400 to-emerald-600 shadow-md shadow-emerald-500/30' : g.decision === 'NO_GO' ? 'bg-rose-500' : g.decision === 'HELD' ? 'bg-violet-500' : g.decision === 'RUNNING' ? 'bg-brand-500 animate-pulse' : 'bg-slate-300';
      return (<motion.li key={g.id} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.09, duration: .4 }} className="relative flex gap-4 pb-6 last:pb-0">
        {i < gates.length - 1 && <motion.span initial={{ scaleY: 0 }} animate={{ scaleY: 1 }} transition={{ delay: i * 0.09 + .2, duration: .5 }} style={{ originY: 0 }} className={cn('absolute left-[15px] top-8 h-[calc(100%-24px)] w-0.5', g.decision === 'GO' ? 'bg-gradient-to-b from-emerald-400 to-emerald-200' : 'bg-slate-200')} />}
        <span className={cn('z-10 grid h-8 w-8 shrink-0 place-items-center rounded-full text-xs font-bold text-white ring-4 ring-white', col)}>{i + 1}</span>
        <div className="min-w-0 flex-1 rounded-xl border border-slate-100 p-3.5 transition hover:border-slate-200 hover:shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-2"><div><p className="font-semibold text-slate-900">{g.name}</p><p className="text-xs text-slate-500">{g.agent}</p></div><GateBadge d={g.decision} /></div>
          <p className="mt-2 text-sm text-slate-600">{g.aiDrafted && <AiBadge className="mr-2 align-middle" />}{g.evidence}</p>
          {g.blockers.map(b => <p key={b} className="mt-2 flex gap-1.5 rounded-lg bg-rose-50 p-2 text-xs text-rose-700"><AlertTriangle className="h-3.5 w-3.5 shrink-0" />{b}</p>)}
          <p className="mt-2 text-xs text-slate-400">Next: {g.next}</p>
        </div></motion.li>);
    })}</ol></Card>);
}
