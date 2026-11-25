# copilot — Ask CredAssure

Owner: Adesh (retrieval with Tejas; corpus: Tejas and Pritish). Requirements: CP-01..03, BR-15, SUP-08; scope #2, #20, #40 (notice).
Design: design-detail §2.4.6. On demand through chat; never a pipeline stage; never advances or blocks a case.

Pipeline (`agent.py`), all decisions in code:
1. **Refusal policy** (`policy.py`, before any model call): acceptance/signing, approval odds, gate override,
   legal/tax advice, prompt/key probing, another case's ids or offers → fixed reply. Forecasts, foreign rules
   and credit scores/ratings → exactly `I can't verify that from the available sources.` (CP-02).
2. **Injection in chat** (`security.injection.scan`): the instruction is not followed; the reply states the code
   ranking (`lw.ranking`) and sets `injection_flagged`.
3. **Model off** → the exact abstention string (ADR 0003 §2, 9e decision 3).
4. **Tool choice** (`cp_tool`, scope #20): one of `search_regulations`, `search_policies`, `get_case_facts`,
   `explain_blocker`; code validates name and query, else `search_regulations`. case_id and filters are injected
   by the gateway (SUP-08).
5. **Retrieval**: ADR 0019 filters; the case's own KFS by uploaded doc_id + sha; ≤5 passages; injection-flagged
   passages dropped; text and section spotlighted.
6. **Answer** (`cp_answer`): cites `[n]` (code maps to chunk ids); case figures only as `{key}` slots rendered by
   code; then `verify_claims` (citations in force and holding the figures, grounded wording, reasons, PII).
   Any finding, unknown `[n]` or slot, or no citation → abstention.

The gateway stores both turns redacted (`chat_messages`, last 4 turns per user and case as memory), shows a
first-use notice, and records each answer as `cp.answer.<trace_id>` with its chunk ids, so the lineage drawer
opens the real passages. There is no path that accepts, signs or submits a lender offer.
