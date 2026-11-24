# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow semver.

## [Unreleased]

## [1.1.0] - draft for the 24 Nov 2026 code freeze (K11; tag after the last freeze-scope PR merges)
Synthetic data only; approval is internal, never loan acceptance. Evaluated configuration unchanged: local Ollama
`qwen3:8b` on the Mac (ADR 0036). Release bundle: `make release` hashes the image digests, `data/frozen/v1`,
`data/frozen/v2/SHA256SUMS` and `evaluation/safety_v2/FROZEN.sha256` (K11). Before tagging, drop any line below whose
PR did not merge.
### Added
- Accounts, MFA and segregation of duties (ADR 0038, K14): gateway logins per HR employee, TOTP for Director, VP and
  account admin, staged sign-in, backup codes, user admin pages that never open a case, step-up with password and code
  above ₹1.5 crore (AUTH-10). Web sign-in, MFA set-up and user admin wired to the gateway (PR #37); the separate web
  auth service is retired.
- LendWise: three negotiation rounds in a fixed order (fee waiver, rate match, tenor change) with re-ranking after every
  counted concession (ADR 0037, K12).
- case.db on MySQL 8 behind `CASE_DATABASE_URL`, SQLite kept as the default (ADR 0039, K13).
- Mousita's stand-alone onboarding prototype kept for reference in `agents/onboarding/prototype` (own rule set and
  HR data, not wired into the app; 127 tests in `make check`); its design ships as onboarding 0.3.0.
- One password per account (ADR 0038): `make db` gives each account a random first password, changed at first
  sign-in, in `var/initial-passwords.txt` (0600); `make passwords` re-issues them. `SEED_PASSWORD_<USER>` sets one
  account's own password; the shared `SEED_PASSWORD` is no longer used.
- `make start` / `make stop` (`scripts/start.sh`): one command connects to the course endpoint (`MODELS=local` for
  Ollama), starts Langfuse when set up, the API and the web app, waits for each and prints the URLs; no demo cases.
- Excel workbook import for case data (ADR 0040); plain-language UI for non-technical operators: forms, readiness,
  case history, Indian dates (P9 9.2–9.3).
- Hosted deployment for evaluators (P15 15.3): model failover from the course endpoint to Hugging Face → Featherless
  (`LLM_FALLBACK_*`, unset by default), production Compose with Caddy HTTPS, hosted profile with the evaluated
  retrieval settings, server set-up, smoke and nightly-backup scripts, runbook `docs/deployment/azure.md`.
- Evaluation: honest labels and no cached replies in scored runs, RAG-only and oracle-context baselines, Critic
  tracing and quote grounding (K2), red-team runner and live log (K6: 25/25 resisted), course-endpoint comparison
  tooling (`make compare-runs`, `embed-parity`), safety_v2 H24 rule (state change or moved outcome is critical).
- System card and model card with measured results (K8); demo script, evidence slide and Q&A for three rounds.
- Gap review of 21 Nov (`docs/plan/gap-review-2026-11-21.md`): an offer that cannot be priced is flagged
  `LW_OFFER_INVALID` instead of failing the case (LW-01); the VP decides a case held at exactly ₹1.5 crore in the
  web app (APR-03); chat recognises data corrections and approval actions in code and changes nothing (SUP-02);
  `GET /v1/eval/runs/{id}` reports the progress of a `make eval` run (BRD §6.1; starting a run stays on the command line); `/v1/health/ready` reports the vector index.
- Onboarding agent 0.3.0 (design: Mousita, PR #43): the agent's own rule checker runs beside the rules engine and stops
  the stage with ERROR on any difference (never GO); the Supervisor's re-check uses that checker (SUP-05); every
  blocker says who fixes it (you, your manager or HR); each `onb.rule.*` fact cites its own HR record. Rules, HR data
  and the 10 onboarding items unchanged.
### Fixed
- The gateway and web images build (the gateway image left out `agents/`; the web image used a stale pnpm lockfile).
### Changed
- G4 result: 88/100 on the frozen test set (local qwen3:8b); course full-precision endpoint within one item.
- CI runs once per PR and on request; the MySQL job only for case.db changes (ADR 0028 amendment).
- Critic: number words in cited passages and approval-matrix wording no longer raise false positives (VER-02, VER-03).
### Added (copilot v3, merged after the 1.0.0 tag)
- Ask CredAssure on every page (ADR 0035): product help as a cited source, code intent routing (CP-07), case status from
  code (CP-10), per-case memory with "New conversation" (CP-11), Critic-first streaming, fixed follow-ups and answer
  ratings (CP-12). New help pages: *Ask CredAssure*, *AI safety and your data*.
- `POST /v1/copilot/chat`, `POST /v1/copilot/chat/stream`, `GET /v1/cases/{id}/chat`, `POST /v1/cases/{id}/chat/reset`,
  `POST /v1/copilot/feedback`, `GET /v1/citations/{chunk_id}`.
### Changed
- `cp_tool` 1.1.0 (six tools); the chat notice names product help, so users acknowledge it once more.
- No demo or replay mode: H19 (demo recording) dropped; `scripts/live_run.sh` defaults to `feature/LendWise`.

## [1.0.0] - 2026-11-18
First complete release for the IIT KGP Track B capstone. Synthetic data only; approval is internal, never loan acceptance.
### Added
- Five gated stages run by a code-driven Supervisor (LangGraph): employee onboarding, working-capital funding need,
  LendWise offer audit/pricing/affordability/ranking with one negotiation round, Verification Critic, approval routing
  (₹1.5 crore threshold, configurable boundary rule).
- Deterministic engines (Decimal/paise): 26-week cash table, recommendation and bridge, APR by IRR with GST and CGTMSE,
  affordability, ranking, routing, Indian number normaliser.
- Fact ledger with lineage and a hash-chained, append-only audit log; maker-checker, step-up re-auth, case deletion with
  tombstones.
- Ask CredAssure copilot: hybrid FTS5 + dense retrieval, reranker, answerability gate, span-cited answers cut by code,
  strict and supported scoring (plan v3.4 P4–P5).
- Guardrails R1–R5 (`packages/guardrails`, policy `config/guardrails.yaml`): PII v2, injection scanning and
  spotlighting, tool allowlists, output checks, masked telemetry; OWASP LLM + ASI mapping; fairness invariance and a
  protected-attribute denylist (P3, P8).
- React web app: case workflow, funding and offer views, copilot chat, approval inbox with approver attestation,
  safety panel, AI-generated labels, audit chain badge, evaluation scorecard, help centre (P9).
- Evaluation tooling: frozen 100-item test set, baseline S1–S3, harness through the API, ablation switches A1–A6, judge
  J1 with kappa calibration, E13 report generator, degradation matrix, load smoke (P7). The live measurements (E13,
  ablations, κ, load smoke, safety_v2) are not yet run; the system card claims none of them.
- Ship (P10): `REPLAY_MODE` demo fallback, online backup/restore, release bundle with CycloneDX SBOM, image-pinning
  tooling (pins pending, ADR 0034), runbook, system card, threat model, Sutra mapping and DPDP gap note.
- Phase 0 scaffold: uv workspace (gateway, observability), validated settings, structured JSON logging with PII masking,
  `/v1/health/live`, Makefile, pre-commit, CI, Compose profiles (dev, test, demo, langfuse), CODEOWNERS, PR template.
- ADRs 0001 (stack), 0002 (threat model), 0016 (self-hosted Langfuse) and the ADR index.
- Data docs: canonical R-ID crosswalk, synthetic sets S18–S24, D3/D5/D6 plants in DATA_SPEC.
