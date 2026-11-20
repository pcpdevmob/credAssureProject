// A cited source opens in a side panel (UI-06): the passage text from the gateway (plain text, never HTML), its document,
// section, effective date, legal basis and source link. Text under any basis other than L1, L2 or L5 arrives already shortened by the gateway.
import { useEffect, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, ShieldAlert } from 'lucide-react';
import { copilotService, safeUrl, type Citation, type CitedPassage } from '@/services/copilot';
import { d } from '@/lib/format';
import { Button, Skeleton } from '../ui';
import ErrorBanner from '../ErrorBanner';

export default function CitationPanel({ caseId, c, quote, onClose, returnFocus }: { caseId: string | null; c: Citation | null; quote?: string; onClose: () => void; returnFocus?: React.RefObject<HTMLElement | null> }) {
  const [p, setP] = useState<CitedPassage | null>(null); const [err, setErr] = useState<unknown>();
  useEffect(() => {
    setP(null); setErr(undefined); if (!c) return;
    let live = true; copilotService.passage(caseId, c.chunkId, quote).then(x => live && setP(x)).catch(e => live && setErr(e));
    return () => { live = false; };
  }, [caseId, c?.chunkId, quote]); // eslint-disable-line react-hooks/exhaustive-deps
  const link = safeUrl(p?.sourceUrl ?? null);
  return (<Dialog.Root open={c !== null} onOpenChange={o => { if (!o) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-50 bg-ink-950/40" />
    <Dialog.Content onCloseAutoFocus={e => { e.preventDefault(); returnFocus?.current?.focus(); }} className="fixed inset-y-0 right-0 z-50 w-full max-w-md overflow-y-auto bg-card p-6 shadow-xl">
      <div className="flex items-start justify-between gap-3"><Dialog.Title className="font-display text-lg font-semibold text-ink-950">Source</Dialog.Title>
        <Dialog.Close asChild><Button variant="outline" size="sm" aria-label="Close source"><X aria-hidden className="h-4 w-4" /></Button></Dialog.Close></div>
      <Dialog.Description className="mt-1 text-sm text-ink-700">The passage this answer cites.</Dialog.Description>
      {c && <dl className="mt-4 space-y-3 text-sm">
        <div><dt className="text-xs uppercase text-ink-600">Document</dt><dd className="font-medium">{p?.title ?? c.title ?? c.docId}</dd></div>
        <div><dt className="text-xs uppercase text-ink-600">Section</dt><dd>{(p?.section ?? c.section) || 'Not recorded'}</dd></div>
        <div><dt className="text-xs uppercase text-ink-600">Effective date</dt><dd>{(p?.effectiveFrom ?? c.effectiveFrom) ? d((p?.effectiveFrom ?? c.effectiveFrom)!) : 'Not recorded'}</dd></div>
        {p?.legalBasis && <div><dt className="text-xs uppercase text-ink-600">Legal basis</dt><dd>{p.legalBasis}</dd></div>}
        <div><dt className="text-xs uppercase text-ink-600">Reference</dt><dd className="break-all font-mono text-xs">{c.docId} · {c.chunkId}</dd></div>
      </dl>}
      {err !== undefined && <ErrorBanner className="mt-4" error={err} />}
      {c && !p && err === undefined && <Skeleton className="mt-4 h-32" />}
      {p?.injectionFlagged && <p className="mt-4 flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />This text contains instructions aimed at an AI. They were ignored; it is shown only as a quotation.</p>}
      {p && <blockquote className="mt-4 whitespace-pre-wrap break-words rounded-xl bg-sunken p-3 text-sm text-ink-900">{p.text}</blockquote>}
      {p?.truncated && <p className="mt-2 text-xs text-ink-700">Shortened to 600 characters{p.legalBasis ? ` (legal basis ${p.legalBasis})` : ''}. Read the rest at the source.</p>}
      {link && <a href={link} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-sm font-medium text-brand-700 underline">Open the source document</a>}
    </Dialog.Content></Dialog.Portal></Dialog.Root>);
}
