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

async function bearer(): Promise<string | null> {
  if (tok && tok.exp > Date.now() + 10_000) return tok.v;
  if (!AUTH_LIVE) return null; // gateway mode: login() sets the token
  const j = await http<{ token: string; expiresIn: number }>(`/auth/gateway-token?role=${GW_ROLE[actingRole] ?? 'preparer'}`).catch(() => { throw new Error('Session expired. Please sign in again.'); });
  setToken(j.token, j.expiresIn); return j.token;
}

export const gw = createClient<paths>({ baseUrl: API_BASE });
gw.use({
  async onRequest({ request }) { const t = await bearer(); if (t) request.headers.set('Authorization', `Bearer ${t}`); return request; },
  async onResponse({ request, response }) {
    if (response.status === 401) {
      tok = null;
      // Gateway sign-in has no refresh endpoint: an expired token means signing in again (bridge mode re-fetches instead).
      if (!AUTH_LIVE && typeof window !== 'undefined' && !request.url.endsWith('/v1/auth/token')) window.location.assign('/login/?expired=1');
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
