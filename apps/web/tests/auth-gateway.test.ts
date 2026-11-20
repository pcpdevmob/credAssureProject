// ADR 0038 step E: the web app signs in with the gateway's own accounts, following `stage` and `next`
// (password → TOTP code, or password change → MFA enrolment) until the token is FULL.
import { afterEach, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';
import { authService, userAdminService } from '@/services/auth';
import { gw, hasToken, setToken } from '@/lib/gateway';

afterEach(() => { setToken(null); try { localStorage.clear(); } catch { /* */ } });

const tok = (access_token: string, stage: string, next: string[] = [], expires_in = 300) => ({ access_token, token_type: 'bearer', expires_in, stage, next });
const me = (o: Record<string, unknown> = {}) => ({ user_id: 'u-dir', username: 'demo.director', display_name: 'Demo Director', role: 'director_finance', stage: 'full', must_change_password: false, mfa_enabled: true, mfa_required: true, ...o });

function record() {
  const seen: { path: string; auth: string; body: unknown }[] = [];
  const keep = async (request: Request) => { const t = await request.text(); seen.push({ path: new URL(request.url).pathname, auth: request.headers.get('Authorization') ?? '', body: t ? JSON.parse(t) : null }); };
  return { seen, keep };
}

describe('ADR 0038 sign-in with a second factor', () => {
  it('stops at the code step for an enrolled user, then signs in with the code', async () => {
    const { seen, keep } = record();
    server.use(
      http.post(`${API}/v1/auth/token`, async ({ request }) => { await keep(request); return HttpResponse.json(tok('stage-mfa', 'mfa', ['verify_mfa'])); }),
      http.post(`${API}/v1/auth/mfa/verify`, async ({ request }) => { await keep(request); return HttpResponse.json(tok('full-1', 'full', [], 1800)); }),
      http.get(`${API}/v1/me`, async ({ request }) => { await keep(request); return HttpResponse.json(me()); }),
    );
    const u = await authService.login('demo.director', 'pw', 'PREPARER');
    expect(u.stage).toBe('mfa');
    expect(seen.map(s => s.path)).toEqual(['/v1/auth/token']); // /v1/me is closed to an MFA stage token
    const full = await authService.verifyMfa('123456');
    expect(full).toMatchObject({ stage: 'full', role: 'DIRECTOR_FINANCE', name: 'Demo Director', mfaEnabled: true });
    expect(seen[1]).toEqual({ path: '/v1/auth/mfa/verify', auth: 'Bearer stage-mfa', body: { code: '123456' } });
    expect(seen[2].auth).toBe('Bearer full-1');
  });

  it('keeps the code-step token after a wrong code, so the user can try again', async () => {
    const auths: string[] = [];
    let n = 0;
    server.use(
      http.post(`${API}/v1/auth/token`, () => HttpResponse.json(tok('stage-mfa', 'mfa', ['verify_mfa']))),
      http.post(`${API}/v1/auth/mfa/verify`, ({ request }) => { auths.push(request.headers.get('Authorization') ?? ''); n += 1; return n === 1 ? HttpResponse.json({ code: 'UNAUTHENTICATED', detail: 'invalid code' }, { status: 401 }) : HttpResponse.json(tok('full-2', 'full', [], 1800)); }),
      http.get(`${API}/v1/me`, () => HttpResponse.json(me())),
    );
    await authService.login('demo.director', 'pw', 'PREPARER');
    await expect(authService.verifyMfa('000000')).rejects.toBeTruthy();
    expect(hasToken()).toBe(true);
    await authService.verifyMfa('123456');
    expect(auths).toEqual(['Bearer stage-mfa', 'Bearer stage-mfa']);
  });

  it('enrols an approver: password again, then a code, then backup codes and a full token', async () => {
    const { seen, keep } = record();
    let enrolled = false;
    server.use(
      http.post(`${API}/v1/auth/token`, () => HttpResponse.json(tok('stage-setup', 'setup', ['enrol_mfa']))),
      http.get(`${API}/v1/me`, async ({ request }) => { await keep(request); return HttpResponse.json(me(enrolled ? {} : { stage: 'setup', mfa_enabled: false })); }),
      http.post(`${API}/v1/auth/mfa/setup`, async ({ request }) => { await keep(request); return HttpResponse.json({ secret: 'JBSWY3DPEHPK3PXP', otpauth_uri: 'otpauth://totp/CredAssure:demo.director?secret=JBSWY3DPEHPK3PXP&issuer=CredAssure' }); }),
      http.post(`${API}/v1/auth/mfa/enable`, async ({ request }) => { await keep(request); enrolled = true; return HttpResponse.json({ backup_codes: ['aaaa-bbbb', 'cccc-dddd'], ...tok('full-3', 'full', [], 1800) }); }),
    );
    const u = await authService.login('demo.director', 'pw', 'PREPARER');
    expect(u).toMatchObject({ stage: 'setup', mustChangePassword: false, mfaEnabled: false });
    expect(authService.mfaSetupNeedsPassword).toBe(true);
    const s = await authService.startMfaSetup('pw');
    expect(s.otpauthUri).toMatch(/^otpauth:\/\/totp\//);
    expect(seen.find(x => x.path === '/v1/auth/mfa/setup')).toMatchObject({ auth: 'Bearer stage-setup', body: { current_password: 'pw' } });
    const codes = await authService.enableMfa('654321');
    expect(codes).toEqual(['aaaa-bbbb', 'cccc-dddd']);
    expect(seen.find(x => x.path === '/v1/auth/mfa/enable')?.body).toEqual({ code: '654321' });
    expect(seen.at(-1)).toMatchObject({ path: '/v1/me', auth: 'Bearer full-3' });
    expect(authService.current()).toMatchObject({ stage: 'full', mfaEnabled: true });
  });

  it('changes a temporary password and follows the stage the gateway returns', async () => {
    const { seen, keep } = record();
    server.use(
      http.post(`${API}/v1/auth/token`, () => HttpResponse.json(tok('stage-setup', 'setup', ['change_password', 'enrol_mfa']))),
      http.get(`${API}/v1/me`, ({ request }) => HttpResponse.json(me({ stage: 'setup', mfa_enabled: false, must_change_password: request.headers.get('Authorization') === 'Bearer stage-setup' }))),
      http.post(`${API}/v1/auth/password`, async ({ request }) => { await keep(request); return HttpResponse.json(tok('stage-setup-2', 'setup', ['enrol_mfa'])); }),
    );
    const u = await authService.login('demo.director', 'temp', 'PREPARER');
    expect(u.mustChangePassword).toBe(true);
    expect(authService.passwordNeedsCode).toBe(false);
    const after = await authService.changePassword('temp', 'a-new-long-passphrase-42');
    expect(seen[0]).toMatchObject({ auth: 'Bearer stage-setup', body: { current_password: 'temp', new_password: 'a-new-long-passphrase-42' } });
    expect(after).toMatchObject({ stage: 'setup', mustChangePassword: false });
  });

  it('a user administrator is an admin-only account', async () => {
    server.use(
      http.post(`${API}/v1/auth/token`, () => HttpResponse.json(tok('full-a', 'full', [], 1800))),
      http.get(`${API}/v1/me`, () => HttpResponse.json(me({ user_id: 'u-adm', username: 'it.admin', display_name: 'IT Admin', role: 'user_admin' }))),
    );
    const u = await authService.login('it.admin', 'pw', 'PREPARER');
    expect(u).toMatchObject({ accountRole: 'global_admin', adminOnly: true });
  });

  it('signs out on the server, then forgets the token', async () => {
    const auths: string[] = [];
    server.use(
      http.post(`${API}/v1/auth/token`, () => HttpResponse.json(tok('full-4', 'full', [], 1800))),
      http.get(`${API}/v1/me`, () => HttpResponse.json(me())),
      http.post(`${API}/v1/auth/logout`, ({ request }) => { auths.push(request.headers.get('Authorization') ?? ''); return HttpResponse.json({ signed_out: true }); }),
    );
    await authService.login('demo.director', 'pw', 'PREPARER');
    await authService.logout();
    expect(auths).toEqual(['Bearer full-4']);
    expect(hasToken()).toBe(false);
    expect(authService.current()).toBeNull();
  });

  it('a 401 on a case route still ends the session', async () => {
    server.use(http.get(`${API}/v1/cases`, () => HttpResponse.json({ code: 'UNAUTHENTICATED' }, { status: 401 })));
    setToken('stale', 1500);
    await gw.GET('/v1/cases');
    expect(hasToken()).toBe(false);
  });
});

describe('ADR 0038 user administration through the gateway', () => {
  const row = (o: Record<string, unknown>) => ({ user_id: 'u-1', username: 'demo.director', display_name: 'Demo Director', role: 'director_finance', emp_id: null, active: true, must_change_password: false, mfa_enabled: true, backup_codes_left: 8, created_at: '2026-11-20T10:00:00+00:00', updated_at: null, ...o });

  it('lists users with their workflow role and acts on them by id', async () => {
    const posts: { path: string; body: unknown }[] = [];
    server.use(
      http.get(`${API}/v1/admin/users`, () => HttpResponse.json([row({}), row({ user_id: 'u-2', username: 'demo.preparer', display_name: 'Demo Preparer', role: 'preparer', emp_id: 'E001', active: false, mfa_enabled: false })])),
      http.post(`${API}/v1/admin/users/:id/:action`, async ({ request, params }) => { const t = await request.text(); posts.push({ path: `${params.id}/${params.action}`, body: t ? JSON.parse(t) : null }); return HttpResponse.json(params.action === 'reset-password' ? { user: row({}), temporary_password: 'Tmp-xyz' } : row({})); }),
    );
    setToken('full-admin', 1800);
    const list = await userAdminService.list();
    expect(list[0]).toMatchObject({ username: 'demo.director', name: 'Demo Director', roleLabel: 'Director, Finance', disabled: false, mfaEnabled: true });
    expect(list[1]).toMatchObject({ username: 'demo.preparer', roleLabel: 'Proposal Preparer', disabled: true });
    await userAdminService.resetMfa('demo.director');
    await userAdminService.setDisabled('demo.preparer', false);
    const r = await userAdminService.resetPassword('demo.director');
    expect(r).toEqual({ username: 'demo.director', temporaryPassword: 'Tmp-xyz' });
    expect(posts.map(p => p.path)).toEqual(['u-1/reset-mfa', 'u-2/enable', 'u-1/reset-password']);
  });

  it('creates a preparer bound to an HR id and shows the temporary password once', async () => {
    let body: unknown;
    server.use(http.post(`${API}/v1/admin/users`, async ({ request }) => { body = await request.json(); return HttpResponse.json({ user: row({ username: 'new.prep', role: 'preparer' }), temporary_password: 'Tmp-abc' }, { status: 201 }); }));
    setToken('full-admin', 1800);
    const r = await userAdminService.create('New Prep', 'new.prep', 'preparer', 'E003');
    expect(body).toEqual({ username: 'new.prep', display_name: 'New Prep', role: 'preparer', emp_id: 'E003' });
    expect(r).toEqual({ username: 'new.prep', temporaryPassword: 'Tmp-abc' });
  });

  it('turns account events into log rows without exposing more than the gateway sent', async () => {
    server.use(
      http.get(`${API}/v1/admin/users`, () => HttpResponse.json([row({}), row({ user_id: 'u-adm', username: 'it.admin', role: 'user_admin' })])),
      http.get(`${API}/v1/admin/users/events`, () => HttpResponse.json([{ seq: 7, ts: '2026-11-20T10:00:00+00:00', actor: 'u-adm', event_type: 'MFA_RESET', payload: { user_id: 'u-1', username: 'demo.director' } }])),
    );
    setToken('full-admin', 1800);
    const rows = await userAdminService.logs();
    expect(rows[0]).toMatchObject({ id: 7, at: Date.parse('2026-11-20T10:00:00Z') / 1000, actor: 'it.admin', action: 'MFA_RESET', target: 'demo.director' });
  });
});
