'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import AuthLayout from '@/components/AuthLayout';
import { Button, Input, Label } from '@/components/ui';
import { authService } from '@/services';
import type { User } from '@/types';

export default function ChangePassword() {
  const r = useRouter(); const [u, setU] = useState<User | null>(null);
  const [cur, setCur] = useState(''); const [code, setCode] = useState(''); const [n1, setN1] = useState(''); const [n2, setN2] = useState('');
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => { authService.verify().then(x => !x || x.stage === 'mfa' ? r.replace('/login/') : x.stage === 'setup' && !x.mustChangePassword ? r.replace('/mfa-setup/') : setU(x)); }, [r]);
  const askCode = !!u?.mfaEnabled && authService.passwordNeedsCode;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr('');
    if (n1 !== n2) return setErr('The new passwords do not match.');
    // Gateway (ADR 0038): length plus a deny-list, no composition rules; it explains any refusal itself.
    if (n1.length < 12 || (authService.passwordNeedsCode && (!/[A-Za-z]/.test(n1) || !/\d/.test(n1)))) return setErr(authService.passwordNeedsCode ? 'Use at least 12 characters with letters and a number.' : 'Use at least 12 characters. A short phrase of four or five words works well.');
    setBusy(true);
    try {
      const next = await authService.changePassword(cur, n1, askCode ? code.trim() : undefined);
      const stage = next?.stage ?? u?.stage;
      r.replace(stage === 'setup' ? '/mfa-setup/' : next?.adminOnly ? '/admin/users/' : '/dashboard/?pw=changed');
    } catch (x) { setErr((x as Error).message); setBusy(false); }
  };
  if (!u) return <div className="grid min-h-screen place-items-center text-slate-400">Loading…</div>;
  return (
    <AuthLayout>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">{u.mustChangePassword ? 'Set your own password' : 'Account & security'}</h1>
      <p className="mt-1 text-slate-500">{u.mustChangePassword ? `Welcome, ${u.name}. Your temporary password must be changed before you continue.` : `Signed in as ${u.username}. Change your password any time${askCode ? '; your authenticator code is required' : ''}.`}</p>
      <form onSubmit={submit} className="mt-8 space-y-5">
        <div><Label htmlFor="cur">Current (temporary) password</Label><Input id="cur" type="password" autoComplete="current-password" required value={cur} onChange={e => setCur(e.target.value)} /></div>
        <div><Label htmlFor="n1">New password</Label><Input id="n1" type="password" autoComplete="new-password" required value={n1} onChange={e => setN1(e.target.value)} /><p className="mt-1 text-xs text-slate-500">{authService.passwordNeedsCode ? 'At least 12 characters, with letters and a number.' : 'At least 12 characters; common passwords are refused.'}</p></div>
        <div><Label htmlFor="n2">Confirm new password</Label><Input id="n2" type="password" autoComplete="new-password" required value={n2} onChange={e => setN2(e.target.value)} /></div>
        {askCode && <div><Label htmlFor="code">Authenticator code</Label><Input id="code" inputMode="numeric" autoComplete="one-time-code" required maxLength={6} placeholder="6-digit code" value={code} onChange={e => setCode(e.target.value)} className="font-mono tracking-[.3em]" /></div>}
        {err && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
        <Button className="w-full" size="lg" loading={busy}>Update password</Button>
      </form>
      {u.stage === 'full' && !u.mustChangePassword && <button type="button" onClick={() => r.replace(u.adminOnly ? '/admin/users/' : '/dashboard/')} className="mt-6 w-full text-center text-sm font-medium text-brand-700 hover:underline">← Back</button>}
      <button type="button" onClick={async () => { await authService.logout(); r.replace('/login/'); }} className="mt-3 w-full text-center text-sm text-slate-500 hover:text-slate-800">Sign out</button>
      {u.mustChangePassword && u.mfaRequired !== false && !u.mfaEnabled && <p className="mt-6 rounded-xl bg-slate-50 p-3 text-xs text-slate-500">Next step: set up two-step verification with Google or Microsoft Authenticator.</p>}
    </AuthLayout>
  );
}
