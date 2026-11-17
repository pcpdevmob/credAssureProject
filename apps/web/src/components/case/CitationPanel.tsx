// A cited source opens in a side panel (UI-06). The gateway returns metadata only (title, section, effective date, chunk ID);
// there is no passage-text endpoint yet, so the panel says so instead of inventing text.
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import type { Citation } from '@/services/copilot';
import { d } from '@/lib/format';
import { Button } from '../ui';

export default function CitationPanel({ c, onClose, returnFocus }: { c: Citation | null; onClose: () => void; returnFocus?: React.RefObject<HTMLElement | null> }) {
  return (<Dialog.Root open={c !== null} onOpenChange={o => { if (!o) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-50 bg-ink-950/40" />
    <Dialog.Content onCloseAutoFocus={e => { e.preventDefault(); returnFocus?.current?.focus(); }} className="fixed inset-y-0 right-0 z-50 w-full max-w-md overflow-y-auto bg-card p-6 shadow-xl">
      <div className="flex items-start justify-between gap-3"><Dialog.Title className="font-display text-lg font-semibold text-ink-950">Source</Dialog.Title>
        <Dialog.Close asChild><Button variant="outline" size="sm" aria-label="Close source"><X aria-hidden className="h-4 w-4" /></Button></Dialog.Close></div>
      <Dialog.Description className="mt-1 text-sm text-ink-700">The passage this answer cites.</Dialog.Description>
      {c && <dl className="mt-4 space-y-3 text-sm">
        <div><dt className="text-xs uppercase text-ink-600">Document</dt><dd className="font-medium">{c.title ?? c.docId}</dd></div>
        <div><dt className="text-xs uppercase text-ink-600">Section</dt><dd>{c.section ?? 'Not recorded'}</dd></div>
        <div><dt className="text-xs uppercase text-ink-600">Effective date</dt><dd>{c.effectiveFrom ? d(c.effectiveFrom) : 'Not recorded'}</dd></div>
        <div><dt className="text-xs uppercase text-ink-600">Reference</dt><dd className="font-mono text-xs">{c.docId} · {c.chunkId}</dd></div>
      </dl>}
      {c && <p className="mt-3 rounded-xl bg-sunken p-3 text-sm text-ink-700">The passage text is not served by the gateway yet. Open the document by its reference to read it.</p>}
    </Dialog.Content></Dialog.Portal></Dialog.Root>);
}
