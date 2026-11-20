# ADR 0039 — case.db on MySQL for the hosted deployment; SQLite stays where it is needed

Status: Proposed (owner decision 2026-11-20: "use SQLite only where necessary, MySQL otherwise"; needed before the
27 Nov submission) · Date: 2026-11-20 · Amends ADR 0001 (stack: SQLite), ARCHITECTURE §5.1 and §8.3, NFR-09 ·
Scope #22, #29, #38, #49

## Context
The project is deployed for evaluators to test from a link (one VM, ADR 0038 accounts). Every store was a SQLite file.
The owner asked for a server database wherever SQLite is not necessary, so the system of record is not a single file on
the app VM and can later move to a managed service. The model endpoint, not SQLite, limits throughput today (one gateway
process; LLM calls take seconds), so this is about operability and the production path, not speed.

| Store | What it holds | Decision |
|---|---|---|
| case.db | cases, files, stage runs, ledger facts, approvals, users, hash-chained audit, jobs, locks | **MySQL 8** when `CASE_DATABASE_URL` is set; SQLite otherwise |
| hr.db | synthetic HR records, read-only at runtime (ONB-05) | SQLite: opened `mode=ro`, rebuilt from frozen data, never written |
| corpus.db | documents, chunks, FTS5 BM25 index | SQLite: the keyword search is FTS5 `bm25()` (KR-02); read-only at runtime |
| Chroma | vectors | Chroma embedded, read-only at runtime (ADR 0024) |
| LangGraph checkpoints | Supervisor interrupt state | SQLite file `CHECKPOINT_DB` beside MySQL (inside case.db on SQLite, as before) |
| LLM / embedding cache, eval and test DBs | throwaway | SQLite |

MongoDB was considered and rejected: the ledger needs multi-row ACID transactions with the audit event in the same
commit (scope #49), unique keys (fact versions, one run per case) and append-only triggers; the repository layer is
SQLAlchemy, which has no MongoDB dialect. PostgreSQL would serve as well; MySQL was the owner's choice and is offered as
a managed service on both Azure and AWS.

## Decision
1. `CASE_DATABASE_URL=mysql+pymysql://user:pass@host/db` switches case.db to MySQL. `session.case_engine()` accepts a
   path (SQLite) or a URL (MySQL); every caller (gateway, seed, migrate, ingest audit) goes through it. Unset, nothing
   changes: development, the test suite and **the frozen evaluation keep running on SQLite**, so no reported number
   depends on this change.
2. **Same concurrency guarantee.** On SQLite every transaction starts with `BEGIN IMMEDIATE`, which serialises writers;
   several invariants rely on it (audit `seq = max + 1`, case id allocation, last active admin, MFA code spending, job
   claim, run lock). On MySQL every transaction first runs `SELECT id FROM write_lock WHERE id = 1 FOR UPDATE` on a
   one-row table, under READ COMMITTED. Writers queue on that row exactly as they queued on the SQLite write lock, and
   each later statement sees what earlier writers committed. Reads also take the lock (as on SQLite); splitting read and
   write engines is the known next step if read concurrency ever matters. `innodb_lock_wait_timeout` is 30 s.
3. **Same stored values.** DATETIME columns are `DATETIME(6)` (the audit hash covers `ts` with microseconds); JSON and
   TEXT columns are `LONGTEXT` (native JSON would rewrite numbers and key order; TEXT stops at 64 KB); the session time
   zone is UTC. The database must use `utf8mb4_bin` (byte-exact and case-sensitive, like SQLite: `Prep` ≠ `prep`); the
   gateway refuses to start on any other collation.
4. **Same append-only rule.** The initial migration creates the `audit_log`, `ledger_facts` and `approvals` triggers in
   the dialect's syntax (`SIGNAL SQLSTATE '45000'` on MySQL). Managed MySQL may need
   `log_bin_trust_function_creators=ON` for triggers.
5. Migration `f4a9d2c6b813` adds `write_lock` (one row) on both backends so the schema is identical. Migrations run with
   the `no_write_lock` option. corpus.db refuses a MySQL URL (it needs FTS5).
6. LangGraph's checkpointer stays `SqliteSaver` (no first-party MySQL saver); with MySQL it uses its own file and
   `DELETE /v1/cases/{id}` also deletes the case's thread there (ADR 0025).
7. Deployment: a `mysql` Compose profile (MySQL 8.4, internal network only, `utf8mb4_bin`, a named volume), the gateway
   pointed at it by `CASE_DATABASE_URL`; `deploy/scripts/backup-mysql.sh` takes a consistent `mysqldump
   --single-transaction --triggers`. Azure Database for MySQL Flexible Server (B1ms) is the managed alternative.
8. Tests: `CREDASSURE_TEST_MYSQL_URL` makes the ledger and gateway fixtures give each test a fresh MySQL database (a
   copy of a seeded template). CI runs the ledger, gateway and end-to-end tests on a MySQL 8.4 service next to the
   SQLite job. `test_adr0039_backends.py` checks eight concurrent writers keep one unbroken audit chain,
   microsecond timestamps and case-sensitive usernames on whichever backend runs.

## Consequences
- Parity is shown, not assumed: the same suite passes on both, and the parity check runs the five end-to-end cases and
  a three-round negotiation on both backends and compares every ledger fact and gate.
- The evaluation, red-team and harness scripts read case.db with `sqlite3` for state digests; they stay on SQLite.
- `scripts/purge_cases.py` (the `make demo-reset` purge) is SQLite-only: it drops and recreates triggers inside one
  transaction, and MySQL DDL commits implicitly. On MySQL a case is removed with `DELETE /v1/cases/{id}` (ADR 0025).
- Fallback: if MySQL is not green before the deployment, the VM runs on SQLite with no code change (unset the URL).
- `make backup` stays the SQLite backup; on MySQL use `backup-mysql.sh` (or the managed service's backups).
