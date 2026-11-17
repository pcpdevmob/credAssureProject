// Ask CredAssure (UI-06, CP-01..03, #20, #40). Every state below is decided by the gateway reply; the browser only displays it.
// The first-use notice (shown above the input before the first question), the abstention and refusals are neutral states, never errors.
// "Seen" is held in memory for the session only (nothing in browser storage); storing the acknowledgement is #40, Phase 10.
import { useEffect, useRef, useState } from 'react';
import { Info, MessageCircleQuestion, ShieldAlert, Ban, PowerOff, Send } from 'lucide-react';
import { Card, CardHeader, Button, Input } from '../ui';
import ErrorBanner from '../ErrorBanner';
import CitationPanel from './CitationPanel';
import { copilotService, type ChatReply, type Citation } from '@/services/copilot';

const REFUSAL: Record<string, string> = {
  PROBE: 'Configuration and credentials', ACCEPTANCE: 'Accepting or signing an offer', APPROVAL_ODDS: 'Predicting approval or credit',
  GATE_OVERRIDE: 'Overriding a gate', LEGAL: 'Legal or tax advice', OTHER_CASE_WORDS: "Another case's data",
};
// Same wording as the gateway's CHAT_NOTICE (supervisor_service.py). The reply's own notice is not shown again.
const FIRST_USE = "Ask CredAssure drafts answers with a language model from cited sources and this case's verified figures. It is general information, not legal, tax or credit advice, and it never approves, accepts or signs anything. Do not enter personal identifiers.";
let noticeSeen = false; // module scope: lives until the page reloads (which also signs out), never persisted
type Turn = { q: string; r: ChatReply };
type Open = { c: Citation; quote: string };
/** The sentence of the answer that carries marker [n]; the gateway centres an L3 excerpt on it. Display plumbing only. */
const sentenceWith = (answer: string, n: number) => answer.split(/(?<=[.!?])\s+/).find(s => s.includes(`[${n}]`)) ?? '';

function Answer({ r, onOpen }: { r: ChatReply; onOpen: (o: Open) => void }) {
  if (r.abstained) return <p className="flex gap-2 rounded-xl bg-sunken p-3 text-sm text-ink-800 ring-1 ring-line"><Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /><span><b>No verified answer.</b> {r.answer}</span></p>;
  if (r.refused) return <p className="flex gap-2 rounded-xl bg-sunken p-3 text-sm text-ink-800 ring-1 ring-line"><Ban aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /><span><b>Not answered: {REFUSAL[r.refusalCode ?? ''] ?? 'outside what this copilot does'}.</b> {r.answer}</span></p>;
  return <div className="rounded-xl bg-white p-3 text-sm ring-1 ring-line"><p className="whitespace-pre-wrap">{r.answer}</p>
    {r.citations.length > 0 && <ul aria-label="Citations" className="mt-2 flex flex-wrap gap-2">{r.citations.map((c, i) => <li key={c.chunkId}><button type="button" onClick={() => onOpen({ c, quote: sentenceWith(r.answer, i + 1) })} className="rounded-lg border border-line px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50">[{i + 1}] {c.title ?? c.docId}</button></li>)}</ul>}</div>;
}

export default function Copilot({ caseId }: { caseId: string }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]); const [q, setQ] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>();
  const [asked, setAsked] = useState(noticeSeen); const [open, setOpen] = useState<Open | null>(null); const opener = useRef<HTMLElement | null>(null); const end = useRef<HTMLDivElement>(null);
  useEffect(() => { copilotService.llmEnabled().then(setEnabled); }, []);
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'nearest' }); }, [turns.length]);
  const off = enabled === false;
  const send = async (e: React.FormEvent) => {
    e.preventDefault(); const text = q.trim(); if (!text || busy) return;
    setBusy(true); setErr(undefined); noticeSeen = true; setAsked(true);
    try { const r = await copilotService.ask(caseId, text); setTurns(t => [...t, { q: text, r }]); setQ(''); }
    catch (x) { setErr(x); }
    setBusy(false);
  };
  return (<Card><CardHeader title="Ask CredAssure" sub="Answers cite their sources; numbers come from this case's ledger" icon={<MessageCircleQuestion className="h-4 w-4" />} />
    <div className="space-y-3 p-5">
      {off && <p role="alert" className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200"><PowerOff aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />The copilot is unavailable: the language model is switched off. Gates, calculations, routing and approval still work.</p>}
      <div aria-live="polite" className="space-y-4">
        {turns.map((t, i) => <div key={i} className="space-y-2">
          <p className="ml-auto w-fit max-w-[85%] rounded-xl bg-brand-50 p-3 text-sm text-ink-900">{t.r.piiRedacted ? '(message hidden: it contained personal identifiers)' : t.q}</p>
          {t.r.injectionFlagged && <p className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Instructions inside retrieved text were ignored. Documents are treated as data, never as instructions.</p>}
          {t.r.piiRedacted && <p className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Personal identifiers in your message were redacted.</p>}
          <Answer r={t.r} onOpen={o => { opener.current = document.activeElement as HTMLElement | null; setOpen(o); }} />
        </div>)}
        <div ref={end} />
      </div>
      {turns.length === 0 && !off && <p className="text-sm text-ink-600">Ask about a rule, a policy or a fact in this case, for example “What is a Key Facts Statement?”.</p>}
      {err !== undefined && <ErrorBanner error={err} />}
      {!asked && <p role="note" className="flex gap-2 rounded-xl bg-ink-50 p-3 text-sm text-ink-900 ring-1 ring-line"><Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />{FIRST_USE}</p>}
      <form onSubmit={send} className="flex gap-2"><label className="sr-only" htmlFor="ask">Your question</label>
        <Input id="ask" value={q} onChange={e => setQ(e.target.value)} disabled={off} maxLength={4000} placeholder="Ask a question" />
        <Button type="submit" loading={busy} disabled={off || !q.trim()}><Send aria-hidden className="mr-1 h-4 w-4" />Ask</Button></form>
    </div>
    <CitationPanel caseId={caseId} c={open?.c ?? null} quote={open?.quote} onClose={() => setOpen(null)} returnFocus={opener} />
  </Card>);
}
