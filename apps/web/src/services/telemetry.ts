// Browser crash reporting (ARCHITECTURE §8.8). Reports go only to our own gateway (POST /v1/client-errors), which redacts
// and logs them; nothing leaves for a third-party tracker. Signed-in sessions only, at most 10 distinct reports per page load,
// and a failed report is dropped silently so reporting can never cause another error.
import { gw, hasToken } from '@/lib/gateway';
import { ApiProblem } from '@/lib/problem';

export type ErrorKind = 'error' | 'unhandledrejection' | 'render';
const MAX = 10;
const sent = new Set<string>();
const cut = (s: string, n: number) => (s.length > n ? s.slice(0, n) : s);

export function describe(err: unknown): { message: string; stack: string; requestId?: string } {
  if (err instanceof ApiProblem) return { message: `${err.status} ${err.code}`, stack: '', requestId: err.requestId };
  if (err instanceof Error) return { message: `${err.name}: ${err.message}`, stack: err.stack ?? '' };
  return { message: typeof err === 'string' ? err : 'non-Error value thrown', stack: '' };
}

export function reportClientError(kind: ErrorKind, err: unknown, digest?: string): void {
  try {
    if (!hasToken() || sent.size >= MAX) return;
    const d = describe(err);
    const key = `${kind}|${d.message}`;
    if (sent.has(key)) return;
    sent.add(key);
    const page = typeof window === 'undefined' ? '' : window.location.pathname; // no query string: ids and filters stay out
    void gw.POST('/v1/client-errors', { body: {
      kind, message: cut(d.message, 500), stack: cut(d.stack, 4000), page: cut(page, 200),
      ...(d.requestId ? { request_id: d.requestId } : {}), ...(digest ? { digest: cut(digest, 64) } : {}),
    } }).catch(() => undefined);
  } catch { /* reporting must never throw */ }
}

/** Only for tests: forget what this page load has already sent. */
export const resetReports = () => sent.clear();
