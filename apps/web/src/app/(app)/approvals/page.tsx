'use client';
// UI-07: the approval inbox. The gateway filters by the signed-in role (a Director sees only Director-routed cases); the browser shows
// exactly that list. A case held at exactly ₹1.5 crore is labelled HELD in words and shape, not colour alone.
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Inbox, PauseCircle, ArrowRight } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import ErrorBanner from '@/components/ErrorBanner';
import { Card, CardHeader, Badge, Skeleton } from '@/components/ui';
import { approvalService, type InboxItem } from '@/services';
import { ROLE_LABEL } from '@/types';

const ROUTE: Record<string, string> = { director_finance: 'Director, Finance', vp_finance: 'VP, Finance', HELD: 'Human decision' };
export default function Approvals() {
  const u = useUser(); const [items, setItems] = useState<InboxItem[] | null>(null); const [err, setErr] = useState<unknown>();
  const approver = u.role === 'DIRECTOR_FINANCE' || u.role === 'VP_FINANCE'; // a hint only: the gateway returns 403 to anyone else
  useEffect(() => { if (!approver) return; let live = true; setItems(null); setErr(undefined); approvalService.inbox().then(i => live && setItems(i)).catch(e => live && setErr(e)); return () => { live = false; }; }, [u.role, approver]);
  return (<>
    <PageHeader title="Approval inbox" sub={<>Proposals routed to you as <Badge tone="blue">{ROLE_LABEL[u.role]}</Badge></>} />
    {!approver ? <Card className="p-10 text-center text-sm text-ink-700">Only finance approvers have an inbox. Preparers follow their cases on the Cases page.</Card> : err !== undefined ? <ErrorBanner error={err} /> : items === null ? <Skeleton className="h-40" /> :
      <Card><CardHeader title="Needs your decision" icon={<Inbox className="h-4 w-4" />} right={<Badge tone="amber">{items.length}</Badge>} />
        {items.length ? <ul className="divide-y divide-line">{items.map(i => <li key={i.caseId}>
          <Link href={`/case/?id=${i.caseId}&tab=review`} className="flex flex-wrap items-center gap-3 px-5 py-4 hover:bg-brand-50/40">
            <div className="min-w-0 flex-1"><p className="font-mono text-xs text-brand-700">{i.caseId}</p><p className="font-medium text-ink-950">{i.msmeName}</p>
              <p className="text-xs text-ink-600">Routed to {ROUTE[i.route ?? ''] ?? 'not yet routed'}</p></div>
            {i.held ? <Badge tone="violet"><PauseCircle aria-hidden className="mr-1 inline h-3.5 w-3.5" />HELD at exactly ₹1.5 crore</Badge> : <Badge tone="amber">Awaiting decision</Badge>}
            <ArrowRight aria-hidden className="h-4 w-4 text-ink-400" /></Link></li>)}</ul>
          : <p className="p-10 text-center text-sm text-ink-600">Nothing needs your decision.</p>}
      </Card>}
    <p className="mt-6 text-center text-sm text-ink-600">Approval is internal and is not loan acceptance.</p>
  </>);
}
