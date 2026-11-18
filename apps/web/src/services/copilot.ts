// Ask CredAssure (UI-06, CP-01..03, CP-07, CP-10..12, ADR 0035). The gateway decides everything below: whether the reply
// abstained, was refused or hit an injection, which source it used, and which follow-ups to offer; the browser only displays
// it. Nothing is stored in the browser: case history comes back from the gateway, and outside a case nothing is kept.
import { gw, ok } from '@/lib/gateway';
import { toProblem } from '@/lib/problem';
import { parseSse } from '@/lib/sse';

export interface Citation { chunkId: string; docId: string; title: string | null; section: string | null; effectiveFrom: string | null; collection: string | null; href: string | null }
export interface ChatReply {
  answer: string; citations: Citation[]; abstained: boolean; refused: boolean; refusalCode: string | null;
  injectionFlagged: boolean; piiRedacted: boolean; notice: string | null; traceId: string; aiDrafted: boolean;
  intent: string | null; followups: string[]; caseId: string | null;
}
type Wire = { answer: string; citations: { chunk_id: string; doc_id: string; title?: string | null; section?: string | null; effective_from?: string | null; collection?: string | null; href?: string | null }[];
  abstained?: boolean; refused: boolean; refusal_code?: string | null; injection_flagged: boolean; pii_redacted?: boolean; notice?: string | null; trace_id: string; source?: 'model' | 'code';
  intent?: string | null; followups?: string[]; case_id?: string | null };

/** A help citation opens the help centre; only an in-app /help/ anchor is accepted, never another URL. */
export const helpHref = (h: string | null | undefined): string | null => (h && /^\/help\/#[a-z0-9-]{1,80}$/.test(h) ? h : null);

export function mapChat(w: Wire): ChatReply {
  return { answer: w.answer, abstained: w.abstained === true, refused: w.refused, refusalCode: w.refusal_code ?? null, injectionFlagged: w.injection_flagged,
    piiRedacted: w.pii_redacted === true, notice: w.notice ?? null, traceId: w.trace_id, aiDrafted: w.source === 'model',
    intent: w.intent ?? null, followups: (w.followups ?? []).filter(f => typeof f === 'string').slice(0, 3), caseId: w.case_id ?? null,
    citations: w.citations.map(c => ({ chunkId: c.chunk_id, docId: c.doc_id, title: c.title ?? null, section: c.section ?? null, effectiveFrom: c.effective_from ?? null,
      collection: c.collection ?? null, href: helpHref(c.href) })) };
}
export interface PastMessage { role: 'user' | 'assistant'; text: string; traceId: string | null }
export type Rating = 'up' | 'down';
export type FeedbackReason = 'wrong' | 'not_cited' | 'unclear' | 'unhelpful' | 'unsafe' | 'other';
export interface StreamHandlers { onStage?: (stage: string) => void; onDelta?: (text: string) => void; signal?: AbortSignal }
export interface CitedPassage {
  chunkId: string; docId: string; title: string; section: string | null; effectiveFrom: string | null; legalBasis: string | null;
  sourceUrl: string | null; text: string; truncated: boolean; injectionFlagged: boolean;
}
type PassageWire = { chunk_id: string; doc_id: string; title: string; section: string | null; effective_from: string | null; legal_basis: string | null;
  source_url: string | null; text: string; truncated: boolean; injection_flagged: boolean };
/** Only web links are offered as links: a stored URL is data, never a script or other scheme. */
export const safeUrl = (u: string | null): string | null => { try { return u && ['http:', 'https:'].includes(new URL(u).protocol) ? u : null; } catch { return null; } };

export interface ChatNotice { text: string; version: string; acknowledgedAt: string | null }
type NoticeWire = { text: string; version: string; acknowledged_at: string | null };
const mapNotice = (w: NoticeWire): ChatNotice => ({ text: w.text, version: w.version, acknowledgedAt: w.acknowledged_at });

export const copilotService = {
  /** #40: the first-use notice and this user's stored acknowledgement (server-side, per notice version). */
  async notice(): Promise<ChatNotice> { return mapNotice(await ok(gw.GET('/v1/me/chat-notice')) as unknown as NoticeWire); },
  async acknowledge(): Promise<ChatNotice> { return mapNotice(await ok(gw.POST('/v1/me/chat-notice/ack')) as unknown as NoticeWire); },
  /** The text behind a citation, from the gateway under the filters the answer used. `quote` (the cited sentence) centres an L3 excerpt. */
  async passage(caseId: string | null, chunkId: string, quote?: string): Promise<CitedPassage> {
    const query = quote ? { quote: quote.slice(0, 1000) } : {};
    const w = (caseId
      ? await ok(gw.GET('/v1/cases/{case_id}/citations/{chunk_id}', { params: { path: { case_id: caseId, chunk_id: chunkId }, query } }))
      : await ok(gw.GET('/v1/citations/{chunk_id}', { params: { path: { chunk_id: chunkId }, query } }))) as unknown as PassageWire;
    return { chunkId: w.chunk_id, docId: w.doc_id, title: w.title, section: w.section, effectiveFrom: w.effective_from, legalBasis: w.legal_basis,
      sourceUrl: w.source_url, text: w.text, truncated: w.truncated, injectionFlagged: w.injection_flagged };
  },
  async ask(caseId: string, message: string): Promise<ChatReply> {
    return mapChat(await ok(gw.POST('/v1/cases/{case_id}/chat', { params: { path: { case_id: caseId } }, body: { message } })) as unknown as Wire);
  },
  /** CP-12: one turn as server-sent events. `stage` names the step; `delta` text arrives only after the Critic passed the
   *  answer; `final` is the full reply. Read through the generated client (it sends the bearer header). */
  async stream(message: string, caseId: string | null, h: StreamHandlers = {}): Promise<ChatReply> {
    const body = caseId ? { message, case_id: caseId } : { message };
    const { response } = await gw.POST('/v1/copilot/chat/stream', { body, parseAs: 'stream', signal: h.signal } as never) as { response: Response };
    if (!response.ok || !response.body) {
      let problem: unknown; try { problem = await response.json(); } catch { problem = undefined; }
      throw toProblem(response.status, problem);
    }
    const reader = response.body.getReader(); const dec = new TextDecoder(); let buf = '';
    for (;;) {
      const { value, done } = await reader.read();
      if (done) throw toProblem(0, undefined);
      const { events, rest } = parseSse(buf + dec.decode(value, { stream: true })); buf = rest;
      for (const e of events) {
        const d = e.data as Record<string, unknown>;
        if (e.event === 'stage' && typeof d.stage === 'string') h.onStage?.(d.stage);
        else if (e.event === 'delta' && typeof d.text === 'string') h.onDelta?.(d.text);
        else if (e.event === 'final') { await reader.cancel().catch(() => undefined); return mapChat(d as unknown as Wire); }
        else if (e.event === 'error') { await reader.cancel().catch(() => undefined); throw toProblem(500, { code: d.code, detail: d.detail, request_id: d.request_id }); }
      }
    }
  },
  /** CP-11: this user's own turns in the case since their last reset. */
  async history(caseId: string): Promise<PastMessage[]> {
    const w = await ok(gw.GET('/v1/cases/{case_id}/chat', { params: { path: { case_id: caseId } } })) as unknown as { messages: { role: string; text: string; trace_id: string | null }[] };
    return w.messages.filter(m => m.role === 'user' || m.role === 'assistant').map(m => ({ role: m.role as PastMessage['role'], text: m.text, traceId: m.trace_id }));
  },
  async reset(caseId: string): Promise<void> { await ok(gw.POST('/v1/cases/{case_id}/chat/reset', { params: { path: { case_id: caseId } } })); },
  async feedback(traceId: string, rating: Rating, reason?: FeedbackReason): Promise<void> {
    await ok(gw.POST('/v1/copilot/feedback', { body: { trace_id: traceId, rating, ...(reason ? { reason } : {}) } }));
  },
  /** `checks.model` is "disabled" when LLM_ENABLED=false and "open" when the model circuit breaker has tripped; an unreachable health check is treated as unknown, not as off. */
  async llmEnabled(): Promise<boolean | null> {
    try { const r = await ok(gw.GET('/v1/health/ready')) as unknown as { checks?: { model?: string } }; return r.checks?.model === undefined ? null : !['disabled', 'open'].includes(r.checks.model); }
    catch { return null; }
  },
};
