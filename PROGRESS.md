# CredAssure — Progress (Claude Code reads this first and updates it last)

## Current phase
Phase 0 — not started

## Gates
- [ ] G1 (end Week 1): test set + 40 retrieval queries frozen; synthetic data v1; baseline S1–S3; AgentResult frozen; endpoint limits confirmed
- [ ] Skeleton (end Week 1, ADR 0003): placeholder agents end to end through API + reference UI; LLM_ENABLED=false works
- [ ] G2 (end Week 2): ≥500 docs indexed; retrieval report; engines + normaliser green; Onboarding + WC agents end to end
- [ ] G3 (end Week 3): real case end to end with traces; Critic blocks planted bad claims
- [ ] G4 (end Week 4): full eval + ablations; red-team log; Docker; report; demo rehearsed

## Phase log
| Phase | Status | Requirement IDs | Commit | Notes |
|---|---|---|---|---|
| 0 Scaffold | todo | NFR-07, NFR-09 | | |
| 0b Monorepo | todo | ADR-0005 | | |
| UI U0–U6 | todo | UI-01..09 | | React lane |

## Open questions (owner, date)
- Endpoint context window, JSON/guided-decoding support, token quota (confirm day 2)
- Owner names for [Name 1]…[Name 6] and UI lead

## Settled defaults (ADRs 0012–0015)
- APR nominal, proven by RBI Annex B reproduction test · Reranker none unless mentor approves · Judge J1 calibrated, kappa ≥ 0.7 else human scoring · Live demo with replay + video fallback · Boundary rule hold

## Decisions pending (human)
- Add agent_version to AgentResult before G1 (scope #25)
- tenant_id on case tables in Week 1 (scope #27)
- Permitted cut order if Week 3 slips (each needs an ADR): scope #35, #41, #38, #37

## Decisions
- See docs/adr/

## Scope items done (docs/BUILD_SCOPE.md)
- none yet
