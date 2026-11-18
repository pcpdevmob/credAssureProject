# ADR 0030 — PII policy: data classes, Presidio behind the existing interface, money never masked

Status: Proposed · Date: 2026-11-18 · Plan v3.4 §4 · Scope #57, #58, #59 · Amends ONB-06 implementation (Phase 6)

## Context
Phase 6 masks Aadhaar (only when the Verhoeff checksum is valid), PAN, IFSC, account, phone and email before every model call, on replies, in logs and traces, and in approver comments; uploads carrying Aadhaar, PAN or account numbers are refused. It does not cover GSTIN, UPI ID, card numbers or Udyam numbers, and there are no data classes.

## Decision
1. **Data classes.** C1 public (corpus) · C2 internal (synthetic policies, prompts) · C3 confidential (case financials, offers, KFS: active case only, ledger references in traces) · C4 restricted (Aadhaar, individual PAN, account/card, mobile, email, UPI ID, DOB, home address: never to the model or traces).
2. **Engine.** Presidio Analyzer **with no NER model** (or the small spaCy model only) plus custom recognisers: GSTIN (check digit), UPI ID (PSP handle list), card (Luhn), Udyam (C3). The existing Aadhaar/PAN/IFSC/account/mobile/email logic is kept or ported. Employee names are matched exactly against hr.db.
3. **Irreversible typed placeholders** (`[PAN]`, `[MOBILE]`). No re-identification vault: the data is synthetic and a vault would be new C4 storage and attack surface.
4. **Money-preservation gate (blocking).** Before Presidio replaces the regex path: rupee figures in every money fixture survive unmasked, the 20,000-number Aadhaar checksum agreement test passes, and `/eval E4` stays READY. Any failure reverts to the regex path.
5. **Fallback.** If Presidio fails to load, the regex path runs and the system fails closed (no storage of the unscanned text).
6. **Exports.** CSV cells starting with `= + - @` are escaped.
7. **Trace-leak test.** Plant every identifier type; search all traces; 0 hits.

## Consequences
- A production version is a DPDP data fiduciary with obligations phasing in to May 2027; the report states this as a production gap, not a compliance claim.
- Presidio adds a dependency; pinned in `uv.lock` and audited like the rest.

## Implementation notes (P3, 2026-11-18)
- Presidio Analyzer 2.2.366 runs **pattern recognisers only** (`nlp_artifacts=None`): no spaCy model is downloaded. If it fails to import or raises, the same regexes and validators run directly (`guardrails/recognisers.py`), so every kind is still scanned.
- Placeholders keep the Phase 6 spelling `[REDACTED_<KIND>]` (typed and irreversible, as decided); renaming to `[PAN]` would change stored text and every caller's tests for no safety gain.
- UPI, GSTIN and Udyam run before the Phase 6 patterns (a UPI ID's digits are not a phone); cards run after them; no kind takes a rupee amount.
- Adding spaCy (a Presidio dependency) moves numpy from 2.5.4 to 2.4.6 in `uv.lock`.
- Built 2026-11-18 (H13): exact-match masking of employee names against hr.db (`guardrails.pii.set_known_names`, loaded by the gateway at startup); kind `EMPLOYEE_NAME`.
