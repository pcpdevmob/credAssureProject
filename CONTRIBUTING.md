# Contributing to CredAssure

## Workflow
- One phase per branch (`phase-N-short-name`); small PRs; the PR template lists requirement IDs, scope items and eval impact.
- Commit at the end of each green phase: `phase-N: <summary> [REQ-IDs]`. Never force-push or rewrite shared history.
- Track state in `PROGRESS.md`: read it first, update it last.

## Before you push
```
make install   # once, and after dependency changes
make check     # ruff, ruff format, mypy --strict, pytest, bandit
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
`.github/CODEOWNERS` maps each agent and package to its owner (docs/REPO_STRUCTURE.md). Shared packages need two reviewers.
