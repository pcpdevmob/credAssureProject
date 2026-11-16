'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import QRCode from 'qrcode';
import { Copy, Download, ShieldCheck, Smartphone } from 'lucide-react';
import AuthLayout from '@/components/AuthLayout';
import { Button, Input, Label } from '@/components/ui';
import { authService } from '@/services';
import type { User } from '@/types';

export default function MfaSetup() {
  const r = useRouter(); const [u, setU] = useState<User | null>(null);
  const [qr, setQr] = useState(''); const [secret, setSecret] = useState(''); const [code, setCode] = useState('');
  const [codes, setCodes] = useState<string[] | null>(null); const [saved, setSaved] = useState(false);
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false);
  useEffect(() => {
    authService.verify().then(async x => {
      if (!x || x.stage === 'mfa') return r.replace('/login/');
      if (x.mustChangePassword) return r.replace('/change-password/');
      if (x.stage === 'full' || x.mfaEnabled) return r.replace('/dashboard/');
      setU(x);
      try { const s = await authService.startMfaSetup(); setSecret(s.secret); setQr(await QRCode.toDataURL(s.otpauthUri, { margin: 1, width: 220, color: { dark: '#0E1628', light: '#ffffff' } })); }
      catch (e) { setErr((e as Error).message); }
    });
  }, [r]);
  const confirm = async (e: React.FormEvent) => { e.preventDefault(); setErr(''); setBusy(true); try { setCodes(await authService.enableMfa(code.trim())); } catch (x) { setErr((x as Error).message); setCode(''); } setBusy(false); };
  if (!u) return <div className="grid min-h-screen place-items-center text-slate-400">{err || 'Loading…'}</div>;
  if (codes) return (
    <AuthLayout>
      <div className="grid h-12 w-12 place-items-center rounded-2xl bg-emerald-50 text-emerald-600"><ShieldCheck className="h-6 w-6" /></div>
      <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">Two-step verification is on</h1>
      <p className="mt-1 text-slate-600">Save these <b>backup codes</b> somewhere safe. Each works once if you lose your phone. <b>They are shown only now.</b></p>
      <ol id="backup-codes" className="mt-5 grid grid-cols-2 gap-2 rounded-2xl bg-midnight-950 p-4 font-mono text-sm text-gold-200">{codes.map(c => <li key={c} className="rounded-lg bg-white/5 px-3 py-1.5 text-center">{c}</li>)}</ol>
      <div className="mt-3 flex gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => navigator.clipboard?.writeText(codes.join('\n'))}><Copy className="h-4 w-4" />Copy</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([`CredAssure backup codes for ${u.username}\n\n${codes.join('\n')}\n`], { type: 'text/plain' })); a.download = 'credassure-backup-codes.txt'; a.click(); }}><Download className="h-4 w-4" />Download</Button>
      </div>
      <label className="mt-5 flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={saved} onChange={e => setSaved(e.target.checked)} className="h-4 w-4 rounded" />I have saved my backup codes</label>
      <Button className="mt-5 w-full" size="lg" disabled={!saved} onClick={() => r.replace('/dashboard/')}>Continue to CredAssure</Button>
    </AuthLayout>
  );
  return (
    <AuthLayout>
      <h1 className="text-2xl font-bold tracking-tight text-slate-900">Set up two-step verification</h1>
      <ol className="mt-3 space-y-1 text-sm text-slate-600">
        <li><b>1.</b> Install <b>Google Authenticator</b> or <b>Microsoft Authenticator</b> on your phone.</li>
        <li><b>2.</b> In the app, tap <b>+</b> → <b>Scan a QR code</b> and scan the code below.</li>
        <li><b>3.</b> Type the 6-digit code the app shows to confirm.</li>
      </ol>
      <div className="mt-5 flex flex-col items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 sm:flex-row">
        {qr ? <img src={qr} alt="QR code for your authenticator app" width={180} height={180} className="rounded-xl ring-1 ring-slate-200" /> : <div className="h-[180px] w-[180px] animate-pulse rounded-xl bg-slate-100" />}
        <div className="min-w-0 text-sm"><p className="flex items-center gap-1.5 font-medium text-slate-800"><Smartphone className="h-4 w-4" />Can&apos;t scan?</p><p className="mt-1 text-xs text-slate-500">Choose “Enter a setup key”, account <b>{u.username}</b>, time-based, then type:</p>
          <code id="manual-key" className="mt-2 block break-all rounded-lg bg-slate-50 px-2 py-1.5 font-mono text-xs text-slate-800 ring-1 ring-slate-200">{secret.replace(/(.{4})/g, '$1 ').trim()}</code></div>
      </div>
      <form onSubmit={confirm} className="mt-5 space-y-4">
        <div><Label htmlFor="code">6-digit code from the app</Label><Input id="code" inputMode="numeric" autoComplete="one-time-code" required maxLength={7} placeholder="123456" value={code} onChange={e => setCode(e.target.value)} className="text-center font-mono text-2xl tracking-[.4em]" /></div>
        {err && <p role="alert" className="rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
        <Button className="w-full" size="lg" loading={busy}>Confirm & turn on</Button>
      </form>
      <button type="button" onClick={async () => { await authService.logout(); r.replace('/login/'); }} className="mt-4 w-full text-center text-sm text-slate-500 hover:text-slate-800">Sign out and finish later</button>
    </AuthLayout>
  );
}
