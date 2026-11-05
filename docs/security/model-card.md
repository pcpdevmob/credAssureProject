# CredAssure model card

Status: started 2026-11-05. The full card (intended use, models, evaluation results, limitations, ethics) is
completed in Phase 12 (BUILD_SCOPE #3).

## Data provenance
CredAssure's retrieval corpus is built only from public, official Indian sources: RBI, CGTMSE, the Gazette, CBIC and the
GST Council, SIDBI, ministries, courts and banks' published schedules of charges. Company, lender, employee and offer data
is synthetic, made by seeded code.

Collection follows ADR 0020:
- **Scripted fetches:** they honour robots.txt, make at most one request per second and identify the team with a
  contactable User-Agent. A host that blocks or refuses is stopped, and a temporary failure gets exactly one retry after
  24 hours. There are no spoofed headers, headless browsers or CAPTCHA solving.
- **Manual-only hosts:** blocked hosts, hosts whose terms restrict automated access, and RBI, e-Gazette, incometaxindia
  and India Code are downloaded by hand in a browser.
- **Where it runs:** on team members' personal machines and networks.
- **No redistribution:** raw third-party files are never redistributed; only hashes, licence basis and metadata are
  committed.
- **Court judgments:** used only for legal points, never for person-centric features.
- **Ingestion safety:** ingestion is size-limited and text-only (pypdf, no rendering). Rejected files are quarantined.

## To complete in Phase 12
Intended use and users · models and endpoints · evaluation results (BRD §13) · known limitations · refusal policy ·
fairness and safety considerations · contacts.
