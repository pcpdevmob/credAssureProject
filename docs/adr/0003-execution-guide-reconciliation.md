# ADR 0003 — Reconciling the "4-Week Detailed Execution Guide" with BRD v3.1

Status: Proposed (team to confirm) · Date: 2026-11-03

## Context
`docs/CredAssure_4_Week_Detailed_Execution_Guide.docx` is a day-by-day plan for one person (3–5 h/day).
It states it was written without access to the UI, the repo or the API contracts. BRD v3.1 is the
mentor-reviewed specification for a 6-person Track B team. Where the two conflict on WHAT is built,
the BRD wins because Track B grading requires it. Where the guide is better on HOW to execute, we adopt it.

## Conflicts — BRD v3.1 wins
| Topic | Guide | BRD v3.1 (kept) | Why |
|---|---|---|---|
| Team model | One person | 6 members, one agent each | Track B role split; individual contribution assessed |
| AI | LLM optional (P1), one feature | Multi-agent with Supervisor, Critic, copilot; RAG over 500–2,000 docs; frozen 100-item eval set; 3-strategy baseline; ablations; tracing | Track B pillars I–VI are mandatory; a no-AI core would not meet the brief |
| Gate 1 "Readiness" | Case completeness checklist (business identity, PO, cash-flow data present) | Employee Onboarding: preparer's role, training, policy ack from HR records | BRD BR-03. Case completeness is kept, but as part of Gate 2 (WC-01/02) |
| Forecast | 6 monthly periods | 26 weekly periods | WC-03; peak shortfall timing needs weekly resolution |
| Uploads | PDF, CSV, XLSX; PDF text extraction | JSON and CSV only; no OCR | BRD §4.3, Q-08 |
| Lender cost | EMI, total interest, fees; rank by lowest total cost | APR by IRR incl. GST, insurance, CGTMSE; KFS hidden-charge check; affordability vs cash flow; rank by APR | LW-03..11, BR-06..08 |
| Verification | Reconciliation checks | Same, plus number normaliser vs ledger, citation checks, banned content | VER-01..05 |
| API | `/api/...`, one endpoint per step | `/cases/...` with `run` orchestrated by Supervisor | Either works; see decision 3 |

## Adopted from the guide (added to the kit)
1. **Integrate the UI early.** A walking skeleton visible in the UI by end of Week 1, not mid-Week 2.
2. **LLM-unavailable mode.** `LLM_ENABLED=false` runs every gate, calculation, routing and approval; narratives fall back to templates; copilot returns "unavailable". Demo and tests must pass in this mode.
3. **Proposal versioning.** Any change to an upstream ledger fact marks the proposal stale and requires regeneration (new version).
4. **Gates enforced server-side.** Navigation or direct API calls cannot skip a gate.
5. **Demo reset.** `make demo-reset` restores the seeded cases, the blocked case and the happy-path case.
6. **Daily discipline.** One concrete output per day; test in Swagger before wiring the UI; commit daily; switch to the documented fallback after 60–90 minutes blocked.
7. **Day 19–20 freeze.** Defect triage order: workflow blockers → wrong figures → display. Rehearse an 8–10 minute demo story; prepare answers to "what is AI doing / what is deterministic / how are figures verified / what is out of scope / what is needed for production".
8. **Explicit endpoints for each step.** Add `POST /cases/{id}/readiness|assessment|verify|proposal` as thin wrappers that run one Supervisor stage. This helps per-agent testing and UIs that expect step calls.

## Open decision — existing UI
The guide says "Keep the existing FinBridge AI UI; do not rebuild it." The BRD and the kit specify a new Streamlit UI.
- If a working FinBridge AI UI exists: keep it, replace its mock services with calls to the FastAPI endpoints, and drop Streamlit. API-01 already requires every screen to go through the API, so the backend does not change. Configure CORS for its origin and add a typed API client.
- If no working UI exists: keep Streamlit.
