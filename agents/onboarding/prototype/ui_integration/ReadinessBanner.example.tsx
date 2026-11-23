/**
 * Example only: how a page can gate the financial tabs on the agent's decision
 * (UI README: "Readiness NO-GO blocks all financial tabs"). Adapt to the UI's own components.
 * Rule: only "GO" unlocks. "NO-GO", "NEEDS_INPUT" and "ERROR" all keep the tabs locked.
 */
"use client";
import { useEffect, useState } from "react";
import { onboardingApiService, type BackendDecision } from "@/services/onboarding";

export function useFinancialTabsUnlocked(caseId: string, userEmail?: string) {
  const [decision, setDecision] = useState<BackendDecision | "LOADING">("LOADING");
  useEffect(() => {
    onboardingApiService
      .getReadiness(caseId, userEmail)
      .then((r: any) => setDecision(r.decision))
      .catch(() => setDecision("ERROR"));          // backend down: stay locked
  }, [caseId, userEmail]);
  return { decision, unlocked: decision === "GO" };
}
