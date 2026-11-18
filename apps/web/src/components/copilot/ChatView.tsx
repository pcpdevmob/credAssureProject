// Ask CredAssure conversation (UI-06, CP-01..03, CP-07, CP-10..12, #40, ADR 0035), shared by the case tab and the panel on
// every page. Every state is decided by the gateway reply; the browser only displays it. The answer text streams in only after
// the gateway's Critic passed it. Follow-ups are the gateway's fixed list. Nothing is stored in the browser.
import { useEffect, useRef, useState } from 'react';
import { Info, ShieldAlert, Ban, PowerOff, Send, ThumbsUp, ThumbsDown, RotateCcw, BookOpen } from 'lucide-react';
import { Button, Input, AiBadge } from '../ui';
import ErrorBanner from '../ErrorBanner';
import CitationPanel from '../case/CitationPanel';
import { copilotService, type ChatNotice, type ChatReply, type Citation, type FeedbackReason, type Rating } from '@/services/copilot';

const REFUSAL: Record<string, string> = {
  PROBE: 'Configuration and credentials', ACCEPTANCE: 'Accepting or signing an offer', APPROVAL_ODDS: 'Predicting approval or credit',
  GATE_OVERRIDE: 'Overriding a gate', LEGAL: 'Legal or tax advice', OTHER_CASE_WORDS: "Another case's data", OTHER_CASE: "Another case's data",
};
const STAGE: Record<string, string> = { routing: 'Choosing a source…', retrieving: 'Finding sources…', drafting: 'Drafting…', checking: 'Checking figures and citations…' };
const REASONS: [FeedbackReason, string][] = [['wrong', 'Wrong'], ['not_cited', 'Not cited'], ['unclear', 'Unclear'], ['unhelpful', 'Not helpful'], ['unsafe', 'Unsafe']];
type Turn = { q: string; r?: ChatReply; live?: string; stage?: string; past?: boolean; rated?: Rating | 'sent' };
type Open = { c: Citation; quote: string };
const sentenceWith = (answer: string, n: number) => answer.split(/(?<=[.!?])\s+/).find(s => s.includes(`[${n}]`)) ?? '';

function Sources({ r, onOpen }: { r: ChatReply; onOpen: (o: Open) => void }) {
  if (!r.citations.length) return null;
  return <ul aria-label="Citations" className="mt-2 flex flex-wrap gap-2">{r.citations.map((c, i) => <li key={c.chunkId}>{c.href
    ? <a href={c.href} className="inline-flex items-center gap-1 rounded-lg border border-line px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50"><BookOpen aria-hidden className="h-3 w-3" />[{i + 1}] Help: {c.title ?? c.docId}{c.section ? ` · ${c.section}` : ''}</a>
    : <button type="button" onClick={() => onOpen({ c, quote: sentenceWith(r.answer, i + 1) })} className="rounded-lg border border-line px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50">[{i + 1}] {c.title ?? c.docId}</button>}</li>)}</ul>;
}

function Answer({ r, onOpen }: { r: ChatReply; onOpen: (o: Open) => void }) {
  if (r.abstained) return <p className="flex gap-2 rounded-xl bg-sunken p-3 text-sm text-ink-800 ring-1 ring-line"><Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /><span><b>No verified answer.</b> {r.answer}</span></p>;
  if (r.refused) return <p className="flex gap-2 rounded-xl bg-sunken p-3 text-sm text-ink-800 ring-1 ring-line"><Ban aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /><span><b>Not answered: {REFUSAL[r.refusalCode ?? ''] ?? 'outside what this copilot does'}.</b> {r.answer}</span></p>;
  return <div className="rounded-xl bg-white p-3 text-sm ring-1 ring-line">{r.aiDrafted && <AiBadge className="mb-2" />}<p className="whitespace-pre-wrap">{r.answer.replace(/\*\*/g, '')}</p><Sources r={r} onOpen={onOpen} /></div>;
}

function Rate({ t, onRated }: { t: Turn; onRated: (v: Turn['rated']) => void }) {
  const [busy, setBusy] = useState(false);
  if (!t.r || t.r.refused) return null;
  if (t.rated === 'sent') return <p className="text-xs text-ink-600">Thanks, your rating was recorded.</p>;
  const send = async (rating: Rating, reason?: FeedbackReason) => { setBusy(true); try { await copilotService.feedback(t.r!.traceId, rating, reason); onRated('sent'); } catch { onRated('sent'); } setBusy(false); };
  return <div className="flex flex-wrap items-center gap-2 text-xs text-ink-600">
    <span>Was this useful?</span>
    <button type="button" disabled={busy} aria-label="Helpful" onClick={() => send('up')} className="rounded-md p-1 hover:bg-sunken"><ThumbsUp aria-hidden className="h-3.5 w-3.5" /></button>
    <button type="button" disabled={busy} aria-label="Not helpful" aria-expanded={t.rated === 'down'} onClick={() => onRated('down')} className="rounded-md p-1 hover:bg-sunken"><ThumbsDown aria-hidden className="h-3.5 w-3.5" /></button>
    {t.rated === 'down' && <span role="group" aria-label="What was wrong?" className="flex flex-wrap gap-1">{REASONS.map(([k, l]) => <button key={k} type="button" disabled={busy} onClick={() => send('down', k)} className="rounded-full border border-line px-2 py-0.5 hover:bg-sunken">{l}</button>)}</span>}
  </div>;
}

export default function ChatView({ caseId }: { caseId: string | null }) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]); const [q, setQ] = useState(''); const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>();
  const [notice, setNotice] = useState<ChatNotice | null>(null); const [open, setOpen] = useState<Open | null>(null); const opener = useRef<HTMLElement | null>(null); const end = useRef<HTMLDivElement>(null);
  useEffect(() => { copilotService.llmEnabled().then(setEnabled); copilotService.notice().then(setNotice).catch(() => setNotice(null)); }, []);
  useEffect(() => {
    setTurns([]); if (!caseId) return; let live = true;
    copilotService.history(caseId).then(ms => {
      if (!live) return; const past: Turn[] = [];
      for (let i = 0; i + 1 < ms.length; i++) if (ms[i].role === 'user' && ms[i + 1].role === 'assistant') {
        past.push({ q: ms[i].text, past: true, r: { answer: ms[i + 1].text, citations: [], abstained: false, refused: false, refusalCode: null, injectionFlagged: false, piiRedacted: false, notice: null, traceId: ms[i + 1].traceId ?? '', aiDrafted: false, intent: null, followups: [], caseId } }); i++;
      }
      setTurns(t => (t.length ? t : past));
    }).catch(() => undefined);
    return () => { live = false; };
  }, [caseId]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'nearest' }); }, [turns]);
  const off = enabled === false;
  const patch = (i: number, p: Partial<Turn>) => setTurns(ts => ts.map((t, k) => (k === i ? { ...t, ...p } : t)));
  const ask = async (text: string) => {
    text = text.trim(); if (!text || busy) return;
    setBusy(true); setErr(undefined); setQ('');
    const i = turns.length; setTurns(ts => [...ts, { q: text, stage: 'routing', live: '' }]);
    try {
      const r = await copilotService.stream(text, caseId, { onStage: stage => patch(i, { stage }), onDelta: d => setTurns(ts => ts.map((t, k) => (k === i ? { ...t, live: (t.live ?? '') + d } : t))) });
      patch(i, { r, live: undefined, stage: undefined });
      setNotice(n => n && { ...n, acknowledgedAt: n.acknowledgedAt ?? 'now' });
    } catch (x) { setErr(x); setTurns(ts => ts.filter((_, k) => k !== i)); setQ(text); }
    setBusy(false);
  };
  const reset = async () => { if (!caseId) return; try { await copilotService.reset(caseId); setTurns([]); } catch (x) { setErr(x); } };
  const last = [...turns].reverse().find(t => t.r && !t.past);
  return (<div className="space-y-3">
    {off && <p role="alert" className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm font-medium text-amber-900 ring-1 ring-amber-200"><PowerOff aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />The copilot is unavailable: the language model is switched off. Gates, calculations, routing and approval still work.</p>}
    <div aria-live="polite" className="space-y-4">
      {turns.some(t => t.past) && <p className="text-xs font-medium uppercase tracking-wide text-ink-600">Earlier in this conversation</p>}
      {turns.map((t, i) => <div key={i} className="space-y-2">
        <p className="ml-auto w-fit max-w-[85%] rounded-xl bg-brand-50 p-3 text-sm text-ink-900">{t.r?.piiRedacted ? '(message hidden: it contained personal identifiers)' : t.q}</p>
        {t.r?.injectionFlagged && <p className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Instructions inside retrieved text were ignored. Documents are treated as data, never as instructions.</p>}
        {t.r?.piiRedacted && <p className="flex gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"><ShieldAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />Personal identifiers in your message were redacted.</p>}
        {t.r ? <Answer r={t.r} onOpen={o => { opener.current = document.activeElement as HTMLElement | null; setOpen(o); }} />
          : <p className="rounded-xl bg-white p-3 text-sm ring-1 ring-line"><span className="whitespace-pre-wrap">{t.live}</span>{!t.live && <span className="text-ink-600">{STAGE[t.stage ?? ''] ?? 'Working…'}</span>}</p>}
        {t.r && !t.past && <Rate t={t} onRated={v => patch(i, { rated: v })} />}
      </div>)}
      <div ref={end} />
    </div>
    {last && last.r && last.r.followups.length > 0 && !busy && <div aria-label="Suggested questions" className="flex flex-wrap gap-2">{last.r.followups.map(f => <button key={f} type="button" onClick={() => ask(f)} disabled={off} className="rounded-full border border-line bg-white px-3 py-1 text-xs text-ink-800 hover:bg-sunken">{f}</button>)}</div>}
    {turns.length === 0 && !off && <p className="text-sm text-ink-600">{caseId ? 'Ask about this case, a rule, a policy or how to use CredAssure, for example “Why is this case blocked?”.' : 'Ask how to use CredAssure, about a rule or a policy, for example “How does CredAssure handle personal data?”. Open a case to ask about its figures.'}</p>}
    {err !== undefined && <ErrorBanner error={err} />}
    {notice && !notice.acknowledgedAt && <div role="note" className="flex flex-wrap items-start gap-2 rounded-xl bg-ink-50 p-3 text-sm text-ink-900 ring-1 ring-line"><Info aria-hidden className="mt-0.5 h-4 w-4 shrink-0" /><span className="min-w-0 flex-1">{notice.text}</span>
      <Button size="sm" variant="outline" onClick={() => copilotService.acknowledge().then(setNotice).catch(setErr)}>I understand</Button></div>}
    <form onSubmit={e => { e.preventDefault(); void ask(q); }} className="flex gap-2"><label className="sr-only" htmlFor={caseId ? 'ask' : 'ask-anywhere'}>Your question</label>
      <Input id={caseId ? 'ask' : 'ask-anywhere'} value={q} onChange={e => setQ(e.target.value)} disabled={off} maxLength={4000} placeholder="Ask a question" />
      <Button type="submit" loading={busy} disabled={off || !q.trim()}><Send aria-hidden className="mr-1 h-4 w-4" />Ask</Button></form>
    {caseId && turns.length > 0 && <button type="button" onClick={reset} className="inline-flex items-center gap-1 text-xs font-medium text-ink-700 hover:text-ink-950"><RotateCcw aria-hidden className="h-3.5 w-3.5" />New conversation</button>}
    <CitationPanel caseId={caseId} c={open?.c ?? null} quote={open?.quote} onClose={() => setOpen(null)} returnFocus={opener} />
  </div>);
}
