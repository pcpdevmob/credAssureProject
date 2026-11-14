'use client';
import * as React from 'react';
import { cn } from '@/lib/utils';
import type { GateDecision } from '@/types';
import { TiltCard } from './fx/motion';
import { CheckCircle2, XCircle, HelpCircle, Clock, Loader2, PauseCircle } from 'lucide-react';

export const Card = ({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) => <div className={cn('rounded-[24px] border border-line bg-white shadow-[0_1px_2px_rgba(7,12,24,.04),0_10px_30px_-18px_rgba(7,12,24,.18)]', className)} {...p} />;
export const CardHeader = ({ title, sub, right, icon }: { title: React.ReactNode; sub?: React.ReactNode; right?: React.ReactNode; icon?: React.ReactNode }) => (
  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line/70 px-5 py-4 sm:px-6">
    <div className="flex items-start gap-3">{icon && <div className="mt-0.5 grid h-9 w-9 place-items-center rounded-full bg-brand-50 text-brand-700">{icon}</div>}<div><h3 className="font-semibold text-slate-900">{title}</h3>{sub && <p className="text-sm text-slate-500">{sub}</p>}</div></div>{right}
  </div>
);
type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'outline' | 'ghost' | 'danger' | 'success'; size?: 'sm' | 'md' | 'lg'; loading?: boolean };
export const Button = ({ className, variant = 'primary', size = 'md', loading, children, disabled, ...p }: BtnProps) => (
  <button disabled={disabled || loading} className={cn('inline-flex items-center justify-center gap-2 rounded-full font-medium transition active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-50',
    size === 'sm' ? 'h-8 px-3 text-sm' : size === 'lg' ? 'h-12 px-6' : 'h-10 px-4 text-sm',
    variant === 'primary' && 'bg-ink-950 text-white shadow-sm hover:bg-ink-800',
    variant === 'outline' && 'border border-ink-200 bg-white text-ink-800 hover:bg-ink-50',
    variant === 'ghost' && 'text-slate-600 hover:bg-slate-100',
    variant === 'danger' && 'bg-rose-600 text-white hover:bg-rose-700',
    variant === 'success' && 'bg-brand-700 text-white hover:bg-brand-800', className)} {...p}>
    {loading && <Loader2 className="h-4 w-4 animate-spin" />}{children}
  </button>
);
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => <input ref={ref} className={cn('h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none ring-brand-500/30 transition placeholder:text-slate-400 focus:border-brand-400 focus:ring-4', className)} {...p} />);
Input.displayName = 'Input';
export const Textarea = (p: React.TextareaHTMLAttributes<HTMLTextAreaElement>) => <textarea {...p} className={cn('min-h-[96px] w-full rounded-xl border border-slate-200 p-3 text-sm outline-none ring-brand-500/30 focus:border-brand-400 focus:ring-4', p.className)} />;
export const Label = ({ children, hint, htmlFor }: { children: React.ReactNode; hint?: string; htmlFor?: string }) => <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-slate-700">{children}{hint && <span className="ml-1 font-normal text-slate-400">{hint}</span>}</label>;
export const Badge = ({ className, children, tone = 'slate' }: { className?: string; children: React.ReactNode; tone?: 'slate' | 'green' | 'red' | 'amber' | 'blue' | 'violet' }) => (
  <span className={cn('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset',
    { slate: 'bg-slate-50 text-slate-700 ring-slate-200', green: 'bg-emerald-50 text-emerald-700 ring-emerald-200', red: 'bg-rose-50 text-rose-700 ring-rose-200', amber: 'bg-amber-50 text-amber-800 ring-amber-200', blue: 'bg-brand-50 text-brand-700 ring-brand-200', violet: 'bg-violet-50 text-violet-700 ring-violet-200' }[tone], className)}>{children}</span>
);
export const GateBadge = ({ d }: { d: GateDecision }) => {
  const m: Record<GateDecision, [string, 'green' | 'red' | 'amber' | 'blue' | 'slate' | 'violet', React.ReactNode]> = {
    GO: ['GO', 'green', <CheckCircle2 key="i" className="h-3.5 w-3.5" />], NO_GO: ['NO-GO', 'red', <XCircle key="i" className="h-3.5 w-3.5" />],
    NEEDS_INPUT: ['NEEDS INPUT', 'amber', <HelpCircle key="i" className="h-3.5 w-3.5" />], PENDING: ['PENDING', 'slate', <Clock key="i" className="h-3.5 w-3.5" />],
    RUNNING: ['IN PROGRESS', 'blue', <Loader2 key="i" className="h-3.5 w-3.5 animate-spin" />], HELD: ['HELD', 'violet', <PauseCircle key="i" className="h-3.5 w-3.5" />],
  };
  const [l, t, i] = m[d]; return <Badge tone={t}>{i}{l}</Badge>;
};
export const Skeleton = ({ className }: { className?: string }) => <div className={cn('animate-pulse rounded-xl bg-slate-100', className)} />;
export const Stat = ({ label, value, sub, icon, tone = 'brand' }: { label: string; value: React.ReactNode; sub?: React.ReactNode; icon: React.ReactNode; tone?: 'brand' | 'green' | 'amber' | 'violet' }) => {
  const t = { brand: ['!bg-ink-100/80', 'bg-ink-900 text-white'], green: ['!bg-brand-100/70', 'bg-brand-700 text-white'], amber: ['!bg-gold-100/80', 'bg-gold-700 text-white'], violet: ['!bg-sunken', 'bg-ink-700 text-white'] }[tone];
  return (
    <TiltCard className={cn('relative overflow-hidden !rounded-[24px] !border-line p-5', t[0])}>
      <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-white text-ink-900 shadow-sm ring-1 ring-line">{icon}</span><p className="text-sm font-medium text-ink-700">{label}</p></div>
      <p className="mt-5 font-display text-4xl font-semibold tracking-tight text-ink-950 num">{value}</p>
      {sub && <p className={cn('mt-3 inline-flex rounded-full px-2.5 py-1 text-[11px] font-medium', t[1])}>{sub}</p>}
    </TiltCard>
  );
};
export const Tabs = <T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; icon?: React.ReactNode }[]; value: T; onChange: (t: T) => void }) => (
  <div className="-mx-1 flex gap-1 overflow-x-auto rounded-full bg-white p-1 ring-1 ring-line scrollbar-none">
    {tabs.map(t => <button key={t.id} onClick={() => onChange(t.id)} className={cn('flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition', value === t.id ? 'bg-ink-950 text-white shadow-sm' : 'text-ink-600 hover:bg-ink-50 hover:text-ink-950')}>{t.icon}{t.label}</button>)}
  </div>
);
export const STAGE_LABEL: Record<string, [string, 'green' | 'red' | 'amber' | 'blue' | 'slate' | 'violet']> = {
  DRAFT: ['Draft', 'slate'], READINESS: ['Readiness check', 'blue'], DATA_COLLECTION: ['Data collection', 'blue'], FUNDING_ASSESSMENT: ['Funding assessment', 'blue'], LENDER_COMPARISON: ['Lender comparison', 'blue'], NEGOTIATION: ['Negotiation', 'blue'], VERIFICATION: ['Verification', 'blue'],
  AWAITING_APPROVAL: ['Awaiting approval', 'amber'], APPROVED: ['Approved', 'green'], REJECTED: ['Rejected', 'red'], RETURNED: ['Returned for rework', 'red'], ROUTING_HELD: ['Routing held', 'violet'],
};
export const StageBadge = ({ s }: { s: string }) => { const [l, t] = STAGE_LABEL[s] ?? [s, 'slate']; return <Badge tone={t}>{l}</Badge>; };
