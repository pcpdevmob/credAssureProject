'use client';
// ADR 0041: add a lender offer from its PDFs. The AI suggests values (each shown with the words it found them in);
// the person checks every field against the PDF and saves. Saving goes through the same upload checks as a typed file.
import { useState } from 'react';
import { AlertTriangle, CheckCircle2, FileUp, Loader2, Plus, Trash2, Sparkles } from 'lucide-react';
import { Button, Input, AiBadge } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { ApiProblem } from '@/lib/problem';
import { plainReason } from '@/lib/caseForms';
import { OFFER_FIELDS, reviewFromDraft, buildOffer, cleanRows, type Review, type ChargeRow, type OfferDraft } from '@/lib/offerPdf';
import { caseFiles, pdfService, type PdfDoc } from '@/services/documents';

const LENDER_TYPES: [string, string][] = [['', 'Not stated'], ['commercial_bank', 'Commercial bank'], ['nbfc', 'NBFC'], ['sfb', 'Small finance bank'], ['coop_bank', 'Co-operative bank']];
const TIMING: [ChargeRow['timing'], string][] = [['upfront', 'Upfront'], ['monthly', 'Monthly'], ['annual', 'Yearly']];
const pick = 'mt-1 max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white';
const select = 'h-10 w-full rounded-xl border border-ink-400 bg-white px-2 text-sm';
const newId = () => Array.from(crypto.getRandomValues(new Uint8Array(4)), b => 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'[b % 32]).join('');

function PdfPicker({ id, label, doc, caseId, onRead }: { id: string; label: string; doc: PdfDoc; caseId: string; onRead: (r: { text: string; draft: OfferDraft & { rows?: ChargeRow[] }; name: string }) => void }) {
  const [busy, setBusy] = useState<string>(); const [err, setErr] = useState<unknown>();
  return (<div><label htmlFor={id} className="block text-sm font-medium text-ink-900">{label}</label>
    <input id={id} type="file" accept=".pdf,application/pdf" className={pick} disabled={!!busy}
      onChange={async e => { const f = e.target.files?.[0]; e.target.value = ''; if (!f) return; setBusy(f.name); setErr(undefined);
        try { onRead({ ...(await pdfService.read(caseId, doc, f)), name: f.name }); } catch (x) { setErr(x); } finally { setBusy(undefined); } }} />
    {busy && <p className="mt-1 flex items-center gap-1.5 text-sm text-ink-600"><Loader2 aria-hidden className="h-4 w-4 animate-spin" />Reading {busy}{doc !== 'kfs' ? ' — the AI is finding the figures, this can take up to a minute' : ''}…</p>}
    {err !== undefined && <div className="mt-2"><ErrorBanner error={err} /></div>}
  </div>);
}

function Found({ quote }: { quote?: string }) {
  return quote ? <p className="mt-1 text-xs text-ink-600"><Sparkles aria-hidden className="mr-1 inline h-3 w-3 text-violet-600" />Found in the PDF: “{quote}”</p>
    : <p className="mt-1 text-xs text-amber-800">Not found in the PDF — type it from the document, or leave blank if it is not stated.</p>;
}

/** The charges of a schedule, one row each, as the person confirms them against the PDF. */
function ChargeRows({ rows, onChange }: { rows: ChargeRow[]; onChange: (rows: ChargeRow[]) => void }) {
  return (<>
    <ul className="space-y-2">{rows.map((r, i) => { const upd = (p: Partial<ChargeRow>) => onChange(rows.map((y, j) => j === i ? { ...y, ...p } : y)); return (
      <li key={i} className="grid items-end gap-2 sm:grid-cols-[2fr_1fr_2fr_auto]">
        <div><label className="text-xs text-ink-700" htmlFor={`sch-n-${i}`}>Charge</label><Input id={`sch-n-${i}`} value={r.name} onChange={e => upd({ name: e.target.value })} /></div>
        <div><label className="text-xs text-ink-700" htmlFor={`sch-t-${i}`}>When</label><select id={`sch-t-${i}`} className={select} value={r.timing} onChange={e => upd({ timing: e.target.value as ChargeRow['timing'] })}>{TIMING.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <div><label className="text-xs text-ink-700" htmlFor={`sch-a-${i}`}>Amount as written</label><Input id={`sch-a-${i}`} placeholder="e.g. 1% of the loan amount + GST" value={r.amount} onChange={e => upd({ amount: e.target.value })} /></div>
        <Button size="sm" variant="ghost" aria-label={`Remove ${r.name || 'charge'}`} onClick={() => onChange(rows.filter((_, j) => j !== i))}><Trash2 aria-hidden className="h-4 w-4" /></Button>
      </li>); })}</ul>
    <Button size="sm" variant="outline" onClick={() => onChange([...rows, { name: '', timing: 'upfront', amount: '' }])}><Plus aria-hidden className="h-4 w-4" />Add a charge</Button>
  </>);
}

/** The offer a KFS document id belongs to: KFS-OF-07-A-v1-SCH → schedule of OF-07-A version 1. */
export function lenderDocOf(docId: string): { kfsDocId: string; offerId: string; version: number; which: 'kfs' | 'schedule' } | null {
  const m = /^KFS-(.+)-v(\d+)(-SCH)?$/.exec(docId);
  return m ? { kfsDocId: `KFS-${m[1]}-v${m[2]}`, offerId: m[1], version: Number(m[2]), which: m[3] ? 'schedule' : 'kfs' } : null;
}

/** ADR 0041 for one missing document of an offer already in the case (the lender comparison asked for it by name):
 *  read the lender's PDF, check the charges (schedule) or the text (KFS), save it under that offer. */
export function MissingDocPdf({ caseId, docId, onSaved }: { caseId: string; docId: string; onSaved?: () => void }) {
  const doc = lenderDocOf(docId);
  const [read, setRead] = useState<{ name: string; text: string; rows: ChargeRow[]; ai: boolean } | null>(null);
  const [checked, setChecked] = useState(false);
  const [state, setState] = useState<{ busy?: boolean; error?: unknown; done?: boolean }>({});
  if (!doc) return null;
  const what = doc.which === 'schedule' ? 'schedule of charges' : 'Key Facts Statement';
  async function save() {
    if (!doc || !read) return;
    setState({ busy: true });
    try {
      await pdfService.saveKfs(caseId, { kfs_doc_id: doc.kfsDocId, offer_id: doc.offerId, version: doc.version, which: doc.which,
        title: `${doc.which === 'schedule' ? 'Schedule of charges' : 'Key Facts Statement'} - ${doc.offerId}`, text: read.text, rows: doc.which === 'schedule' ? cleanRows(read.rows) : [] });
      setState({ done: true }); setRead(null); setChecked(false); onSaved?.();
    } catch (x) { setState({ error: x }); }
  }
  if (state.done) return <p role="status" className="flex items-center gap-1.5 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900 ring-1 ring-emerald-200"><CheckCircle2 aria-hidden className="h-4 w-4" />The {what} for {doc.offerId} was saved. Press Continue.</p>;
  if (!read) return <PdfPicker id="pdf-missing-doc" label={`The lender's ${what} for ${doc.offerId} (PDF)`} doc={doc.which} caseId={caseId}
    onRead={r => { setRead({ name: r.name, text: r.text, rows: r.draft.rows ?? [], ai: r.draft.model === 'used' }); setState({}); }} />;
  const fe = state.error instanceof ApiProblem ? state.error.fieldErrors : [];
  return (<div className="space-y-3">
    <p className="flex items-center gap-1.5 text-sm"><CheckCircle2 aria-hidden className="h-4 w-4 text-emerald-600" />{read.name} <Button size="sm" variant="ghost" onClick={() => { setRead(null); setChecked(false); }}>Choose another</Button></p>
    {doc.which === 'schedule' ? <>
      <p className="text-xs text-ink-600">{read.ai ? 'The AI listed these charges. Check each row against the PDF:' : 'List each charge from the PDF:'} the comparison looks for charges the offer leaves out.</p>
      <ChargeRows rows={read.rows} onChange={rows => setRead({ ...read, rows })} />
    </> : <p className="text-xs text-ink-600">The Key Facts Statement is kept as the lender wrote it ({read.text.length.toLocaleString('en-IN')} characters read); no AI is used for it.</p>}
    {fe.length > 0 ? <div role="alert" className="rounded-xl bg-rose-50 p-3 text-sm ring-1 ring-rose-200"><p className="font-semibold text-rose-700">Not saved. Please fix:</p>
      <ul className="mt-1 list-disc pl-5">{fe.map((e, i) => <li key={i}>{plainReason(e.reason)}</li>)}</ul></div>
      : state.error !== undefined && <ErrorBanner error={state.error} />}
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={checked} onChange={e => setChecked(e.target.checked)} />I checked this against the lender&apos;s PDF.</label>
    <Button onClick={save} disabled={!checked || state.busy} loading={state.busy}><FileUp aria-hidden className="h-4 w-4" />Save the {what}</Button>
  </div>);
}

export default function PdfOffer({ caseId, onSaved }: { caseId: string; onSaved: () => void }) {
  const [letter, setLetter] = useState<{ name: string; draft: OfferDraft } | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [kfs, setKfs] = useState<{ name: string; text: string } | null>(null);
  const [sch, setSch] = useState<{ name: string; text: string; rows: ChargeRow[]; ai: boolean } | null>(null);
  const [checked, setChecked] = useState(false);
  const [state, setState] = useState<{ busy?: boolean; error?: unknown; done?: string; problems?: Record<string, string> }>({});
  const [id] = useState(newId);

  const set = (k: string, v: string) => setReview(r => r && { ...r, values: { ...r.values, [k]: v } });
  const quotes = letter?.draft.fields ?? {};
  const built = review ? buildOffer(review, id) : null;
  const reset = () => { setLetter(null); setReview(null); setKfs(null); setSch(null); setChecked(false); };

  async function save() {
    if (!review) return;
    const b = buildOffer(review, id);
    if (!b.json) { setState({ problems: b.problems }); return; }
    setState({ busy: true });
    try {
      await caseFiles.save(caseId, 'offer', `${b.offerId}.v1.json`, b.json);
      const title = review.values.lender_name || 'Lender';
      if (kfs) await pdfService.saveKfs(caseId, { kfs_doc_id: b.kfsDocId, offer_id: b.offerId, version: 1, which: 'kfs', title: `Key Facts Statement - ${title}`, text: kfs.text, rows: [] });
      if (sch) await pdfService.saveKfs(caseId, { kfs_doc_id: b.kfsDocId, offer_id: b.offerId, version: 1, which: 'schedule', title: `Schedule of charges - ${title}`, text: sch.text, rows: cleanRows(sch.rows) });
      setState({ done: title }); reset(); onSaved();
    } catch (x) { setState({ error: x }); }
  }

  if (!letter || !review) return (<div className="space-y-3">
    {state.done && <p role="status" className="flex items-center gap-1.5 rounded-xl bg-emerald-50 p-3 text-sm text-emerald-900 ring-1 ring-emerald-200"><CheckCircle2 aria-hidden className="h-4 w-4" />The offer from {state.done} was saved.</p>}
    <PdfPicker id="pdf-offer-letter" label="1. The lender's offer letter or sanction letter (PDF)" doc="offer" caseId={caseId}
      onRead={r => { setLetter({ name: r.name, draft: r.draft }); setReview(reviewFromDraft(r.draft)); setState({}); }} />
    <p className="text-xs text-ink-600">Only PDFs with selectable text can be read; a scanned image cannot. The AI suggests the figures; you check each one before anything is saved.</p>
  </div>);

  const fe = state.error instanceof ApiProblem ? state.error.fieldErrors : [];
  const problems = state.problems ?? {};
  const model = letter.draft.model;
  return (<div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-violet-50 p-3 text-sm text-violet-950 ring-1 ring-violet-200">
      <p className="flex items-center gap-2"><AiBadge />{model === 'used' ? `Suggested from ${letter.name}. Check every field against the PDF.` : `The AI is ${model === 'off' ? 'switched off' : 'not available right now'}: fill in the fields from ${letter.name}.`}{letter.draft.dropped > 0 && ` ${letter.draft.dropped} suggestion(s) were left out because they could not be found in the PDF.`}</p>
      <Button size="sm" variant="ghost" onClick={reset}>Start again</Button>
    </div>

    <fieldset className="grid gap-4 sm:grid-cols-2"><legend className="mb-2 text-sm font-semibold text-ink-950">Offer terms</legend>
      {OFFER_FIELDS.map(f => <div key={f.name}>
        <label htmlFor={`pdf-${f.name}`} className="block text-sm font-medium text-ink-900">{f.label}{f.material && <span className="text-ink-500"> (needed to compare)</span>}</label>
        {f.kind === 'select'
          ? <select id={`pdf-${f.name}`} className={select} value={review.values[f.name] ?? ''} onChange={e => set(f.name, e.target.value)}>{f.options!.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
          : <Input id={`pdf-${f.name}`} type={f.kind === 'date' ? 'date' : 'text'} inputMode={f.kind === 'int' || f.kind === 'percent' ? 'decimal' : undefined} placeholder={f.help} value={review.values[f.name] ?? ''} onChange={e => set(f.name, e.target.value)} aria-invalid={!!problems[f.name]} />}
        {problems[f.name] && <p className="mt-1 text-xs text-rose-700">{problems[f.name]}</p>}
        <Found quote={quotes[f.name]?.quote} />
      </div>)}
      <div><label htmlFor="pdf-lender-type" className="block text-sm font-medium text-ink-900">Type of lender</label>
        <select id="pdf-lender-type" className={select} value={review.lenderType} onChange={e => setReview({ ...review, lenderType: e.target.value })}>{LENDER_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
      <div className="space-y-1 text-sm">
        {review.values.insurance_premium && <label className="flex items-center gap-2"><input type="checkbox" checked={review.insuranceFinanced} onChange={e => setReview({ ...review, insuranceFinanced: e.target.checked })} />The insurance premium is added to the loan</label>}
        {review.values.guarantee_fee && <label className="flex items-center gap-2"><input type="checkbox" checked={review.guaranteeGst} onChange={e => setReview({ ...review, guaranteeGst: e.target.checked })} />GST is charged on the guarantee fee</label>}
      </div>
    </fieldset>

    <fieldset><legend className="mb-2 text-sm font-semibold text-ink-950">Fees and charges in the letter</legend>
      <ul className="space-y-3">{review.fees.map((x, i) => { const upd = (p: Partial<typeof x>) => setReview({ ...review, fees: review.fees.map((y, j) => j === i ? { ...y, ...p } : y) }); return (
        <li key={i} className="grid items-end gap-2 rounded-xl p-3 ring-1 ring-line sm:grid-cols-[2fr_1fr_1.3fr_1fr_auto_auto]">
          <div><label className="text-xs text-ink-700" htmlFor={`fee-n-${i}`}>Fee name</label><Input id={`fee-n-${i}`} value={x.name} onChange={e => upd({ name: e.target.value })} /></div>
          <div><label className="text-xs text-ink-700" htmlFor={`fee-t-${i}`}>When</label><select id={`fee-t-${i}`} className={select} value={x.timing} onChange={e => upd({ timing: e.target.value as ChargeRow['timing'] })}>{TIMING.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
          <div><label className="text-xs text-ink-700" htmlFor={`fee-b-${i}`}>Charged as</label><select id={`fee-b-${i}`} className={select} value={x.basis} onChange={e => upd({ basis: e.target.value as typeof x.basis })}><option value="pct_of_principal">% of the loan</option><option value="fixed">Fixed amount (₹)</option></select></div>
          <div><label className="text-xs text-ink-700" htmlFor={`fee-v-${i}`}>{x.basis === 'fixed' ? 'Amount' : '%'}</label><Input id={`fee-v-${i}`} value={x.value} onChange={e => upd({ value: e.target.value })} /></div>
          <label className="flex h-10 items-center gap-1 text-xs"><input type="checkbox" checked={x.gst} onChange={e => upd({ gst: e.target.checked })} />+ GST</label>
          <Button size="sm" variant="ghost" aria-label={`Remove ${x.name || 'fee'}`} onClick={() => setReview({ ...review, fees: review.fees.filter((_, j) => j !== i) })}><Trash2 aria-hidden className="h-4 w-4" /></Button>
          {problems[`fee.${i}`] && <p className="text-xs text-rose-700 sm:col-span-6">{problems[`fee.${i}`]}</p>}
          {letter.draft.fees[i] && letter.draft.fees[i].name === x.name && <p className="text-xs text-ink-600 sm:col-span-6"><Sparkles aria-hidden className="mr-1 inline h-3 w-3 text-violet-600" />Found in the PDF: “{letter.draft.fees[i].quote}”</p>}
        </li>); })}</ul>
      <div className="mt-2 flex flex-wrap items-center gap-4">
        <Button size="sm" variant="outline" onClick={() => setReview({ ...review, noFees: false, fees: [...review.fees, { name: '', timing: 'upfront', basis: 'pct_of_principal', value: '', gst: true }] })}><Plus aria-hidden className="h-4 w-4" />Add a fee</Button>
        {review.fees.length === 0 && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={review.noFees} onChange={e => setReview({ ...review, noFees: e.target.checked })} />The letter says there are no fees</label>}
      </div>
    </fieldset>

    <fieldset className="space-y-4"><legend className="mb-2 text-sm font-semibold text-ink-950">The lender&apos;s other documents (recommended)</legend>
      {kfs ? <p className="flex items-center gap-1.5 text-sm"><CheckCircle2 aria-hidden className="h-4 w-4 text-emerald-600" />Key Facts Statement: {kfs.name} <Button size="sm" variant="ghost" onClick={() => setKfs(null)}>Remove</Button></p>
        : <PdfPicker id="pdf-kfs" label="2. Key Facts Statement (PDF) — kept as the lender wrote it, no AI" doc="kfs" caseId={caseId} onRead={r => setKfs({ name: r.name, text: r.text })} />}
      {sch ? <div className="space-y-2">
          <p className="flex items-center gap-1.5 text-sm"><CheckCircle2 aria-hidden className="h-4 w-4 text-emerald-600" />Schedule of charges: {sch.name} <Button size="sm" variant="ghost" onClick={() => setSch(null)}>Remove</Button></p>
          <p className="text-xs text-ink-600">{sch.ai ? 'The AI listed these charges. Check each row against the PDF:' : 'List each charge from the PDF:'} the comparison looks for charges the offer letter leaves out.</p>
          <ChargeRows rows={sch.rows} onChange={rows => setSch({ ...sch, rows })} />
        </div>
        : <PdfPicker id="pdf-schedule" label="3. Schedule of charges (PDF)" doc="schedule" caseId={caseId} onRead={r => setSch({ name: r.name, text: r.text, rows: r.draft.rows ?? [], ai: r.draft.model === 'used' })} />}
    </fieldset>

    {built && built.missing.length > 0 && <p className="flex items-start gap-1.5 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Not filled in: {built.missing.join(', ')}. You can still save, but this offer will be marked “not comparable” and left out of the ranking.</p>}
    {fe.length > 0 ? <div role="alert" className="rounded-xl bg-rose-50 p-3 text-sm ring-1 ring-rose-200"><p className="font-semibold text-rose-700">Not saved. Please fix:</p>
      <ul className="mt-1 list-disc pl-5">{fe.map((e, i) => <li key={i}>{OFFER_FIELDS.find(f => e.field?.startsWith(f.name))?.label ?? e.field ?? 'Document'}: {plainReason(e.reason)}</li>)}</ul></div>
      : state.error !== undefined && <ErrorBanner error={state.error} />}
    {Object.keys(problems).length > 0 && <p role="alert" className="text-sm text-rose-700">Some fields need fixing (marked in red above).</p>}
    <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={checked} onChange={e => setChecked(e.target.checked)} />I checked every field above against the lender&apos;s PDF.</label>
    <Button onClick={save} disabled={!checked || state.busy} loading={state.busy}><FileUp aria-hidden className="h-4 w-4" />Save this offer</Button>
  </div>);
}
