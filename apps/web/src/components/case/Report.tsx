// UI-08: the proposal report as the gateway renders it (shown as plain text, never as HTML) plus every ledger figure the
// proposal rests on, each with the provenance drawer. Export downloads exactly what the report endpoint returned.
import { useEffect, useState } from 'react';
import { FileText, Download } from 'lucide-react';
import { Card, CardHeader, Button, Skeleton } from '../ui';
import ErrorBanner from '../ErrorBanner';
import { Figure } from '../Figure';
import { reportService, type ReportFmt } from '@/services/report';
import type { FundingAssessment, OfferView } from '@/types';

export default function Report({ caseId, a, offers, stamp }: { caseId: string; a?: FundingAssessment | null; offers?: OfferView | null; stamp: string }) {
  const [text, setText] = useState<string>(); const [err, setErr] = useState<unknown>(); const [saveErr, setSaveErr] = useState<unknown>();
  useEffect(() => { setText(undefined); setErr(undefined); let live = true; reportService.get(caseId).then(t => live && setText(t)).catch(e => live && setErr(e)); return () => { live = false; }; }, [caseId, stamp]);
  const save = (f: ReportFmt) => { setSaveErr(undefined); reportService.download(caseId, f).catch(setSaveErr); };
  return (<div className="grid gap-6 lg:grid-cols-3">
    <Card className="lg:col-span-2"><CardHeader title="Proposal report" icon={<FileText className="h-4 w-4" />}
      right={<div className="flex gap-2"><Button size="sm" variant="outline" onClick={() => save('md')}><Download aria-hidden className="mr-1 h-4 w-4" />Markdown</Button><Button size="sm" variant="outline" onClick={() => save('html')}>HTML</Button></div>} />
      <div className="p-5">{saveErr !== undefined && <ErrorBanner className="mb-3" error={saveErr} />}{err !== undefined ? <ErrorBanner error={err} /> : text === undefined ? <Skeleton className="h-64" /> : <pre className="whitespace-pre-wrap break-words font-sans text-sm text-ink-900">{text}</pre>}</div></Card>
    <Card><CardHeader title="Figures in this proposal" sub="Open any figure to see where it comes from" />
      <dl className="space-y-2 p-5 text-sm">
        {a && <>{([['Validated funding need', a.recommendedAmount], ['Indicative request', a.requestedAmount], ['Peak shortfall', a.peakShortfall], ['Minimum cash buffer', a.minCashBuffer], ['Undrawn limits', a.existingFacility]] as const)
          .map(([l, f]) => <div key={l} className="flex justify-between gap-3"><dt className="text-ink-600">{l}</dt><dd><Figure value={f} label={l} caseId={caseId} /></dd></div>)}</>}
        {offers?.offers.filter(o => o.apr).map(o => <div key={o.id} className="flex justify-between gap-3"><dt className="text-ink-600">APR, offer {o.id}</dt><dd><Figure value={o.apr!} label={`APR, offer ${o.id}`} caseId={caseId} /></dd></div>)}
        {!a && <p className="text-ink-600">Figures appear once the funding stage has run.</p>}
      </dl></Card>
  </div>);
}
