# Human review list (plan v3.4)

Items accepted provisionally so the build could continue, waiting for a second person. Tick and sign when reviewed.

| # | Item | Accepted as | Why it still needs a review | Who | Status |
|---|---|---|---|---|---|
| H1 | Retrieval dev split labels D01–D20 (`evaluation/retrieval/dev/queries.jsonl`) | Approved by Pritish 2026-11-18 (whole-document labels) | README rule: nobody labels queries for a module they own, and most are bank-charge questions close to LendWise. Reviewer opens each document, confirms it answers the question and narrows to a section where it has headings. Changes after P4 tuning go in `queries.v2.jsonl` and re-run the threshold curve. | Tejas or Abhishek | [ ] |
| H2 | Dev-only unanswerable queries DN01–DN08 (`evaluation/retrieval/dev/unanswerable.jsonl`) | Drafted by Claude 2026-11-18 | Confirm none of them is answerable from the corpus. | Tejas or Abhishek | [ ] |
| H3 | G3 gate tick (`docs/progress/gates.md`) | Ticked on cloud evidence 2026-11-18 | Integration lead confirms; one live-model demo run with a Langfuse trace is still to be recorded. | [Name 1] | [ ] |
| H4 | ADR 0029, 0030, 0031, 0033 | Proposed | Team accepts or amends. | Team | [ ] |
