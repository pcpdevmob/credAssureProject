import { defineConfig } from '@playwright/test';
import { join } from 'node:path';

// Load the repo-root .env at run time if present (never overrides variables already set).
try {
  process.loadEnvFile(join(__dirname, '../../.env')); // relative to this file, not the cwd
} catch {
  /* no .env: rely on the shell environment */
}

// E2E runs against its own stack (make e2e-db, run-api-e2e, run-ui-e2e: :8001 + :3001 + var/case-e2e.db),
// so test cases never reach the demo database or its dashboard totals.
// A stale E2E_BASE_URL in the env file once pointed these tests at the demo web app. Refuse :3000 unless asked.
const baseURL = process.env.E2E_BASE_URL || 'http://localhost:3001';
if (new URL(baseURL).port === '3000' && process.env.E2E_ALLOW_DEMO !== '1') {
  throw new Error(`E2E_BASE_URL is ${baseURL}, the demo web app. Use \`make e2e\` (:3001, isolated), or set E2E_ALLOW_DEMO=1.`);
}

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  use: {
    baseURL,
    actionTimeout: 60_000, // a missing control fails in a minute, not at the 30-minute test cap
    trace: 'off', // a trace would record the typed password and the bearer token
    channel: 'chrome', // the bundled chromium headless shell is incomplete on this machine (U0 notes)
  },
  projects: [
    // Creates a fresh demo case through the live gateway so its facts carry producer {agent, stage, trace_id}.
    { name: 'demo-case', testMatch: /demo-case\.setup\.ts/, timeout: 15 * 60_000 },
    { name: 'u1', testMatch: /u1\.spec\.ts/, dependencies: ['demo-case'] },
    { name: 'u3', testMatch: /u3\.spec\.ts/, dependencies: ['demo-case'], timeout: 5 * 60_000 },
    { name: 'u4', testMatch: /u4\.spec\.ts/, dependencies: ['demo-case'], timeout: 5 * 60_000 },
    { name: 'u2', testMatch: /u2\.spec\.ts/ }, // drives its own demo case through the UI
  ],
});
