# ADR 0020: Data-acquisition policy

Status: Accepted · 2026-11-05 · approved by the project owner · Scope #14 · KR-01, NFR-07 · Builds on ADR 0019 (corpus scope)

## Context
The real corpus (ADR 0019) is collected from public websites, partly by script and partly by hand. This ADR is the single
policy for how that collection is done and the controls that enforce it. The code is in `data/generators/src/credassure/datagen/`
(`corpus.py`, `harvest.py`, `common.py`).

## Decision

### What we collect
- Public, official Indian sources only: regulators, ministries, the Gazette, statutory bodies, courts, banks' and NBFCs'
  published schedules of charges. No foreign documents, no logged-in or paywalled content, no personal data.
- Raw L3/L4 files are never redistributed. `data/corpus/raw/`, `text/` and `quarantine/` are gitignored. Only
  `manifest.yaml`, `manifest.lock.json` (hashes, status, legal basis) and the generated indexes are committed.

### How scripts fetch
All network access goes through one `Gate`:
- **Respect the site:** robots.txt is honoured (matched on the product token `CredAssure-capstone`). If robots.txt
  can't be fetched (5xx or a block), the site is treated as disallowed.
- **Pace:** one request per second, including the robots.txt fetch and each form page.
- **Identify ourselves:** the User-Agent always names the product and purpose, and adds a contact when one is configured
  (amended 2026-11-06; contact is optional):
  - `CORPUS_CONTACT_EMAIL` set: `CredAssure-capstone/1.0 (IIT KGP academic project; contact: <email>)`;
  - else `CORPUS_CONTACT_URL` set: `CredAssure-capstone/1.0 (IIT KGP academic project; +<url>)`;
  - else: `CredAssure-capstone/1.0 (IIT KGP academic project)`.

  Both values come from settings (`.env`), never hard-coded. A value that is set but malformed (not an email, not an
  http(s) URL) stops the run, so a typo is never sent. The product token for robots.txt matching is unchanged.
- **Stop on a block:** 403, 418, 429, 444 or a bot-challenge page stops that host for the rest of the run, and its
  documents move to `MANUAL_DOWNLOADS.md`. These hosts are never retried.
- **One retry only:** a 502/503/504 or a connection error gets exactly one retry, no sooner than 24 hours later. The
  outcome is recorded in the lock as `host:<name>`.
- **Manual hosts:** blocked hosts, and RBI, e-Gazette, incometaxindia and India Code, are downloaded by a person in a
  browser and imported with `make corpus-import`.
- **Never:** spoofed or rotated headers, headless or automated browsers, CAPTCHA solving, proxy rotation, or working
  around a block in any other way.

### Terms of use
- `manifest.yaml` keeps a `hosts:` map: `terms_url`, `terms_note` (does it allow automated access? any reuse limits?) and
  `automated_access: allowed | restricted | unknown`.
- A `restricted` host is never requested by script. Its documents move to manual.
- Hosts whose terms nobody has recorded yet are listed in `MANUAL_DOWNLOADS.md` for owners to check. The audit warns
  until they are filled in.

### Who runs it, and where
- From team members' personal machines and personal networks, never from an employer's network or equipment. Each
  network run prints this notice.
- Preferably inside the hardened `corpus` container: `make corpus-docker-download`, `-import`, `-status`, and the
  Phase 7 `make ingest`. The container runs non-root with a read-only root filesystem, no Linux capabilities, no new
  privileges and memory/CPU limits; only `data/corpus` is writable.

### Court judgments (source 15)
Used for legal points only: how courts read the MSMED Act, delayed-payment interest, Facilitation Councils. No
person-centric features: no extraction or indexing of party names as entities, no profiling, no search by person.
Judgments are L2 (Copyright Act s.52(1)(q)(iv)).

### Ingestion safety
- **Size:** at most 20 MB per file. A script download is streamed and abandoned past the limit
  (`rejected_too_large`, nothing stored). The same limit applies to files imported by hand.
- **Text extraction:** pypdf only, at most 500 pages, with no rendering, no OCR and no external converters. HTML is
  parsed with the standard-library parser, and scripts and styles are dropped.
- **Quarantine:** files rejected for having no text layer are kept in `data/corpus/quarantine/` for the audit trail and
  are never parsed again.
- **Data, not instructions:** retrieved text is data. Injection scanning and spotlighting happen at ingest
  (Phase 7, BR-15).

## Consequences
- Some sources stay manual. The corpus grows more slowly than an unrestricted crawl would, and `make corpus-status`
  shows the gap honestly.
- Every scripted request is attributable to the team through the contact address.
- The policy summary is in `docs/security/model-card.md` ("Data provenance").
