'use client';
import { useState } from 'react';
import type { CaseRecord, Negotiation as N, NegotiationMove, NegotiationRound } from '@/types';
import { Card, CardHeader, Button, Badge } from '../ui';
import { Figure } from '../Figure';
import ErrorBanner from '../ErrorBanner';
import { lendWiseService } from '@/services';
import { flagText } from '@/lib/flags';
import { Handshake, ShieldCheck, Hourglass } from 'lucide-react';

// Up to three simulated rounds, one per request (LW-12/13/15, BR-09/10, ADR 0037): fee waiver, rate match, tenor change, each
// from a fixed template filled with verified figures. A revised offer counts only after re-audit; a counted concession re-ranks
// the offers above. The lender's reply text is masked by the API and shown as plain text, never as markup (BR-15).
export const MAX_ROUNDS = 3;
const MOVE: Record<NegotiationMove, string> = { fee_waiver_v1: 'Fee waiver', rate_match_v1: 'Rate match', tenor_change_v1: 'Tenor change' };

function Round({ c, r }: { c: CaseRecord; r: NegotiationRound }) {
  return (<section aria-label={`Round ${r.round}`} className="space-y-2 rounded-xl border border-line p-3">
    <p><b>Round {r.round} · {MOVE[r.move]}</b> · offer {r.target}</p>
    {r.cited.length > 0 && <p className="text-xs text-ink-700">Verified figures cited: {r.cited.map(x => `${x.label} ${x.value}`).join(' · ')}</p>}
    {r.message && <blockquote className="rounded-xl border-l-4 border-ink-400 bg-sunken p-3 text-ink-800">{r.message}</blockquote>}
    {r.status === 'blocked' && <p className="flex gap-2 text-rose-700"><Hourglass aria-hidden className="mt-0.5 h-4 w-4" />The message was blocked by the Verification Critic and was not sent.</p>}
    {r.reply && <div className="rounded-xl border border-line p-3">
      <p className="font-medium">Lender&apos;s reply, round {r.reply.round}</p>
      {r.reply.injectionFlags.length > 0 && <p role="note" className="mt-1 text-xs text-amber-800">This reply contains text that looks like instructions. It is shown as data and had no effect.</p>}
      <p className="mt-1 whitespace-pre-wrap text-ink-700" data-testid="lender-reply">{r.reply.text}</p>
    </div>}
    {r.status === 'sent' && !r.revised && <p className="text-ink-700">No revised offer: nothing changes.</p>}
    {r.revised && <div className="rounded-xl border border-line p-3">
      <p className="font-medium">Revised offer {r.target}, version {r.revised.version}</p>
      <p className="mt-1 text-ink-700">APR {r.revised.apr ? <Figure value={r.revised.apr} label="Revised APR" caseId={c.id} /> : '—'} · total cost {r.revised.totalCost ? <Figure value={r.revised.totalCost} label="Revised total cost" caseId={c.id} /> : '—'}</p>
      {r.revised.flags.map(f => <p key={f} className="mt-1 text-xs text-ink-700">{flagText(f)}</p>)}
      <p className="mt-2">{r.countsAsConcession
        ? <Badge tone="green"><ShieldCheck aria-hidden className="h-3.5 w-3.5" />Concession verified by re-audit</Badge>
        : <Badge tone="amber"><Hourglass aria-hidden className="h-3.5 w-3.5" />Revised offer not re-audited</Badge>}</p>
      <p className="mt-1 text-xs text-ink-600">{r.countsAsConcession
        ? 'The offers above are re-ranked with this revision.'
        : 'It did not pass re-audit, so it does not count and the ranking above is unchanged.'}</p>
    </div>}
  </section>);
}

export default function Negotiation({ c, n, canStart, onChange }: { c: CaseRecord; n: N | null; canStart: boolean; onChange: () => void }) {
  const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>();
  const start = async () => { setBusy(true); setErr(undefined); try { await lendWiseService.negotiate(c); onChange(); } catch (e) { setErr(e); } setBusy(false); };
  const rounds = n?.rounds ?? [];
  const sent = rounds.filter(r => r.status === 'sent').length;
  const complete = n?.complete === true;
  const sub = rounds.length ? `Round ${sent} of ${MAX_ROUNDS}${complete ? ' · complete' : ''}` : `Up to ${MAX_ROUNDS} rounds: fee waiver, rate match, tenor change`;
  return (<Card><CardHeader title="Negotiation" sub={sub} icon={<Handshake className="h-4 w-4" />} />
    <div className="space-y-3 p-5 text-sm">
      {!rounds.length && !complete && <p className="text-ink-700">No negotiation round has run. Each round asks one lender, from a fixed template, to match a verified figure from a competing offer or to move its first repayment past the cash low point.</p>}
      {rounds.map(r => <Round key={`${r.move}-${r.round}`} c={c} r={r} />)}
      {complete && <p className="text-ink-700">Negotiation is complete{rounds.length ? '' : ': no verified figure to cite'}. The ranking above includes every counted concession.</p>}
      {err != null && <ErrorBanner error={err} />}
      {canStart && !complete && <Button onClick={start} loading={busy}>{rounds.length ? 'Run next negotiation round' : 'Start negotiation round'}</Button>}
    </div></Card>);
}
