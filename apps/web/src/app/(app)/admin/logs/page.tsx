'use client';
import { toCsv } from '@/lib/csv';
import { useEffect, useMemo, useState } from 'react';
import { Download, RefreshCw } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import { Badge, Button, Card, Input } from '@/components/ui';
import { userAdminService } from '@/services';
import type { UserLogEvent } from '@/types';

const fmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'Africa/Johannesburg', year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const sast = (s: number) => fmt.format(new Date(s * 1000)) + ' SAST';
const tone = (a: string) => a.includes('FAIL') ? 'red' : a.startsWith('LOGIN_SUCCESS') ? 'green' : a.startsWith('USER_') || a.includes('MFA') ? 'violet' : a.includes('PASSWORD') ? 'amber' : 'slate';
const browser = (ua: string | null) => !ua ? '—' : ua === 'cli' ? 'Server CLI' : /Edg\//.test(ua) ? 'Edge' : /Chrome\//.test(ua) ? 'Chrome' : /Firefox\//.test(ua) ? 'Firefox' : /Safari\//.test(ua) ? 'Safari' : ua.slice(0, 24);

export default function UserLogs() {
  const me = useUser();
  const [rows, setRows] = useState<UserLogEvent[]>(); const [err, setErr] = useState('');
  const [user, setUser] = useState(''); const [action, setAction] = useState(''); const [q, setQ] = useState(''); const [from, setFrom] = useState(''); const [to, setTo] = useState('');
  const load = () => userAdminService.logs().then(setRows).catch(e => setErr((e as Error).message));
  useEffect(() => { load(); }, []);
  const users = useMemo(() => Array.from(new Set((rows ?? []).flatMap(r => [r.actor, r.target]).filter(Boolean))).sort(), [rows]);
  const actions = useMemo(() => Array.from(new Set((rows ?? []).map(r => r.action))).sort(), [rows]);
  const list = useMemo(() => (rows ?? []).filter(r => (!user || r.actor === user || r.target === user) && (!action || r.action === action)
    && (!from || r.at >= Date.parse(from + 'T00:00:00+02:00') / 1000) && (!to || r.at <= Date.parse(to + 'T23:59:59+02:00') / 1000)
    && (!q || `${r.actor} ${r.target} ${r.action} ${r.detail} ${r.ip} ${r.ua}`.toLowerCase().includes(q.toLowerCase()))), [rows, user, action, q, from, to]);
  const csv = () => {
    const body = toCsv([['Time (SAST)', 'Username', 'Action', 'Target', 'Detail', 'IP', 'User agent'], ...list.map(r => [sast(r.at), r.actor, r.action, r.target, r.detail, r.ip, r.ua])]);
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([body], { type: 'text/csv' })); a.download = `credassure-user-logs-${new Date().toISOString().slice(0, 10)}.csv`; a.click();
  };
  if (me.accountRole !== 'global_admin') return <Card className="p-10 text-center">Global Admin only.</Card>;
  const sel = 'h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm';
  return (<>
    <PageHeader title="User logs" sub="Append-only server log of sign-ins, MFA, password and account changes, and acting-role switches. Times in SAST." right={<div className="flex gap-2"><Button variant="outline" onClick={load}><RefreshCw className="h-4 w-4" />Refresh</Button><Button onClick={csv} disabled={!list.length}><Download className="h-4 w-4" />Export CSV</Button></div>} />
    <Card className="mb-4 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
      <select aria-label="Filter by user" className={sel} value={user} onChange={e => setUser(e.target.value)}><option value="">All users</option>{users.map(u => <option key={u}>{u}</option>)}</select>
      <select aria-label="Filter by action" className={sel} value={action} onChange={e => setAction(e.target.value)}><option value="">All actions</option>{actions.map(a => <option key={a}>{a}</option>)}</select>
      <Input aria-label="From date" type="date" value={from} onChange={e => setFrom(e.target.value)} />
      <Input aria-label="To date" type="date" value={to} onChange={e => setTo(e.target.value)} />
      <Input aria-label="Search" placeholder="Search IP, detail…" value={q} onChange={e => setQ(e.target.value)} />
    </Card>
    {err && <p role="alert" className="mb-4 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
    <Card className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="px-4 py-3">Time (SAST)</th><th className="px-4 py-3">Username</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Target / detail</th><th className="px-4 py-3">IP</th><th className="px-4 py-3">Browser</th></tr></thead>
        <tbody>{list.slice(0, 500).map(r => <tr key={r.id} className="border-t border-slate-100 align-top">
          <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-slate-600">{sast(r.at)}</td><td className="px-4 py-2.5 font-medium">{r.actor || '—'}</td>
          <td className="px-4 py-2.5"><Badge tone={tone(r.action)}>{r.action}</Badge></td>
          <td className="px-4 py-2.5 text-xs text-slate-600">{r.target && r.target !== r.actor ? <b className="text-slate-800">{r.target} </b> : null}{r.detail}</td>
          <td className="px-4 py-2.5 font-mono text-xs">{r.ip}</td><td className="px-4 py-2.5 text-xs text-slate-500" title={r.ua ?? ''}>{browser(r.ua)}</td></tr>)}</tbody></table>
      <p className="px-4 py-3 text-xs text-slate-400">{rows ? `${list.length} of ${rows.length} events${list.length > 500 ? ' (first 500 shown; CSV has all)' : ''}` : 'Loading…'}</p>
    </Card>
  </>);
}
