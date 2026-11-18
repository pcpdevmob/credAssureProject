// H12: the web app renews the gateway token while the user works, never after it expired.
import { afterEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';
import { gw, setToken } from '@/lib/gateway';

afterEach(() => setToken(null));

function capture() {
  const seen: { me: string[]; refresh: string[] } = { me: [], refresh: [] };
  server.use(
    http.post(`${API}/v1/auth/refresh`, ({ request }) => { seen.refresh.push(request.headers.get('Authorization') ?? ''); return HttpResponse.json({ access_token: 'new', token_type: 'bearer', expires_in: 1800 }); }),
    http.get(`${API}/v1/me`, ({ request }) => { seen.me.push(request.headers.get('Authorization') ?? ''); return HttpResponse.json({}); }),
  );
  return seen;
}

describe('H12 token refresh', () => {
  it('renews a token in its last five minutes and uses the new one', async () => {
    const seen = capture();
    setToken('old', 120);
    await gw.GET('/v1/me');
    expect(seen.refresh).toEqual(['Bearer old']);
    expect(seen.me).toEqual(['Bearer new']);
  });
  it('does not refresh a token with plenty of time left', async () => {
    const seen = capture();
    setToken('fresh', 1500);
    await gw.GET('/v1/me');
    expect(seen.refresh).toEqual([]);
    expect(seen.me).toEqual(['Bearer fresh']);
  });
  it('keeps the old token when the gateway refuses (session cap reached)', async () => {
    const seen = capture();
    server.use(http.post(`${API}/v1/auth/refresh`, () => HttpResponse.json({ code: 'UNAUTHENTICATED' }, { status: 401 })));
    setToken('old', 120);
    await gw.GET('/v1/me');
    expect(seen.me).toEqual(['Bearer old']);
  });
});
