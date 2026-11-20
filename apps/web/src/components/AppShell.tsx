'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState, createContext, useContext } from 'react';
import { LayoutDashboard, FolderKanban, PlusCircle, Inbox, ScrollText, LogOut, Menu, X, Sparkles, RotateCcw, Users, KeyRound, ListChecks, ShieldCheck, BarChart3, LifeBuoy } from 'lucide-react';
import { authService } from '@/services';
import type { User, Role } from '@/types';
import { ROLE_LABEL } from '@/types';
import { cn } from '@/lib/utils';
import { Logo } from './Logo';
import ThemeToggle from './ThemeToggle';
import { ProvenanceProvider } from './Figure';

const Ctx = createContext<User | null>(null);
export const useUser = () => useContext(Ctx)!;

const NAV = [
  { href: '/dashboard/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/cases/', label: 'Cases', icon: FolderKanban },
  { href: '/cases/new/', label: 'New case', icon: PlusCircle, roles: ['PREPARER'] },
  { href: '/approvals/', label: 'Approval inbox', icon: Inbox },
  { href: '/audit/', label: 'Case history', icon: ScrollText },
  { href: '/evaluation/', label: 'Evaluation', icon: BarChart3, roles: ['EVALUATOR'] },
  { href: '/help/', label: 'Help', icon: LifeBuoy },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [open, setOpen] = useState(false);
  const router = useRouter(); const path = usePathname();
  useEffect(() => {
    let alive = true;
    (async () => {
      const u = await authService.verify();
      if (!alive) return;
      if (!u) return router.replace('/login/');
      if (u.stage === 'mfa') { await authService.logout(); return router.replace('/login/'); }
      if (u.stage === 'setup') return router.replace(u.mustChangePassword ? '/change-password/' : '/mfa-setup/');
      if (u.mustChangePassword) return router.replace('/change-password/');
      if (path.startsWith('/admin') && u.accountRole !== 'global_admin') return router.replace('/dashboard/');
      // ADR 0038: a user_admin account manages accounts only; every case route refuses it.
      if (u.adminOnly && !path.startsWith('/admin') && !path.startsWith('/help')) return router.replace('/admin/users/');
      setUser(u);
    })();
    return () => { alive = false; };
  }, [router, path]);
  const act = (r: Role) => { const u = authService.setActingRole(r); if (u) { setUser(u); router.refresh(); } };
  useEffect(() => setOpen(false), [path]);
  useEffect(() => { const n = [...NAV].reverse().find(x => path.startsWith(x.href)); document.title = `${path.startsWith('/case/') ? 'Case' : n?.label ?? 'Workspace'} · CredAssure`; }, [path]);
  if (!user) return <div className="grid min-h-screen place-items-center text-slate-400">Loading…</div>;
  const admin = user.accountRole === 'global_admin' && authService.live ? [{ href: '/admin/users/', label: 'User management', icon: Users }, { href: '/admin/logs/', label: 'User logs', icon: ListChecks }] : [];
  const items = user.adminOnly ? [...admin, ...NAV.filter(n => n.href === '/help/')] : [...NAV.filter(n => !n.roles || n.roles.includes(user.role)), ...admin];
  const Side = (
    <div className="flex h-full flex-col gap-1 p-4">
      <div className="mb-6 flex items-center justify-between px-2"><Logo /><button className="lg:hidden" aria-label="Close menu" onClick={() => setOpen(false)}><X className="h-5 w-5 text-ink-300" /></button></div>
      {items.map(n => { const active = path === n.href || (n.href === '/cases/' && path.startsWith('/case') && path !== '/cases/new/'); return (
        <Link key={n.href} href={n.href} aria-current={active ? 'page' : undefined} className={cn('relative flex items-center gap-3 rounded-full px-4 py-2.5 text-sm font-medium transition', active ? 'text-ink-950' : 'text-ink-300 hover:bg-white/5 hover:text-white')}>{active && <span aria-hidden className="absolute inset-0 rounded-full bg-white" />}<n.icon className="relative h-[18px] w-[18px]" /><span className="relative">{n.label}</span></Link>); })}
      <div className="mt-auto space-y-3">
        <div className="flex items-center justify-between px-2"><span className="text-[11px] font-semibold uppercase tracking-wider text-ink-300">Theme</span><ThemeToggle /></div>
        <div className="rounded-2xl bg-white/[.05] p-4 text-xs text-slate-300 ring-1 ring-white/10">
          <p className="flex items-center gap-1.5 font-semibold text-white"><Sparkles className="h-4 w-4 text-gold-300" /> Prototype</p>
          <p className="mt-1">Synthetic data & simulated lenders only. </p>
        </div>
        {authService.live && <Link href="/change-password/" className="flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-slate-300 ring-1 ring-white/10 hover:bg-white/5 hover:text-white"><ShieldCheck className="h-4 w-4 text-emerald-300" />Account & security<span className="ml-auto rounded-full bg-emerald-400/15 px-2 py-0.5 text-[10px] text-emerald-300">{user.mfaEnabled ? 'MFA on' : 'MFA'}</span></Link>}
        {authService.actingRoles && <div className="rounded-xl bg-white/5 p-3 ring-1 ring-white/10">
          <label htmlFor="acting-role" className="text-[11px] font-semibold uppercase tracking-wider text-ink-300">Acting role</label>
          <select id="acting-role" value={user.role} onChange={e => act(e.target.value as Role)} className="mt-1 w-full rounded-lg border-0 bg-slate-900 px-2 py-1.5 text-sm text-white ring-1 ring-white/15 focus:ring-brand-400">
            <option value="PREPARER">Preparer</option><option value="VP_FINANCE">VP Finance</option><option value="DIRECTOR_FINANCE">Director Finance</option>
          </select>
        </div>}
        <div className="flex items-center gap-3 rounded-xl px-2 py-2">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-gold-300 to-emerald-400 text-sm font-semibold text-midnight-950">{user.name.split(' ').map(s => s[0]).join('').slice(0, 2).toUpperCase()}</div>
          <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-white">{user.name}</p><p className="truncate text-xs text-ink-300">{user.adminOnly ? 'User administrator' : authService.actingRoles ? `${user.accountRole === 'global_admin' ? 'Global Admin' : user.accountRole === 'admin' ? 'Admin' : ROLE_LABEL[user.role]} · as ${ROLE_LABEL[user.role]}` : ROLE_LABEL[user.role]}</p></div>
          {authService.live && <Link title="Account & security: change password" aria-label="Account & security" href="/change-password/" className="text-ink-300 hover:text-white"><KeyRound className="h-4 w-4" /></Link>}
          <button title="Sign out" aria-label="Sign out" onClick={async () => { await authService.logout(); router.replace('/login/'); }} className="text-ink-300 hover:text-white"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </div>
  );
  return (
    <Ctx.Provider value={user}><ProvenanceProvider>
      <div className="dot-canvas min-h-screen">
        <aside className="fixed inset-y-3 left-3 z-30 hidden w-64 overflow-y-auto rounded-[28px] bg-ink-950 keep-light lg:block">{Side}</aside>
        {open && <div className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm lg:hidden" onClick={() => setOpen(false)} />}
        <aside className={cn('fixed inset-y-0 left-0 z-50 w-72 overflow-y-auto bg-ink-950 keep-light transition-transform lg:hidden', open ? 'translate-x-0' : '-translate-x-full')}>{Side}</aside>
        <div className="lg:pl-[17.5rem]">
          <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-white/85 px-4 backdrop-blur lg:hidden">
            <button aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button><Logo dark />
          </header>
          <main className="mx-auto max-w-7xl p-4 sm:p-6 lg:p-8">{children}</main>
          <footer className="mx-auto max-w-7xl px-4 pb-6 text-center text-[11px] tracking-wide text-slate-400 sm:px-6 lg:px-8">CredAssure · Team IntelliCore · IIT Kharagpur Capstone</footer>
        </div>
      </div>
    </ProvenanceProvider></Ctx.Provider>
  );
}
