// E2E login. Read from the environment at run time; the password is never logged or written anywhere.
// E2E_USERNAME defaults to the seeded demo preparer (a username, not a secret).
export const E2E_USERNAME = process.env.E2E_USERNAME || 'demo.preparer';

// E2E_PASSWORD, else the seed's own rule: SEED_PASSWORD_<USER> (dots → underscores, upper case), then SEED_PASSWORD.
export function e2ePassword(username: string = E2E_USERNAME): string {
  const env = process.env;
  const perUser = env[`SEED_PASSWORD_${username.replace(/\./g, '_').toUpperCase()}`];
  const pw = env.E2E_PASSWORD || perUser || env.SEED_PASSWORD;
  if (!pw) throw new Error('Set E2E_PASSWORD or SEED_PASSWORD to run login tests.');
  return pw;
}

// Written by demo-case.setup.ts (gitignored): the fresh demo case the U1 spec screenshots.
export const DEMO_FILE = require('node:path').join(__dirname, '.demo-case.json') as string;
