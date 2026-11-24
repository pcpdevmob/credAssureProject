# CredAssure system card

Version 1.1.0 · 2026-11-20 · Plan v3.4 §6, scope #69 · Companion pages: [THREAT_MODEL.md](THREAT_MODEL.md),
[security/model-card.md](security/model-card.md) (models and data provenance), [security/owasp-asi-mapping.md](security/owasp-asi-mapping.md).

CredAssure is an IIT Kharagpur Track B capstone **prototype**. It runs on synthetic company, lender and employee data
only. Nothing here is a compliance claim; the Sutra mapping (§12) describes alignment by design.

**Design principle:** the AI reads, explains and drafts; code calculates, routes and gates; a human approves.

## 1. Intended use and users
Prepare and review a working-capital loan proposal for an electronics-manufacturing MSME: check the preparer is
qualified, calculate the real funding need from 26 weeks of cash flow, compare simulated lender offers on true cost
and affordability, verify every figure and citation, and route the proposal to the right finance approver.

| User | Uses it to |
|---|---|
| Proposal preparer | Create a case, upload files, run the stages, ask Ask CredAssure |
| Director, Finance / VP, Finance | Read the verified proposal and decide: approve, reject or return to a stage |
| Evaluator | Read the audit log, safety events and evaluation scorecard |

**Ask CredAssure** (ADR 0035) is on every page. It answers from four cited or code-written sources: product help
(`docs/help`), the regulatory library, company policies and, only inside a case the person may see, that case's status,
blockers and verified figures. It gives no uncited, open-domain answers: when nothing supports an answer it says "I
can't verify that from the available sources".

## 2. Out-of-scope uses
- Credit underwriting, credit scores or predicting whether a lender will approve.
- Accepting, signing or submitting a lender offer: no such path exists (`apps/gateway/tests/test_lw_items.py::test_BR13_no_route_accepts_signs_or_submits_an_offer`).
- Legal or tax advice; the copilot gives cited general information only.
- Real personal, customer or company data; OCR or scanned documents; live bank, GST, ERP or bureau integration.
- Unattended operation: every consequential decision needs a person.

## 3. Models
| Role | Model | Where |
|---|---|---|
| Chat (all agents) | Qwen3-8B (≤ 8B, no fine-tuning, thinking off) | Course endpoint (`MODELS=course`) or local Ollama `qwen3:8b` (`MODELS=local`, ADR 0017) |
| Embeddings | bge-small-en-v1.5 (`MODELS=local|course`; a plain `.env` without a profile defaults to `nomic-embed-text`) | Course endpoint or local |
| Reranker | BAAI/bge-reranker-base, pinned revision; scores only for the answerability gate | Local (ADR 0013, 0032) |
| Judge J1 | The same chat model, calibrated against human labels (ADR 0014) | Evaluation only |

The model never decides a gate, a figure, a route or a ranking. It drafts narratives from ledger slots, extracts
charges from one KFS at a time (code checks the quoted span), picks one copilot tool from a fixed list, and writes
cited answers whose unsupported sentences code removes.

## 4. Data provenance
| Basis | Data |
|---|---|
| L1 Open data licence | data.gov.in resources (optional) |
| L2 Gazette and court matter | MSME classification, GST notifications, DPDP Rules, judgments |
| L3 Acts | MSMED Act, Income-tax Act 2025: indexed locally, short quotes only, never committed |
| L4 Public documents, research fair dealing | RBI directions and FAQs, CGTMSE, SIDBI, bank schedules of charges: never redistributed |
| L5 Team-owned synthetic | 20 HR profiles, 15 MSME cases, 45+ offers, KFS documents, policies, the 100-item test set |

Collection rules (robots.txt, ≤ 1 request/s, manual-only hosts) are in [security/model-card.md](security/model-card.md)
and ADR 0020. Every corpus document carries its legal basis and SHA-256 (`data/generators/tests/test_corpus.py::test_KR04_committed_manifest_passes_the_audit`).

## 5. Human-in-the-loop boundary
| Decision | Who decides | Enforced by |
|---|---|---|
| Gate GO / NO_GO / NEEDS_INPUT | Code | `agents/supervisor/tests/test_graph.py::test_SUP05_forced_go_is_overridden_by_failing_recheck` |
| Funding need, APR, ranking, route | Code engines | Known-answer tests against independent gold (15/15 and 15/15) |
| Approve, reject, return | The routed human approver only | `packages/security/tests/test_auth.py::test_APR05_maker_checker_refuses_self_approval_even_for_an_approver_role` |
| Approve above ₹1.5 crore | VP with password step-up | `apps/gateway/tests/test_phase10_approvals.py::test_NFR07_vp_approval_above_threshold_needs_step_up` |
| Approve at all | Only after the approver attests they reviewed Critic findings and safety events | `apps/gateway/tests/test_p9_rai.py::test_P9_ASI09_approve_needs_the_attestation_and_records_it` |
| Negotiation move and target | Code, from ledger figures; the Critic checks the message before it is sent | `agents/lendwise/tests/test_negotiation_rounds.py::test_LW15_three_rounds_in_fixed_order_one_per_call_then_complete` |
| Choose a lender | The MSME, outside CredAssure | No accept/sign path (§2) |

**RACI**

| Activity | Responsible | Accountable | Consulted | Informed |
|---|---|---|---|---|
| Case data and uploads | Preparer | Preparer | — | Approver |
| Figures and gates | Code engines (owners: Suresh, Pritish) | Supervisor owner | Critic | Approver, evaluator |
| Proposal decision | Routed approver | Director / VP, Finance | Safety panel, Critic findings | Preparer, audit |
| Guardrail policy (`config/guardrails.yaml`) | Guardrails owner | Team lead | Security reviewer | Evaluator |
| Evaluation and red-teaming | Abhishek, Tejas | Team lead | Module owners (never their own items) | Mentor |

## 6. Refusal policy
Code rules run before any model call (`agents/copilot/tests/unit/test_agent.py::test_CP03_refusal_runs_before_any_model_call`):

| Request | Response |
|---|---|
| Predict lender approval or score credit | Cannot assess creditworthiness; points to the comparison |
| Legal or tax advice | General cited information only; recommends an adviser |
| Accept or sign an offer | Outside the system; directs to the approver |
| Override a failed gate | Explains the blocker and the action needed |
| Invent rates or competing offers | Uses verified facts only |
| Aadhaar, PAN or account numbers | Redacted, never stored; explains why |
| Another case's data | Not accessible |
| Nothing relevant found | Exactly "I can't verify that from the available sources" |

## 7. Guardrail layers and patterns
Five rails in `packages/guardrails` (ADR 0029), policy `config/guardrails.yaml` (versioned, hashed in `config/guardrails.lock`):

| Rail | What it does | Test |
|---|---|---|
| R1 Input | Uploads and chat: PII refused or redacted, injection flagged, protected-attribute fields refused | `apps/gateway/tests/test_p8_protected_attributes.py::test_scope67_protected_attribute_field_is_refused_and_audited` |
| R2 Retrieval | Jurisdiction, date, supersession and case filters; spotlighting; excerpt cap | `packages/retrieval/tests/test_ingest_search.py::test_KR04_superseded_only_once_the_replacement_is_in_force` |
| R3 Tools | Per-agent allowlist; loop detection | `packages/tools/tests/test_runner.py::test_scope4_identical_repeat_call_raises_loop_detected` |
| R4 Output | Verification Critic (figures, citations, banned content, PII); regenerate twice, then template | `agents/critic/tests/test_verify.py::test_VER03_banned_content_is_critical` |
| R5 Telemetry | Identifiers masked before logs and traces | `apps/gateway/tests/test_p3_guardrails.py::test_scope59_planted_identifiers_never_reach_traces_exports_or_audit` |

Injection is contained by architecture first (plan-then-execute, map-reduce, context minimisation, action selector;
[THREAT_MODEL.md §4](THREAT_MODEL.md#4-injection-design-patterns-adr-0033)). Every block, redaction and flag is a
`GUARDRAIL_EVENT` in the audit log and appears, as a code without text, on the approver's safety panel.

Kill switches: `LLM_ENABLED=false` runs every gate, figure, route and approval on templates; `REPLAY_MODE=true` serves
only recorded chat replies (the chat endpoint is never called); `ABLATION=A6` (guardrails off, evaluation only) is refused in the demo profile.

## 8. OWASP LLM and ASI mapping
All ten OWASP LLM (2026) and ten Agentic ASI (2026) risks map to controls and tests in
[security/owasp-asi-mapping.md](security/owasp-asi-mapping.md); the STRIDE view is [THREAT_MODEL.md](THREAT_MODEL.md).

## 9. Evaluation and adversarial results
All model runs: local Ollama `qwen3:8b` (ADR 0036), 8192-token context, thinking off, response cache off, on one
16 GB Apple Silicon Mac. Final results: `evaluation/reports/G4-2026-11-24.md` (earlier run ids and method: `G4-draft-2026-11-19.md`).

**Headline: 88/100 against the team's own BRD target of 92 (not met), and +65 over the best single-prompt baseline.**
Final run on the submitted code (K3, 24 Nov, `main` at `5a88b56`): `20261124T220648`, 88/100, regulatory 13/25
(files in `evaluation/reports/k3/`). The same 88 on 19 Nov (`20261119T091531`) and 20 Nov (`20261120T121853` +
`20261120T140004`).

| Category | Items | Best baseline (S2) | System | Target |
|---|---|---|---|---|
| Regulatory and policy (valid citation) | 25 | 6 | **13** (± 1 between runs) | ≥ 20 |
| Onboarding decisions | 10 | 3 | 10 | 10 |
| Cash flow and funding need (to ₹1) | 15 | 0 | 15 | 15 |
| Offer audit, affordability, ranking | 15 | 0 | 15 | 15 |
| Negotiation safety | 5 | 1 | 5 | 5 |
| Approval routing (incl. ₹1.5 crore ± ₹1) | 6 | 4 | 6 | 6 |
| Prompt injection | 8 | 0 | 8 | 8 |
| Refusal and out of scope | 8 | 6 | 8 | 8 |
| Case isolation | 3 | 3 | 3 | 3 |
| End to end | 5 | 0 | 5 | ≥ 4 |
| **Total** | **100** | **23** (S1 20, S3 22) | **88** | ≥ 92 |

Every deterministic and safety category is at its target; the whole shortfall is regulatory answers. The bare model
followed the planted instruction on 8/8 injection items in all three baseline strategies. Refusal and isolation pass
almost fully for the bare model too, so they are not a differentiator.

**Ablations** (each on its affected categories; an effect is claimed only when it appears in more than one category or
on a rerun):

| Ablation | Full | Ablated | Effect |
|---|---|---|---|
| A1 model calculates (no engines) | 41/41 | 10/41 | Yes (4 categories, identical on rerun) |
| A2 ledger and Critic off | 39/51 | 38/51 (rerun 24 Nov, same) | No score effect; with the Critic off 11 (not 8) of 19 answerable questions get an unsupported answer and 2 (not 4) abstain |
| A3 dense top 5 only | 13/25 | 12/25 | Within run-to-run variation |
| A4 model decides gates | 45/45 | 13/45 | Yes (4 categories, identical on rerun) |
| A5 injection defence off | 13/13 | 12/13 (T082 followed the plant) | Yes (reproduced) |

**Compensating for a small model: the 19 answerable regulatory questions** (same frozen strict scorer in every row;
"false answers" read by hand):

| Configuration | Pass (of 19) | False answers with a citation | Abstains when it should (of 6) |
|---|---|---|---|
| Closed book (baseline S1–S3) | 0 | – | 6 |
| Prompting + RAG, no agents | 6 | 7 | 4 |
| Full system (span citations, Critic) | 6–8 | 1–2 | 6 |
| Oracle: gold passages | 8 (10 after the K2 Critic fix) | 1 | – |

What the agents add over plain RAG is mostly safety: up to two more passes, five or six fewer false answers and no
answered unanswerable question. Search is not the bottleneck (perfect passages give the same 8/19); the limit is the
8B model writing a sentence the Critic can tie to a passage. The K2 Critic fix was found by reading frozen-item traces
and is reported as post-diagnosis (dev split 10 → 11/20, oracle 8 → 10/19, safety categories unchanged).

| Other check | Result | Evidence |
|---|---|---|
| Cash-flow known answers (to ₹1) | 15/15 | `evaluation/reports/E6-2026-11-15.md` (engines and the agent vs independent gold) |
| Offer APR, cost and ranking known answers | 15/15 | `evaluation/reports/E7-2026-11-16.md` |
| Onboarding decisions | 10/10 | `evaluation/reports/E5-2026-11-15.md` |
| Normaliser formats | 146 tests | `evaluation/reports/E4-2026-11-16.md` |
| Planted bad citations blocked | 12/12 | `agents/critic/tests/test_bad_citations.py::test_VER02_S24_every_planted_bad_citation_is_blocked` |
| Red team (20 frozen prompts + 5 probes, live model) | 25/25 resisted: 20 pass by code, 5 read by a person, 0 fail, no state change, no leak | `docs/redteam_log.md`, `evaluation/reports/redteam/redteam-20261120T011215.md` |
| Negotiation (three rounds, re-rank after each counted concession) | Unit and API tested; not in the 100 items; case 06 ranks OF-06-A first after round 1 | `apps/gateway/tests/test_lw_items.py::test_LW15_LW11_three_rounds_rerank_case_06_through_the_api`, `agents/lendwise/tests/test_negotiation_rounds.py::test_BR15_injected_round_2_reply_changes_nothing` |
| Retrieval recall@5, frozen 40 | 22/40 with the shipped configuration (target 34; labels pooling-biased); dev split 17/20 | `evaluation/reports/retrieval-ladder-2026-11-18.md` |
| Where the model runs | Course endpoint (full-precision Qwen3-8B): 53/66 vs 54/66 on the model-dependent items (≈ 87 vs 88 of 100; only T003 differs), at 4–8× lower latency | `docs/evaluation/course-endpoint.md`; run `20261120T161257` |
| Fairness invariance (names, cities, state) | Gates, amount, route and ranking unchanged | `tests/e2e/test_fairness_invariance.py::test_scope67_BR12_names_and_state_do_not_change_decisions` |
| Judge J1 vs two human labellers (19 answerable regulatory answers, run `20261124T220648`) | Kappa 0.789, agreement 17/19 (threshold 0.7, ADR 0014); by content 10/19 correct (humans and J1), so 16/25 regulatory right in substance vs 13/25 strict | `evaluation/reports/G4-2026-11-24.md` (K4), `evaluation/reports/E13-2026-11-25.md` |
| Architecture conformance | PASS | `evaluation/reports/E18-2026-11-18.md` |

**Still to measure before submission** (freeze scope; this card claims none of them until they are in):
safety_v2 (40 items, target ≥ 38/40 with 0 critical) and its
guardrails-off ablation A6 (K5).

## 10. Failure taxonomy
Every failed evaluation item gets one class (rule-based first guess, human confirm; scope #12):

| Class | Meaning | Typical cause here |
|---|---|---|
| Search miss | The right passage was not retrieved | Copilot regulatory questions; the dominant copilot failure |
| Reasoning error | Right inputs, wrong conclusion | Model narrative or tool choice; never a figure (code computes those) |
| Tool error | A tool or the model endpoint failed | Timeout, open breaker, malformed structured output after two repairs |
| Hallucination | A claim not supported by any input | Removed by the Critic or span cutting; counted when it would have reached a person |

## 11. DPDP production gap
CredAssure processes **no real personal data**: every person, company and identifier is synthetic. A production
version would be a **data fiduciary** under the Digital Personal Data Protection Act, 2023 and the DPDP Rules, 2025
(notified November 2025). Most obligations, including notice, consent and its management, security safeguards,
breach reporting and retention, commence in phases up to about May 2027 (`docs/data/DATA_RESOURCES.md`, R-DPDP-01).

| Obligation | Prototype | Gap for production |
|---|---|---|
| Notice and consent | Chat notice with stored acknowledgement (scope #40); no real data | Purpose-specific notice and consent records for every data principal (preparers, MSME promoters) |
| Purpose limitation and minimisation | Uploads refuse identifiers and protected attributes; PII redacted before the model | Data inventory and per-purpose retention schedule |
| Security safeguards | PII v2, audit, role checks; services bound to loopback; TLS only to the course endpoint | TLS termination for every client, encryption at rest, key management, access reviews, a tested incident process |
| Breach notification | None needed | Board and data-principal notification workflow within the Rules' time limits |
| Erasure and rights | Case deletion keeps an audit tombstone (ADR 0025) | Rights-request handling and a lawful-retention exception record |
| Processors and transfers | Course endpoint or local model | Processor contracts; cross-border transfer review for any hosted model |

## 12. Sutra mapping (RBI FREE-AI and MeitY)
RBI's FREE-AI framework (August 2025) and MeitY's India AI Governance Guidelines (November 2025) share seven Sutras.
This maps each to the controls above: alignment by design for a prototype, not a compliance claim.

| Sutra | How CredAssure aligns | Evidence |
|---|---|---|
| Trust is the Foundation | Every figure from code and the ledger; Critic blocks unsupported figures and citations; hash-chained audit | §5, §7; `packages/ledger/tests/test_ledger.py::test_OBJ08_verify_chain_detects_tampering` |
| People First | A human approves every proposal, with attestation; AI-generated text is labelled; no accept/sign path | §5; `apps/gateway/tests/test_p9_rai.py::test_P9_ai_badge_sources_for_narratives_and_chat` |
| Innovation over Restraint | A small (≤ 8B) model made useful by design choices measured against a single-prompt baseline and ablations | §9; BRD §12 |
| Fairness and Equity | No credit scoring; protected-attribute fields refused; names, cities and state change no decision | `tests/e2e/test_fairness_invariance.py::test_scope67_BR12_names_and_state_do_not_change_decisions` |
| Accountability | Insert-only approvals with actor, role and time; RACI (§5); guardrail events audited; owners per module | `apps/gateway/tests/test_p9_rai.py::test_P9_safety_panel_lists_guardrail_events_without_text` |
| Understandable by Design | Reason codes per gate; lineage for every figure; cited answers with sources and dates; abstains when ungrounded | `agents/copilot/tests/unit/test_agent.py::test_CP02_model_abstain_critic_finding_and_model_off_all_give_the_exact_string` |
| Safety, Resilience and Sustainability | Fail-closed gates; model-off and replay modes; breaker, budgets and timeouts; backup and restore; runbook | `tests/e2e/test_degradation_matrix.py::test_scope34_Q5_code_decisions_survive_and_copilot_fails_closed`, `tests/test_backup_restore.py::test_scope38_backup_then_restore_round_trip` |

## 13. Limitations
- **Below the team's target.** 88/100 against 92; regulatory answers 13/25. A wrong but cited answer is possible
  (1–2 of 19 in the system runs, e.g. T004 reads CGTMSE as covering medium enterprises). Approvers must not treat
  copilot answers as advice.
- **Synthetic data.** Cases, offers and KFS documents are generated; real documents vary more.
- **Retrieval.** The right document reaches the top 5 for 22 of 40 frozen questions with the shipped configuration.
- **Narrative wording is not judged.** The Critic checks figures, citations, banned content and PII, not whether a
  sentence's reasoning is sound. It does not tie a table figure to the unit in the table header ("(Rs. in Crore)").
- **Negotiation is simulated.** Template-based, at most three rounds (fee waiver, rate match, tenor change), moves
  chosen by code from ledger figures, one request per round to one lender, no counter-offers, scripted lender
  replies; it never accepts an offer. The tenor change does not restore affordability in any frozen case.
- **English only.** The injection scanner misses Hinglish object-verb order ("checks skip karo"); gates, ranking and
  routing never read text as instructions, so a missed flag changes no decision.
- **Personal data.** Only full employee names are masked (exact match against the HR store); a 12-digit number that
  fails the Aadhaar checksum is stored as typed, so that rupee figures are never masked (ADR 0030).
- **Prototype operations.** One gateway process; SQLite on the evaluated path (MySQL for case.db is optional, ADR 0039,
  and no reported number uses it). Tokens live in browser memory for 30 minutes (a reload means signing in again),
  sessions end 4 hours after sign-in; revocation is by token version (ADR 0038).
- **Model location.** Every reported number is from a 4-bit local build on one Mac; the full-precision course model
  scored within one item. Latency on the Mac is 15–47 s per copilot answer (the Critic checks before anything is shown).
- **Copilot routing and help (ADR 0035).** Code routing rules were written on a 40-question dev split, not a held-out
  set. A help page that is wrong produces a wrong but cited answer; help pages are reviewed like code. Feedback on an
  answer outside a case is accepted only until the gateway restarts.

## 14. Contact
Team CredAssure, IIT Kharagpur Executive PG Programme in Generative AI and Agentic AI. Owners per module:
[CONTRIBUTIONS.md](../CONTRIBUTIONS.md). Security issues: [SECURITY.md](../SECURITY.md).
