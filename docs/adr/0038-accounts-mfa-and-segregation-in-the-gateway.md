# ADR 0038 — Accounts, MFA and segregation of duties in the gateway

Status: Accepted (owner decision 2026-11-19, Pritish: "consolidate in the gateway"; product work beyond the capstone, merged
after the 27 Nov submission) · Date: 2026-11-20 · Extends NFR-07, APR-05, BR-13, UI-07, SUP-08 · Supersedes the bridge
service `deploy/auth/server.py` (retired in the web step of this work) · New IDs AUTH-01…AUTH-10 below

## Context
Identity lived in two places. The gateway had password sign-in (argon2), short JWTs with refresh (H12), four roles,
case scoping, maker-checker and a password step-up above ₹1.5 crore, but users came only from a seed file: no way to
create, disable or re-role a user, no second factor, no password change. A separate stdlib "bridge" service had TOTP MFA,
user administration and cookie sessions, but after sign-in it issued a token for **one shared gateway user per role** and
let a person switch "acting role". Two directors were the same gateway user, so the audit log could not tell people apart,
and one person could prepare a case and approve it under another acting role, which defeats maker-checker (APR-05). The
bridge had no tests and was not in Compose or CI.

## Decision
| ID | Rule |
|---|---|
| AUTH-01 | One gateway user per person. The business role (preparer, director_finance, vp_finance, evaluator) is fixed on the user row and changed only by an admin, audited. No acting-role switch. |
| AUTH-02 | A separate `user_admin` role manages accounts and nothing else. Every case and workflow route refuses it (deny by default in `deps.current_user`); `can_view_case` and `can_decide` are false for it. |
| AUTH-03 | Staged sign-in. A correct password yields a FULL token, or a short stage token: `mfa` (5 min, opens only `/auth/mfa/verify`) or `setup` (10 min, opens only password change, MFA enrolment and `/me`). The response names the steps still due in `next`. |
| AUTH-04 | TOTP (RFC 6238, SHA-1, 30 s, 6 digits, ±1 step) with replay protection (a code must be for a later step than the last one used) and 8 one-time backup codes stored as argon2 hashes. Required for `MFA_REQUIRED_ROLES` (default director_finance, vp_finance, user_admin) whenever MFA is enforced. |
| AUTH-05 | The TOTP secret is sealed at rest with AES-256-GCM under `MFA_ENCRYPTION_KEY`, the user id as associated data. A missing or malformed key fails at startup while MFA is enforced; enrolment without a key answers 503. |
| AUTH-06 | Passwords: argon2id; at least 12 characters, not containing the username, not on a common-password list, not the current one (NIST SP 800-63B style; no composition rules). Admin create and reset give a one-time temporary password that must be changed at the next sign-in. |
| AUTH-07 | Revocation: every token carries the user's `token_version`, re-checked on every request. Sign-out (everywhere), password change or reset, MFA enrolment or reset, role change and disable bump it, so old tokens die at once. |
| AUTH-08 | Admin API `/v1/admin/users` (POST for changes; CORS stays GET/POST): list, create, change role, disable, enable, reset password, reset MFA, account events. An admin cannot change their own role, disable themselves or reset their own MFA; the last active admin can be neither demoted nor disabled (checked in the same transaction as the write). The first admin comes from `make admin NAME=…` (password from `BOOTSTRAP_ADMIN_PASSWORD`), refused when an active admin exists. |
| AUTH-09 | Audit: every account change and failed sign-in of a known user goes into the hash-chained audit log (`case_id` null) as an allow-listed event with allow-listed payload keys (who, whom, role, field names) and never a value of a hash, code, secret or temporary password. |
| AUTH-10 | Step-up above ₹1.5 crore: the password as before, and a current TOTP code (or a backup code) once the approver has MFA. Failures share the per-user limit and are audited. |

Rate limits: 5 failures per minute and 20 per hour per username and IP for passwords, plus 50 per hour per username across
all IPs; 5 per minute and 20 per hour per user for second-factor codes, password change, MFA setup and step-up; a right
answer is refused too while limited. Starting MFA enrolment needs the password again, and enrolment keeps the session's
original sign-in time, so a stolen token alone can neither bind another authenticator nor extend the session. A code is
checked and spent inside one write transaction, so two parallel requests cannot both use it.

MFA enforcement is a setting: on everywhere except `APP_ENV=test` unless `MFA_ENFORCED` says otherwise. The evaluation
scripts (`make eval`, oracle, RAG-only, dev citations, live runs, load smoke; `make redteam` when PR #26
merges) set it off explicitly, so the frozen
evaluation keeps its password-only sign-in and its numbers are unaffected. The demo profile template sets it off for
the seeded users; a real deployment removes that line and sets the key.

## Consequences
- The audit log names the person for every decision; maker-checker holds between people with the same role.
- The web app needs one auth mode against the gateway: a login page that follows `stage`/`next`, an MFA prompt,
  first-sign-in password change and enrolment, Admin → Users on the new API, and no acting-role switch (next step).
- After merge, `make run-api` in the dev profile needs `MFA_ENCRYPTION_KEY` (or `MFA_ENFORCED=false`). Existing users
  keep working: the migration adds the columns with no forced change, no MFA and version 0.
- Tokens stay in browser memory only (no storage, ADR 0004/#52): a reload means signing in again within the 30-minute
  token life. A refresh token in an httpOnly cookie was considered and not taken (it adds CSRF handling).
- Usernames are unique across tenants (sign-in names no tenant); an HR id binds at most one login per tenant.
- **Accepted risk (security review, owner to decide on four-eyes):** a single `user_admin` can, with audit, reset an
  approver's password and MFA and sign in with the temporary password, or create a new approver. AUTH-02 stops the admin
  role itself from touching cases, but not an admin who makes themselves a business user. Next step if wanted: a second
  admin approves role changes into or out of `user_admin` and approver roles, and combined password + MFA resets.
- Accepted (review NITs): the per-username bucket can be used to lock a known user out of password sign-in for up to
  an hour (alerting on it is a follow-up); a backup-code attempt runs up to 8 argon2 checks inside the write
  transaction, bounded by the per-user limits.
- Accepted: a failed sign-in of an existing user writes one audit row, so its timing differs slightly from an unknown
  username (argon2 dominates); TOTP uses SHA-1 because authenticator apps expect it; logout is "everywhere" rather than
  per device.
