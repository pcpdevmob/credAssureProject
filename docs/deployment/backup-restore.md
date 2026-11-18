# Backup and restore

Scope #38. Script: `scripts/backup_db.py` (called by `make backup` / `make restore`). Tests: `tests/test_backup_restore.py`.

| Store | Backed up | How it comes back otherwise |
|---|---|---|
| `var/case.db` (cases, ledger facts, append-only audit, approvals) | yes | — |
| `var/corpus.db` (ingested library, FTS5) | yes | `make ingest` (slow) |
| `var/llm_cache.db` (recorded model replies; the REPLAY_MODE source) | yes | a fresh live rehearsal |
| `data/frozen/v1/hr.db` | no | `make hr-db` from the frozen profiles |
| `var/chroma/` | no | `make ingest` |

## backup
```bash
make backup          # var/backups/<UTC time>/{case.db,corpus.db,llm_cache.db,MANIFEST.json}
```
It uses SQLite's online backup API, so it is safe while `make run-api` is running. Each copy passes
`PRAGMA integrity_check` and its SHA-256 goes into `MANIFEST.json`. `var/` is gitignored: copy the folder off the machine
if it matters.

## restore
```bash
# stop make run-api first
make restore FROM=var/backups/20261118T101500Z
```
Before anything is replaced, every file is checked against its MANIFEST hash and `integrity_check`. A missing, changed
or corrupt file stops the restore with nothing changed. The current files are copied to
`var/backups/pre-restore-<time>/` first, so a restore can be undone with another `make restore`. Stale `-wal`/`-shm`
files are removed so they cannot replay over the restored database. After a restore, open any case as the evaluator:
the audit tab's **Hash chain verified** badge confirms the restored audit log is intact.

## Tested
`tests/test_backup_restore.py` takes a backup while a WAL writer is open, changes the database, restores and checks
the rows and the pre-restore copy; a tampered backup and a manifest pointing outside the store list are refused.
