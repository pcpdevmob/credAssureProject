# CredAssure web

Next.js (static export) client for the CredAssure gateway (ADR 0022). No business logic: every figure comes from the API.

- Dev server: `make run-ui` or `npm run dev -w apps/web` → **http://localhost:3000** (the gateway CORS allows :3000).
- Checks: `npm run typecheck -w apps/web`, `npm test -w apps/web`, `npm run build -w apps/web`.
- e2e (own database, never the demo data): `make e2e-db`, then `make run-api-e2e` (:8001) and `make run-ui-e2e` (:3001), then `npm run e2e -w apps/web` (credentials from `E2E_PASSWORD` / `SEED_PASSWORD*`).
- Design and screens: `docs/ui/design-plan.md`.
