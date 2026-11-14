'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { UploadedDoc } from '@/types';
import { Card, CardHeader, Badge, Button } from '../ui';
import { documentService } from '@/services';
import { FILE_KINDS } from '@/services/documents';
import { UploadCloud, FileSpreadsheet, FileText, FileType2, Loader2, ShieldAlert } from 'lucide-react';
import { cn } from '@/lib/utils';
import { dt } from '@/lib/format';
const TYPES = [...FILE_KINDS] as string[];
const ICON = { CSV: FileSpreadsheet, JSON: FileText, EXCEL: FileSpreadsheet, PDF: FileText } as const;
const ST: Record<UploadedDoc['status'], ['green' | 'amber' | 'red' | 'blue', string]> = { UPLOADING: ['blue', 'Uploading'], EXTRACTING: ['blue', 'Extracting'], EXTRACTED: ['green', 'Extracted'], NEEDS_REVIEW: ['amber', 'Needs review'], FLAGGED: ['red', 'Security flag'] };
export default function Documents({ caseId, canEdit }: { caseId: string; canEdit: boolean }) {
  const [docs, setDocs] = useState<UploadedDoc[]>([]); const [busy, setBusy] = useState<string[]>([]); const [over, setOver] = useState(false); const [type, setType] = useState(TYPES[0]); const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { documentService.list(caseId).then(setDocs); }, [caseId]);
  const handle = useCallback(async (files: FileList | null) => {
    if (!files) return;
    const ok = Array.from(files).filter(f => /\.(csv|json)$/i.test(f.name));
    setBusy(b => [...b, ...ok.map(f => f.name)]);
    for (const f of ok) { try { const d = await documentService.upload(caseId, f, type); setDocs(x => [...x, d]); } catch (e) { setDocs(x => [...x, { id: f.name + Date.now(), caseId, name: f.name, kind: 'CSV', docType: type, sizeKb: 0, status: 'FLAGGED', fields: 0, warnings: [(e as Error).message], uploadedAt: new Date().toISOString() }]); } setBusy(b => b.filter(n => n !== f.name)); }
  }, [caseId, type]);
  return (<div className="grid gap-6 lg:grid-cols-3">
    <Card className="p-5">
      <p className="font-semibold">Upload financial documents</p><p className="text-sm text-slate-500">JSON (order, opening_position) or CSV (costs, receipts, receivables, payables, inventory). Each file is validated field by field; errors name the field, row and reason.</p>
      <label className="mt-4 block text-sm font-medium text-slate-700">Document type</label>
      <select value={type} onChange={e => setType(e.target.value)} className="mt-1.5 h-10 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm">{TYPES.map(t => <option key={t}>{t}</option>)}</select>
      <div onDragOver={e => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={e => { e.preventDefault(); setOver(false); if (canEdit) handle(e.dataTransfer.files); }} onClick={() => canEdit && ref.current?.click()}
        className={cn('mt-4 grid cursor-pointer place-items-center rounded-2xl border-2 border-dashed p-8 text-center transition', over ? 'border-brand-500 bg-brand-50' : 'border-slate-200 hover:border-brand-300 hover:bg-slate-50', !canEdit && 'cursor-not-allowed opacity-50')}>
        <UploadCloud className="h-10 w-10 text-brand-500" /><p className="mt-2 font-medium">Drag & drop files here</p><p className="text-xs text-slate-500">or click to browse</p>
        <input ref={ref} type="file" multiple accept=".csv,.json" className="hidden" onChange={e => handle(e.target.files)} />
      </div>
      {!canEdit && <p className="mt-2 text-xs text-slate-500">Only the case preparer can upload.</p>}
      <div className="mt-4 flex gap-2 rounded-xl bg-slate-50 p-3 text-xs text-slate-600"><ShieldAlert className="h-4 w-4 shrink-0 text-slate-400" />Uploaded content is treated as untrusted data. Instructions inside documents are never followed.</div>
    </Card>
    <Card className="lg:col-span-2"><CardHeader title="Documents & extraction status" sub={`${docs.length} file(s)`} right={<Button size="sm" variant="outline" onClick={() => ref.current?.click()} disabled={!canEdit}>Add files</Button>} />
      <ul className="divide-y divide-slate-50">
        {busy.map(n => <li key={n} className="flex items-center gap-3 px-5 py-3.5 text-sm"><Loader2 className="h-5 w-5 animate-spin text-brand-500" /><span className="flex-1 truncate">{n}</span><Badge tone="blue">Extracting…</Badge></li>)}
        {docs.map(d => { const I = ICON[d.kind] ?? FileType2; return (
          <li key={d.id} className="flex items-start gap-3 px-5 py-3.5">
            <div className={cn('rounded-lg p-2', d.kind === 'PDF' ? 'bg-rose-50 text-rose-600' : 'bg-emerald-50 text-emerald-600')}><I className="h-5 w-5" /></div>
            <div className="min-w-0 flex-1"><p className="truncate font-medium text-slate-900">{d.name}</p><p className="text-xs text-slate-500">{d.docType} · {d.kind} · {d.sizeKb} KB · {d.fields} fields · {dt(d.uploadedAt)}</p>
              {d.warnings.map(w => <p key={w} className="mt-1 text-xs text-amber-700">⚠ {w}</p>)}</div>
            <Badge tone={ST[d.status][0]}>{ST[d.status][1]}</Badge>
          </li>); })}
        {!docs.length && !busy.length && <li className="p-10 text-center text-sm text-slate-400">No documents yet. Pick a file type, then drop the matching JSON or CSV.</li>}
      </ul></Card>
  </div>);
}
