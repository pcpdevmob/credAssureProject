// UI-08: the proposal report as the gateway renders it (plain text, never HTML). Figures inside the text carry their
// ledger key and version, so each opens the provenance drawer (#33). A stale version says so and the preparer can
// create a new one (scope #6). Export downloads exactly what the report endpoint returned.
import { useEffect, useState } from 'react';
import { FileText, Download, Hourglass, RefreshCw } from 'lucide-react';
import { Card, CardHeader, Button, Skeleton } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { Figure } from '../Figure';
import { reportService, segments, type ReportFmt, type ReportView } from '@/services/report';

const REASON: Record<string, string> = {
  no_version: 'No report version yet: this is a draft from the current figures.',
  newer_version: 'A newer version exists.',
  onboarding: 'Readiness figures changed.', working_capital: 'Funding figures changed.', lendwise: 'Offer figures changed.', critic: 'Verification changed.',
};
const reason = (r: string) => REASON[r] ?? (r.startsWith('upload:') ? `New ${r.slice(7)} upload: re-run the stage that reads it.` : r);

export default function Report({ caseId, stamp, canRegenerate }: { caseId: string; stamp: string; canRegenerate: boolean }) {
  const [view, setView] = useState<ReportView>(); const [err, setErr] = useState<unknown>(); const [saveErr, setSaveErr] = useState<unknown>(); const [busy, setBusy] = useState(false); const [tick, setTick] = useState(0);
  useEffect(() => { setView(undefined); setErr(undefined); let live = true; reportService.view(caseId).then(v => live && setView(v)).catch(e => live && setErr(e)); return () => { live = false; }; }, [caseId, stamp, tick]);
  const save = (f: ReportFmt) => { setSaveErr(undefined); reportService.download(caseId, f).catch(setSaveErr); };
  const regenerate = async () => { setBusy(true); setSaveErr(undefined); try { await reportService.regenerate(caseId); setTick(t => t + 1); } catch (e) { setSaveErr(e); } setBusy(false); };
  return (<Card><CardHeader title="Proposal report" sub={view ? (view.version ? `Version ${view.version}` : 'Draft') : undefined} icon={<FileText className="h-4 w-4" />}
      right={<div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => save('md')}><Download aria-hidden className="mr-1 h-4 w-4" />Markdown</Button><Button size="sm" variant="outline" onClick={() => save('html')}>HTML</Button></div>} />
    <div className="space-y-5 p-5">
      {saveErr !== undefined && <ErrorBanner error={saveErr} />}
      {err !== undefined ? <ErrorBanner error={err} /> : view === undefined ? <Skeleton className="h-64" /> : <>
        {view.stale && <div role="status" className="flex flex-wrap items-start gap-3 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200">
          <Hourglass aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0 flex-1"><p>Stale: the figures changed after this version.</p><ul className="mt-1 list-disc pl-5 font-normal">{view.reasons.map(r => <li key={r}>{reason(r)}</li>)}</ul></div>
          {canRegenerate && <Button size="sm" variant="outline" loading={busy} onClick={regenerate}><RefreshCw aria-hidden className="mr-1 h-4 w-4" />Create new version</Button>}
        </div>}
        {view.sections.map(s => <section key={s.title} aria-labelledby={`rep-${s.title}`}>
          <h3 id={`rep-${s.title}`} className="font-display text-sm font-semibold text-ink-950">{s.title}</h3>
          <p className="mt-1 whitespace-pre-wrap break-words text-sm text-ink-900">{segments(s).map((g, i) => typeof g === 'string' ? <span key={i}>{g}</span>
            : <Figure key={i} value={{ display: g.display, key: g.key, version: g.version }} label={`${s.title}: ${g.key}`} caseId={caseId} />)}</p>
        </section>)}
      </>}
    </div></Card>);
}
