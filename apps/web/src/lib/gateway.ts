// The only way the UI talks to the CredAssure gateway: generated client, bearer token held in memory (never localStorage).
import { createClient, type paths } from '@credassure/api-client';
import { API_BASE, AUTH_LIVE } from '@/services/config';
import { http } from '@/services/http';
import { toProblem } from './problem';

let tok: { v: string; exp: number } | null = null;
let actingRole = 'PREPARER';
const GW_ROLE: Record<string, string> = { PREPARER: 'preparer', DIRECTOR_FINANCE: 'director_finance', VP_FINANCE: 'vp_finance', EVALUATOR: 'evaluator' };

export const setToken = (v: string | null, ttlSec = 1500) => { tok = v ? { v, exp: Date.now() + ttlSec * 1000 } : null; };
export const setActingRole = (r: string) => { if (r !== actingRole) tok = null; actingRole = r; };
export const hasToken = () => !!tok && tok.exp > Date.now();

// H12: a separate client with no middleware, so a refresh never recurses through bearer().
const raw = createClient<paths>({ baseUrl: API_BASE });
let refreshing: Promise<void> | null = null;
let refusedFor: string | null = null; // a token the gateway would not renew (session cap): don't ask again
const REFRESH_BEFORE_MS = 5 * 60_000;

/** Gateway sign-in: renew the token while the user is working (any API call in its last 5 minutes). The gateway ends the
 * session JWT_SESSION_MAX_MINUTES after sign-in; a refused refresh just lets the token run out (then sign-in again). */
function refreshSoon(): Promise<void> {
  if (refreshing || !tok || tok.v === refusedFor) return refreshing ?? Promise.resolve();
  const current = tok.v;
  refreshing = raw.POST('/v1/auth/refresh', { headers: { Authorization: `Bearer ${current}` } })
    .then(({ data, response }) => {
      if (!response.ok) { refusedFor = current; return; }
      const d = data as { access_token?: unknown; expires_in?: unknown } | undefined;
      if (typeof d?.access_token === 'string' && typeof d.expires_in === 'number' && tok?.v === current) setToken(d.access_token, d.expires_in);
    })
    .catch(() => undefined)
    .finally(() => { refreshing = null; });
  return refreshing;
}

async function bearer(): Promise<string | null> {
  if (!AUTH_LIVE && tok && tok.exp > Date.now() + 10_000 && tok.exp - Date.now() < REFRESH_BEFORE_MS) await refreshSoon();
  if (tok && tok.exp > Date.now() + 10_000) return tok.v;
  if (!AUTH_LIVE) return null; // gateway mode: login() sets the token
  const j = await http<{ token: string; expiresIn: number }>(`/auth/gateway-token?role=${GW_ROLE[actingRole] ?? 'preparer'}`).catch(() => { throw new Error('Session expired. Please sign in again.'); });
  setToken(j.token, j.expiresIn); return j.token;
}

export const gw = createClient<paths>({ baseUrl: API_BASE });
gw.use({
  async onRequest({ request }) { const t = await bearer(); if (t) request.headers.set('Authorization', `Bearer ${t}`); return request; },
  async onResponse({ request, response }) {
    // A wrong password or code on a sign-in step is an answer, not an ended session: keep the stage token so the
    // user can try again (the gateway rate-limits failures per user).
    if (response.status === 401 && !/\/v1\/auth\/(token|mfa\/verify)$/.test(new URL(request.url).pathname)) {
      tok = null;
      // The token was renewed while the user worked (H12); a 401 now means the session ended: sign in again.
      if (!AUTH_LIVE && typeof window !== 'undefined') window.location.assign('/login/?expired=1');
    }
    return response;
  },
});

/** Unwrap a gateway call: an RFC 9457 problem+json body becomes an ApiProblem (lib/problem.ts). */
export async function ok<T>(p: Promise<{ data?: T; error?: unknown; response: Response }>): Promise<T> {
  const { data, error, response } = await p;
  if (error !== undefined || !response.ok) throw toProblem(response.status, error);
  return data as T;
}
