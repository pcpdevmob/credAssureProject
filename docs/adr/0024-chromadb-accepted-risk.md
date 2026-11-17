# ADR 0024 — chromadb 1.5.9 advisories: accepted risk, embedded mode only

Status: Accepted · Date: 2026-11-16 · Review again at G3 and G4

## Context
`pip-audit` reports four advisories against chromadb 1.5.9: PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814 and
PYSEC-2026-3815 (PROGRESS.md earlier counted 5; 311 is listed twice). `uv lock --upgrade-package chromadb` on 2026-11-16
still resolves 1.5.9: no fixed release exists.

## Decision
Keep chromadb 1.5.9 and accept the risk, because the vulnerable code is not reachable in the mode we run:
- All four advisories are in Chroma's HTTP server and its authorization provider.
- CredAssure opens Chroma only as the embedded, in-process `chromadb.PersistentClient`
  (`packages/retrieval/src/credassure/retrieval/index.py`). No `HttpClient`, no Chroma server process, and no Chroma
  service in `deploy/compose/*.yaml`.
- `tests/test_boundaries.py::test_chroma_runs_embedded_only` fails if a Chroma service or an HTTP client is added.
- `make audit` ignores exactly these four IDs; any new advisory still fails the build.

## Consequences
- At G3 and G4: re-run `uv lock --upgrade-package chromadb`. If a fixed release exists, upgrade, re-run the retrieval tests
  and `make ingest` smoke, and drop the `--ignore-vuln` flags.
- If a Chroma server is ever needed, this ADR is void: keep it on the internal Compose network with no published port and
  re-assess the advisories first.
- Detail and owner: `docs/security/risk-register.md`.

## Re-check (Phase 10b, 2026-11-17)
- `uv lock --upgrade-package chromadb` still resolves **1.5.9**: no fixed release. `make audit` passes with exactly the four
  accepted IDs ignored (pip-audit counts 5 because PYSEC-2026-311 is listed twice).
- **No network listener:** Chroma runs only as the in-process `PersistentClient` on a local directory. No Chroma HTTP server,
  no `chroma run`, no `chromadb.server` / `chromadb.app` import, no Compose service. `tests/test_boundaries.py::
  test_chroma_runs_embedded_only` now also fails on any of those in code, the Makefile, `scripts/` or `deploy/`.
- Next re-check: G3 sign-off, then G4.

