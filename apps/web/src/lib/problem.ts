// RFC 9457 problem+json → what the UI shows (design-plan §8). openapi.json declares every 4XX/5XX as problem+json (Phase 10,
// scope #51). Never surfaces raw JSON: a field error goes to its field, everything else becomes a banner.

export type FieldError = { field: string; row?: number | null; reason: string };
export type Banner = { what: string; fix: string; requestId?: string };

/** How to fix each stable gateway error code (packages/core errors.py ApiErrorCode; docs/help/error-messages.md). */
export const FIX: Record<string, string> = {
  VALIDATION_FAILED: 'Correct the fields marked below and submit again.',
  UNAUTHENTICATED: 'Sign in again to continue.',
  FORBIDDEN: 'Your role cannot do this. Ask the person this case is routed to.',
  STEP_UP_REQUIRED: 'Enter your password to confirm this approval.',
  REPORT_STALE: 'Ask the preparer to regenerate the report, then approve the new version.',
  ATTESTATION_REQUIRED: 'Tick that you reviewed the Critic findings and the safety events, then approve.',
  NOT_FOUND: 'Check the case ID, or open the case from the cases list.',
  TOOL_NOT_ALLOWED: 'This agent cannot use that tool. Report it to the evaluator.',
  COLLECTION_NOT_ALLOWED: 'This search is not allowed for the case. Rephrase the question.',
  CASE_REQUIRED: 'Open a case first, then try again.',
  CONFLICT: 'Someone changed this case. Reload it and try again.',
  RUN_IN_PROGRESS: 'A run is already in progress. Wait for it to finish.',
  RATE_LIMITED: 'Too many requests. Wait a minute and try again.',
  PAYLOAD_TOO_LARGE: 'The file is over 2 MB. Upload a smaller file.',
  UNSUPPORTED_MEDIA_TYPE: 'Upload a JSON or CSV file (Markdown for KFS documents).',
  NOT_IMPLEMENTED: 'This feature is not available yet.',
  INTERNAL_ERROR: 'Try again. If it keeps happening, tell the evaluator and quote the request ID.',
};
const BY_STATUS: Record<number, string> = { 400: 'VALIDATION_FAILED', 401: 'UNAUTHENTICATED', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'CONFLICT', 413: 'PAYLOAD_TOO_LARGE', 415: 'UNSUPPORTED_MEDIA_TYPE', 422: 'VALIDATION_FAILED', 429: 'RATE_LIMITED' };

export class ApiProblem extends Error {
  constructor(readonly status: number, readonly code: string, readonly banner: Banner, readonly fieldErrors: FieldError[], readonly requestId?: string) {
    super(banner.what);
    this.name = 'ApiProblem';
  }
}

const str = (v: unknown): string | undefined => (typeof v === 'string' && v.trim() ? v.slice(0, 300) : undefined); // capped: server text

/** Build an ApiProblem from a status and whatever body came back (problem+json, FastAPI 422, text or nothing). */
export function toProblem(status: number, body: unknown): ApiProblem {
  const b = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
  const code = str(b.code) ?? (Object.hasOwn(BY_STATUS, status) ? BY_STATUS[status] : 'INTERNAL_ERROR');
  const fieldErrors: FieldError[] = [];
  if (Array.isArray(b.errors)) {
    for (const e of b.errors) if (e && typeof e === 'object' && str((e as FieldError).reason)) {
      const x = e as FieldError; fieldErrors.push({ field: str(x.field) ?? '', row: typeof x.row === 'number' ? x.row : null, reason: x.reason });
    }
  } else if (Array.isArray(b.detail)) { // FastAPI request validation before the problem handler: [{loc, msg}]
    for (const e of b.detail) if (e && typeof e === 'object' && str((e as { msg?: string }).msg)) {
      const loc = (e as { loc?: unknown[] }).loc; fieldErrors.push({ field: Array.isArray(loc) ? String(loc[loc.length - 1]) : '', reason: (e as { msg: string }).msg });
    }
  }
  // 5xx detail is not shown: the server already withholds it, and the generic text is safer.
  const what = (status < 500 && (str(b.detail) ?? str(b.title))) || (status >= 500 ? 'Something went wrong on the server.' : `The request failed (${status}).`);
  // The gateway puts its X-Request-ID in every problem body; it is shown so a user can quote it.
  const requestId = typeof b.request_id === 'string' && /^[0-9a-f]{32}$/.test(b.request_id) ? b.request_id : undefined;
  const fix = Object.hasOwn(FIX, code) ? FIX[code] : FIX.INTERNAL_ERROR;
  return new ApiProblem(status, code, { what, fix, ...(requestId ? { requestId } : {}) }, fieldErrors, requestId);
}

/** Any thrown value → a banner (network errors and plain Errors included). */
export function bannerOf(e: unknown): Banner {
  if (e instanceof ApiProblem) return e.banner;
  if (e instanceof TypeError) return { what: 'Cannot reach the CredAssure service.', fix: 'Check your connection, then try again.' };
  return { what: e instanceof Error && e.message ? e.message : 'Something went wrong.', fix: FIX.INTERNAL_ERROR };
}
