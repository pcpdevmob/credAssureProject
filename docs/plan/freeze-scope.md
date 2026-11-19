# Freeze scope: what is built and measured before 24 Nov 2026

Decided 2026-11-19 (Pritish asked for a call on what is essential). Basis: the course template's deliverables and
assessment (technical depth 30%, punctuality 25%, working deployed system 20%, report and demo 25%; no score threshold)
and BRD §13/§15 G4. Everything not listed under **Keep** is a stated limitation in the report, not unfinished work.

## Keep (each maps to a course deliverable)

| # | Item | Course deliverable | Thread | Done when |
|---|---|---|---|---|
| K1 | RAG-only row (`make rag-baseline`, PR #22) | Report: baseline comparisons | Eval | Four-row regulatory table filled |
| K2 | Regulatory answer fix (PR #23 and its follow-up), **time-boxed to Sun 22 Nov** | Technical depth: "compensating for a small model" | Eval | Dev split does not drop; injection 8/8, negotiation 5/5, safety_v2 unchanged; else report 88 as is |
| K3 | Final full run on the frozen code + A2 rerun (Critic on/off on final code) | Report: results, "full system minus Critic" | Eval | One reference `var/eval/` run, cache off |
| K4 | J1 judge + human labels on every judged answer (~15) + kappa (D4) | Technical rigour | Eval + Human review | Strict and supported regulatory scores, kappa reported |
| K5 | safety_v2 freeze (teammate) → run → A6 | Model card: adversarial tests | AI Safety | ≥ 38/40, 0 critical, or the misses explained |
| K6 | Red-team log, 20 prompts, outcome, fix or accepted limitation | Model card: failure modes, adversarial tests | Security | `docs/redteam_log.md` complete |
| K7 | Trace dashboard: Langfuse receives one case run and one eval run; trace links in the report | Trace dashboard (Track B) | Deployment | Screenshot + 3 trace links from eval rows (`trace_ids`) |
| K8 | `SYSTEM_CARD.md` §9 and model card with the final numbers | Model card / Responsible AI section | AI Safety | Numbers match the G4 report |
| K9 | Clean-machine run of the demo profile from the setup guide (one teammate) | Working deployed system | Deployment | Case runs end to end on a second machine |
| K10 | G4 report, 12-page technical report, demo script, recorded backup video | Report and demo | All | Submitted 27 Nov |
| K11 | Release: `v1.1.0` tag (owner) with eval report, data hashes; image pins if a networked machine is free (ADR 0034) | Reproducible repository | Deployment | Tag pushed by the owner after G4 |

## Cut (reported as known limitations)

| Item | Why it is cut |
|---|---|
| LendWise re-ranking after the negotiation round (§8a) | No evaluation item scores a post-round ranking, so it adds no measured result; it changes negotiation and offers code five days before the freeze and needs 20 items re-run. The approver already sees `negotiation_in_progress`. Reverses the 19 Nov 18:09 plan: owner to confirm. |
| Hinglish object-verb injection gap, employee-name PII matching, Critic table-unit check | Found by our own review; listed in the red-team log and system card as open limitations |
| JWT refresh endpoint | 30-minute re-login does not affect a 10-minute demo |
| Lighthouse ≥ 95 (H15), load smoke (#35, first in the permitted cut order), full e2e u6 | Replaced by one demo-path smoke test; latency and tokens per stage come from the eval run's `summary.json` |
| Further model, prompt or retrieval experiments beyond K2 | No measured gain on the dev split so far (source priority, llama3.1, thinking) |
| Retrieval human judging of 249 items (D3), LW-15, CP-08 full, A7 | Already cut (D3, ADR 0032) |

## The numbers the report uses (one canonical set)

1. 100-item score per category: full system vs S1, S2, S3 (closed-book).
2. Ablations A1–A5 on their categories, plus A6 (guardrails off) on safety_v2.
3. Regulatory ladder on the 19 answerable items: no documents, RAG only, full system, oracle passages.
4. Retrieval recall@5 on the frozen 40 queries (22/40, D1) and the dev split (17/20).
5. Safety: injection 8/8, safety_v2, red-team 20, refusals.
6. Judge agreement (kappa) and the supported regulatory score beside the strict one.
7. Tokens, latency and notional cost per stage from the reference run.

No other metric is added after 22 Nov.

## CI minutes (GitHub Free, 2,000 min/month; ~772 used 1–19 Nov)

`make check` is about 18 of the ~21 billed minutes per PR run. From 2026-11-19: draft PRs run no CI jobs (mark ready to
run it once); the web job builds only when web-relevant files change. Expected use for the rest of November is well
under the ~1,230 minutes left.
