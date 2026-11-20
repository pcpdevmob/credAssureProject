import type { Role, User, ManagedUser, AccountRole, UserLogEvent } from '@/types';
import { AUTH_LIVE } from './config';
import { http } from './http';
import { gw, ok, setToken, setActingRole, hasToken } from '@/lib/gateway';

export interface AuthService {
  live: boolean;
  /** Bridge mode only: the old auth service lets one account act in several workflow roles. */
  actingRoles: boolean;
  /** The gateway asks for the password again before it shows a new authenticator secret (ADR 0038). */
  mfaSetupNeedsPassword: boolean;
  /** The bridge asks an enrolled user for a code to change the password; the gateway does not. */
  passwordNeedsCode: boolean;
  login(username: string, password: string, role: Role): Promise<User>;
  current(): User | null;
  /** Re-validates the server session. Returns null when signed out. */
  verify(): Promise<User | null>;
  setActingRole(role: Role): User | null;
  changePassword(current: string, next: string, code?: string): Promise<User | null>;
  verifyMfa(code: string): Promise<User>;
  startMfaSetup(password?: string): Promise<{ secret: string; otpauthUri: string }>;
  enableMfa(code: string): Promise<string[]>;
  logout(): Promise<void>;
}

// Only the (non-secret) profile is remembered across reloads; tokens live in memory (lib/gateway.ts).
const KEY = 'finbridge:user';
const save = (u: User) => { try { localStorage.setItem(KEY, JSON.stringify(u)); } catch { /* */ } return u; };
const read = (): User | null => { try { const r = typeof window === 'undefined' ? null : localStorage.getItem(KEY); return r ? JSON.parse(r) : null; } catch { return null; } };
const clear = () => { try { localStorage.removeItem(KEY); } catch { /* */ } setToken(null); };
const ROLE: Record<string, Role> = { preparer: 'PREPARER', director_finance: 'DIRECTOR_FINANCE', vp_finance: 'VP_FINANCE', evaluator: 'EVALUATOR' };

// ---- gateway mode (ADR 0038): the gateway's own accounts. POST /v1/auth/token answers a FULL token or a short stage
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
  if (stage === 'mfa') return save({ id: username, name: username, email: username, role: 'PREPARER', employeeId: '', username, stage: 'mfa', mfaEnabled: true });
  return profile(await ok(gw.GET('/v1/me')) as unknown as Me, stage);
}

const direct: AuthService = {
  live: true, actingRoles: false, mfaSetupNeedsPassword: true, passwordNeedsCode: false,
  async login(username, password) {
    clear();
    return settle(await ok(gw.POST('/v1/auth/token', { body: { username, password } })) as unknown as Tok, username);
  },
  current: read,
  // The token lives only in memory, so after a reload there is none: the profile alone is not a session.
  async verify() { if (hasToken()) return read(); clear(); return null; },
  setActingRole: () => read(),
  async changePassword(current, next) {
    const t = await ok(gw.POST('/v1/auth/password', { body: { current_password: current, new_password: next } })) as unknown as Tok;
    return settle(t, read()?.username ?? '');
  },
  async verifyMfa(code) {
    return settle(await ok(gw.POST('/v1/auth/mfa/verify', { body: { code } })) as unknown as Tok, read()?.username ?? '');
  },
  async startMfaSetup(password) {
    const s = await ok(gw.POST('/v1/auth/mfa/setup', { body: { current_password: password ?? '' } })) as unknown as { secret: string; otpauth_uri: string };
    return { secret: s.secret, otpauthUri: s.otpauth_uri };
  },
  async enableMfa(code) {
    const r = await ok(gw.POST('/v1/auth/mfa/enable', { body: { code } })) as unknown as Tok & { backup_codes: string[] };
    await settle(r, read()?.username ?? '');
    return r.backup_codes;
  },
  // Signs out everywhere (the gateway revokes every token this user holds), then forgets the local copy.
  async logout() { if (hasToken()) { try { await gw.POST('/v1/auth/logout'); } catch { /* the token runs out anyway */ } } clear(); },
};

// ---- bridge mode: the finbridge auth service owns identity (password + TOTP MFA) and issues gateway tokens ----
type Acc = { username: string; name: string; accountRole: AccountRole; mustChangePassword: boolean; mfaEnabled?: boolean; stage?: 'setup' | 'mfa' | 'full' };
const persona = (acc: Acc, role: Role): User => ({ id: acc.username, name: acc.name, email: acc.username, role, employeeId: '', username: acc.username, accountRole: acc.accountRole, mustChangePassword: acc.mustChangePassword, mfaEnabled: acc.mfaEnabled, stage: acc.stage });

const bridge: AuthService = {
  live: true, actingRoles: true, mfaSetupNeedsPassword: false, passwordNeedsCode: true,
  async login(username, password, role) { const acc = await http<Acc>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }); setActingRole(role); return save(persona(acc, role)); },
  current: read,
  async verify() {
    try { const acc = await http<Acc>('/auth/me'); const u = read(); const role = u?.role ?? 'PREPARER'; setActingRole(role); return save(persona(acc, role)); }
    catch { clear(); return null; }
  },
  setActingRole(role) {
    const u = read(); if (!u || !u.username) return null;
    setActingRole(role);
    http('/auth/event', { method: 'POST', body: JSON.stringify({ action: 'ACTING_ROLE_SWITCH', actingRole: role }) }).catch(() => undefined);
    return save(persona({ username: u.username, name: u.name, accountRole: u.accountRole!, mustChangePassword: !!u.mustChangePassword, mfaEnabled: u.mfaEnabled, stage: u.stage }, role));
  },
  async changePassword(current, next, code) { const acc = await http<Acc>('/auth/change-password', { method: 'POST', body: JSON.stringify({ currentPassword: current, newPassword: next, code }) }); const u = read(); return save(persona(acc, u?.role ?? 'PREPARER')); },
  async verifyMfa(code) { const acc = await http<Acc>('/auth/mfa/verify', { method: 'POST', body: JSON.stringify({ code }) }); const u = read(); return save(persona(acc, u?.role ?? 'PREPARER')); },
  startMfaSetup: () => http('/auth/mfa/setup', { method: 'POST', body: '{}' }),
  async enableMfa(code) { const r = await http<{ backupCodes: string[] }>('/auth/mfa/enable', { method: 'POST', body: JSON.stringify({ code }) }); const u = read(); if (u) save({ ...u, mfaEnabled: true, stage: 'full' }); return r.backupCodes; },
  async logout() { try { await http('/auth/logout', { method: 'POST', body: '{}' }); } catch { /* ignore */ } clear(); },
};
export const authService: AuthService = AUTH_LIVE ? bridge : direct;

// User management: the auth service in bridge mode, the gateway's /v1/admin/users (user_admin role) otherwise.
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
let ids = new Map<string, string>(); // username → user_id, from the last list (actions are by id on the gateway)
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
export const userAdminService: UserAdminService = AUTH_LIVE ? {
  roles: [{ value: 'admin', label: 'Admin' }, { value: 'global_admin', label: 'Global Admin' }],
  list: () => http<ManagedUser[]>('/users/'),
  create: (name, username, role) => http('/users/', { method: 'POST', body: JSON.stringify({ name, username, role }) }),
  resetPassword: u => http(`/users/${encodeURIComponent(u)}/reset-password`, { method: 'POST', body: '{}' }),
  async setDisabled(u, d) { await http(`/users/${encodeURIComponent(u)}/${d ? 'disable' : 'enable'}`, { method: 'POST', body: '{}' }); },
  async resetMfa(u) { await http(`/users/${encodeURIComponent(u)}/reset-mfa`, { method: 'POST', body: '{}' }); },
  logs: () => http<UserLogEvent[]>('/users/logs'),
} : gatewayAdmin;
