// LendWise comparison. The gateway returns no offers until Phase 9c, so this is null until then (never invented).
import type { CaseRecord, LenderComparison } from '@/types';
import { gw, ok } from '@/lib/gateway';

export interface LendWiseService { compare(c: CaseRecord): Promise<LenderComparison | null> }
export const lendWiseService: LendWiseService = {
  async compare(c) {
    const r = await ok(gw.GET('/v1/cases/{case_id}/offers', { params: { path: { case_id: c.id } } })) as unknown as { offers: unknown[] };
    if (!r.offers.length) return null;
    throw new Error('Offer mapping arrives with Phase 9c'); // ponytail: map the real offer shape once the LendWise agent returns one
  },
};
