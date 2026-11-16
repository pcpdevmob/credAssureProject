# Risk register

TODO owner: Abhishek.

See the OWASP table in docs/adr/0002-threat-model.md.

## Accepted dependency advisories
| Advisory | Package | Why it is not reachable | Review |
|---|---|---|---|
| PYSEC-2026-311, PYSEC-2026-3813, PYSEC-2026-3814, PYSEC-2026-3815 | chromadb 1.5.9 (no fixed release on 2026-11-14, rechecked 2026-11-16; ADR 0024) | All four are in Chroma's HTTP server and authorization provider. CredAssure never runs that server: retrieval opens Chroma only as the embedded, in-process `PersistentClient` (`packages/retrieval/.../index.py` `open_chroma`), and neither `deploy/compose/compose.yaml` nor `langfuse.yaml` defines a Chroma service (checked 2026-11-14). `tests/test_boundaries.py::test_chroma_runs_embedded_only` fails if a Chroma service or an HTTP client is added. If a server is ever needed, keep it on the internal Compose network with no published port, and re-assess these advisories first. | Upgrade chromadb as soon as a fixed release exists, then drop the `--ignore-vuln` flags in the Makefile `audit` target. |
