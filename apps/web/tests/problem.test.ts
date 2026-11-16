import { describe, expect, it } from 'vitest';
import { ApiProblem, bannerOf, toProblem } from '@/lib/problem';
import { gw, ok } from '@/lib/gateway';
import { server } from './setup';
import { http } from 'msw';
import { API, problem } from '@/mocks/handlers';

describe('RFC 9457 mapper', () => {
  it('maps field errors with row and reason', () => {
    const p = toProblem(422, { code: 'VALIDATION_FAILED', detail: 'The file has errors.', errors: [{ field: 'min_cash_buffer', row: 1, reason: 'required' }] });
    expect(p.fieldErrors).toEqual([{ field: 'min_cash_buffer', row: 1, reason: 'required' }]);
    expect(p.banner).toEqual({ what: 'The file has errors.', fix: 'Correct the fields marked below and submit again.' });
  });
  it('reads FastAPI request-validation bodies', () => {
    expect(toProblem(422, { detail: [{ loc: ['body', 'due_date'], msg: 'Field required' }] }).fieldErrors).toEqual([{ field: 'due_date', reason: 'Field required' }]);
  });
  it('never shows 5xx detail or raw bodies', () => {
    const p = toProblem(500, { detail: 'Traceback (most recent call last)' });
    expect(p.banner.what).toBe('Something went wrong on the server.');
    expect(toProblem(502, '<html>bad gateway</html>').banner.what).toBe('Something went wrong on the server.');
  });
  it('falls back from status when code is missing', () => {
    expect(toProblem(409, {}).code).toBe('CONFLICT');
    expect(toProblem(418, null).banner.what).toBe('The request failed (418).');
  });
  it('turns network failures into a plain banner', () => expect(bannerOf(new TypeError('Failed to fetch')).what).toBe('Cannot reach the CredAssure service.'));
});

it('ok() throws ApiProblem from the runtime problem+json body', async () => {
  server.use(http.get(`${API}/v1/cases`, () => problem(429, 'RATE_LIMITED', 'Slow down.')));
  const err = await ok(gw.GET('/v1/cases')).catch(e => e);
  expect(err).toBeInstanceOf(ApiProblem);
  expect(err.code).toBe('RATE_LIMITED');
  expect(err.banner.fix).toMatch(/Wait a minute/);
});
