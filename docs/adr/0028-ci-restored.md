# ADR 0028 — GitHub Actions CI restored alongside the local pre-push gates

Status: Accepted · Date: 2026-11-18 · Amends ADR 0027 (does not supersede it) · Scope #28, #36, #51

## Context
ADR 0027 replaced CI with `.githooks/pre-push` after commit cd57a3e removed `ci.yml` and `eval-fast.yml`
at the user's request. Its stated consequence: a push with `--no-verify`, or from a clone without
`core.hooksPath`, skips every gate and nothing on the remote enforces them.

On 2026-11-18 the team moved to one branch per person and phase, with one PR per phase reviewed on
GitHub (README §11), and the user asked for CI back so every PR shows its own pass/fail.

## Decision
Restore one workflow, `.github/workflows/ci.yml`, that runs the same targets as the pre-push hook:

| Job | Runs | Scope |
|---|---|---|
| python | `make hr-db`, `make check` (ruff, format, mypy --strict, the full pytest suite incl. the slow Schemathesis fuzz, bandit, `progress.py --check`), `make openapi-diff BASE=origin/<base>`, `make eval-fast` when `*/prompts/*` changed | #28, #36, #51 |
| audit | `make audit` (accepted advisories as listed in the Makefile), gitleaks | #41 (part) |
| web | `npm ci`, typecheck, vitest, `next build` (npm only, never pnpm) | UI |

The local pre-push hook stays: it is still the fastest feedback and the gate for anyone pushing.
CI is the remote enforcement ADR 0027 said was missing.

Two supporting changes:
- `make hr-db` rebuilds the gitignored `data/frozen/v1/hr.db` from the frozen, hashed
  `hr/profiles.json`. `make data` refuses after the G1 freeze, so before this a fresh clone (and CI)
  could not build the HR store and 56 tests failed (HISTORY, Phase 10b notes).
- CI installs `sentence-transformers` without dependencies (types only, pinned to `uv.lock`), so mypy
  sees the optional reranker module without downloading torch.

## Consequences
- PRs show a pass/fail check; branch protection on `main` can require it once CODEOWNERS handles are real.
- GitHub Actions minutes are used (private repositories: 2,000 free minutes a month on the free plan;
  one run is roughly 15–25 minutes).
- Actions are pinned by major version tag; pinning by digest is part of #41 in Phase 12.
- Course-endpoint and live-model checks never run in CI (no secrets in CI; FakeLLM only).
