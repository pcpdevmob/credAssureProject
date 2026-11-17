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
export const copilotService = {
  async ask(caseId: string, message: string): Promise<ChatReply> {
    return mapChat(await ok(gw.POST('/v1/cases/{case_id}/chat', { params: { path: { case_id: caseId } }, body: { message } })) as unknown as Wire);
  },
  /** `checks.model` is "disabled" when LLM_ENABLED=false and "open" when the model circuit breaker has tripped; an unreachable health check is treated as unknown, not as off. */
  async llmEnabled(): Promise<boolean | null> {
    try { const r = await ok(gw.GET('/v1/health/ready')) as unknown as { checks?: { model?: string } }; return r.checks?.model === undefined ? null : !['disabled', 'open'].includes(r.checks.model); }
    catch { return null; }
  },
};
