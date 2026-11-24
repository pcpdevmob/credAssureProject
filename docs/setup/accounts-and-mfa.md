# Accounts and two-step verification (ADR 0038)

How to run the full app with real accounts and authenticator-app codes, on the evaluated path (`make run-api` +
`make run-ui`). Works with any model profile (`MODELS=local`, `course` or, from 23 Nov, `hf`). The frozen evaluation and
the red-team runner always sign in with a password only, so none of this changes a reported number.

## One-time setup (in `.env`, never committed)
1. Turn MFA on and give the gateway a key to seal TOTP secrets:
   ```
   MFA_ENFORCED=true
   MFA_ENCRYPTION_KEY=<output of: python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())">
   ```
   Keep the key: if it changes, every enrolled user must be reset by an admin. `MFA_REQUIRED_ROLES` defaults to
   `director_finance,vp_finance,user_admin`; preparers and evaluators sign in with a password only.
2. Accounts: `make db` (or `make start` on its first run) gives every account its own random first password, in
   `var/initial-passwords.txt` (readable only by you; hand each one out, then delete the file). Each is changed at
   first sign-in. `make passwords` issues new ones for every seeded account (signs them out; MFA stays set up).
   `SEED_PASSWORD_<USERNAME>` in `.env` sets one account's own password instead (never shared between accounts).
   Demo cases (optional): `SEED_PASSWORD_DEMO_PREPARER` in `.env`, then `make demo-reset`.
3. First user administrator (once per tenant; the password must not contain the username):
   `BOOTSTRAP_ADMIN_PASSWORD='<12+ characters>' make admin NAME=it.admin`

## Run
```
make run-api MODELS=course     # or MODELS=local
make run-ui                    # http://localhost:3000
```
Tokens live only in the browser's memory: a page reload or a typed URL means signing in again (by design).

## What to test
| Who | Steps | Expected |
|---|---|---|
| `demo.director` (or `demo.vp`) | Sign in with its first password → set an own password → confirm password → scan the QR with Google/Microsoft Authenticator → type the code | 8 backup codes shown once; then the dashboard, "MFA on" in the sidebar |
| same | Sign out → sign in → wrong code `000000` | "That code did not work…", still on the code step |
| same | Right code (or one backup code, `xxxx-xxxx`) | Dashboard; approve a routed case (Review & approval) |
| `demo.vp` | Approve a case above ₹1.5 crore (e.g. CA-2026-0018) | Asks for your password **and** a code from the app (AUTH-10); wrong code refused, right code approves |
| `it.admin` | Sign in with the bootstrap password | Must set an own password, then enrol MFA; sees only User management, User logs, Help |
| `it.admin` | Add user (role Evaluator or Director), Reset MFA, Disable/Enable | Temporary password shown once; every change listed in User logs (IST) |
| new user | Sign in with the temporary password | Must change it; approvers then enrol MFA |

One login per HR profile: the seeded preparers already hold every HR id in the synthetic data, so a new preparer
account needs a new HR record. Five failed codes a minute (20 an hour) per user are refused with "too many attempts".
Lost phone: a backup code signs in once; an admin's "Reset MFA" makes the user enrol again.
