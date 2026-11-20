'use client';
import { useCallback, useEffect, useState } from 'react';
import { ShieldCheck, UserPlus, KeyRound, Ban, RotateCcw, Copy } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import { Badge, Button, Card, Input, Label } from '@/components/ui';
import { userAdminService } from '@/services';
import type { ManagedUser } from '@/types';

export default function UsersAdmin() {
  const me = useUser();
  const [list, setList] = useState<ManagedUser[]>(); const [err, setErr] = useState('');
  const [name, setName] = useState(''); const [un, setUn] = useState(''); const roles = userAdminService.roles; const [role, setRole] = useState(roles[0].value); const [hr, setHr] = useState('');
  const needsHr = !!roles.find(x => x.value === role)?.hrId;
  const [shown, setShown] = useState<{ username: string; temporaryPassword: string } | null>(null); const [busy, setBusy] = useState('');
  const load = useCallback(async () => { try { setList(await userAdminService.list()); } catch (x) { setErr((x as Error).message); } }, []);
  useEffect(() => { load(); }, [load]);
  const suggest = (n: string) => n.trim().toLowerCase().replace(/[^a-z\s]/g, '').split(/\s+/).filter(Boolean).slice(0, 2).join('.');
  const run = async (key: string, f: () => Promise<unknown>) => { setErr(''); setBusy(key); try { const r = await f(); if (r && typeof r === 'object' && 'temporaryPassword' in r) setShown(r as { username: string; temporaryPassword: string }); await load(); } catch (x) { setErr((x as Error).message); } setBusy(''); };
  if (me.accountRole !== 'global_admin') return <Card className="p-10 text-center">Global Admin only.</Card>;
  return (<>
    <PageHeader title="User management" sub="Add people, reset passwords or two-step verification, and disable access. Users are never deleted, and every change is in the audit log." />
    {shown && <Card className="mb-6 border-amber-300 bg-amber-50 p-5" role="status">
      <p className="font-semibold text-amber-900">Temporary password for {shown.username} — shown once</p>
      <div className="mt-2 flex items-center gap-2"><code className="rounded-lg bg-white px-3 py-1.5 font-mono text-sm ring-1 ring-amber-200">{shown.temporaryPassword}</code>
        <Button variant="outline" size="sm" onClick={() => navigator.clipboard?.writeText(shown.temporaryPassword)}><Copy className="h-4 w-4" />Copy</Button>
        <Button variant="ghost" size="sm" onClick={() => setShown(null)}>Done</Button></div>
      <p className="mt-2 text-xs text-amber-800">Share it privately. The user must change it on first sign-in.</p></Card>}
    {err && <p role="alert" className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
    <div className="grid gap-6 lg:grid-cols-3">
      <Card className="p-5 lg:col-span-1">
        <h2 className="flex items-center gap-2 font-semibold"><UserPlus className="h-4 w-4" />Add user</h2>
        <form className="mt-4 space-y-4" onSubmit={e => { e.preventDefault(); run('add', async () => { const r = await userAdminService.create(name.trim(), un.trim(), role, needsHr ? hr.trim() : undefined); setName(''); setUn(''); setHr(''); return r; }); }}>
          <div><Label htmlFor="nm">Full name</Label><Input id="nm" required value={name} onChange={e => { setName(e.target.value); setUn(suggest(e.target.value)); }} /></div>
          <div><Label htmlFor="un">Username</Label><Input id="un" required pattern="[a-z0-9][a-z0-9._\-]{2,63}" value={un} onChange={e => setUn(e.target.value.toLowerCase())} /><p className="mt-1 text-xs text-slate-500">lowercase firstname.lastname</p></div>
          <div><Label htmlFor="rl">Role</Label><select id="rl" value={role} onChange={e => setRole(e.target.value)} className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm">{roles.map(x => <option key={x.value} value={x.value}>{x.label}</option>)}</select></div>
          {needsHr && <div><Label htmlFor="hr">HR employee ID</Label><Input id="hr" required pattern="E[0-9]{3,6}" placeholder="E001" value={hr} onChange={e => setHr(e.target.value.toUpperCase())} /><p className="mt-1 text-xs text-slate-500">The preparer check reads this person&apos;s role and training from the HR record.</p></div>}
          <Button className="w-full" loading={busy === 'add'}>Create & show temporary password</Button>
        </form>
      </Card>
      <Card className="overflow-x-auto lg:col-span-2">
        <table className="w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Name</th><th className="px-4 py-3">Username</th><th className="px-4 py-3">Role</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">MFA</th><th className="px-4 py-3 text-right">Actions</th></tr></thead>
          <tbody>{(list ?? []).map(u => <tr key={u.username} className="border-t border-slate-100">
            <td className="px-4 py-3 font-medium">{u.name}</td><td className="px-4 py-3 font-mono text-xs">{u.username}</td>
            <td className="px-4 py-3">{u.roleLabel ? <Badge tone={u.accountRole === 'global_admin' ? 'violet' : 'blue'}>{u.roleLabel}{u.hrId ? ` · ${u.hrId}` : ''}</Badge> : u.accountRole === 'global_admin' ? <Badge tone="violet"><ShieldCheck className="h-3 w-3" />Global Admin</Badge> : <Badge tone="blue">Admin</Badge>}</td>
            <td className="px-4 py-3">{u.disabled ? <Badge tone="red">Disabled</Badge> : u.mustChangePassword ? <Badge tone="amber">Must change password</Badge> : <Badge tone="green">Active</Badge>}</td>
            <td className="px-4 py-3">{u.mfaEnabled ? <Badge tone="green">On</Badge> : <Badge tone="slate">Not set up</Badge>}</td>
            <td className="px-4 py-3"><div className="flex justify-end gap-2">
              <Button size="sm" variant="outline" loading={busy === 'r' + u.username} onClick={() => confirm(`Reset password for ${u.username}?`) && run('r' + u.username, () => userAdminService.resetPassword(u.username))}><KeyRound className="h-3.5 w-3.5" />Reset</Button>
              {u.username !== me.username && u.mfaEnabled && <Button size="sm" variant="outline" loading={busy === 'm' + u.username} onClick={() => confirm(`Reset MFA for ${u.username}? They will set it up again at next sign-in.`) && run('m' + u.username, () => userAdminService.resetMfa(u.username))}><ShieldCheck className="h-3.5 w-3.5" />Reset MFA</Button>}
              {u.username !== me.username && (u.disabled
                ? <Button size="sm" variant="outline" loading={busy === 'e' + u.username} onClick={() => run('e' + u.username, () => userAdminService.setDisabled(u.username, false))}><RotateCcw className="h-3.5 w-3.5" />Enable</Button>
                : <Button size="sm" variant="outline" loading={busy === 'd' + u.username} onClick={() => confirm(`Disable ${u.username}? They will be signed out.`) && run('d' + u.username, () => userAdminService.setDisabled(u.username, true))}><Ban className="h-3.5 w-3.5" />Disable</Button>)}
            </div></td></tr>)}</tbody></table>
        {!list && !err && <p className="p-6 text-center text-slate-400">Loading…</p>}
      </Card>
    </div>
  </>);
}
