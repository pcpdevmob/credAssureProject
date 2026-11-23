# Ask CredAssure

## What it can help with
Ask CredAssure is the assistant on every page. Open it with the **Ask CredAssure** button at the bottom right. It
answers four kinds of question:

- **Using CredAssure:** screens, uploads, roles, approvals, error messages and how the AI and your data are handled.
  Answers cite this help centre.
- **Rules and schemes:** RBI directions, CGTMSE, GST, the MSMED Act, Udyam, TReDS and bank charges. Answers cite the
  document library.
- **Company policies:** the working-capital policy, the approval matrix and the other internal policies.
- **The open case:** its status, why it is blocked, who it is routed to, and its verified figures. These questions
  work only when a case is open, so one case's data never appears in another conversation.

It answers questions; it never changes anything. If you type a correction ("the buffer should be ₹12 lakh") it tells
you which form on the **Case data** tab to correct, and if you type "approve it" it points to the **Review & approval**
tab: data changes only through the forms, and a decision is recorded only by the routed approver there.

It does not predict approval, score credit, give legal or tax advice, accept or sign an offer, override a gate or show
another case's data. When nothing it can cite supports an answer it says "I can't verify that from the available
sources", which is not an error.

## How answers are made
Code reads your question first. It refuses what the copilot must not do, then decides which source fits: help,
rules, policies or the open case. Only when that is unclear does the language model pick a source from a fixed list,
and code checks its choice. Case status and blockers are written by code from the stored workflow state, so they work
even when the language model is switched off. Every other answer is drafted by the language model from at most five
passages or from the case's verified figures, and then checked by the Verification Critic: each sentence must cite a
passage, every figure must match its source, and banned wording and personal identifiers are blocked. Sentences
that fail are removed. If nothing is left, you get the "can't verify" reply.

## Citations
Each cited source appears under the answer. A help-centre citation opens the help page it came from. A document
citation opens the passage itself, with its document, section, effective date and legal basis.

## Streaming
While it works, the assistant shows what it is doing: routing, retrieving, drafting, checking. The answer text
appears only after the Critic has checked it, so you never see a sentence that is later withdrawn.

## Suggested questions
After each answer the assistant offers up to three follow-up questions. They are fixed questions chosen by code for
the kind of question you asked, never written by the language model, and case questions are offered only inside a
case.

## Conversation memory
Inside a case, the assistant remembers your last few questions and answers in that case so that "and in later
years?" makes sense. Memory belongs to you and that case only: it never crosses cases or people. **New conversation**
stops the earlier turns being shown or used; they are kept, redacted, as evidence. Outside a case nothing is stored.

## Rating an answer
Use the thumbs up or down under an answer and, if you like, pick a reason: wrong, not cited, unclear, unhelpful or
unsafe. Ratings are recorded with the answer's reference, never with free text.
