import type { Fig } from '@/lib/money';
// Shared domain types. Backend teammates: keep API payloads in this shape (or adapt in src/services/http.ts).
export type Role = 'PREPARER' | 'VP_FINANCE' | 'DIRECTOR_FINANCE' | 'EVALUATOR';
export const ROLE_LABEL: Record<Role, string> = { PREPARER: 'Proposal Preparer', VP_FINANCE: 'VP, Finance', DIRECTOR_FINANCE: 'Director, Finance', EVALUATOR: 'Evaluator' };

export type AccountRole = 'global_admin' | 'admin';
export interface User { id: string; name: string; email: string; role: Role; employeeId: string; username?: string; accountRole?: AccountRole; mustChangePassword?: boolean; mfaEnabled?: boolean; stage?: 'setup' | 'mfa' | 'full' }
export interface ManagedUser { username: string; name: string; accountRole: AccountRole; mustChangePassword: boolean; disabled: boolean; mfaEnabled?: boolean; createdAt?: number }
export interface UserLogEvent { id: number; at: number; actor: string; action: string; target: string; ip: string; ua: string | null; detail: string | null }

export type GateDecision = 'GO' | 'NO_GO' | 'NEEDS_INPUT' | 'ERROR' | 'PENDING' | 'RUNNING' | 'HELD';

export type CaseStage =
  | 'DRAFT' | 'READINESS' | 'DATA_COLLECTION' | 'FUNDING_ASSESSMENT' | 'LENDER_COMPARISON'
  | 'NEGOTIATION' | 'VERIFICATION' | 'AWAITING_APPROVAL' | 'APPROVED' | 'REJECTED' | 'RETURNED' | 'ROUTING_HELD';

export type Approver = 'VP_FINANCE' | 'DIRECTOR_FINANCE' | 'HELD_PENDING_POLICY';

export interface CaseRecord {
  id: string; msmeName: string; sector: string; gstinMasked: string;
  customerName: string; orderValue: Fig; orderRef: string; customerDueDate: string;
  currency: 'INR'; requestedAmount: Fig; recommendedAmount?: Fig;
  preparerId: string; preparerName: string; createdAt: string; updatedAt: string;
  stage: CaseStage; rowVersion?: number; question?: string | null; nextAction?: string; routedTo?: Approver; selectedLenderId?: string; city?: string; negotiationRound?: number;
}

export interface Prerequisite { id: string; name: string; category: 'Onboarding' | 'Training' | 'Policy' | 'Authorisation'; mandatory: boolean; status: 'COMPLETE' | 'INCOMPLETE' | 'UNKNOWN'; evidence?: string; completedOn?: string; owner: string }
export interface ReadinessResult { employeeId: string; employeeName: string; role: string; buddy: string; manager: string; decision: GateDecision; prerequisites: Prerequisite[]; blockers: string[]; checkedAt: string }


export interface CashRow { week: number; inflow: Fig; outflow: Fig; cumulative: Fig; shortfall: boolean; belowBuffer: boolean | null }
export interface CashTable { buffer: Fig | null; peakWeek: number | null; rows: CashRow[] }
export interface FundingAssessment {
  caseId: string; requestedAmount: Fig; minCashBuffer: Fig; peakShortfall: Fig; peakWeek: number | null; shortfallWeeks: number | null; existingFacility: Fig;
  recommendedAmount: Fig; bridge: { code: string; amount: Fig }[]; decision: GateDecision; cash: CashTable | null;
}

/** One offer at its latest version, exactly as the gateway computed it. `affordable` and `rank` are null in the read-only preview. */
export interface OfferRow {
  id: string; version: number; flags: string[]; comparable: boolean; affordable: boolean | null; rank: number | null;
  /** Set by the gateway on the lowest-APR offer(s). The UI never compares APRs itself. */
  cheapest: boolean;
  apr: Fig | null; aprPct: string | null; amountReceived: Fig | null; totalRepayment: Fig | null; totalCost: Fig | null;
}
export interface Negotiation {
  target: string | null; competingFee: Fig | null; countsAsConcession: boolean; message: string; status: string | null;
  revised: { version: number; comparable: boolean; flags: string[]; apr: Fig | null; totalCost: Fig | null } | null;
}
/** `preview` = audit and pricing only; affordability and ranking have not been checked. */
export interface OfferView { caseId: string; source: 'ledger' | 'preview'; offers: OfferRow[]; ranking: string[]; negotiation: Negotiation | null }

export interface WorkflowGate { id: string; name: string; agent: string; decision: GateDecision; evidence: string; blockers: string[]; at?: string; next: string }

export interface ApprovalDecision { caseId: string; decision: 'APPROVED' | 'REJECTED' | 'RETURNED'; comment: string; by: string; role: Role; at: string }

export interface AuditEvent { id: string; caseId: string; at: string; actor: string; actorType: 'HUMAN' | 'AGENT' | 'SUPERVISOR' | 'SYSTEM'; action: string; detail: string; severity: 'info' | 'warn' | 'critical' }
