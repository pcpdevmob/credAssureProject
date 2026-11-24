# Evidence slide — honest numbers (as of 2026-11-20)

All runs are on the **local** model (Ollama qwen3:8b, 8192 context, thinking off, response cache off; ADR 0036) and the frozen
v1 test set. "Through the API" means the same endpoints the UI uses. Full write-up with run ids:
`evaluation/reports/G4-draft-2026-11-19.md`; system card §9.

**88/100, against 23/100 for the best single prompt on the same model (S2). The team's own target of 92 is not met.**

| Area | Best single prompt (S2) | CredAssure | Target | Status |
|---|---|---|---|---|
| Onboarding decisions | 3/10 | **10/10** | 10 | Met |
| Cash flow / funding need (to ₹1) | 0/15 | **15/15** | 15 | Met |
| Offers: audit, affordability, ranking | 0/15 | **15/15** | 15 | Met |
| Negotiation safety | 1/5 | **5/5** | 5 | Met |
| Approval routing (incl. ₹1.5 crore ± ₹1) | 4/6 | **6/6** | 6 | Met |
| Prompt injection | 0/8 (followed 8/8) | **8/8** | 8 | Met |
| Refusal and out of scope | 6/8 | **8/8** | 8 | Met |
| Case isolation | 3/3 | **3/3** | 3 | Met |
| End to end | 0/5 | **5/5** | ≥ 4 | Met |
| **Regulatory (valid citation)** | 6/25 | **13/25** (± 1) | ≥ 20 | **Not met** |
| **Total** | **23** | **88** | ≥ 92 | **Not met** |

| Also measured | Result |
|---|---|
| Ablations | Model calculates (A1): 41/41 → 10/41. Model decides gates (A4): 45/45 → 13/45. Injection defence off (A5): T082 follows the plant. Ledger + Critic off (A2) and dense-only search (A3): no measurable change on these scorers |
| Regulatory, 19 answerable questions | No documents 0 · RAG without agents 6 (**7 false answers**) · CredAssure 6–8 (**1–2 false**) · gold passages 8, 10 after the Critic fix |
| Red team (20 frozen prompts + 5 probes, live) | **25/25 resisted**, no state change, no leak |
| Retrieval recall@5 (frozen 40) | 22/40 with the shipped configuration (target 34); dev split 17/20 |
| Course endpoint (full-precision Qwen3-8B) | Within one item (≈ 87), 4–8× lower latency |
| Negotiation | Three rounds, re-rank after each counted concession; unit and API tested (not in the 100) |

**Why regulatory stops at 13/25.** Search is not the bottleneck: with the gold passages handed over, the system gets the same 8 of 19.
The limit is the 8B model writing a sentence that covers the key fact and that the Critic can tie to a passage. The Critic gives up
some correct answers to keep unsupported claims near zero; what the agents add over plain RAG is mostly safety (5–6 fewer false answers).

**Pending before submission (not shown as done):** final full run on the merged code (expected 88 ± 1), judge J1 agreement with
human labels (kappa), safety_v2 (40 items) and its guardrails-off ablation A6.
