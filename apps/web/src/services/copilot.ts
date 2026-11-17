// Ask CredAssure (UI-06, CP-01..03). The gateway decides everything below: whether the reply abstained, was refused or hit an
// injection; the browser only displays it. Case-scoped; nothing is stored in the browser.
import { gw, ok } from '@/lib/gateway';

export interface Citation { chunkId: string; docId: string; title: string | null; section: string | null; effectiveFrom: string | null }
export interface ChatReply {
  answer: string; citations: Citation[]; abstained: boolean; refused: boolean; refusalCode: string | null;
  injectionFlagged: boolean; piiRedacted: boolean; notice: string | null; traceId: string;
}
type Wire = { answer: string; citations: { chunk_id: string; doc_id: string; title?: string | null; section?: string | null; effective_from?: string | null }[];
  abstained?: boolean; refused: boolean; refusal_code?: string | null; injection_flagged: boolean; pii_redacted?: boolean; notice?: string | null; trace_id: string };

export function mapChat(w: Wire): ChatReply {
  return { answer: w.answer, abstained: w.abstained === true, refused: w.refused, refusalCode: w.refusal_code ?? null, injectionFlagged: w.injection_flagged,
    piiRedacted: w.pii_redacted === true, notice: w.notice ?? null, traceId: w.trace_id,
    citations: w.citations.map(c => ({ chunkId: c.chunk_id, docId: c.doc_id, title: c.title ?? null, section: c.section ?? null, effectiveFrom: c.effective_from ?? null })) };
}
export interface CitedPassage {
  chunkId: string; docId: string; title: string; section: string | null; effectiveFrom: string | null; legalBasis: string | null;
  sourceUrl: string | null; text: string; truncated: boolean; injectionFlagged: boolean;
}
type PassageWire = { chunk_id: string; doc_id: string; title: string; section: string | null; effective_from: string | null; legal_basis: string | null;
  source_url: string | null; text: string; truncated: boolean; injection_flagged: boolean };
/** Only web links are offered as links: a stored URL is data, never a script or other scheme. */
export const safeUrl = (u: string | null): string | null => { try { return u && ['http:', 'https:'].includes(new URL(u).protocol) ? u : null; } catch { return null; } };

export const copilotService = {
  /** The text behind a citation, from the gateway under the filters the answer used. `quote` (the cited sentence) centres an L3 excerpt. */
  async passage(caseId: string, chunkId: string, quote?: string): Promise<CitedPassage> {
    const w = await ok(gw.GET('/v1/cases/{case_id}/citations/{chunk_id}', { params: { path: { case_id: caseId, chunk_id: chunkId }, query: quote ? { quote: quote.slice(0, 1000) } : {} } })) as unknown as PassageWire;
    return { chunkId: w.chunk_id, docId: w.doc_id, title: w.title, section: w.section, effectiveFrom: w.effective_from, legalBasis: w.legal_basis,
      sourceUrl: w.source_url, text: w.text, truncated: w.truncated, injectionFlagged: w.injection_flagged };
  },
  async ask(caseId: string, message: string): Promise<ChatReply> {
    return mapChat(await ok(gw.POST('/v1/cases/{case_id}/chat', { params: { path: { case_id: caseId } }, body: { message } })) as unknown as Wire);
  },
  /** `checks.model` is "disabled" when LLM_ENABLED=false and "open" when the model circuit breaker has tripped; an unreachable health check is treated as unknown, not as off. */
  async llmEnabled(): Promise<boolean | null> {
    try { const r = await ok(gw.GET('/v1/health/ready')) as unknown as { checks?: { model?: string } }; return r.checks?.model === undefined ? null : !['disabled', 'open'].includes(r.checks.model); }
    catch { return null; }
  },
};
