// Fact lineage (scope #33): GET /v1/cases/{id}/facts/{key}/lineage[?version=n]. Typed from openapi.json; no mapping.
import type { components } from '@credassure/api-client';
import { gw, ok } from '@/lib/gateway';

export type Lineage = components['schemas']['Lineage'];

export const lineageService = {
  get: (caseId: string, key: string, version?: number): Promise<Lineage> =>
    ok(gw.GET('/v1/cases/{case_id}/facts/{key}/lineage', { params: { path: { case_id: caseId, key }, query: version ? { version } : {} } })) as Promise<Lineage>,
};
