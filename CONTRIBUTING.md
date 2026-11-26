# Contributing to CredAssure

## Workflow
- One branch per person and phase (`feature/<module>-<phase>`, e.g. `feature/copilot-p4`) from an up-to-date `main`; one PR per phase; the PR template lists requirement IDs, scope items, and eval impact.
- Merge with **Create a merge commit** only: evaluation reports cite commit hashes, which squash or rebase would change. Resync after every merge: `git pull origin main`.
- Commit at the end of each green phase: `phase-N: <summary> [REQ-IDs]`. Never force-push or rewrite shared history.
- CI (`.github/workflows/ci.yml`, ADR 0028) runs the same gates as the pre-push hook on every PR.

## Before you push
```
make install   # once, and after dependency changes
make check     # ruff, ruff format, mypy --strict, pytest, bandit, import contracts
make audit     # pip-audit
uv run pre-commit install   # once per clone
```

## Rules that reviewers enforce
- Requirement IDs (SUP, ONB, WC, LW, KR, CP, VER, APR, UI, BR, NFR) appear in docstrings and test names.
- Money is `Decimal` / integer paise; gates are computed in code; agents never call each other.
- Tests first for engines and gates; unit tests never touch the network or the LLM (use `FakeLLM`).
- No code path accepts, signs or submits a lender offer.
- Changes to the shared contract, the stack or the schema need an ADR (`docs/adr/README.md`).

## Ownership
`.github/CODEOWNERS` maps each agent and package to its owner (BRD §5.2). Shared packages need two reviewers.
