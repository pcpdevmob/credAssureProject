import type { Role, User, ManagedUser, AccountRole, UserLogEvent } from '@/types';
import { AUTH_LIVE } from './config';
import { http } from './http';
import { gw, ok, setToken, setActingRole } from '@/lib/gateway';

export interface AuthService {
  live: boolean;
  login(username: string, password: string, role: Role): Promise<User>;
  current(): User | null;
  /** Re-validates the server session. Returns null when signed out. */
  verify(): Promise<User | null>;
  setActingRole(role: Role): User | null;
  changePassword(current: string, next: string, code?: string): Promise<void>;
  verifyMfa(code: string): Promise<User>;
  startMfaSetup(): Promise<{ secret: string; otpauthUri: string }>;
  enableMfa(code: string): Promise<string[]>;
  logout(): Promise<void>;
}

// Only the (non-secret) profile is remembered across reloads; tokens live in memory (lib/gateway.ts).
const KEY = 'finbridge:user';
const save = (u: User) => { try { localStorage.setItem(KEY, JSON.stringify(u)); } catch { /* */ } return u; };
const read = (): User | null => { try { const r = typeof window === 'undefined' ? null : localStorage.getItem(KEY); return r ? JSON.parse(r) : null; } catch { return null; } };
const clear = () => { try { localStorage.removeItem(KEY); } catch { /* */ } setToken(null); };
const ROLE: Record<string, Role> = { preparer: 'PREPARER', director_finance: 'DIRECTOR_FINANCE', vp_finance: 'VP_FINANCE', evaluator: 'EVALUATOR' };
const noMfa = () => Promise.reject(new Error('MFA is handled by the auth service (NEXT_PUBLIC_AUTH_MODE=bridge).'));

// ---- gateway mode: sign in directly with a gateway account (dev/test profile, no MFA) ----
const direct: AuthService = {
  live: false,
  async login(username, password) {
    const t = await ok(gw.POST('/v1/auth/token', { body: { username, password } })) as unknown as { access_token: string; expires_in: number };
    setToken(t.access_token, t.expires_in);
    const me = await ok(gw.GET('/v1/me')) as unknown as { user_id: string; username: string | null; role: string };
    const role = ROLE[me.role] ?? 'PREPARER';
    return save({ id: me.user_id, name: me.username ?? username, email: me.username ?? username, role, employeeId: '', username: me.username ?? username, stage: 'full' });
  },
  current: read,
  async verify() { return read(); },
  setActingRole: () => read(),
  changePassword: noMfa, verifyMfa: noMfa, startMfaSetup: noMfa, enableMfa: noMfa,
  async logout() { clear(); },
};

// ---- bridge mode: the finbridge auth service owns identity (password + TOTP MFA) and issues gateway tokens ----
type Acc = { username: string; name: string; accountRole: AccountRole; mustChangePassword: boolean; mfaEnabled?: boolean; stage?: 'setup' | 'mfa' | 'full' };
const persona = (acc: Acc, role: Role): User => ({ id: acc.username, name: acc.name, email: acc.username, role, employeeId: '', username: acc.username, accountRole: acc.accountRole, mustChangePassword: acc.mustChangePassword, mfaEnabled: acc.mfaEnabled, stage: acc.stage });

const bridge: AuthService = {
  live: true,
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
  async changePassword(current, next, code) { const acc = await http<Acc>('/auth/change-password', { method: 'POST', body: JSON.stringify({ currentPassword: current, newPassword: next, code }) }); const u = read(); save(persona(acc, u?.role ?? 'PREPARER')); },
  async verifyMfa(code) { const acc = await http<Acc>('/auth/mfa/verify', { method: 'POST', body: JSON.stringify({ code }) }); const u = read(); return save(persona(acc, u?.role ?? 'PREPARER')); },
  startMfaSetup: () => http('/auth/mfa/setup', { method: 'POST', body: '{}' }),
  async enableMfa(code) { const r = await http<{ backupCodes: string[] }>('/auth/mfa/enable', { method: 'POST', body: JSON.stringify({ code }) }); const u = read(); if (u) save({ ...u, mfaEnabled: true, stage: 'full' }); return r.backupCodes; },
  async logout() { try { await http('/auth/logout', { method: 'POST', body: '{}' }); } catch { /* ignore */ } clear(); },
};
export const authService: AuthService = AUTH_LIVE ? bridge : direct;

// User management (Global Admin) lives in the auth service only.
export interface UserAdminService {
  list(): Promise<ManagedUser[]>;
  create(name: string, username: string, role: AccountRole): Promise<{ username: string; temporaryPassword: string }>;
  resetPassword(username: string): Promise<{ username: string; temporaryPassword: string }>;
  setDisabled(username: string, disabled: boolean): Promise<void>;
  resetMfa(username: string): Promise<void>;
  logs(): Promise<UserLogEvent[]>;
}
const nope = () => Promise.reject(new Error('User administration needs the auth service (NEXT_PUBLIC_AUTH_MODE=bridge).'));
export const userAdminService: UserAdminService = AUTH_LIVE ? {
  list: () => http<ManagedUser[]>('/users/'),
  create: (name, username, role) => http('/users/', { method: 'POST', body: JSON.stringify({ name, username, role }) }),
  resetPassword: u => http(`/users/${encodeURIComponent(u)}/reset-password`, { method: 'POST', body: '{}' }),
  async setDisabled(u, d) { await http(`/users/${encodeURIComponent(u)}/${d ? 'disable' : 'enable'}`, { method: 'POST', body: '{}' }); },
  async resetMfa(u) { await http(`/users/${encodeURIComponent(u)}/reset-mfa`, { method: 'POST', body: '{}' }); },
  logs: () => http<UserLogEvent[]>('/users/logs'),
} : { list: nope, create: nope, resetPassword: nope, setDisabled: nope, resetMfa: nope, logs: nope };
