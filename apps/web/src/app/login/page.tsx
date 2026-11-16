'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import AuthLayout from '@/components/AuthLayout';
import RolePicker from '@/components/RolePicker';
import { Button, Input, Label } from '@/components/ui';
import { authService, AUTH_LIVE } from '@/services';
import type { Role } from '@/types';
import { bannerOf } from '@/lib/problem';
const say = (x: unknown) => { const b = bannerOf(x); return `${b.what} ${b.fix}`; };

export default function Login() {
  const [email, setEmail] = useState(''); const [pw, setPw] = useState(''); const [role, setRole] = useState<Role>('PREPARER');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false); const r = useRouter();
  const [mfa, setMfa] = useState(false); const [code, setCode] = useState('');
  const [expired, setExpired] = useState(false);
  useEffect(() => { setExpired(new URLSearchParams(window.location.search).get('expired') === '1'); }, []);
  useEffect(() => { if (!AUTH_LIVE) return; authService.verify().then(u => { if (!u) return; if (u.stage === 'setup') r.replace(u.mustChangePassword ? '/change-password/' : '/mfa-setup/'); else if (u.stage === 'mfa') setMfa(true); else if (u.stage === 'full') r.replace('/dashboard/'); }).catch(() => undefined); }, [r]);
  const submitCode = async (e: React.FormEvent) => { e.preventDefault(); setErr(''); setBusy(true); try { await authService.verifyMfa(code.trim()); r.push('/dashboard/'); } catch (x) { setErr(say(x)); setBusy(false); setCode(''); } };
  if (mfa) return (
    <AuthLayout>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Two-step verification</h1>
      <p className="mt-1 text-slate-500">Open Google or Microsoft Authenticator and enter the 6-digit code for <b>CredAssure</b>. Lost your phone? Use one of your backup codes.</p>
      <form onSubmit={submitCode} className="mt-8 space-y-5">
        <div><Label htmlFor="code">Authentication code</Label><Input id="code" inputMode="numeric" autoComplete="one-time-code" autoFocus required maxLength={12} placeholder="123 456" value={code} onChange={e => setCode(e.target.value)} className="text-center font-mono text-2xl tracking-[.4em]" /></div>
        {err && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
        <Button className="w-full" size="lg" loading={busy}>Verify & sign in</Button>
      </form>
      <button type="button" onClick={async () => { await authService.logout(); setMfa(false); setPw(''); }} className="mt-6 w-full text-center text-sm text-slate-500 hover:text-slate-800">Use a different account</button>
    </AuthLayout>
  );
  const submit = async (e: React.FormEvent) => { e.preventDefault(); setErr(''); setBusy(true); try { const u = await authService.login(email, pw, role); if (u.stage === 'mfa') { setMfa(true); setBusy(false); return; } r.push(u.stage === 'setup' ? (u.mustChangePassword ? '/change-password/' : '/mfa-setup/') : '/dashboard/'); } catch (x) { setErr(say(x)); setBusy(false); } };
  return (
    <AuthLayout>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Welcome back</h1><p className="mt-1 text-slate-500">Sign in to continue to your workspace.</p>
      {expired && <p role="status" className="mt-6 rounded-xl bg-gold-50 p-3 text-sm text-gold-800 ring-1 ring-gold-200">Your session expired. Sign in again to continue.</p>}
      <form onSubmit={submit} className="mt-8 space-y-5">
        {AUTH_LIVE && <div><Label>Act as (workflow role)</Label><RolePicker value={role} onChange={setRole} /></div>}
        <div><Label htmlFor="username">Username</Label><Input id="username" name="username" autoComplete="username" autoCapitalize="none" required value={email} onChange={e => setEmail(e.target.value)} /></div>
        <div><Label htmlFor="password">Password</Label><Input id="password" type="password" autoComplete="current-password" required value={pw} onChange={e => setPw(e.target.value)} /></div>
        {err && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
        <Button className="w-full" size="lg" loading={busy}>Sign in</Button>
      </form>
      <p className="mt-6 rounded-2xl border border-dashed border-slate-200 p-4 text-xs text-slate-500">Accounts are issued by your administrator; there is no self sign-up.</p>
    </AuthLayout>
  );
}
