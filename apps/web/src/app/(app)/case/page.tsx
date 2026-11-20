'use client';
import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { ArrowLeft, GitBranch, UserCheck, Upload, LineChart, Scale, FileCheck2, ScrollText, MessageCircleQuestion, FileText } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { Card, StageBadge, Tabs, Skeleton, Badge, STAGE_LABEL } from '@/components/ui';
import { caseService, onboardingService, workingCapitalService, lendWiseService, supervisorService } from '@/services';
import type { CaseRecord, ReadinessResult, FundingAssessment, OfferView, WorkflowGate } from '@/types';
import Workflow from '@/components/case/Workflow';
import RunPanel, { overlay, type Live } from '@/components/case/RunPanel';
import { d } from '@/lib/format';
import { Figure } from '@/components/Figure';
// The conversation loads when its tab opens (it is shared with the Ask CredAssure panel), keeping the case page in budget.
// Each tab's view loads when the tab opens (U6 budget: initial JS ≤ 250 kB gzip on /case/).
const tab = (load: () => Promise<{ default: React.ComponentType<never> }>) => dynamic(load, { ssr: false, loading: () => <Skeleton className="h-64" /> });
const Readiness = tab(() => import('@/components/case/Readiness')) as unknown as typeof import('@/components/case/Readiness').default;
const Documents = tab(() => import('@/components/case/Documents')) as unknown as typeof import('@/components/case/Documents').default;
const Funding = tab(() => import('@/components/case/Funding')) as unknown as typeof import('@/components/case/Funding').default;
const Lenders = tab(() => import('@/components/case/Lenders')) as unknown as typeof import('@/components/case/Lenders').default;
const Review = tab(() => import('@/components/case/Review')) as unknown as typeof import('@/components/case/Review').default;
const Report = tab(() => import('@/components/case/Report')) as unknown as typeof import('@/components/case/Report').default;
const History = tab(() => import('@/components/case/History')) as unknown as typeof import('@/components/case/History').default;
const Copilot = dynamic(() => import('@/components/case/Copilot'), { ssr: false, loading: () => <Skeleton className="h-40" /> });

type Tab = 'workflow' | 'readiness' | 'documents' | 'funding' | 'lenders' | 'review' | 'copilot' | 'report' | 'audit';
const TABS = [
  { id: 'workflow', label: 'Workflow', icon: <GitBranch className="h-4 w-4" /> }, { id: 'readiness', label: 'Readiness', icon: <UserCheck className="h-4 w-4" /> },
  { id: 'documents', label: 'Documents', icon: <Upload className="h-4 w-4" /> }, { id: 'funding', label: 'Funding gap', icon: <LineChart className="h-4 w-4" /> },
  { id: 'lenders', label: 'Lender offers', icon: <Scale className="h-4 w-4" /> }, { id: 'review', label: 'Review & approval', icon: <FileCheck2 className="h-4 w-4" /> },
  { id: 'copilot', label: 'Ask CredAssure', icon: <MessageCircleQuestion className="h-4 w-4" /> }, { id: 'report', label: 'Report', icon: <FileText className="h-4 w-4" /> },
  { id: 'audit', label: 'History', icon: <ScrollText className="h-4 w-4" /> },
] as { id: Tab; label: string; icon: React.ReactNode }[];

function CaseView() {
  const sp = useSearchParams(); const router = useRouter(); const user = useUser();
  const id = sp.get('id') ?? ''; const tab = (sp.get('tab') as Tab) || 'workflow';
  const [c, setC] = useState<CaseRecord | null | undefined>(null);
  const [r, setR] = useState<ReadinessResult | null>(); const [a, setA] = useState<FundingAssessment | null>(); const [cmp, setCmp] = useState<OfferView | null>(); const [g, setG] = useState<WorkflowGate[]>(); const [loadErr, setLoadErr] = useState(''); const [live, setLive] = useState<Live | null>(null);
  const load = useCallback(async () => {
    try {
      const x = await caseService.get(id); setC(x); if (!x) return;
      const [rr, gg, aa, cc] = await Promise.all([onboardingService.checkReadiness(x).catch(() => null), supervisorService.gates(x), workingCapitalService.assess(x), lendWiseService.compare(x).catch(() => null)]);
      setR(rr); setG(gg); setA(aa); setCmp(cc); setLoadErr('');
    } catch (e) { setLoadErr((e as Error).message); setC(c => c ?? undefined); }
  }, [id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => setLive(null), [id]); // a run log belongs to one case
  const setTab = (t: Tab) => router.replace(`/case/?id=${id}&tab=${t}`, { scroll: false });
  if (c === undefined) return <Card className="p-10 text-center">Case not found. <Link href="/cases/" className="text-brand-600">Back to cases</Link></Card>;
  if (!c) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-96" /></div>;
  const NotYet = ({ what }: { what: string }) => <Card className="p-10 text-center"><p className="font-semibold text-slate-700">Not available yet</p><p className="mt-1 text-sm text-slate-500">{what} appears here once the workflow has reached that step (case is at: {(STAGE_LABEL[c.stage]?.[0] ?? c.stage).toLowerCase()}).{c.question ? ' The Workflow tab has a question for you.' : ''}</p></Card>;
  return (<>
    <Link href="/cases/" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"><ArrowLeft className="h-4 w-4" />Cases</Link>
    <Card className="mb-6 overflow-hidden animate-fadein">
      <div className="keep-light bg-gradient-to-r from-slate-950 via-brand-950 to-violet-950 p-5 text-white sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-xs text-brand-200">{c.id}</p><h1 className="mt-1 text-xl font-bold sm:text-2xl">{c.msmeName}</h1><p className="text-sm text-slate-300">Customer due date {d(c.customerDueDate)}</p></div><StageBadge s={c.stage} /></div>
        <div className="mt-5 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div><p className="text-xs text-slate-400">Order</p><p className="font-medium">{c.orderRef} · <Figure value={c.orderValue} label="Order value" caseId={c.id} /></p></div>
          <div><p className="text-xs text-slate-400">Requested</p><Figure className="font-medium" value={c.requestedAmount} label="Requested amount" caseId={c.id} /></div>
          <div><p className="text-xs text-slate-400">Validated need</p>{a ? <Figure className="font-semibold text-emerald-300" value={a.recommendedAmount} label="Validated need" caseId={c.id} showApprox /> : <p className="font-semibold">—</p>}</div>
          <div><p className="text-xs text-slate-400">Next action</p><p className="font-medium">{c.nextAction ?? '—'}</p></div>
        </div>
      </div>
      <div className="p-3"><Tabs tabs={TABS} value={tab} onChange={setTab} /></div>
    </Card>
    <div key={tab} className="animate-fadein">
      {tab === 'workflow' && (g ? <><RunPanel c={c} gates={g} canRun={user.role === 'PREPARER'} live={live} setLive={setLive} onDone={load} /><Workflow gates={overlay(g, live)} /></> : <Skeleton className="h-96" />)}
      {tab === 'readiness' && (r ? <Readiness r={r} /> : r === null ? <NotYet what="The preparer check" /> : <Skeleton className="h-96" />)}
      {loadErr && <p role="alert" className="mb-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{loadErr}</p>}
      {tab === 'documents' && <Documents caseId={c.id} canEdit={user.role === 'PREPARER'} locked={['AWAITING_APPROVAL', 'ROUTING_HELD', 'APPROVED', 'REJECTED'].includes(c.stage)} onChange={load} />}
      {tab === 'funding' && (a ? <Funding a={a} /> : <NotYet what="The validated funding assessment" />)}
      {tab === 'lenders' && (cmp ? <Lenders c={c} view={cmp} canNegotiate={user.role === 'PREPARER'} onChange={load} /> : <NotYet what="The lender comparison" />)}
      {tab === 'review' && <Review c={c} need={a?.recommendedAmount} user={user} onChange={load} />}
      {tab === 'copilot' && <Copilot caseId={c.id} />}
      {tab === 'report' && <Report caseId={c.id} stamp={c.stage} canRegenerate={user.role === 'PREPARER'} />}
      {tab === 'audit' && <History caseId={c.id} technical={user.role === 'EVALUATOR'} />}
    </div>
  </>);
}
export default function Page() { return <Suspense fallback={<Skeleton className="h-96" />}><CaseView /></Suspense>; }
