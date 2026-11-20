'use client';
// Case history across the cases this user can see: pick a case, read its history in plain words (GET /history).
// Evaluators can open the technical audit log from there. There is no cross-case audit endpoint, so one case at a time.
import { useEffect, useState } from 'react';
import { PageHeader } from '@/components/PageHeader';
import History from '@/components/case/History';
import ErrorBanner from '@/components/ErrorBanner';
import { useUser } from '@/components/AppShell';
import { Card, Skeleton } from '@/components/ui';
import { caseService } from '@/services';
import type { CaseRecord } from '@/types';

export default function Audit() {
  const user = useUser();
  const [cases, setCases] = useState<CaseRecord[] | null>(null); const [err, setErr] = useState<unknown>(); const [id, setId] = useState('');
  useEffect(() => { caseService.list().then(cs => { const sorted = [...cs].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)); setCases(sorted); setId(sorted[0]?.id ?? ''); }, setErr); }, []);
  return (<>
    <PageHeader title="Case history" sub="Who did what and when on each case. Entries cannot be edited or removed." />
    {err !== undefined ? <ErrorBanner error={err} /> : !cases ? <Skeleton className="h-64" /> : !cases.length ? <Card className="p-10 text-center text-sm text-ink-600">No cases yet.</Card> : <div className="space-y-4">
      <label className="block text-sm font-medium text-ink-900">Case
        <select value={id} onChange={e => setId(e.target.value)} className="ml-2 h-10 max-w-full rounded-xl border border-ink-400 bg-white px-3 text-sm">
          {cases.map(c => <option key={c.id} value={c.id}>{c.id} · {c.msmeName}</option>)}</select></label>
      {id && <History key={id} caseId={id} technical={user.role === 'EVALUATOR'} />}
    </div>}
  </>);
}
