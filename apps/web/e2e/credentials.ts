// E2E login. Read from the environment at run time; the password is never logged or written anywhere.
// E2E_USERNAME defaults to the seeded demo preparer (a username, not a secret).
export const E2E_USERNAME = process.env.E2E_USERNAME || 'demo.preparer';

// E2E_PASSWORD: the one fixture password `make e2e-db` gives every user of the throwaway e2e database
// (the app's own accounts each have their own password; ADR 0038).
export function e2ePassword(_username: string = E2E_USERNAME): string {
  const pw = process.env.E2E_PASSWORD;
  if (!pw) throw new Error('Set E2E_PASSWORD (12+ characters), then make e2e-db, to run login tests.');
  return pw;
}

// Written by demo-case.setup.ts (gitignored): the fresh demo case the U1 spec screenshots.
export const DEMO_FILE = require('node:path').join(__dirname, '.demo-case.json') as string;
