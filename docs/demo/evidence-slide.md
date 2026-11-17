# Evidence slide — honest numbers (as of 2026-11-17)

All runs below are on the **local** model (Ollama qwen3:8b, thinking off) and the frozen v1 test set (provisional freeze, 2026-11-15).
"Through the API" means the same endpoints the UI uses.

| Area | Result | Target | Status | Source |
|---|---|---|---|---|
| Onboarding decisions | **10/10** | 10 | Met | E5-2026-11-15 |
| Cash-flow / funding need (to ₹1) | **15/15** | 15 | Met | E6-2026-11-15 |
| LendWise offers: audit, affordability, ranking | **15/15** | 15 | Met | E7-2026-11-16 |
| Negotiation safety | **5/5** | 5 | Met | E7-2026-11-16 |
| Prompt injection | **8/8** | 8 | Met | E8-2026-11-16 (live and CI, model off and on) |
| Refusal and out of scope | **8/8** | 8 | Met | E8-2026-11-16 |
| Case isolation | **3/3** | 3 | Met | E8-2026-11-16 |
| Critic: planted bad citations | **12/12** blocked | all | Met | E4-2026-11-16 |
| **Copilot regulatory (valid citation)** | **10/25** | ≥20 | **OPEN** | E8-2026-11-16 §2 |
| **Retrieval recall@5, v1.0 labels** | **24/40** | ≥34 | **OPEN** | E8-2026-11-15 add. 3 |
| Retrieval recall@5, v1.1-silver strict | 35/40 | ≥34 | Not claimed | E8-2026-11-15 add. 2–3 |
| Automated tests | **1,317 passed** (`make check-fast`) + web 109/109 | green | Met | PROGRESS U4 follow-ups, 2026-11-17 |

**Why the copilot is 10/25: it is limited by retrieval, not by answering.** At the copilot's own settings, a gold document reaches the
top 5 for only **10 of the 19** answerable items. Even a perfect answerer would score about **16/25** (10 reachable plus 6 abstentions).
In the live failures, 6 answers were correct but cited a non-gold document, and 2 quoted outdated passages that are not yet tagged superseded (R-CG-C-274,
R-SIDBI-P-008). No unsupported paraphrase was seen: answers share ≥80% of their content words with the cited passage. The frozen items were not tuned against.

**Read the 35/40 with care.** The silver labels were judged by an LLM, only on passages these same 18 configurations returned. That pooling bias makes
recall optimistic by construction. It is useful for comparing configurations, not as a claim. The 24/40 figure dropped from 26
when labels moved to section level. The drop removed document-level inflation and is not a regression. **KR-05 stays OPEN until humans agree with the silver labels (weighted κ ≥ 0.7).**

**Pending, and not shown as done**
- G1-final human checks: the 249-item label sample (κ), the 10-row gold hand check, and the two-person APR transcription matching RBI's 17.07%.
- Graded baseline S1–S3 and every graded run on the **course endpoint** (Qwen3-8B). All numbers here are local.
- G3 (traced real case end to end, as a gate sign-off) and G4 (full 100-item evaluation, ablations A1–A5 measured, red-team log, Docker).
- Copilot fix path: human-checked labels → tag outdated documents `superseded_by` → only then ≤2 answer regenerations.
