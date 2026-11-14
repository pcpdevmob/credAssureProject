// Audit log: the gateway exposes it per case, to evaluators only.
import type { AuditEvent } from '@/types';
import { gw, ok } from '@/lib/gateway';

export interface AuditService { list(caseId?: string): Promise<AuditEvent[]> }
export const auditService: AuditService = {
  async list(caseId) {
    if (!caseId) return []; // no global list endpoint yet
    const r = await ok(gw.GET('/v1/cases/{case_id}/audit', { params: { path: { case_id: caseId } } })) as unknown as { events: { seq: number; event_type: string; actor: string; ts: string }[] };
    return r.events.map(e => ({ id: String(e.seq), caseId, at: e.ts, actor: e.actor, actorType: 'SYSTEM' as const, action: e.event_type, detail: '', severity: 'info' as const })).reverse();
  },
};
