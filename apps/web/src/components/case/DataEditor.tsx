'use client';
// One case file as a form (order, opening position) or a table (weekly rows). Saving builds the same file the upload
// endpoint already takes and the gateway validates it field by field (UI-02); its errors come back to the field and row
// they name. Rows can be pasted from Excel or Google Sheets. No figure is calculated here.
import { useEffect, useMemo, useRef, useState } from 'react';
import { ClipboardPaste, Plus, Save, Trash2, CheckCircle2, AlertTriangle } from 'lucide-react';
import { Button, Input, Textarea } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { caseFiles, type FileKind } from '@/services/documents';
import { ApiProblem } from '@/lib/problem';
import { plainReason } from '@/lib/caseForms';
export { plainReason };
import { FORMS, blankState, build, emptyRow, placeServerError, rowsFromPaste, stateFromStored, type Field, type FormState, type Problem, type Values } from '@/lib/caseForms';
import { paiseFromInput, inrFromPaise } from '@/lib/money';
import { cn } from '@/lib/utils';

const keyOf = (p: { path: string; row?: number; field: string }) => `${p.path}|${p.row ?? ''}|${p.field}`;

function Cell({ f, value, onChange, error, disabled, id }: { f: Field; value: string; onChange: (v: string) => void; error?: string; disabled?: boolean; id: string }) {
  const bad = !!error;
  const common = { id, disabled, 'aria-invalid': bad, title: error ?? f.help, className: cn('h-9 w-full rounded-lg border bg-white px-2 text-sm disabled:bg-sunken disabled:text-ink-700', bad ? 'border-rose-500 ring-2 ring-rose-200' : 'border-ink-300') };
  if (f.type === 'select' || f.type === 'bool') return (
    <select {...common} value={value} onChange={e => onChange(e.target.value)}>
      {f.need !== 'required' && <option value="">—</option>}
      {f.type === 'bool' && value === '' && <option value="">Choose…</option>}
      {(f.options ?? []).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      {value && !(f.options ?? []).some(([k]) => k === value) && <option value={value}>{value}</option>}
    </select>);
  if (f.type === 'date') return <input {...common} type="date" value={value} onChange={e => onChange(e.target.value)} />;
  return <input {...common} inputMode={f.type === 'money' || f.type === 'int' || f.type === 'percent' ? 'decimal' : undefined} autoComplete="off" placeholder={f.placeholder} value={value}
    onChange={e => onChange(e.target.value)}
    onBlur={() => { if (f.type === 'money' && value.trim()) { const p = paiseFromInput(value); if (p !== null) onChange(inrFromPaise(p)); } }} />;
}

function TableEditor({ fields, rows, setRows, problems, disabled, idBase, dom, minRows = 0 }: {
  fields: Field[]; rows: Values[]; setRows: (r: Values[]) => void; problems: Map<string, string>; disabled?: boolean; idBase: string; dom: string; minRows?: number;
}) {
  const [paste, setPaste] = useState<string | null>(null);
  const set = (i: number, name: string, v: string) => setRows(rows.map((r, k) => (k === i ? { ...r, [name]: v } : r)));
  return (<div className="space-y-2">
    <div className="overflow-x-auto rounded-xl ring-1 ring-line">
      <table className="w-full min-w-[36rem] text-sm">
        <thead className="bg-sunken text-left"><tr><th scope="col" className="w-10 px-2 py-2 text-xs font-medium text-ink-600">#</th>
          {fields.map(f => <th key={f.name} scope="col" className="px-2 py-2 text-xs font-medium text-ink-700" title={f.help}>{f.label}{f.need === 'required' && <span aria-hidden className="text-rose-600"> *</span>}{f.help && <span className="block font-normal text-ink-500">{f.help}</span>}</th>)}
          {!disabled && <th className="w-10"><span className="sr-only">Remove</span></th>}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-line align-top">
          <td className="px-2 py-1.5 text-xs text-ink-500">{i + 1}</td>
          {fields.map(f => { const err = problems.get(`${idBase}|${i + 1}|${f.name}`); return <td key={f.name} className="px-1.5 py-1.5">
            <label className="sr-only" htmlFor={`${dom}-${i}-${f.name}`}>{f.label}, row {i + 1}</label>
            <Cell id={`${dom}-${i}-${f.name}`} f={f} value={r[f.name] ?? ''} onChange={v => set(i, f.name, v)} error={err} disabled={disabled} />
            {err && <p className="mt-0.5 text-xs text-rose-700">{err}</p>}</td>; })}
          {!disabled && <td className="px-1 py-1.5"><button type="button" aria-label={`Remove row ${i + 1}`} disabled={rows.length <= minRows} onClick={() => setRows(rows.filter((_, k) => k !== i))} className="grid h-9 w-9 place-items-center rounded-lg text-ink-500 hover:bg-rose-50 hover:text-rose-700 disabled:opacity-30"><Trash2 aria-hidden className="h-4 w-4" /></button></td>}
        </tr>)}
        {!rows.length && <tr><td colSpan={fields.length + 2} className="p-4 text-center text-sm text-ink-500">No rows yet.</td></tr>}</tbody>
      </table>
    </div>
    {!disabled && <div className="flex flex-wrap gap-2">
      <Button type="button" size="sm" variant="outline" onClick={() => setRows([...rows, emptyRow(fields)])}><Plus aria-hidden className="h-4 w-4" />Add row</Button>
      <Button type="button" size="sm" variant="outline" onClick={() => setPaste('')}><ClipboardPaste aria-hidden className="h-4 w-4" />Paste rows from Excel</Button>
    </div>}
    {paste !== null && <div className="rounded-xl bg-sunken p-3">
      <label htmlFor={`${dom}-paste`} className="text-sm font-medium text-ink-900">Copy the rows in Excel or Google Sheets (columns in this order: {fields.map(f => f.label).join(', ')}), then paste here.</label>
      <Textarea id={`${dom}-paste`} className="mt-2 font-mono text-xs" value={paste} onChange={e => setPaste(e.target.value)} placeholder={fields.map(f => f.label).join('\t')} />
      <div className="mt-2 flex gap-2"><Button type="button" size="sm" onClick={() => { const add = rowsFromPaste(fields, paste); setRows([...rows.filter(r => Object.values(r).some(v => String(v).trim())), ...add]); setPaste(null); }} disabled={!paste.trim()}>Add these rows</Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setPaste(null)}>Cancel</Button></div>
    </div>}
  </div>);
}

export default function DataEditor({ caseId, kind, stored, canEdit, onSaved, focus }: {
  caseId: string; kind: FileKind; stored: unknown; canEdit: boolean; onSaved?: () => void; focus?: string;
}) {
  const def = FORMS[kind];
  const initial = useMemo(() => (stored ? stateFromStored(def, stored) : blankState(def)), [def, stored]);
  const [s, setS] = useState<FormState>(initial);
  useEffect(() => setS(initial), [initial]);
  const [problems, setProblems] = useState<Problem[]>([]); const [err, setErr] = useState<unknown>(); const [busy, setBusy] = useState(false); const [saved, setSaved] = useState<string>('');
  const top = useRef<HTMLDivElement>(null);
  useEffect(() => { if (focus) document.getElementById(`${kind}-field-${focus}`)?.focus(); }, [focus, kind]);
  const map = useMemo(() => new Map(problems.map(p => [keyOf(p), p.reason])), [problems]);
  const save = async () => {
    setErr(undefined); setSaved('');
    const out = build(def, s);
    if (!out.text) { setProblems(out.problems); top.current?.scrollIntoView({ block: 'nearest' }); return; }
    setBusy(true); setProblems([]);
    try { const r = await caseFiles.save(caseId, kind, out.name, out.text); setSaved(`Saved · ${r.rows} ${r.rows === 1 ? 'entry' : 'rows'}${r.flagged ? ' (instruction-like text was found and ignored)' : ''}`); onSaved?.(); }
    catch (e) {
      const fe = e instanceof ApiProblem ? e.fieldErrors : [];
      if (fe.length) setProblems(fe.map(x => { const p = placeServerError(def, x); return { ...p, reason: plainReason(p.reason) }; }));
      else setErr(e);
    }
    setBusy(false);
  };
  const disabled = !canEdit;
  const unplaced = problems.filter(p => def.shape === 'table' ? !p.field || !def.fields.some(f => f.name === p.field) : (p.path === '' ? !def.fields.some(f => f.name === p.field) : !def.tables.some(t => t.name === p.path)));
  return (<div ref={top} className="space-y-4">
    {problems.length > 0 && <div role="alert" className="flex gap-2 rounded-xl bg-rose-50 p-3 text-sm text-rose-800 ring-1 ring-rose-200"><AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /><div>
      <p className="font-semibold">{problems.length === 1 ? 'One thing to fix' : `${problems.length} things to fix`} before this can be saved. They are marked in red below.</p>
      {unplaced.length > 0 && <ul className="mt-1 list-disc pl-5">{unplaced.map((p, i) => <li key={i}>{p.row ? `Row ${p.row}: ` : ''}{p.reason}</li>)}</ul>}</div></div>}
    {def.shape === 'form' ? <>
      <div className="grid gap-4 sm:grid-cols-2">{def.fields.map(f => { const err = map.get(keyOf({ path: '', field: f.name })); return (<div key={f.name}>
        <label htmlFor={`${kind}-field-${f.name}`} className="mb-1 block text-sm font-medium text-ink-900">{f.label}{f.need === 'required' && <span aria-hidden className="text-rose-600"> *</span>}</label>
        <Cell id={`${kind}-field-${f.name}`} f={f} value={s.values[f.name] ?? ''} onChange={v => setS(x => ({ ...x, values: { ...x.values, [f.name]: v } }))} error={err} disabled={disabled} />
        {err ? <p className="mt-1 text-xs text-rose-700">{err}</p> : f.help ? <p className="mt-1 text-xs text-ink-600">{f.help}</p> : f.need === 'needed' && !s.values[f.name] ? <p className="mt-1 text-xs text-amber-800">Needed to work out the funding need.</p> : null}
      </div>); })}</div>
      {def.tables.map(t => <div key={t.name}><h4 className="text-sm font-semibold text-ink-950">{t.label}</h4><p className="mb-2 text-xs text-ink-600">{t.help}</p>
        <TableEditor idBase={t.name} dom={`${kind}-${t.name}`} fields={t.fields} rows={s.tables[t.name] ?? []} setRows={rows => setS(x => ({ ...x, tables: { ...x.tables, [t.name]: rows } }))} problems={map} disabled={disabled} /></div>)}
    </> : <TableEditor idBase="rows" dom={`${kind}-rows`} fields={def.fields} rows={s.tables.rows ?? []} setRows={rows => setS(x => ({ ...x, tables: { rows } }))} problems={map} disabled={disabled} minRows={1} />}
    {err !== undefined && <ErrorBanner error={err} />}
    {!disabled && <div className="flex flex-wrap items-center gap-3">
      <Button type="button" onClick={save} loading={busy}><Save aria-hidden className="h-4 w-4" />Save {def.title.toLowerCase()}</Button>
      {saved && <p role="status" className="flex items-center gap-1.5 text-sm text-brand-700"><CheckCircle2 aria-hidden className="h-4 w-4" />{saved}</p>}
    </div>}
  </div>);
}
