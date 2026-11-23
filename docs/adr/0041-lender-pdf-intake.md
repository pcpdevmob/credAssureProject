# ADR 0041 — Lender PDFs: text-layer intake, AI-suggested offer fields, human review before saving

Status: Accepted (owner decision 2026-11-20: "KFS + offer letters via AI") · Date: 2026-11-20 · Amends ADR 0040 ("PDF: not
now"), BRD Q-08 and §4.3 (uploads) for lender documents only · Requirements UI-02, API-01, LW-01, LW-04, BR-05, BR-15,
NFR-07, OBJ-08

## Context
Lenders send offer letters, Key Facts Statements and schedules of charges as PDFs. The non-technical preparer could only
add them as offer JSON and KFS Markdown (or the Excel `offers` sheet). The owner asked for PDF upload before the code
freeze, with the 88/100 evaluation path left untouched. Bank statements were not chosen: they need a design of their own.

## Decision
1. **Input side only.** Nothing here changes an agent, the Critic, an engine, retrieval, the evaluation or any prompt they
   use. A PDF becomes the same offer JSON or KFS document a person could upload, stored through `store_upload` (the
   single upload path: validation, PII refusal, injection scan, audit). The stored records have the existing shapes.
2. `POST /v1/cases/{id}/pdf?doc=offer|kfs|schedule` (case preparer; same lock and run checks as an upload; 2 MB cap;
   `.pdf` only) reads the **text layer** with pypdf (≤ 40 pages). No OCR: an encrypted, damaged or scanned PDF is refused
   with a plain reason (BRD §4.3). Personal identifiers are redacted from the text (NFR-07). **Nothing is stored**; the
   response is the text and a draft. Audit `PDF_DRAFTED` records the document kind, file hash, whether the model was
   used and how many values it suggested or had dropped (counts only, never text) (OBJ-08).
3. **The model quotes, code reads.** For an offer letter (`intake_offer_quotes` 1.0.0) or a schedule of charges
   (`intake_schedule_rows` 1.0.0), the spotlighted text (BR-15) goes to the model, which returns only *quotes* per field.
   Code keeps a quote only if it appears in the PDF text, and reads the value from it with the VER-01 normaliser
   (exactly one money / rate / date / number in the quote, else dropped). The model never supplies a number (BR-05).
   With the model off or failing, the draft is empty and the person types the fields (`LLM_ENABLED=false` still works).
4. **A person checks every field.** The web form shows each suggested value with the words it was found in, marks fields
   not found, lists material terms left blank ("will be marked not comparable", LW-02, BR-06) and saves only after the
   person ticks "I checked every field against the lender's PDF". Absent fees are a missing term unless the person says
   the letter has no fees.
5. A **KFS** needs no model: its text is the KFS document body. A **schedule of charges** is saved via
   `POST /v1/cases/{id}/kfs-document` as `<kfs_doc_id>-SCH`: the reviewed rows become the `| name | timing | amount |`
   table LendWise already parses (LW-04); the PDF text follows as data with every `|` neutralised so PDF text can never
   become a charge row. Offer, KFS and schedule ids are generated so they always match.
6. The intake prompts live in `apps/gateway` and are referenced by no agent, package or evaluation code (a test checks).

## Consequences
- The comparison prices a schedule saved from a PDF exactly like a typed one (test: the hidden-charge cost changes by the
  exact rupee amount). The evaluation inputs are frozen files, so the 88/100 path does not read any PDF.
- Two new model calls exist on the data-entry side, counted against the same budget; a wrong suggestion is caught by the
  quote check or the person, never stored without review.
- Scanned PDFs, bank statements and case data in PDF stay out of scope (Excel template or forms instead).
