// P9 safety panel (plan v3.4 §6): the case's guardrail and Critic events, as codes and counts only. The gateway never
// returns the text that was blocked or redacted, so nothing sensitive reaches the browser.
import { gw, ok } from '@/lib/gateway';

export interface SafetyEvent { seq: number; at: string; type: string; rail?: string; rule?: string; action?: string; detail: string }
export interface SafetySummary { counts: Record<string, number>; events: SafetyEvent[] }
type Wire = { counts: Record<string, number>; events: ({ seq: number; ts: string; event_type: string; rail?: string; rule_id?: string; action?: string } & Record<string, unknown>)[] };

const LIST = (v: unknown) => (Array.isArray(v) ? v.map(String).join(', ') : v == null ? '' : String(v));
export function mapSafety(w: Wire): SafetySummary {
  return {
    counts: w.counts,
    events: w.events.map(e => ({
      seq: e.seq, at: e.ts, type: e.event_type, rail: e.rail, rule: e.rule_id, action: e.action,
      detail: ['kinds', 'flags', 'fields', 'codes', 'stage', 'reason', 'file_kind'].filter(k => e[k] != null && LIST(e[k])).map(k => `${k.replace('_', ' ')}: ${LIST(e[k])}`).join(' · '),
    })),
  };
}
export const safetyService = {
  async get(caseId: string): Promise<SafetySummary> {
    return mapSafety(await ok(gw.GET('/v1/cases/{case_id}/safety', { params: { path: { case_id: caseId } } })) as unknown as Wire);
  },
};
