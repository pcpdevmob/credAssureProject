# ADR 0022 — Web UI is the finbridge Next.js app, API-only

Status: Accepted · Date: 2026-11-14 · Amends ADR 0005 (Vite → Next.js static export); closes the open decision in ADR 0003

## Decision
`apps/web` is the `SureN8088/finbridge` front-end (Next.js 14 static export, Tailwind) instead of the Vite stub.
- Every call goes through `@credassure/api-client` (`createClient`) in `src/lib/gateway.ts`. The bearer token is held in memory only.
- Removed from the import: `lib/calc.ts` (browser maths), the localStorage mock DB, mock data and self sign-up. The UI computes nothing (BR-05, ADR 0004); it maps gateway payloads to view types in `src/services/*`.
- Auth: `NEXT_PUBLIC_AUTH_MODE=gateway` (default) signs in with a gateway account. `bridge` keeps the finbridge auth service (password + TOTP MFA); after a full session it issues a 15-minute gateway JWT at `GET /api/auth/gateway-token`, signed with the shared `JWT_SECRET`, for the gateway user mapped to the acting role (`FB_GATEWAY_USERS`). The gateway still re-checks the user row per request.

## Consequences / open items
- Bridge risk: the auth host holds the JWT secret, and an admin who can act as several roles can use distinct gateway users for preparer and approver. The maker-checker rule is enforced per gateway user, not per human. Review with `security-reviewer` before enabling bridge mode.
- Gateway gaps the UI shows as "not available yet": 26-week cash table (501, Phase 9b), offers (empty, Phase 9c), per-rule readiness table (9a), global audit list, document list, fact lineage, user admin.
- The landing page still carries illustrative marketing figures (₹1.74 Cr, lender names); replace with BRD Appendix A figures or remove.
- Typed responses: `openapi.json` declares most responses as free-form objects, so the services cast. Typing them is a gateway task.
