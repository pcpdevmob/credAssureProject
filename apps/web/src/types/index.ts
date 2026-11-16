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

export interface UploadedDoc { id: string; caseId: string; name: string; kind: 'CSV' | 'JSON' | 'EXCEL' | 'PDF'; docType: string; sizeKb: number; status: 'UPLOADING' | 'EXTRACTING' | 'EXTRACTED' | 'NEEDS_REVIEW' | 'FLAGGED'; fields: number; warnings: string[]; uploadedAt: string }

export interface FundingAssessment {
  caseId: string; requestedAmount: Fig; minCashBuffer: Fig; peakShortfall: Fig; peakPeriod: string; existingFacility: Fig;
  recommendedAmount: Fig; drivers: { label: string; amount: Fig }[]; decision: GateDecision;
}

export interface LenderOffer {
  // Shape lands with the LendWise mapping in U3; figures are display strings + ledger keys, never floats.
  lenderId: string; lenderName: string; annualRate: Fig; apr: Fig; netDisbursal: Fig; totalCost: Fig; flags: string[];
}
export interface NegotiationEvent { round: number; lenderId: string; lenderName: string; ask: string; outcome: 'ACCEPTED' | 'PARTIAL' | 'REFUSED' | 'NO_RESPONSE' | 'INITIAL'; detail: string; at: string }
export interface LenderComparison { caseId: string; offers: LenderOffer[]; history: NegotiationEvent[]; bestLenderId: string; roundsUsed: number; maxRounds: 3; decision: GateDecision }

export interface WorkflowGate { id: string; name: string; agent: string; decision: GateDecision; evidence: string; blockers: string[]; at?: string; next: string }

export interface ApprovalDecision { caseId: string; decision: 'APPROVED' | 'REJECTED' | 'RETURNED'; comment: string; by: string; role: Role; at: string }

export interface AuditEvent { id: string; caseId: string; at: string; actor: string; actorType: 'HUMAN' | 'AGENT' | 'SUPERVISOR' | 'SYSTEM'; action: string; detail: string; severity: 'info' | 'warn' | 'critical' }
