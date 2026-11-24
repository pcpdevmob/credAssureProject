'use client';
// One upload step for a case (owner, 24 Nov): drop the Excel workbook, the lender's PDFs and any lender files together.
// Each file goes to the import that already exists for it, with the same server checks; lender PDFs open the ADR 0041
// review one offer at a time, and nothing from a PDF is saved until the person has checked it.
import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { AlertTriangle, CheckCircle2, FileStack, Loader2, ShieldAlert } from 'lucide-react';
import { Card, CardHeader, Skeleton } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { ApiProblem } from '@/lib/problem';
import { FORMS, plainReason } from '@/lib/caseForms';
import { ACCEPT, groupPdfs, pendingUploads, sortFiles, type PdfGroup } from '@/lib/intake';
import { documentService, workbookService } from '@/services/documents';
import { INSTRUCTION_LIKE, OTHER_CASE } from './Documents';
const PdfOffer = dynamic(() => import('./PdfOffer'), { ssr: false, loading: () => <Skeleton className="h-24" /> });

type Line = { name: string; state: 'busy' | 'ok' | 'error' | 'skipped'; text?: string; error?: unknown; flagged?: boolean; otherCase?: boolean };

export default function QuickUpload({ caseId, onChanged }: { caseId: string; onChanged: () => void }) {
  const [lines, setLines] = useState<Line[]>([]);
  const [groups, setGroups] = useState<PdfGroup[]>([]); const [at, setAt] = useState(0);
  const [unmatched, setUnmatched] = useState<File[]>([]);
  const started = useRef(false);
  const put = (l: Line) => setLines(ls => [...ls.filter(x => x.name !== l.name), l]);

  async function process(files: File[]) {
    if (!files.length) return;
    const s = sortFiles(files); let changed = false;
    // The workbook first (it can hold offers), then offers, then their KFS / schedules: a KFS names its offer.
    for (const f of s.workbooks) {
      put({ name: f.name, state: 'busy' });
      try {
        const done = await workbookService.upload(caseId, f); changed = true;
        const data = done.filter(d => d.kind !== 'offer').map(d => FORMS[d.kind]?.title ?? d.kind); const offers = done.length - data.length;
        put({ name: f.name, state: 'ok', text: `case data imported (${data.join(', ') || 'no sections'})${offers ? ` and ${offers} lender ${offers === 1 ? 'offer' : 'offers'}` : ''}`,
          flagged: done.some(d => d.flagged), otherCase: done.some(d => d.otherCase) });
      } catch (e) { put({ name: f.name, state: 'error', error: e }); }
    }
    for (const f of [...s.offers, ...s.kfsDocs]) {
      const kind = documentService.kindOf(f.name)!;
      put({ name: f.name, state: 'busy' });
      try { const r = await documentService.upload(caseId, f, kind); changed = true; put({ name: f.name, state: 'ok', text: kind === 'offer' ? 'lender offer added' : 'Key Facts Statement / schedule added', ...r }); }
      catch (e) { put({ name: f.name, state: 'error', error: e }); }
    }
    for (const f of s.unsupported) put({ name: f.name, state: 'skipped', text: 'not read: use an Excel workbook (.xlsx), a PDF, or a lender file (.json, .md)' });
    const g = groupPdfs(s.pdfs);
    if (g.groups.length) { setGroups(gs => [...gs, ...g.groups]); }
    setUnmatched(u => [...u, ...g.unmatched]);
    if (changed) onChanged();
  }

  useEffect(() => {  // files chosen on the New case page
    if (started.current) return; started.current = true;
    process(pendingUploads.take(caseId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  const current = groups[at];
  return (<Card className="ring-1 ring-brand-300"><CardHeader title="Add all the documents at once" icon={<FileStack className="h-4 w-4" />}
      sub="Pick the case's Excel workbook and the lenders' PDFs (offer letter, Key Facts Statement, schedule of charges) together. Each file goes to the right place and is checked the same way as below. Figures read from a PDF are saved only after you check them." />
    <div className="space-y-4 p-5">
      <div><label htmlFor="upload-all" className="block text-sm font-medium text-ink-900">Choose files (.xlsx, .pdf; lender files .json, .md)</label>
        <input id="upload-all" type="file" multiple accept={ACCEPT} className="mt-1 max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white"
          onChange={e => { const fs = Array.from(e.target.files ?? []); e.target.value = ''; process(fs); }} /></div>

      {lines.length > 0 && <ul className="space-y-2" aria-label="Files added">{lines.map(l => <li key={l.name} className="text-sm"><LineView l={l} /></li>)}</ul>}

      {current && <div className="rounded-xl p-4 ring-1 ring-violet-200">
        <h4 className="mb-1 font-medium text-ink-950">Check the offer from {current.offer.name}{groups.length > 1 && <span className="font-normal text-ink-600"> ({at + 1} of {groups.length})</span>}</h4>
        <p className="mb-3 text-xs text-ink-600">With it: {[current.kfs && `Key Facts Statement ${current.kfs.name}`, current.schedule && `schedule of charges ${current.schedule.name}`].filter(Boolean).join(' and ') || 'no other PDF (add them below if you have them)'}.</p>
        <PdfOffer key={at} caseId={caseId} preset={current} onSaved={() => { setAt(a => a + 1); onChanged(); }} />
      </div>}
      {groups.length > 0 && at >= groups.length && <p role="status" className="flex items-center gap-1.5 text-sm text-emerald-800"><CheckCircle2 aria-hidden className="h-4 w-4" />Every offer from the PDFs is saved.</p>}

      {unmatched.length > 0 && <p className="flex items-start gap-1.5 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
        Not matched to an offer letter: {unmatched.map(f => f.name).join(', ')}. Add the offer letter PDF with them, or add each one with its offer under “Documents from lenders” below.</p>}
    </div></Card>);
}

function LineView({ l }: { l: Line }) {
  if (l.state === 'busy') return <p className="flex items-center gap-1.5 text-ink-600"><Loader2 aria-hidden className="h-4 w-4 animate-spin" />Reading {l.name}…</p>;
  if (l.state === 'skipped') return <p className="flex items-center gap-1.5 text-amber-800"><AlertTriangle aria-hidden className="h-4 w-4" />{l.name}: {l.text}</p>;
  if (l.state === 'ok') return (<div>
    <p className="flex items-center gap-1.5 text-emerald-800"><CheckCircle2 aria-hidden className="h-4 w-4" />{l.name}: {l.text}</p>
    {l.otherCase && <p className="mt-1 flex gap-1.5 text-xs text-gold-800"><ShieldAlert aria-hidden className="h-3.5 w-3.5 shrink-0" />{OTHER_CASE}</p>}
    {l.flagged && <p className="mt-1 flex gap-1.5 text-xs text-gold-800"><ShieldAlert aria-hidden className="h-3.5 w-3.5 shrink-0" />{INSTRUCTION_LIKE}</p>}
  </div>);
  const fe = l.error instanceof ApiProblem ? l.error.fieldErrors : [];
  if (!fe.length) return <div><p className="font-medium text-rose-700">{l.name} was not added:</p><ErrorBanner className="mt-1" error={l.error} /></div>;
  return (<div role="alert" className="rounded-xl bg-rose-50 p-3 ring-1 ring-rose-200">
    <p className="flex items-center gap-1.5 font-semibold text-rose-700"><AlertTriangle aria-hidden className="h-4 w-4" />Nothing was added from {l.name}. Fix these and add it again:</p>
    <ul className="mt-1 space-y-1 text-ink-800">{fe.map((e, i) => <li key={i}>{e.field && <code className="font-mono">{e.field}</code>}{e.row != null ? `, row ${e.row}` : ''} · {plainReason(e.reason)}</li>)}</ul>
  </div>);
}
