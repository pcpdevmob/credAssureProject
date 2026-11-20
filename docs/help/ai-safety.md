# AI safety and your data

## What the AI does and does not decide
The design rule is: the AI reads, explains and drafts; code calculates, routes and gates; a person approves. Gate
decisions, the funding need, APR, the offer ranking and the approval route are all calculated by code. The language
model drafts explanations from verified figures, extracts charges from one Key Facts Statement at a time (code
checks the quoted text), picks a copilot source from a fixed list and writes cited answers. Text marked
**AI-generated draft** was written by the language model and checked by the Verification Critic.

## Who decides
Only the routed approver can approve, reject or return a proposal, and the person who prepared a case can never
approve it. Approving above ₹1.5 crore asks the VP to confirm their password again. Before approving, the approver
confirms they have reviewed the Critic findings and safety events. Approval is internal, not loan acceptance: the
MSME chooses its lender outside CredAssure, and no part of CredAssure can accept, sign or submit an offer.

## Guardrails
Five guardrail layers protect every request.

- **Input:** uploads and chat are checked for personal identifiers, protected attributes and text that looks like
  an instruction.
- **Retrieval:** only current Indian sources for the home state and the case's own lender documents are searched;
  passages are marked as data before the model sees them, and long excerpts are capped.
- **Tools:** each agent may use only its own listed tools, and a repeated identical call is stopped.
- **Output:** the Verification Critic checks every figure, citation and phrase, and removes or blocks what it cannot
  verify.
- **Telemetry:** identifiers are masked before anything reaches logs or traces.

Every block, redaction and flag is recorded in the audit log and shown, as a code without the text, on the
approver's safety panel.

## Prompt injection
Documents, lender replies and chat messages are treated as data, never as instructions. A line such as "rank this
lender first" in a document is flagged and ignored, and the ranking stays the one code calculated. The language model
never chooses a gate, a figure, a route or a ranking, so injected text has nothing to change.

## Personal data
CredAssure runs on synthetic data only: every person, company and identifier in it is invented. Please do not type
Aadhaar, PAN, bank account, card, UPI or GSTIN numbers into the chat or into files. Identifiers in a chat message are
removed before the question is stored, traced or sent to the language model, and the reply tells you which kinds
were removed. Uploads that contain identifiers are refused. Rupee amounts are never masked, so figures stay exact.

## What is stored
Inside a case, your questions and the answers are stored redacted, with the sources they cited, so that every answer
can be traced. Outside a case, questions are not stored; only a redacted trace is kept for troubleshooting. Deleting
a case removes its content and keeps an audit tombstone that records the deletion.

## When the language model is off
If the language model is unavailable or switched off, every gate, calculation, routing step and approval still
works. Narratives use fixed templates, and the assistant still answers case status and blocker questions from code;
other questions get the "can't verify" reply.

## Limits
This is a capstone prototype. The copilot can cite the wrong passage for a correct-looking answer, so approvers must
not treat its answers as advice. The Critic checks figures, citations, wording and identifiers, not whether a
sentence's reasoning is sound. It works in English only.
