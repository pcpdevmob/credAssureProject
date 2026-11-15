# working-capital

Owner: Suresh. Requirements: WC-01..07, BR-01, BR-02, BR-05 (design-detail §2.4.3).

Gate 2 funding need. Code validates the stored case files (Indian-format amounts are normalised at
upload), builds the 26-week cash table, peak shortfall and recommended facility (rounded up to
₹1 lakh), and the bridge from the indicative request. Each figure is a `wc.*` ledger fact with
`source_ref` (file hashes) and `input_hash` (lineage). Any blocker → NEEDS_INPUT with one question.
The model only words the drivers (`wc_explain`); any number that is not a fact → template.

Endpoints (`/v1/agents/working-capital`): `GET /card`, `GET /health`, `POST /cases/{id}/run`,
`GET /cases/{id}/result`, `GET /cases/{id}/cash-table`. Stage runs go through the Supervisor.
This agent calls no other agent, and no path accepts a lender offer.
