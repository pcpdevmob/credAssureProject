# Authentication

**Owner:** Pritish
**Phases:** P8 (SEC), P14 (ADR 0038)
**Status:** JWT + roles + maker-checker + step-up above ₹1.5 cr done (Phases 5, 10a); P14 backend: per-person accounts, user_admin role, staged sign-in, TOTP MFA, password policy, revocation, admin API (#27); **P14 step E (2026-11-20, `feature/web-auth-p14e`):** the web app signs in on the gateway's accounts: code step, temporary-password change, MFA enrolment (password again, QR, backup codes), admin-only accounts, user management and logs on `/v1/admin/users`; walked live with MFA enforced

## Open items
- JWT expiry and refresh, login rate limit, CSP and headers review, upload limits (plan v3.4 §5.3).
- CORS allowlist lacks DELETE (HISTORY "Phase 10b notes", Open).
- Retiring `deploy/auth/` (ADR 0038 step F); role change from the admin screen (API exists, no button yet).
