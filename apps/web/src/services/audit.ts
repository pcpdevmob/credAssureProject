// Case history for every case member (GET /v1/cases/{id}/history); the raw audit log stays the evaluator's (/audit).
import type { AuditEvent, HistoryEvent } from '@/types';
import { gw, ok } from '@/lib/gateway';

type RawHistory = { events: { seq: number; ts: string; event_type: string; actor: string; actor_name: string | null; actor_role: string | null; details: Record<string, unknown> }[]; chain_ok: boolean };

export interface AuditService { list(caseId?: string): Promise<AuditEvent[]>; chain(caseId: string): Promise<boolean>; history(caseId: string): Promise<{ events: HistoryEvent[]; chainOk: boolean }> }
export const auditService: AuditService = {
  async list(caseId) {
    if (!caseId) return []; // no global list endpoint yet
    const r = await ok(gw.GET('/v1/cases/{case_id}/audit', { params: { path: { case_id: caseId } } })) as unknown as { events: { seq: number; event_type: string; actor: string; ts: string }[] };
    return r.events.map(e => ({ id: String(e.seq), caseId, at: e.ts, actor: e.actor, actorType: 'SYSTEM' as const, action: e.event_type, detail: '', severity: 'info' as const })).reverse();
  },
  /** U5: the gateway re-verifies the tenant's hash chain on every read (OBJ-08). */
  async chain(caseId) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/audit', { params: { path: { case_id: caseId } } })) as unknown as { chain_ok: boolean };
    return r.chain_ok === true;
  },
  async history(caseId) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/history', { params: { path: { case_id: caseId } } })) as unknown as RawHistory;
    return { chainOk: r.chain_ok === true, events: r.events.map(e => ({ seq: e.seq, ts: e.ts, type: e.event_type, actor: e.actor, actorName: e.actor_name, actorRole: e.actor_role, details: e.details ?? {} })) };
  },
};
