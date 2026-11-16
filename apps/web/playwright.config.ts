import { defineConfig } from '@playwright/test';
import { join } from 'node:path';

// Load the repo-root .env at run time if present (never overrides variables already set).
try {
  process.loadEnvFile(join(__dirname, '../../.env')); // relative to this file, not the cwd
} catch {
  /* no .env: rely on the shell environment */
}

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:3000',
    trace: 'off', // a trace would record the typed password and the bearer token
    channel: 'chrome', // the bundled chromium headless shell is incomplete on this machine (U0 notes)
  },
  projects: [
    // Creates a fresh demo case through the live gateway so its facts carry producer {agent, stage, trace_id}.
    { name: 'demo-case', testMatch: /demo-case\.setup\.ts/, timeout: 15 * 60_000 },
    { name: 'u1', testMatch: /u1\.spec\.ts/, dependencies: ['demo-case'] },
  ],
});
