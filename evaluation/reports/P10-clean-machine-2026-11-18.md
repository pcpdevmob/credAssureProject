# P10 clean-machine run · 2026-11-18

Exit check for plan v3.4 P10 ("clean-machine run from README only"). A fresh `git clone` of `feature/deploy-p10`
into an empty folder, following README §2–§8 only. No `.env`: `JWT_SECRET` (`openssl rand -hex 32`), `SEED_PASSWORD`,
`LLM_ENABLED=false` and `TRACING_ENABLED=false` were exported instead, as README §3 allows. Linux cloud workspace,
Python 3.12 via uv, Node 22. Script and full log were kept outside the repository.

| Step (README) | Command | Result |
|---|---|---|
| §4 install | `make install` | PASS |
| §4 install | `npm ci` | PASS (first run used `npm install`, which rewrote `package-lock.json`; README now says `npm ci`) |
| §6 data | `make hr-db` | PASS: 20 profiles |
| §6 data | `make db` | PASS: 25 users seeded |
| §6 corpus | `make ingest` | SKIPPED: raw corpus files are gitignored (L3/L4); `make corpus-download` needs a personal network (ADR 0020) |
| §7 run | `make run-api` with the model off; `GET /v1/health/ready`; login as `demo.preparer` | PASS: `status ok`, `model disabled`; token issued |
| Ops | `make restore` while the API is running | PASS: refused, nothing changed |
| Ops | `make demo-reset` | PASS: demo, blocked and question cases recreated |
| §8 tests | `tests/e2e/test_demo_case.py` (FakeLLM and model off) | PASS: 2 passed |
| Ops | `make backup`, then `make restore FROM=...` | PASS: case.db and corpus.db backed up, restored, pre-restore copy kept |
| §8 web | `npm run build -w apps/web` | NOT RUN HERE: the workspace cannot reach Google Fonts (`next/font`); CI builds it (web job) |
| Release | `make sbom`, `make release VERSION=1.0.0` | PASS: 707 components; RELEASE.json with 6 hashes and 10 reports; no Docker daemon, recorded as such |
| Hygiene | `git status` after the run | PASS: clean |
| §8 tests | `make check-fast` | First run: 2 failures in `test_copilot_items.py`. Cause: `make db` creates an empty `corpus.db`, and the tests skipped only when the file was missing. Fixed: they now skip unless the corpus has chunks. Re-run of that file in the clean clone: 5 passed, 4 skipped |

Not covered here (needs the Mac): the live model path (`MODELS=local` with Ollama), `make ingest`, the web build with
fonts, Docker Compose (`make up`), Lighthouse and the Playwright e2e run. Those are in `docs/plan/human-review.md`
(H15, H16, H17) and the P11 live runs.
