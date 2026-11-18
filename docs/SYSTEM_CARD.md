# CredAssure system card

Version 1.0.0 · 2026-11-18 · Plan v3.4 §6, scope #69 · Companion pages: [THREAT_MODEL.md](THREAT_MODEL.md),
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
Measured so far (reports in `evaluation/reports/`):

| Check | Result | Evidence |
|---|---|---|
| Cash-flow known answers (to ₹1) | 15/15 | `evaluation/reports/E6-2026-11-15.md` (engines and the agent vs independent gold) |
| Offer APR, cost and ranking known answers | 15/15 | `evaluation/reports/E7-2026-11-16.md` |
| Onboarding decisions | 10/10 | `evaluation/reports/E5-2026-11-15.md` |
| Normaliser formats | 146 tests | `evaluation/reports/E4-2026-11-16.md` |
| Planted bad citations blocked | 12/12 | `agents/critic/tests/test_bad_citations.py::test_VER02_S24_every_planted_bad_citation_is_blocked` |
| Refusal and isolation through the API | 8/8, 3/3 | `apps/gateway/tests/test_copilot_items.py::test_CP03_SUP08_refusal_8_and_isolation_3_through_the_api` |
| Retrieval recall@5, frozen 40 | 25/40 (target 30; labels pooling-biased) | `evaluation/reports/retrieval-ladder-2026-11-18.md` |
| Fairness invariance (names, cities, state) | Gates, amount, route and ranking unchanged | `tests/e2e/test_fairness_invariance.py::test_scope67_BR12_names_and_state_do_not_change_decisions` |
| Architecture conformance | PASS | `evaluation/reports/E18-2026-11-18.md` |

**Pending the live model run** (Gate G4, P11; needs the Mac with the model): the 100-item score against the best
baseline (`make eval`, `make eval-report` → E13), ablations A1–A6, judge J1 kappa, copilot strict and supported scores,
safety_v2 (≥ 38/40, 0 critical, after a teammate freezes it) and the load smoke (Q6). This card is updated with those
numbers; until then it claims none of them.

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
- **Synthetic data.** Cases, offers and KFS documents are generated; real documents vary more.
- **Copilot accuracy.** Retrieval reaches the right document in the top 5 for 25 of 40 frozen questions; a wrong
  but cited answer is possible. Approvers must not treat copilot answers as advice.
- **Narrative wording is not judged.** The Critic checks figures, citations, banned content and PII, not whether a
  sentence's reasoning is sound.
- **One negotiation round**, fee-waiver template only; simulated lenders.
- **English only**; Hinglish injection text is tested, Hinglish answers are not.
- **Prototype operations:** one gateway, SQLite, 30-minute sessions without refresh.

## 14. Contact
Team CredAssure, IIT Kharagpur Executive PG Programme in Generative AI and Agentic AI. Owners per module:
[CONTRIBUTIONS.md](../CONTRIBUTIONS.md). Security issues: [SECURITY.md](../SECURITY.md).
