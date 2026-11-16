# Local development

TODO owner: [Name 1].

## Install
## Run the API
## Run the web app
`make run-ui` starts the Next.js dev server on **http://localhost:3000** (`npm run dev -w apps/web`). The gateway's
default CORS origins include `http://localhost:3000`; use that port so sign-in works. Playwright (`npm run e2e -w apps/web`)
expects the web app on :3000 and the gateway on :8000 (`E2E_BASE_URL`, `E2E_API_URL` override them).
