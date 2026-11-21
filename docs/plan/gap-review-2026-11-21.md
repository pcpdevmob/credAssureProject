# Implementation gap review — 21 Nov 2026

Scope: `main` (at the #33 sync), `feature/LendWise` (#34–#36 ahead), open PRs #37 (web accounts and MFA) and #38
(lender PDF intake), and the two branches prepared the same day (hosted deployment, docs). Method: every BRD
requirement ID traced to code and tests; every API route checked for a caller in the web app; unfinished-work
markers and 501 answers read; typed-data probes run through the API; the images' install step reproduced from only
the files they copy. Branch `feature/gaps-p16` holds the fixes.

`main` and `feature/LendWise` differ only by the merged PRs #34–#36: no code exists on `main` that is missing
from `feature/LendWise`. The four open branches merge together without conflict; with all of them merged the web
type-check and unit tests pass.

## Fixed in this review

| # | Gap | Requirement | Was | Now |
|---|---|---|---|---|
| 1 | An offer the engine cannot price stopped the case | LW-01, BR-06 | Financed insurance or another CGTMSE basis (ADR 0021: not priced), a zero or percent-typed rate, zero tenure, no repayment month: Lender comparison failed (case FAILED) and `GET /offers` answered 500. A negative rate or fee was priced and could rank. The PDF intake form (#38) has a "financed" tick box that led straight to it. `LW_OFFER_INVALID` existed in the catalogue and was never produced | The offer is flagged `LW_OFFER_INVALID`, never priced or ranked, the card names the term to correct, the other offers are compared |
| 2 | A case held at exactly ₹1.5 crore could not be decided in the web app | APR-03, UI-07 | The gateway lets the VP decide a HELD case; the Review tab showed the decision form only for AWAITING_APPROVAL. No API test covered a HELD decision | The VP gets the form; API and web tests added |
| 3 | Chat did not classify its input | SUP-02 | "placeholder" since phase 8b: "Approve it now" or "the buffer should be ₹12 lakh" went to the model's tool choice and ended as an abstention; the S18 fixtures were unused | Code classifies a data correction and an approval action before routing; fixed replies; nothing changes from chat. S18: 15/15 on intent, form and step |
| 4 | `GET /v1/eval/runs/{id}` answered 501 | BRD §6.1 | "arrive in Phase 11" | Reports the progress and per-category counts of a `make eval` run from the files it writes. Starting a run through the API stays refused: see the decision below |
| 5 | `/v1/health/ready` reported `chroma: not_configured` as a constant | scope #50 | "Phase 7 adds the embedded Chroma client" | Reports `ok`, `missing` or `not_configured` from the index on disk |
| 6 | The gateway image could not build | NFR-09 | `Dockerfile.gateway` did not copy `agents/`; the gateway imports `credassure.retrieval` without declaring it | Installs every workspace member like `make install`; proven by installing from only the copied files and running demo-reset and the smoke test |
| 7 | The web image could not build | NFR-09 | `pnpm install --frozen-lockfile` on a lockfile last updated at the first UI commit | `npm ci` on `package-lock.json`, as CI does |
| 8 | Compose gateways had no data | NFR-09 | The image excludes `data/`; dev/demo containers had no reference tables, lender scripts or hr.db | `data/` mounted read-only |

## Found, not built (stated as limitations; each has an API or a manual path)

| Gap | Requirement | Today | Why left |
|---|---|---|---|
| No screen to delete a case | scope #39 | `DELETE /v1/cases/{id}` (evaluator) works | Evaluator-only housekeeping; a typed confirmation dialog is UI work after the freeze |
| No screen to retry a failed step as evaluator | scope #25 | `POST …/stages/{stage}/retry` works; the preparer can press Run again on a FAILED case | Covered by the preparer path |
| No screen for the ₹1.5 crore boundary rule | APR-03 | `POST /v1/admin/config` (evaluator, audited) and `BOUNDARY_RULE` | Needs a read route for the current value first |
| No button to change a user's role | ADR 0038 | `POST /v1/admin/users/{id}/role` works | A preparer needs an HR record; disable + create covers it |
| `POST /v1/eval/runs` does not start a run | BRD §6.1 | 501 with the reason; `make eval` starts a run, the API and the scorecard page read it | Decision below |
| Header mapping for renamed CSV columns (`wc_header_map`, S20 fixtures) | design-detail §2.4.3 (optional) | Not built; fixtures unused | Superseded by the forms and the Excel template (ADR 0040) |
| Financed insurance and other CGTMSE bases are not priced | ADR 0021 | Flagged, not compared (gap 1) | Needs an agreed convention and independent gold |
| Out-of-scope chat has no class of its own | SUP-02 | Ends as a refusal or the abstention sentence | Same user outcome; a fourth class would change the scored regulatory path |
| Dev/demo Compose profiles use Ollama embeddings, not the evaluated retrieval settings | handoff §5 | The hosted stack (`production.yaml`) and `make run-api` run the evaluated settings | Dev/demo profiles are not a presented path |
| Stretch items UI-09, UI-10, ONB-07, WC-08, CP-04, VER-06 | BRD §4.2 | Not built | Cut by ADR 0032 |

## Decision for the owner: starting an evaluation run through the API

BRD §6.1 lists `POST /eval/runs`. Building it means the gateway starts the harness as a process for hours of model
calls. That breaks a tested security rule: no agent, package or gateway module imports `subprocess`
(`test_ASI05_no_runtime_module_can_execute_code_or_spawn_a_process`; the only exception is a developer CLI that no
request can reach), and the security map counts ASI05 as proven on that test. The route was built in this review,
the full check caught the conflict, and it was withdrawn: the route answers 501 and says to use `make eval`.

- **Kept (recommended):** runs start from the command line; the API reads them. No security claim changes. The
  hosted deployment would refuse to start runs anyway (shared model endpoint), and on the Mac `make eval` is the
  evaluated path.
- **Alternative, if the team wants the route:** add a reviewed exception to the ASI05 test for one fixed-argv
  process started by an evaluator, and say so in `docs/security/owasp-asi-mapping.md`. About an hour, plus a
  security review. Not done without the owner's decision.

## Not gaps (checked)
- Every core requirement ID (UI, API, SUP, ONB, WC, LW, KR, CP, VER, APR) has tests; only the stretch IDs above
  have none.
- A FAILED case is not a dead end: the preparer can run it again.
- The boundary rule set through the API survives a restart (read from `app_config` at start).
- #37 and #38 together: no code or type conflict; 184 web tests pass on the merged tree.
