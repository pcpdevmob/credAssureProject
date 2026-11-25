# ADR 0027 — Local pre-push gates replace GitHub Actions CI

Status: Accepted (amended by [ADR 0028](0028-ci-restored.md): CI restored alongside these gates) · Date: 2026-11-17 · Phase 10b · Amends ADR 0004 (line "CI fails if it is stale"),
BUILD_SCOPE #28, #36, #41 and #51, and docs/build/REPO_STRUCTURE.md (`.github/workflows/`)

## Context
Commit cd57a3e ("chore: remove GitHub Actions CI") deleted `ci.yml` and `eval-fast.yml` at the user's
request. The commit body is empty; its PROGRESS line reads "GitHub Actions CI (ci.yml, eval-fast.yml)
removed at user request; run `make check` and `make eval-fast` locally before committing". Several scope
items named CI as the place where a check fails, and E10 and E17 (2026-11-17b) asked for the deviation to
be recorded.

## Decision
The checks run locally in `.githooks/pre-push` (enabled per clone with `git config core.hooksPath .githooks`):

| Scope item | Was ("in CI") | Now (pre-push) |
|---|---|---|
| #28 breaking openapi.json diff | oasdiff step | `make openapi-diff` (`scripts/openapi_diff.py` vs `main`) after `make check-fast`, which includes `test_openapi_current` |
| #36 prompt change → fast eval | eval-fast workflow | `make eval-fast` when the branch changes any `*/prompts/*` file vs `main` |
| #51 Schemathesis | CI job | `pytest -m slow apps/gateway/tests/test_phase10_contract.py` (Preparer, Director, Evaluator) |
| #41 SBOM | CI artefact | Not run yet (Phase 12, `make sbom`) |

`make check` (ruff, mypy --strict, pytest, bandit) stays the gate before each phase commit.

## Consequences
- A push with `--no-verify`, or from a clone without `core.hooksPath`, skips the gates; nothing on the
  remote enforces them. This is accepted for a 6-person capstone with local runs.
- The hook takes about 15 minutes (check-fast ~10 min, fuzz ~4 min).
- Restoring CI later means adding back one workflow that runs these same targets; no code change.
