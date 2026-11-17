'use client';
import { useState } from 'react';
import type { CaseRecord, Negotiation as N } from '@/types';
import { Card, CardHeader, Button, Badge } from '../ui';
import { Figure } from '../Figure';
import ErrorBanner from '../ErrorBanner';
import { lendWiseService } from '@/services';
import { flagText } from '@/lib/flags';
import { Handshake, ShieldCheck, Hourglass } from 'lucide-react';

// One simulated fee-waiver round (LW-12/13, BR-09/10). A revised offer counts only after the stage re-audits it, so until
// then it is labelled "not re-audited". The lender's reply text is masked by the API and shown as plain text, never as markup (BR-15).
export default function Negotiation({ c, n, canStart, onChange }: { c: CaseRecord; n: N | null; canStart: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>();
  const start = async () => { setBusy(true); setErr(undefined); try { await lendWiseService.negotiate(c); onChange(); } catch (e) { setErr(e); } setBusy(false); };
  const ran = !!n?.target;
  return (<Card><CardHeader title="Negotiation" sub={ran ? 'Round 1 of 1' : 'One round: a fee waiver, from a fixed template'} icon={<Handshake className="h-4 w-4" />} />
    <div className="space-y-3 p-5 text-sm">
      {!ran && <p className="text-ink-700">No negotiation round has run. The round asks the lender with the highest fee to match a verified lower fee from a competing offer.</p>}
      {n && ran && <>
        <p><b>Offer {n.target}</b>: fee waiver requested{n.competingFee && <>, citing a verified competing fee of <Figure value={n.competingFee} label="Competing fee" caseId={c.id} /></>}.</p>
        {n.message && <blockquote className="rounded-xl border-l-4 border-ink-400 bg-sunken p-3 text-ink-800">{n.message}</blockquote>}
        {n.status === 'blocked' && <p className="flex gap-2 text-rose-700"><Hourglass aria-hidden className="mt-0.5 h-4 w-4" />The message was blocked by the Verification Critic and was not sent.</p>}
        {n.status === 'sent' && !n.revised && <p className="flex gap-2 text-ink-700"><Hourglass aria-hidden className="mt-0.5 h-4 w-4" />Sent. Waiting for the lender&apos;s revised offer.</p>}
        {n.status !== 'blocked' && n.status !== 'sent' && !n.revised && <p className="text-ink-700">Status: {n.status ?? 'not sent'}. No lender reply yet.</p>}
        {n.reply && <div className="rounded-xl border border-line p-3">
          <p className="font-medium">Lender&apos;s reply, round {n.reply.round}</p>
          {n.reply.injectionFlags.length > 0 && <p role="note" className="mt-1 text-xs text-amber-800">This reply contains text that looks like instructions. It is shown as data and had no effect.</p>}
          <p className="mt-1 whitespace-pre-wrap text-ink-700" data-testid="lender-reply">{n.reply.text}</p>
        </div>}
        {n.revised && <div className="rounded-xl border border-line p-3">
          <p className="font-medium">Lender&apos;s reply: revised offer {n.target}, version {n.revised.version}</p>
          <p className="mt-1 text-ink-700">APR {n.revised.apr ? <Figure value={n.revised.apr} label="Revised APR" caseId={c.id} /> : '—'} · total cost {n.revised.totalCost ? <Figure value={n.revised.totalCost} label="Revised total cost" caseId={c.id} /> : '—'}</p>
          {n.revised.flags.map(f => <p key={f} className="mt-1 text-xs text-ink-700">{flagText(f)}</p>)}
          <p className="mt-2">{n.countsAsConcession
            ? <Badge tone="green"><ShieldCheck aria-hidden className="h-3.5 w-3.5" />Concession verified by re-audit</Badge>
            : <Badge tone="amber"><Hourglass aria-hidden className="h-3.5 w-3.5" />Revised offer not re-audited</Badge>}</p>
          {!n.countsAsConcession && <p className="mt-1 text-xs text-ink-600">It does not count until the stage re-runs and re-audits it. The ranking above still uses the original offer.</p>}
        </div>}
      </>}
      {err != null && <ErrorBanner error={err} />}
      {canStart && !ran && <Button onClick={start} loading={busy}>Start negotiation round</Button>}
    </div></Card>);
}
