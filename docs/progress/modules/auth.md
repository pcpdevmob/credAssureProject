# Authentication

**Owner:** Pritish
**Phases:** P8 (SEC), P14 (ADR 0038)
**Status:** JWT + roles + maker-checker + step-up above ₹1.5 cr done (Phases 5, 10a); P14 backend: per-person accounts, user_admin role, staged sign-in, TOTP MFA, password policy, revocation, admin API (branch `feature/auth-p14`)

## Open items
- JWT expiry and refresh, login rate limit, CSP and headers review, upload limits (plan v3.4 §5.3).
- CORS allowlist lacks DELETE (HISTORY "Phase 10b notes", Open).
- P14 web step (login stages, MFA screens, Admin → Users on the gateway) and retiring `deploy/auth/` (ADR 0038).
