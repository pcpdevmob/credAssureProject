import type { Role, User, ManagedUser, UserLogEvent } from '@/types';
import { gw, ok, setToken, hasToken } from '@/lib/gateway';

export interface AuthService {
  /** Password → (TOTP code | temporary-password change | MFA enrolment) → FULL; see the gateway stages below. */
  login(username: string, password: string): Promise<User>;
  current(): User | null;
  /** Re-validates the session held by this tab. Returns null when signed out. */
  verify(): Promise<User | null>;
  changePassword(current: string, next: string): Promise<User>;
  verifyMfa(code: string): Promise<User>;
  /** The gateway shows a new authenticator secret only after the password is typed again (ADR 0038). */
  startMfaSetup(password: string): Promise<{ secret: string; otpauthUri: string }>;
  enableMfa(code: string): Promise<string[]>;
  logout(): Promise<void>;
}

// Only the (non-secret) profile is remembered across reloads; tokens live in memory (lib/gateway.ts).
const KEY = 'finbridge:user';
const save = (u: User) => { try { localStorage.setItem(KEY, JSON.stringify(u)); } catch { /* */ } return u; };
const read = (): User | null => { try { const r = typeof window === 'undefined' ? null : localStorage.getItem(KEY); return r ? JSON.parse(r) : null; } catch { return null; } };
// The profile in localStorage is shared by every tab; `mine` is the account this tab's in-memory token belongs to (review S2).
let mine: string | null = null;
let ids = new Map<string, string>(); // username → user_id, from the admin list (actions are by id on the gateway)
const clear = () => { try { localStorage.removeItem(KEY); } catch { /* */ } setToken(null); mine = null; ids = new Map(); };
const ROLE: Record<string, Role> = { preparer: 'PREPARER', director_finance: 'DIRECTOR_FINANCE', vp_finance: 'VP_FINANCE', evaluator: 'EVALUATOR' };

// ---- The gateway's own accounts (ADR 0038; the old finbridge auth service is retired). POST /v1/auth/token answers a FULL token or a short stage
// token (`stage` "mfa" → a TOTP code; "setup" → change the temporary password and/or enrol MFA). Each step answers the
// next token, so the client follows `stage` until FULL. With MFA off (dev/test) the first token is already FULL.
type Stage = 'setup' | 'mfa' | 'full';
type Tok = { access_token: string; expires_in: number; stage?: Stage };
type Me = { user_id: string; username: string | null; display_name?: string | null; role: string; stage?: Stage; must_change_password?: boolean; mfa_enabled?: boolean; mfa_required?: boolean };
const take = (t: Tok): Stage => { setToken(t.access_token, t.expires_in); return t.stage ?? 'full'; };
const profile = (m: Me, stage: Stage): User => {
  const admin = m.role === 'user_admin'; // refused on every case route: an account-administration-only user
  const name = m.display_name || m.username || 'User';
  return save({ id: m.user_id, name, email: m.username ?? '', role: ROLE[m.role] ?? 'PREPARER', employeeId: '', username: m.username ?? '', stage, mustChangePassword: !!m.must_change_password, mfaEnabled: !!m.mfa_enabled, mfaRequired: !!m.mfa_required, ...(admin ? { accountRole: 'global_admin' as const, adminOnly: true } : {}) });
};
async function settle(t: Tok, username: string): Promise<User> {
  const stage = take(t);
  // A code-step token opens only POST /v1/auth/mfa/verify, so there is nothing more to read yet.
  const u = stage === 'mfa'
    ? save({ id: username, name: username, email: username, role: 'PREPARER', employeeId: '', username, stage: 'mfa', mfaEnabled: true })
    : profile(await ok(gw.GET('/v1/me')) as unknown as Me, stage);
  mine = u.id;
  return u;
}

const direct: AuthService = {
  async login(username, password) {
    clear();
    return settle(await ok(gw.POST('/v1/auth/token', { body: { username, password } })) as unknown as Tok, username);
  },
  current: read,
  // The token lives only in memory, so after a reload there is none: the profile alone is not a session.
  // Another tab signing in as someone else rewrites the shared profile: then this tab's token is not that person's, so this
  // tab signs out (drops only its own token; the other tab's profile stays).
  async verify() {
    if (!hasToken()) { clear(); return null; }
    const u = read();
    if (u && u.id === mine) return u;
    setToken(null); mine = null; return null;
  },
  async changePassword(current, next) {
    const t = await ok(gw.POST('/v1/auth/password', { body: { current_password: current, new_password: next } })) as unknown as Tok;
    return settle(t, read()?.username ?? '');
  },
  async verifyMfa(code) {
    return settle(await ok(gw.POST('/v1/auth/mfa/verify', { body: { code } })) as unknown as Tok, read()?.username ?? '');
  },
  async startMfaSetup(password) {
    const s = await ok(gw.POST('/v1/auth/mfa/setup', { body: { current_password: password } })) as unknown as { secret: string; otpauth_uri: string };
    return { secret: s.secret, otpauthUri: s.otpauth_uri };
  },
  async enableMfa(code) {
    const r = await ok(gw.POST('/v1/auth/mfa/enable', { body: { code } })) as unknown as Tok & { backup_codes: string[] };
    await settle(r, read()?.username ?? '');
    return r.backup_codes;
  },
  // Signs out everywhere (the gateway revokes every token this user holds), then forgets the local copy.
  // A code-step token cannot sign out on the server (it opens only /mfa/verify; review S1): it expires within 5 minutes.
  async logout() { if (hasToken() && read()?.stage !== 'mfa') { try { await gw.POST('/v1/auth/logout'); } catch { /* the token runs out anyway */ } } clear(); },
};

export const authService: AuthService = direct;

// User management on the gateway's /v1/admin/users (user_admin role only, audited).
export interface UserAdminService {
  /** Roles the create form offers; `hrId` = the role is bound to an HR record (preparers, ONB-01). */
  roles: { value: string; label: string; hrId?: boolean }[];
  list(): Promise<ManagedUser[]>;
  create(name: string, username: string, role: string, hrId?: string): Promise<{ username: string; temporaryPassword: string }>;
  resetPassword(username: string): Promise<{ username: string; temporaryPassword: string }>;
  setDisabled(username: string, disabled: boolean): Promise<void>;
  resetMfa(username: string): Promise<void>;
  logs(): Promise<UserLogEvent[]>;
}
const GW_ROLE_LABEL: Record<string, string> = { preparer: 'Proposal Preparer', director_finance: 'Director, Finance', vp_finance: 'VP, Finance', evaluator: 'Evaluator', user_admin: 'User administrator' };
type GwUser = { user_id: string; username: string; display_name: string | null; role: string; emp_id: string | null; active: boolean; must_change_password: boolean; mfa_enabled: boolean; created_at: string | null };
const names = () => new Map([...ids].map(([u, i]) => [i, u]));
const managed = (u: GwUser): ManagedUser => ({ username: u.username, name: u.display_name || u.username, accountRole: u.role === 'user_admin' ? 'global_admin' : 'admin', roleLabel: GW_ROLE_LABEL[u.role] ?? u.role, hrId: u.emp_id, mustChangePassword: u.must_change_password, disabled: !u.active, mfaEnabled: u.mfa_enabled, createdAt: u.created_at ? Date.parse(u.created_at) / 1000 : undefined });
async function gwList(): Promise<ManagedUser[]> {
  const rows = await ok(gw.GET('/v1/admin/users')) as unknown as GwUser[];
  ids = new Map(rows.map(r => [r.username, r.user_id]));
  return rows.map(managed);
}
async function idOf(username: string): Promise<string> {
  if (!ids.has(username)) await gwList();
  const id = ids.get(username);
  if (!id) throw new Error(`No user ${username}.`);
  return id;
}
const temp = (r: unknown) => { const x = r as { user: GwUser; temporary_password: string }; return { username: x.user.username, temporaryPassword: x.temporary_password }; };
const gatewayAdmin: UserAdminService = {
  roles: [{ value: 'preparer', label: 'Proposal Preparer', hrId: true }, { value: 'director_finance', label: 'Director, Finance' }, { value: 'vp_finance', label: 'VP, Finance' }, { value: 'evaluator', label: 'Evaluator' }, { value: 'user_admin', label: 'User administrator' }],
  list: gwList,
  async create(name, username, role, hrId) {
    const body = { username, display_name: name, role, ...(hrId ? { emp_id: hrId } : {}) };
    return temp(await ok(gw.POST('/v1/admin/users', { body: body as never })));
  },
  async resetPassword(username) {
    return temp(await ok(gw.POST('/v1/admin/users/{user_id}/reset-password', { params: { path: { user_id: await idOf(username) } } })));
  },
  async setDisabled(username, disabled) {
    const path = { user_id: await idOf(username) };
    await ok(disabled ? gw.POST('/v1/admin/users/{user_id}/disable', { params: { path } }) : gw.POST('/v1/admin/users/{user_id}/enable', { params: { path } }));
  },
  async resetMfa(username) { await ok(gw.POST('/v1/admin/users/{user_id}/reset-mfa', { params: { path: { user_id: await idOf(username) } } })); },
  async logs() {
    await gwList(); // fresh id → username map for the actor and target columns
    const who = names();
    const rows = await ok(gw.GET('/v1/admin/users/events', { params: { query: { limit: 500 } } })) as unknown as { seq: number; ts: string; actor: string; event_type: string; payload: Record<string, unknown> | null }[];
    return rows.map(e => {
      const p = e.payload ?? {};
      const target = typeof p.username === 'string' ? p.username : typeof p.user_id === 'string' ? (who.get(p.user_id) ?? p.user_id) : '';
      const rest = Object.entries(p).filter(([k]) => k !== 'username' && k !== 'user_id').map(([k, v]) => `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`).join('; ');
      return { id: e.seq, at: Date.parse(e.ts) / 1000, actor: who.get(e.actor) ?? e.actor, action: e.event_type, target, ip: '', ua: null, detail: rest || null };
    });
  },
};
export const userAdminService: UserAdminService = gatewayAdmin;
