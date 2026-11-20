'use client';
import { useEffect, useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { ArrowLeft, Check, Copy, X } from 'lucide-react';
import type { Target } from './Figure';
import type { Lineage } from '@/services/lineage';
import { lineageService } from '@/services/lineage';
import { d, dt } from '@/lib/format';
import { engineLabel, factLabel, fileLabel } from '@/lib/plain';
import ErrorBanner from './ErrorBanner';
import { Skeleton } from './ui';

// The lineage chain for one ledger fact (design-plan §4). Ledger limits handled here, never hidden:
// producer fields may be null, passages may lack title/section/chunk, and the engine records no formula line.

const NR = <span className="text-ink-500">not recorded</span>;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-line px-5 py-4">
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-500">{title}</h3>
      <div className="space-y-2 text-sm text-ink-800">{children}</div>
    </section>
  );
}
const None = ({ children }: { children: React.ReactNode }) => <p className="text-ink-500">{children}</p>;

function CopyTrace({ id }: { id: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" aria-label={`Copy trace ID ${id}`} className="inline-flex h-8 items-center gap-1 rounded-full px-2 text-xs text-ink-600 ring-1 ring-ink-300 hover:bg-sunken"
      onClick={() => navigator.clipboard?.writeText(id).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }, () => undefined)}>
      {done ? <Check aria-hidden className="h-3.5 w-3.5" /> : <Copy aria-hidden className="h-3.5 w-3.5" />}{done ? 'Copied' : 'Copy'}
    </button>
  );
}

export function LineageView({ l, onOpenFact, technical = false }: { l: Lineage; onOpenFact: (key: string) => void; technical?: boolean }) {
  const p = l.producer;
  const noProducer = !p.agent && !p.stage && !p.trace_id;
  const latest = l.superseded_by === null;
  return (
    <>
      <section className="px-5 pb-4" aria-label="In plain words">
        <p className="text-sm text-ink-600">{factLabel(l.key)}</p>
        <p className="num font-display text-3xl font-semibold text-ink-950">{l.value.display}</p>
        <p className="mt-2 text-sm text-ink-800">{engineLabel(l.engine.name)} worked this out{l.created_at ? ` on ${dt(l.created_at)}` : ''}{l.files.length ? ' from the data you provided:' : l.inputs.length ? ' from these figures:' : '.'}</p>
        {l.files.length > 0 && <ul className="mt-1 list-disc pl-5 text-sm text-ink-800">{[...new Map(l.files.map(f => [f.kind + f.name, f])).values()].map(f => <li key={f.sha256 + f.name}>{fileLabel(f.kind)}{f.kind === 'offer' || f.kind === 'kfs' ? ` (${f.name.replace(/^(offer|kfs):/, '')})` : ''}<span className="text-ink-500">, provided {d(f.uploaded_at)}</span></li>)}</ul>}
        {l.inputs.some(i => i.fact_key) && <ul className="mt-1 space-y-1 text-sm">{l.inputs.filter(i => i.fact_key).map(i => <li key={i.ref}><button type="button" onClick={() => onOpenFact(i.fact_key!)} className="text-left text-brand-700 underline decoration-dotted underline-offset-4">{factLabel(i.fact_key!)}</button></li>)}</ul>}
        {l.passages.length > 0 && <p className="mt-2 text-sm text-ink-800">Sources: {l.passages.map(p => p.title ?? 'a document').join('; ')}.</p>}
        <p className={latest ? 'mt-2 text-sm text-emerald-800' : 'mt-2 text-sm font-medium text-rose-700'}>{latest ? 'This is the current figure.' : 'A newer figure has replaced this one.'}</p>
        <p className="mt-1 text-xs text-ink-500">Calculated by fixed rules, not by the AI. The AI may only quote it.</p>
      </section>
      <details className="border-t border-line" open={technical}>
        <summary className="cursor-pointer px-5 py-3 text-sm font-medium text-ink-700 hover:bg-sunken">Technical details (for auditors)</summary>
      <Section title="Value">
        <p className="num font-display text-2xl font-semibold text-ink-950">{l.value.display}</p>
        <p className="font-mono text-xs text-ink-600">{l.key} · v{l.version}{l.unit ? ` · ${l.unit}` : ''}</p>
        {l.superseded_by !== null
          ? <p className="font-medium text-rose-700">Superseded by v{l.superseded_by}: this is not the latest value.</p>
          : <p className="text-ink-500">Latest version.</p>}
      </Section>
      <Section title="How it was produced">
        <p>Engine <span className="font-mono text-xs">{l.engine.name}{l.engine.version ? `@${l.engine.version}` : ''}</span></p>
        <p className="text-ink-500">The engine records no formula line for this value.</p>
        <p className="text-xs text-ink-500">Written {dt(l.created_at)} · source <span className="font-mono">{l.source_type}</span></p>
      </Section>
      <Section title="Inputs">
        {l.files.length === 0 && l.inputs.length === 0 && <None>No files or other facts cited.</None>}
        {l.files.map(f => (
          <p key={f.sha256 + f.name}>File <b className="font-medium">{f.name}</b> <span className="text-ink-500">({f.kind})</span><br />
            <span className="font-mono text-xs text-ink-600">sha {f.sha256.slice(0, 12)}</span> <span className="text-xs text-ink-500">uploaded {dt(f.uploaded_at)}</span></p>
        ))}
        {l.inputs.map(i => i.fact_key
          ? <button key={i.ref} type="button" onClick={() => onOpenFact(i.fact_key!)} className="block text-left font-mono text-xs text-brand-700 underline decoration-dotted underline-offset-4">◈ {i.fact_key}</button>
          : <p key={i.ref} className="text-xs"><span className="text-ink-500">{i.kind === 'hr_record' ? 'HR record' : i.kind}</span> <span className="font-mono">{i.ref}</span></p>)}
      </Section>
      <Section title="Sources">
        {l.passages.length === 0 ? <None>No document passages cited.</None> : l.passages.map(s => (
          <p key={s.doc_id + (s.chunk_id ?? '')}>{s.title ?? 'Untitled document'} <span className="font-mono text-xs text-ink-500">{s.doc_id}</span>
            {s.section && <><br /><span className="text-xs text-ink-600">{s.section}</span></>}
            {s.chunk_id && <><br /><span className="font-mono text-xs text-ink-500">passage {s.chunk_id}</span></>}</p>
        ))}
      </Section>
      <Section title="Run and audit">
        {noProducer
          ? <None>Producer not recorded: this value was written before provenance tracking, or outside a stage run.</None>
          : <dl className="grid grid-cols-[6rem_1fr] gap-x-2 gap-y-1">
              <dt className="text-ink-500">Agent</dt><dd>{p.agent ?? NR}</dd>
              <dt className="text-ink-500">Stage</dt><dd>{p.stage ?? NR}</dd>
              <dt className="text-ink-500">Trace</dt><dd className="flex flex-wrap items-center gap-2">{p.trace_id ? <><span className="break-all font-mono text-xs">{p.trace_id}</span><CopyTrace id={p.trace_id} /></> : NR}</dd>
            </dl>}
        {p.trace_id && <p className="text-xs text-ink-500">The trace is the first run that wrote this value; an identical re-run adds no version.</p>}
        {l.audit ? <p className="text-xs">Audit event #{l.audit.seq} by <b className="font-medium">{l.audit.actor}</b> at {dt(l.audit.ts)}</p> : <None>No audit event linked.</None>}
      </Section>
      </details>
    </>
  );
}

export default function ProvenanceDrawer({ target, onClose }: { target: Target | null; onClose: () => void }) {
  const [stack, setStack] = useState<string[]>([]);
  const opener = useRef<HTMLElement | null>(null); // kept past close: `target` is already null when focus is restored
  useEffect(() => { if (target) opener.current = target.opener ?? null; }, [target]);
  const [state, setState] = useState<{ l?: Lineage; err?: unknown; loading: boolean }>({ loading: false });
  useEffect(() => { setStack(target?.key ? [target.key] : []); }, [target]);
  const key = stack[stack.length - 1];
  const caseId = target?.caseId;
  useEffect(() => {
    if (!caseId || !key) { setState({ loading: false }); return; }
    let alive = true;
    setState({ loading: true });
    lineageService.get(caseId, key).then(l => alive && setState({ l, loading: false }), err => alive && setState({ err, loading: false }));
    return () => { alive = false; };
  }, [caseId, key]);

  return (
    <Dialog.Root open={!!target} onOpenChange={o => { if (!o) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink-950/40 backdrop-blur-[2px]" />
        <Dialog.Content data-drawer onCloseAutoFocus={e => { if (opener.current?.isConnected) { e.preventDefault(); opener.current.focus(); } }}
          className="fixed z-50 flex flex-col overflow-hidden bg-white text-ink-800 shadow-2xl ring-1 ring-line focus:outline-none inset-x-0 bottom-0 h-[90vh] rounded-t-[24px] sm:inset-x-auto sm:bottom-0 sm:right-0 sm:top-0 sm:h-full sm:w-[420px] sm:rounded-none sm:rounded-l-[24px]">
          <header className="flex items-start gap-2 px-5 pb-3 pt-5">
            {stack.length > 1 && <button type="button" aria-label="Back to previous figure" onClick={() => setStack(s => s.slice(0, -1))} className="grid h-9 w-9 place-items-center rounded-full hover:bg-sunken"><ArrowLeft aria-hidden className="h-4 w-4" /></button>}
            <div className="min-w-0 flex-1">
              <Dialog.Title className="font-display text-lg font-semibold text-ink-950">Source of this figure</Dialog.Title>
              <Dialog.Description className="text-sm text-ink-500">{target?.label}{stack.length > 1 ? ` › ${key}` : ''}</Dialog.Description>
            </div>
            <Dialog.Close aria-label="Close source panel" className="grid h-9 w-9 place-items-center rounded-full hover:bg-sunken"><X aria-hidden className="h-4 w-4" /></Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto pb-6">
            {!key || !caseId ? (
              <Section title="Value">
                <p className="num font-display text-2xl font-semibold text-ink-950">{target?.display}</p>
                <p className="text-ink-600">Source not available yet: the service does not record a ledger fact for this figure.</p>
              </Section>
            ) : state.loading ? (
              <div className="space-y-3 px-5"><Skeleton className="h-8 w-40" /><Skeleton className="h-4 w-64" /><Skeleton className="h-24 w-full" /></div>
            ) : state.err ? (
              <ErrorBanner className="mx-5" error={state.err} />
            ) : state.l ? (
              <LineageView l={state.l} onOpenFact={k => setStack(s => [...s, k])} />
            ) : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
