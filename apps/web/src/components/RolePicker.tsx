'use client';
import type { Role } from '@/types';
import { FileEdit, BadgeCheck, Crown } from 'lucide-react';
import { cn } from '@/lib/utils';
const R: { id: Role; label: string; d: string; i: typeof FileEdit }[] = [
  { id: 'PREPARER', label: 'Preparer', d: 'Create & submit', i: FileEdit },
  { id: 'DIRECTOR_FINANCE', label: 'Director, Finance', d: 'Approves < ₹1.5 Cr', i: BadgeCheck },
  { id: 'VP_FINANCE', label: 'VP, Finance', d: 'Approves > ₹1.5 Cr', i: Crown },
];
export default function RolePicker({ value, onChange }: { value: Role; onChange: (r: Role) => void }) {
  return <div className="grid grid-cols-3 gap-2">{R.map(r => (
    <button type="button" key={r.id} onClick={() => onChange(r.id)} className={cn('rounded-xl border p-3 text-left transition', value === r.id ? 'border-brand-500 bg-brand-50 ring-4 ring-brand-500/15' : 'border-slate-200 hover:border-slate-300')}>
      <r.i className={cn('h-5 w-5', value === r.id ? 'text-brand-600' : 'text-slate-400')} /><p className="mt-2 text-xs font-semibold leading-tight text-slate-900 sm:text-sm">{r.label}</p><p className="text-[11px] text-slate-500">{r.d}</p>
    </button>))}</div>;
}
