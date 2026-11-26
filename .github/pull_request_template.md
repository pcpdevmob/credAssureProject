## What and why

## Requirement IDs
<!-- e.g. LW-09, BR-07. Every implementing docstring and test name carries the ID. -->

## Build scope items
<!-- e.g. #31 -->

## Eval impact
- [ ] No prompt or model change
- [ ] Prompt/model change: version bumped and fast eval subset run (scope #36) — results:

## Progress (README §11)
- Phase and step (plan Sheet): 
- [ ] Merge with **Create a merge commit** (not squash or rebase: reports cite commit hashes)

## Checks
- [ ] `make check` green (CI shows the same)
- [ ] No frozen file changed (`evaluation/FROZEN.sha256` list, `data/frozen/v1`) — or ADR linked
- [ ] Reviewed for money, security and BRD conformance; MUST findings fixed
- [ ] `openapi.json` regenerated if the API changed (ADR 0004)
- [ ] No code path accepts, signs or submits a lender offer
- [ ] Screenshots attached (UI changes only)
