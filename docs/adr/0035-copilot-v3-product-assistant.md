# ADR 0035 — Copilot v3: Ask CredAssure as the product assistant on every page

Status: Accepted (user decision 2026-11-18) · Date: 2026-11-18 · Amends ADR 0032 §6 (deferred items) · BRD §8.6 CP-01..03,
§14 · Scope #2, #20 · Requirement tags CP-07, CP-10, CP-11, CP-12 (plan v3.4 numbering)

## Context
The user asked for the copilot to work like a general chat assistant for the product, one stop to get all details, keeping AI
safety, guardrails, responsible AI and PII handling. The copilot (ADR 0032) answered regulatory and policy questions
inside a case only, and plan v3.4 deferred intent routing (CP-07), case-aware tools (CP-10), case memory (CP-11) and
streaming, follow-ups and feedback (CP-12). The model is ≤ 8B and has no verified general knowledge.

User decisions (2026-11-18): answer **product help, the open case's data, and regulations/policies**; **no open-domain
"general knowledge"**; build CP-07, CP-11, CP-12 and a **copilot panel on every page**; build it **now, before G4**,
with frozen sets untouched.

## Decision
1. **Sources.** Four, all cited or code-written: product help (`docs/help/*.md`, team-owned L5), the regulatory library
   (unchanged), company policies (unchanged), and the open case (figures as code-rendered slots, status and blockers as
   code text). There is no uncited, open-domain answer: nothing found means the exact abstention string (CP-02).
2. **Product help as a source.** Indexed in memory at gateway start (`credassure.retrieval.help`): one passage per
   section, ids `HELP-<page>#<slug>`, BM25. No embeddings, no corpus.db change, no re-ingest. The Critic resolves
   `HELP-` ids like corpus ids (VER-02); an unknown id is `VER_BAD_CITATION`. Two new pages: *Ask CredAssure* and
   *AI safety and your data* (the RAI, guardrail and PII answers come from there, worded from the system card).
3. **CP-07 intent routing in code** (`agents/copilot/intent.py`), after the refusal policy and before any model call.
   Code routes when the wording is unambiguous; a question naming a regulator, scheme or tax never goes to help or case
   data. Otherwise the model picks from the fixed tool list (`cp_tool` 1.1.0, six tools) and code validates it.
4. **No case open = no case data.** A case question without a case gets a fixed "open the case" reply with no tool and
   no model call; a model-chosen case tool without a case is invalid; KFS are not searched; a message naming a case id
   is refused (`OTHER_CASE`). With a case, the gateway checks visibility before anything runs (SUP-08).
5. **CP-10 case status** (`get_case_status`): status, stage decisions, route and next step, written by code from stored
   state, Critic-checked, and available with the model off. Figures stay on the slot path; HR detail is never read.
6. **CP-11 memory.** Per user and case, the last `COPILOT_MEMORY_MESSAGES` (default 8) redacted messages since the
   user's last reset. **Reset** appends a marker; nothing is deleted (OBJ-08). Outside a case nothing is stored or
   replayed.
7. **CP-12 streaming.** `POST /v1/copilot/chat/stream` (SSE) sends `stage` events while it works and the answer text
   only **after** the Critic passed it, as `delta` chunks, then one `final` reply. Raw model tokens are never streamed,
   so no withdrawn sentence is ever shown. Follow-ups are a fixed list chosen by code per intent (never model text; case
   questions only inside a case). Feedback is thumbs up/down with a fixed reason code, accepted only from the person
   who received the answer, and recorded as `COPILOT_FEEDBACK` in the audit log.
8. **Every page.** A lazily loaded panel (`components/copilot`): only the button ships with each route. On a case page it
   is scoped to that case; elsewhere, help, rules and policies only. The case tab uses the same conversation component.
   `POST /v1/cases/{id}/chat` is unchanged, so the frozen harness is unaffected.

## Consequences
- 11 of the 25 frozen regulatory questions are now routed by code to `search_regulations` instead of by the model; none
  goes to help or case data (`agents/copilot/tests/unit/test_v3.py::test_CP07_frozen_regulatory_items_never_route_to_help_or_case_data`).
  The live G4 run measures the effect; the frozen items were read, never tuned on.
- The routing rules were written against a 40-question **dev** split (`evaluation/copilot/dev/routing.jsonl`, team
  L5). A held-out routing set is future work; the dev score is not reported as a result.
- `cp_tool` changed version, so recorded replays of it are stale. No replay or demo mode is used (H19 dropped).
- The chat notice text changed (it now names product help), so every user acknowledges it once more (scope #40).
- Help answers are only as good as `docs/help`; a wrong help page gives a wrong but cited answer. Help pages are
  reviewed like code.

## Not built (still deferred)
Full two-call CP-08, A7 guard-model ablation, adaptive red-team round, open-domain answers, token-level streaming.
