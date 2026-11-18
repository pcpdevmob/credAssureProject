# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow semver.

## [Unreleased]

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
- Evaluation: frozen 100-item test set, baseline S1–S3, harness through the API, ablations A1–A6, judge J1 with kappa
  calibration, E13 report, degradation matrix, load smoke (P7).
- Ship (P10): `REPLAY_MODE` demo fallback, online backup/restore, release bundle with CycloneDX SBOM, image pinning,
  runbook, system card, threat model, Sutra mapping and DPDP gap note.
### Added
- Phase 0 scaffold: uv workspace (gateway, observability), validated settings, structured JSON logging with PII masking,
  `/v1/health/live`, Makefile, pre-commit, CI, Compose profiles (dev, test, demo, langfuse), CODEOWNERS, PR template.
- ADRs 0001 (stack), 0002 (threat model), 0016 (self-hosted Langfuse) and the ADR index.
- Data docs: canonical R-ID crosswalk, synthetic sets S18–S24, D3/D5/D6 plants in DATA_SPEC.
