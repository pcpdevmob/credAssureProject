# CredAssure web app — design brief

## Subject, audience, job
- **Subject:** an internal finance-operations tool where an Indian MSME's finance team prepares a working-capital loan proposal and its
  Director or VP of Finance approves it.
- **Audience:** proposal preparers (daily, desktop, detail-heavy), approvers (occasional, often on a phone, need the decision fast),
  evaluators (examiners and mentors inspecting evidence).
- **Primary job:** make every number trustworthy at a glance and every decision traceable. The product's promise is
  "code calculates, a human approves" — the interface must show where each figure came from.

## The one memorable element
**Provenance on every number.** Any amount, rate or date shown can be opened to show its source: engine, inputs, documents or passages,
and the ledger version (lineage endpoint). Spend the design's boldness here; keep everything else quiet and disciplined.

## Constraints from the domain
- Money in Indian grouping (₹1,42,00,000), lakh/crore where the user reads them; tabular figures so columns align; never round silently.
- Gate states (GO, NO_GO, NEEDS_INPUT, ERROR) need unambiguous, colour-independent encoding (shape or text, not colour alone).
- The 26-week cash chart is the centre of the funding view: shortfall weeks, the buffer line and the peak week must read instantly.
- Offer comparison must make an unaffordable "cheapest" offer impossible to miss.
- Approval is internal, not loan acceptance — say so wherever a decision is taken.
- Synthetic data only; never show a field that looks like a real identifier.

## Process (follow before writing any component)
1. Write a design plan in `docs/ui/design-plan.md`: 4–6 named hex colours, one or two typefaces with roles and a type scale,
   a layout concept with ASCII wireframes for the case workspace and the approval screen, and 3–4 principles specific to this brief.
2. Review the plan against this brief. Replace any choice you would have made for any generic dashboard. Avoid these defaults unless
   this brief requires them: cream background with serif display and terracotta accent; near-black with one neon accent; newspaper
   hairline layout; identical rounded cards with soft grey shadows and gradient washes; all-caps eyebrow labels, middle-dot meta strings,
   monospace micro-labels, arrows appended to button text; one accented word in a headline; numbered markers on content that is not a sequence.
   Record what you changed and why.
3. Build to a quality floor without announcing it: responsive to 360 px, visible keyboard focus, reduced motion respected,
   WCAG 2.2 AA contrast, light and dark themes from the same tokens.
4. Motion only to answer a user action (opening provenance, confirming a decision). No entrance animations on every section.
5. Critique with screenshots (Playwright) after each screen; remove one decoration before calling it done.

## Writing
Plain, specific, active voice, sentence case. Name things as users do ("Funding need", not "WC agent output").
Buttons say what happens ("Approve proposal" → toast "Proposal approved"). Errors state what happened and how to fix it, without apology.
Empty states invite the next action ("Upload the order file to start").

## Screen inventory (BRD UI-01..09)
| Screen | Who | Key content |
|---|---|---|
| Sign in | All | Role-aware landing |
| Cases | Preparer | List, status by stage, create case |
| Case workspace | Preparer | Stage tracker (5 gates), current blocker and its one question, next action |
| Upload | Preparer | 7 file slots, schema errors by field, row and reason |
| Funding need | Preparer, approver | 26-week cash chart, peak shortfall, recommendation vs ₹2 crore request, bridge |
| Offers | Preparer, approver | APR, total cost, amount received, flags, affordability, rank; negotiation round and re-audit |
| Ask CredAssure | Case members | Chat with clickable citations, abstentions, refusal messages |
| Approval | Routed approver | Summary, evidence, approve / reject / return to a named stage, comment, step-up confirm |
| Report | Case members | Rendered report with decision history and trace IDs; export Markdown/HTML |
| Audit | Evaluator | Hash-chained log with verification status |
| Evaluation | Evaluator | Runs, scorecard by category, baseline and ablation comparison |
| Help | All | Guides from docs/help, glossary, error-message reference, contextual help links on every screen |
| Provenance drawer | All | Lineage of any number (global component) |
