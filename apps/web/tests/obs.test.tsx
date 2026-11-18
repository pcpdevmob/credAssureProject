// Observability: request ID on banners, crash screen, browser error reports (ARCHITECTURE §8.8, §8.10).
import { afterEach, describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';
import { toProblem } from '@/lib/problem';
import { setToken } from '@/lib/gateway';
import { reportClientError, resetReports } from '@/services/telemetry';
import ErrorBanner from '@/components/ErrorBanner';
import CrashScreen from '@/components/CrashScreen';

const RID = '0123456789abcdef0123456789abcdef';
afterEach(() => { setToken(null); resetReports(); });

describe('request ID', () => {
  it('is read from the problem body and shown on the banner', () => {
    const p = toProblem(500, { code: 'INTERNAL_ERROR', status: 500, request_id: RID });
    expect(p.requestId).toBe(RID);
    render(<ErrorBanner error={p} />);
    expect(screen.getByText(RID)).toBeTruthy();
  });
  it('ignores anything that is not a request ID', () => {
    expect(toProblem(500, { request_id: '<script>' }).requestId).toBeUndefined();
  });
});

describe('client error reports', () => {
  it('sends one redacted-shape report per distinct error, only when signed in', async () => {
    const bodies: Record<string, unknown>[] = [];
    server.use(http.post(`${API}/v1/client-errors`, async ({ request }) => { bodies.push(await request.json() as Record<string, unknown>); return new HttpResponse(null, { status: 204 }); }));
    reportClientError('error', new Error('before login'));
    setToken('t');
    reportClientError('error', new TypeError('x is undefined'));
    reportClientError('error', new TypeError('x is undefined')); // duplicate: dropped
    reportClientError('render', toProblem(500, { request_id: RID }));
    await waitFor(() => expect(bodies).toHaveLength(2));
    expect(bodies[0].message).toBe('TypeError: x is undefined');
    expect(String(bodies[0].page)).not.toContain('?');
    expect(bodies[1]).toMatchObject({ kind: 'render', message: '500 INTERNAL_ERROR', request_id: RID });
  });
  it('never throws when the report fails', () => {
    server.use(http.post(`${API}/v1/client-errors`, () => HttpResponse.error()));
    setToken('t');
    expect(() => reportClientError('error', new Error('boom'))).not.toThrow();
  });
});

describe('crash screen', () => {
  it('shows plain words, the reference and a retry, never the stack', () => {
    const err = Object.assign(new Error('secret internals'), { digest: 'abc123' });
    render(<CrashScreen error={err} reset={() => undefined} />);
    expect(screen.getByRole('heading', { name: 'This page stopped working' })).toBeTruthy();
    expect(screen.getByText('abc123')).toBeTruthy();
    expect(screen.queryByText(/secret internals/)).toBeNull();
    expect(screen.getByRole('button', { name: /Try again/ })).toBeTruthy();
  });
});
