// UI-02: one slot per case file, plus offers and KFS. A rejected file lists every field / row / reason the gateway
// returned (never raw JSON). The gateway has no file list endpoint, so results are kept per case for this session only.
import { useState } from 'react';
import { CheckCircle2, FileText, Loader2, ShieldAlert, AlertTriangle } from 'lucide-react';
import { Card, CardHeader } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { documentService, type FileKind } from '@/services/documents';
import { ApiProblem } from '@/lib/problem';
import { cn } from '@/lib/utils';

type Result = { name: string; state: 'busy' | 'ok' | 'error'; rows?: number; flagged?: boolean; error?: unknown };
export const SLOTS: { kind: FileKind; label: string; ext: string; what: string }[] = [
  { kind: 'order', label: 'Order', ext: '.json', what: 'Customer order, value, delivery and payment terms' },
  { kind: 'opening_position', label: 'Opening position', ext: '.json', what: 'Opening cash, minimum cash buffer, credit lines' },
  { kind: 'costs', label: 'Costs', ext: '.csv', what: 'Weekly costs by category' },
  { kind: 'receipts', label: 'Receipts', ext: '.csv', what: 'Expected receipts (only confirmed ones count)' },
  { kind: 'receivables', label: 'Receivables', ext: '.csv', what: 'Open invoices and expected collection week' },
  { kind: 'payables', label: 'Payables', ext: '.csv', what: 'Supplier bills and due weeks' },
  { kind: 'inventory', label: 'Inventory', ext: '.csv', what: 'Weekly inventory movement' },
];

// ponytail: session-only memory of upload results; a GET /files endpoint replaces it when the gateway has one.
const memory = new Map<string, Record<string, Result[]>>();
function useResults(caseId: string, key: string) {
  const [list, setList] = useState<Result[]>(() => memory.get(caseId)?.[key] ?? []);
  const update = (fn: (l: Result[]) => Result[]) => setList(l => { const n = fn(l); memory.set(caseId, { ...memory.get(caseId), [key]: n }); return n; });
  return [list, update] as const;
}

async function send(caseId: string, file: File, kind: FileKind, update: (fn: (l: Result[]) => Result[]) => void) {
  const put = (r: Result) => update(l => [r, ...l.filter(x => x.name !== file.name)]);
  put({ name: file.name, state: 'busy' });
  try { const r = await documentService.upload(caseId, file, kind); put({ name: file.name, state: 'ok', ...r }); return true; }
  catch (e) { put({ name: file.name, state: 'error', error: e }); return false; }
}

function Outcome({ r }: { r: Result }) {
  if (r.state === 'busy') return <p className="flex items-center gap-1.5 text-xs text-ink-600"><Loader2 aria-hidden className="h-3.5 w-3.5 animate-spin" />Uploading {r.name}…</p>;
  if (r.state === 'ok') return (<div className="text-xs">
    <p className="flex items-center gap-1.5 text-brand-700"><CheckCircle2 aria-hidden className="h-3.5 w-3.5" />{r.name} accepted · {r.rows} {r.rows === 1 ? 'row' : 'rows'}</p>
    {r.flagged && <p className="mt-1 flex gap-1.5 text-gold-800"><ShieldAlert aria-hidden className="h-3.5 w-3.5 shrink-0" />Instruction-like text found and ignored: documents are data, never instructions.</p>}
  </div>);
  const fe = r.error instanceof ApiProblem ? r.error.fieldErrors : [];
  if (!fe.length) return <ErrorBanner className="p-3 text-xs" error={r.error} />;
  return (<div role="alert" className="rounded-xl bg-rose-50 p-3 text-xs ring-1 ring-inset ring-rose-200">
    <p className="flex items-center gap-1.5 font-semibold text-rose-700"><AlertTriangle aria-hidden className="h-3.5 w-3.5" />{r.name} was rejected. Fix these and upload it again:</p>
    <ul className="mt-2 space-y-1 text-ink-800">{fe.map((e, i) => <li key={i}><span className="font-medium">{e.row != null ? `Row ${e.row}` : 'File'}</span>{e.field && <> · <code className="font-mono">{e.field}</code></>} · {e.reason}</li>)}</ul>
  </div>);
}

/** One labelled file slot. Also used by the stage question to take the corrected file. */
export function UploadSlot({ caseId, slot, canEdit, onUploaded }: { caseId: string; slot: (typeof SLOTS)[number]; canEdit: boolean; onUploaded?: () => void }) {
  const [list, update] = useResults(caseId, slot.kind);
  const id = `upload-${slot.kind}`;
  return (<li className="space-y-2 rounded-2xl p-4 ring-1 ring-line">
    <div className="flex flex-wrap items-start justify-between gap-2">
      <div><label htmlFor={id} className="font-medium text-ink-950">{slot.label} <span className="font-mono text-xs text-ink-500">{slot.ext}</span></label><p className="text-xs text-ink-500">{slot.what}</p></div>
      <input id={id} type="file" accept={slot.ext} disabled={!canEdit} className="max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white disabled:opacity-50"
        onChange={async e => { const f = e.target.files?.[0]; e.target.value = ''; if (f && await send(caseId, f, slot.kind, update)) onUploaded?.(); }} />
    </div>
    {list[0] && <Outcome r={list[0]} />}
  </li>);
}

function OffersSlot({ caseId, canEdit }: { caseId: string; canEdit: boolean }) {
  const [list, update] = useResults(caseId, 'offers');
  return (<Card><CardHeader title="Lender offers and KFS documents" sub="Each offer as JSON; its KFS and schedule of charges as Markdown. Needed for the lender comparison." icon={<FileText className="h-4 w-4" />} />
    <div className="space-y-3 p-5">
      <label htmlFor="upload-offers" className="block text-sm font-medium text-ink-900">Offer and KFS files</label>
      <input id="upload-offers" type="file" multiple accept=".json,.md" disabled={!canEdit} className="max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white disabled:opacity-50"
        onChange={async e => { const files = Array.from(e.target.files ?? []); e.target.value = ''; for (const f of files) { const k = documentService.kindOf(f.name); if (k) await send(caseId, f, k, update); } }} />
      <ul className="space-y-2">{list.map(r => <li key={r.name}><Outcome r={r} /></li>)}</ul>
    </div></Card>);
}

export default function Documents({ caseId, canEdit }: { caseId: string; canEdit: boolean }) {
  return (<div className="space-y-6">
    <Card><CardHeader title="Case files" sub="Upload all seven. Each file is checked field by field; errors name the field, row and reason." />
      <ul className={cn('grid gap-3 p-5 md:grid-cols-2')}>{SLOTS.map(s => <UploadSlot key={s.kind} caseId={caseId} slot={s} canEdit={canEdit} />)}</ul>
      {!canEdit && <p className="px-5 pb-5 text-xs text-ink-500">Only the case preparer can upload.</p>}
    </Card>
    <OffersSlot caseId={caseId} canEdit={canEdit} />
  </div>);
}
