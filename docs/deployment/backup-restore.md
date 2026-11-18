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
Before anything is replaced:
- every file is checked against its MANIFEST hash and `integrity_check`, and `case.db`'s audit hash chain must verify
  (OBJ-08), so a data file edited together with its MANIFEST hash is still refused;
- every live store must be free: the restore takes each one out of WAL mode with no wait, which SQLite refuses while
  another process (a running gateway) has it open. "is in use; stop make run-api first" means nothing was changed.

The current files are then copied to `var/backups/pre-restore-<time>/`, so a restore can be undone with another
`make restore`. Each store is replaced in one step through SQLite's backup API; if a later store fails, the ones already
replaced are put back before the error is shown. Backup folders are owner-only (0700, files 0600): they hold case data
and the audit log.

## Tested
`tests/test_backup_restore.py` takes a backup while a WAL writer is open, changes the database, restores and checks
the rows and the pre-restore copy; a changed backup, a manifest pointing outside the store list and a store held open
by another connection are refused; a failure on the second store puts the first back; backups are owner-only.
