// UI-02, UI thread 20 Nov: the case data as forms and tables (DataEditor), so nobody edits CSV or JSON by hand. Each
// section shows what the case holds now (GET /files). A file can still be uploaded instead; a rejected file or form lists
// every field / row / reason the gateway returned, in plain words (never raw JSON).
import { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, FileText, Loader2, ShieldAlert, AlertTriangle, ChevronDown, Circle, Lock, Pencil, Eye, FileSpreadsheet, Download } from 'lucide-react';
import { Card, CardHeader, Button, Skeleton } from '../ui';
import ErrorBanner from '../ErrorBanner';
import dynamic from 'next/dynamic';
import { plainReason } from '@/lib/caseForms';
const DataEditor = dynamic(() => import('./DataEditor'), { ssr: false, loading: () => <Skeleton className="h-40" /> });
const PdfOffer = dynamic(() => import('./PdfOffer'), { ssr: false, loading: () => <Skeleton className="h-24" /> });
const QuickUpload = dynamic(() => import('./QuickUpload'), { ssr: false, loading: () => <Skeleton className="h-24" /> });
import { documentService, caseFiles, workbookService, type FileKind, type StoredFile, type StoredDoc, type Imported } from '@/services/documents';
import { ApiProblem } from '@/lib/problem';
import { FORMS } from '@/lib/caseForms';
import { ago, dt } from '@/lib/format';
import { cn } from '@/lib/utils';

export const INSTRUCTION_LIKE = 'Instruction-like text found and ignored: documents are data, never instructions.';
export const OTHER_CASE = 'This document names a different case number. It was kept and flagged for review: check it is the right lender document for this case.';
type Result = { name: string; state: 'busy' | 'ok' | 'error'; rows?: number; flagged?: boolean; otherCase?: boolean; error?: unknown };
export const SLOTS: { kind: FileKind; label: string; ext: string; what: string }[] = (['order', 'opening_position', 'costs', 'receipts', 'receivables', 'payables', 'inventory'] as const)
  .map(kind => ({ kind, label: FORMS[kind].title, ext: kind === 'order' || kind === 'opening_position' ? '.json' : '.csv', what: FORMS[kind].intro }));

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
    {r.otherCase && <p className="mt-1 flex gap-1.5 text-gold-800"><ShieldAlert aria-hidden className="h-3.5 w-3.5 shrink-0" />{OTHER_CASE}</p>}
    {r.flagged && <p className="mt-1 flex gap-1.5 text-gold-800"><ShieldAlert aria-hidden className="h-3.5 w-3.5 shrink-0" />{INSTRUCTION_LIKE}</p>}
  </div>);
  const fe = r.error instanceof ApiProblem ? r.error.fieldErrors : [];
  if (!fe.length) return <ErrorBanner className="p-3 text-xs" error={r.error} />;
  return (<div role="alert" className="rounded-xl bg-rose-50 p-3 text-xs ring-1 ring-inset ring-rose-200">
    <p className="flex items-center gap-1.5 font-semibold text-rose-700"><AlertTriangle aria-hidden className="h-3.5 w-3.5" />{r.name} was rejected. Fix these and upload it again:</p>
    <ul className="mt-2 space-y-1 text-ink-800">{fe.map((e, i) => <li key={i}><span className="font-medium">{e.row != null ? `Row ${e.row}` : 'File'}</span>{e.field && <> · <code className="font-mono">{e.field}</code></>} · {plainReason(e.reason)}</li>)}</ul>
  </div>);
}

/** A file upload, the alternative to the form. Also used where a stage asks for a corrected file. */
export function UploadSlot({ caseId, slot, canEdit, onUploaded }: { caseId: string; slot: (typeof SLOTS)[number]; canEdit: boolean; onUploaded?: () => void }) {
  const [list, update] = useResults(caseId, slot.kind);
  const id = `upload-${slot.kind}`;
  return (<div className="space-y-2">
    <div className="flex flex-wrap items-center gap-2 text-xs text-ink-600">
      <label htmlFor={id}>Have it as a file already? Upload it instead <span className="font-mono">({slot.ext})</span>:</label>
      <input id={id} type="file" accept={slot.ext} disabled={!canEdit} className="max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-100 file:px-3 file:py-1 file:text-ink-900 disabled:opacity-50"
        onChange={async e => { const f = e.target.files?.[0]; e.target.value = ''; if (f && await send(caseId, f, slot.kind, update)) onUploaded?.(); }} />
    </div>
    {list[0] && <Outcome r={list[0]} />}
  </div>);
}

function Section({ caseId, file, canEdit, open, setOpen, onSaved }: { caseId: string; file: StoredFile; canEdit: boolean; open: boolean; setOpen: (o: boolean) => void; onSaved: () => void }) {
  const def = FORMS[file.kind]; const slot = SLOTS.find(s => s.kind === file.kind)!; const has = !!file.uploadedAt;
  return (<li className={cn('rounded-2xl ring-1', open ? 'ring-brand-300' : 'ring-line')}>
    <div className="flex flex-wrap items-center gap-3 p-4">
      {has ? <CheckCircle2 aria-hidden className="h-5 w-5 shrink-0 text-emerald-600" /> : <Circle aria-hidden className="h-5 w-5 shrink-0 text-ink-300" />}
      <div className="min-w-0 flex-1"><h4 className="font-medium text-ink-950">{def.title}</h4><p className="text-xs text-ink-600">{def.intro}</p>
        <p className="mt-0.5 text-xs" title={has ? dt(file.uploadedAt) : undefined}>{has ? <span className="text-emerald-800">Provided · {file.rows} {file.rows === 1 ? 'entry' : 'rows'} · updated {ago(file.uploadedAt)}</span> : <span className="text-amber-800">Not provided yet</span>}</p></div>
      <Button size="sm" variant={open ? 'ghost' : has || !canEdit ? 'outline' : 'primary'} aria-expanded={open} aria-controls={`sec-${file.kind}`} onClick={() => setOpen(!open)}>
        {open ? <><ChevronDown aria-hidden className="h-4 w-4 rotate-180" />Close</> : !canEdit ? <><Eye aria-hidden className="h-4 w-4" />View</> : has ? <><Pencil aria-hidden className="h-4 w-4" />Edit</> : 'Fill in'}</Button>
    </div>
    {open && <div id={`sec-${file.kind}`} className="border-t border-line p-4"><DataEditor caseId={caseId} kind={file.kind} stored={file.data} canEdit={canEdit} onSaved={onSaved} /></div>}
    {canEdit && <div className="border-t border-line px-4 py-3"><UploadSlot caseId={caseId} slot={slot} canEdit={canEdit} onUploaded={onSaved} /></div>}
  </li>);
}

/** The lender's own files (offer .json, KFS or schedule of charges .md), several at once. Also shown where the lender
 *  comparison stops and asks for one of them. */
export function LenderUpload({ caseId, onUploaded, id = 'upload-offers', label = 'Or add the lender\u2019s files directly (offer .json, KFS .md; you can pick several at once)' }: { caseId: string; onUploaded?: () => void; id?: string; label?: string }) {
  const [list, update] = useResults(caseId, 'offers');
  return (<div><label htmlFor={id} className="block text-sm font-medium text-ink-900">{label}</label>
    <input id={id} type="file" multiple accept=".json,.md" className="mt-1 max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white"
      onChange={async e => { const files = Array.from(e.target.files ?? []); e.target.value = ''; for (const f of files) { const k = documentService.kindOf(f.name); if (k) await send(caseId, f, k, update); } onUploaded?.(); }} />
    <ul className="mt-2 space-y-2">{list.map(r => <li key={r.name}><Outcome r={r} /></li>)}</ul></div>);
}

function LenderDocs({ caseId, canEdit, docs, onUploaded }: { caseId: string; canEdit: boolean; docs: StoredDoc[]; onUploaded: () => void }) {
  return (<Card><CardHeader title="Documents from lenders" sub="Each lender's offer with its Key Facts Statement and schedule of charges. Needed for the lender comparison." icon={<FileText className="h-4 w-4" />} />
    <div className="space-y-4 p-5">
      {docs.length > 0 ? <ul className="divide-y divide-line rounded-xl ring-1 ring-line">{docs.map(d => <li key={d.name} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 text-sm"><span className="flex items-center gap-2"><CheckCircle2 aria-hidden className="h-4 w-4 text-emerald-600" />{d.name}</span><span className="text-xs text-ink-500">{ago(d.uploadedAt)}</span></li>)}</ul>
        : <p className="text-sm text-amber-800">No lender documents yet.</p>}
      {canEdit && <div className="rounded-xl p-4 ring-1 ring-brand-200"><h4 className="mb-2 font-medium text-ink-950">Add an offer from the lender&apos;s PDFs</h4><PdfOffer caseId={caseId} onSaved={onUploaded} /></div>}
      {canEdit && <LenderUpload caseId={caseId} onUploaded={onUploaded} />}
    </div></Card>);
}


/** ADR 0040: one Excel workbook for the whole case. Sheets left empty are skipped; on any error nothing is stored. */
function ExcelImport({ caseId, onImported }: { caseId: string; onImported: () => void }) {
  const [state, setState] = useState<{ busy?: boolean; done?: Imported[]; error?: unknown; name?: string }>({});
  const [dlErr, setDlErr] = useState<unknown>();
  const label = (sheet: string) => (sheet === 'offers' ? 'Lender offers' : FORMS[sheet]?.title ?? sheet);
  const fe = state.error instanceof ApiProblem ? state.error.fieldErrors : [];
  const docs = state.done?.filter(f => f.kind === 'offer').length ?? 0;
  return (<Card className="ring-1 ring-brand-200"><CardHeader title="Have it in Excel? Upload one workbook" icon={<FileSpreadsheet className="h-4 w-4" />}
      sub="Download the CredAssure Excel template, fill in the sheets you have (one sheet per section below, plus lender offers), and upload it. It is turned into the same case data and checked the same way. Sheets left empty are skipped." />
    <div className="space-y-3 p-5">
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => workbookService.template(false).catch(setDlErr)}><Download aria-hidden className="h-4 w-4" />Blank template</Button>
        <Button size="sm" variant="ghost" onClick={() => workbookService.template(true).catch(setDlErr)}>Example, filled in</Button>
      </div>
      {dlErr !== undefined && <ErrorBanner error={dlErr} />}
      <div><label htmlFor="upload-workbook" className="block text-sm font-medium text-ink-900">Upload the filled workbook (.xlsx)</label>
        <input id="upload-workbook" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" className="mt-1 max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white"
          onChange={async e => { const f = e.target.files?.[0]; e.target.value = ''; if (!f) return; setState({ busy: true, name: f.name });
            try { const done = await workbookService.upload(caseId, f); setState({ done, name: f.name }); onImported(); } catch (err) { setState({ error: err, name: f.name }); } }} /></div>
      {state.busy && <p className="flex items-center gap-1.5 text-sm text-ink-600"><Loader2 aria-hidden className="h-4 w-4 animate-spin" />Reading {state.name}…</p>}
      {state.done && <div role="status" className="rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900 ring-1 ring-emerald-200">
        <p className="flex items-center gap-1.5 font-semibold"><CheckCircle2 aria-hidden className="h-4 w-4" />{state.name} imported</p>
        <ul className="mt-1 list-disc pl-5">{state.done.filter(f => f.kind !== 'offer').map(f => <li key={f.name}>{FORMS[f.kind]?.title ?? f.kind}: {f.rows} {f.rows === 1 ? 'entry' : 'rows'}</li>)}
          {docs > 0 && <li>{docs} lender {docs === 1 ? 'offer' : 'offers'} (add each offer's Key Facts Statement below)</li>}</ul>
        {state.done.some(f => f.otherCase) && <p className="mt-1 text-xs text-gold-800">{OTHER_CASE}</p>}
        {state.done.some(f => f.flagged) && <p className="mt-1 text-xs text-gold-800">{INSTRUCTION_LIKE}</p>}
      </div>}
      {state.error !== undefined && (fe.length ? <div role="alert" className="rounded-xl bg-rose-50 p-3 text-sm ring-1 ring-rose-200">
        <p className="flex items-center gap-1.5 font-semibold text-rose-700"><AlertTriangle aria-hidden className="h-4 w-4" />Nothing was imported from {state.name}. Fix these in the workbook and upload it again:</p>
        <ul className="mt-2 space-y-1 text-ink-800">{fe.map((e, i) => { const [sheet, col] = e.field.split('.'); return <li key={i}><span className="font-medium">Sheet “{label(sheet)}”{e.row != null ? `, row ${e.row}` : ''}</span>{col && <> · column <code className="font-mono">{col}</code></>} · {plainReason(e.reason)}</li>; })}</ul>
      </div> : <ErrorBanner error={state.error} />)}
      <p className="text-xs text-ink-600">Lender offers can also be added from their PDFs under “Documents from lenders”. Bank statements are not read: type the figures into the template or the sections below.</p>
    </div></Card>);
}

export default function Documents({ caseId, canEdit, locked, onChange }: { caseId: string; canEdit: boolean; locked?: boolean; onChange?: () => void }) {
  const [state, setState] = useState<{ files: StoredFile[]; documents: StoredDoc[] } | null>(null); const [err, setErr] = useState<unknown>();
  const [open, setOpen] = useState<string | null>(null);
  const load = useCallback(() => caseFiles.list(caseId).then(setState, setErr), [caseId]);
  useEffect(() => { load(); }, [load]);
  const saved = () => { load(); onChange?.(); };
  const edit = canEdit && !locked;
  const provided = state?.files.filter(f => f.uploadedAt).length ?? 0;
  return (<div className="space-y-6">
    {edit && <QuickUpload caseId={caseId} onChanged={saved} />}
    {edit && <ExcelImport caseId={caseId} onImported={saved} />}
    <Card><CardHeader title="Case data" sub={edit ? 'Fill in each section; it is checked as soon as you save it. When all seven are provided, go to the Workflow tab and press Run.' : 'What was submitted for this case.'}
      right={state && <span className={cn('rounded-full px-3 py-1 text-xs font-semibold', provided === 7 ? 'bg-emerald-50 text-emerald-800' : 'bg-amber-50 text-amber-800')}>{provided} of 7 provided</span>} />
      {locked && canEdit && <p className="mx-5 mt-4 flex items-center gap-2 rounded-xl bg-sunken p-3 text-sm text-ink-700"><Lock aria-hidden className="h-4 w-4" />The case is with the approver, so its data cannot be changed now.</p>}
      {!canEdit && <p className="mx-5 mt-4 text-sm text-ink-600">Only the person preparing the case can change its data.</p>}
      {err !== undefined ? <ErrorBanner className="m-5" error={err} /> : !state ? <div className="space-y-3 p-5"><Skeleton className="h-16" /><Skeleton className="h-16" /></div>
        : <ul className="space-y-3 p-5">{state.files.map(f => <Section key={f.kind} caseId={caseId} file={f} canEdit={edit} open={open === f.kind} setOpen={o => setOpen(o ? f.kind : null)} onSaved={saved} />)}</ul>}
    </Card>
    <LenderDocs caseId={caseId} canEdit={edit} docs={state?.documents ?? []} onUploaded={saved} />
  </div>);
}
