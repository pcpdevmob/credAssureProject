/**
 * Live implementation of the FinBridge UI's onboardingService, calling the Onboarding Agent.
 *
 * Where it goes:  src/services/onboarding.ts  (next to the existing mock implementation)
 * Backend call:   GET {NEXT_PUBLIC_API_BASE_URL}/agents/onboarding/readiness?caseId=...&user=...
 *
 * ADJUST ME: `toReadinessResult` maps the backend response onto the UI's `ReadinessResult`
 * type from src/types/index.ts. The field names on the right-hand side below are a best
 * guess; rename them to match that type (TypeScript will flag every mismatch).
 */
import type { ReadinessResult } from "@/types";
import { http } from "./http"; // the existing helper that adds the Bearer token

/* ---------- what the backend returns (stable contract, see API docs at /docs) ---------- */
export type BackendDecision = "GO" | "NO-GO" | "NEEDS_INPUT" | "ERROR";

export interface BackendRule {
  rule_id: string;            // e.g. "TRAINING:FINDATA", "ACK:POL_CREDIT", "ROLE_AUTHORISED"
  label: string;              // e.g. "Financial Data Handling and Privacy"
  outcome: "pass" | "fail" | "unknown";
  detail: string;             // plain-language reason written by code
  fix_by: "preparer" | "manager" | "hr" | "case" | null;
  source: string | null;      // HR record ID used as evidence
}

export interface BackendReadiness {
  case_id: string;
  preparer_id: string;
  decision: BackendDecision;
  rules: BackendRule[];
  blockers: BackendRule[];
  warnings: string[];
  explanation: string;
  explanation_source: "template" | "llm";
  next_action: string;
  rules_version: string;
  as_of: string;
  trace_id: string;
  output_ref: string;
  case_found: boolean;
}

/* ---------- mapping onto the UI type: ADJUST field names to src/types/index.ts ---------- */
export function toReadinessResult(r: BackendReadiness): ReadinessResult {
  return {
    caseId: r.case_id,
    preparerId: r.preparer_id,
    // The UI treats anything but GO as "blocked"; NEEDS_INPUT and ERROR must block too.
    decision: r.decision,
    isReady: r.decision === "GO",
    checklist: r.rules.map((rule) => ({
      id: rule.rule_id,
      label: rule.label,
      status: rule.outcome,               // "pass" | "fail" | "unknown"
      detail: rule.detail,
      fixBy: rule.fix_by ?? undefined,
    })),
    blockers: r.blockers.map((b) => b.detail),
    warnings: r.warnings,
    explanation: r.explanation,
    nextAction: r.next_action,
    checkedAt: r.as_of,
    traceId: r.trace_id,
  } as unknown as ReadinessResult; // remove this cast once the fields match the UI type
}

/* ---------- the service ---------- */
export const onboardingApiService = {
  async getReadiness(caseId: string, userEmail?: string): Promise<ReadinessResult> {
    const q = new URLSearchParams({ caseId });
    if (userEmail) q.set("user", userEmail);          // mapped to an HR employee by data/user_map.json
    const data = await http.get<BackendReadiness>(`/agents/onboarding/readiness?${q.toString()}`);
    return toReadinessResult(data);
  },

  /** Optional: chat with the agent. PII (Aadhaar, PAN, bank account) is removed server-side. */
  async sendMessage(caseId: string, message: string, userEmail?: string) {
    return http.post<{ reply: string; pii_redacted: string[] }>(`/agents/onboarding/message`, {
      case_id: caseId,
      user: userEmail,
      message,
    });
  },
};

/*
 * Switch only this service to live, leaving the other services on mocks:
 *
 *   const live = process.env.NEXT_PUBLIC_ONBOARDING_LIVE === "true" || process.env.NEXT_PUBLIC_USE_MOCK === "false";
 *   export const onboardingService = live ? onboardingApiService : onboardingMockService;
 *
 * NEXT_PUBLIC_* values are baked in at build time: rebuild (npm run build) after changing them.
 */
