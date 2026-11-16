'use client';
import { createContext, useCallback, useContext, useState } from 'react';
import type { Fig } from '@/lib/money';
import { approx } from '@/lib/money';
import { cn } from '@/lib/utils';
import ProvenanceDrawer from './ProvenanceDrawer';

// Every figure on a case screen renders through <Figure>: the API's exact display string plus the ◈ provenance mark,
// which opens the lineage drawer (design-plan §4). It never formats or computes; `approx` is only the labelled "≈" reading.

export type Target = { caseId?: string; key?: string; version?: number; label: string; display: string; opener?: HTMLElement | null };
const Ctx = createContext<(t: Target) => void>(() => undefined);

/** One drawer for the whole app. Focus goes back to the figure that opened it (Radix only does that for a Dialog.Trigger). */
export function ProvenanceProvider({ children }: { children: React.ReactNode }) {
  const [target, setTarget] = useState<Target | null>(null);
  const open = useCallback((t: Target) => setTarget({ ...t, opener: document.activeElement as HTMLElement | null }), []);
  return (
    <Ctx.Provider value={open}>
      {children}
      <ProvenanceDrawer target={target} onClose={() => setTarget(null)} />
    </Ctx.Provider>
  );
}

export function Figure({ value, label, caseId, showApprox, className }: { value: Fig; label: string; caseId?: string; showApprox?: boolean; className?: string }) {
  const open = useContext(Ctx);
  const short = showApprox && value.paise !== undefined ? approx(value.paise) : null;
  const sourced = !!(caseId && value.key);
  return (
    <span className={cn('inline-flex flex-col', className)}>
      <button type="button" onClick={() => open({ caseId, key: value.key, label, display: value.display })}
        aria-label={`${label}: ${value.display}, ${sourced ? 'show source' : 'source not available yet'}`}
        className="num group inline-flex items-baseline gap-1 whitespace-nowrap rounded-sm text-left underline decoration-brand-600/50 decoration-dotted decoration-2 underline-offset-4 hover:decoration-brand-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-600">
        <span>{value.display}</span>
        <span aria-hidden className={cn('text-[0.7em] no-underline', sourced ? 'text-brand-600' : 'text-ink-400')}>◈</span>
      </button>
      {short && <span className="num text-xs font-normal text-ink-500">{short}</span>}
    </span>
  );
}
