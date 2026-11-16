'use client';
import { notFound } from 'next/navigation';
import { FileSearch } from 'lucide-react';
import { ProvenanceProvider, Figure } from '@/components/Figure';
import { LineageView } from '@/components/ProvenanceDrawer';
import ErrorBanner from '@/components/ErrorBanner';
import EmptyState from '@/components/EmptyState';
import ThemeToggle from '@/components/ThemeToggle';
import { Badge, Button, Card, CardHeader, GateBadge, Input, Label } from '@/components/ui';
import { toProblem } from '@/lib/problem';
import { lineageFull, lineageLegacy, lineageRefRate } from '@/mocks/fixtures';
import type { GateDecision } from '@/types';

// Dev-only component gallery (/__gallery): every U1 building block in one place, from fixtures, with no API calls.
const GATES: GateDecision[] = ['GO', 'NO_GO', 'NEEDS_INPUT', 'ERROR', 'HELD', 'RUNNING', 'PENDING'];
const SWATCHES = ['bg-canvas', 'bg-white', 'bg-sunken', 'bg-line', 'bg-ink-900', 'bg-brand-600', 'bg-brand-700', 'bg-gold-400', 'bg-gold-700', 'bg-rose-700'];

export default function Gallery() {
  if (process.env.NODE_ENV === 'production') notFound();
  return (
    <ProvenanceProvider>
      <main className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div><h1 className="font-display text-3xl font-semibold text-ink-950">Component gallery</h1><p className="text-ink-500">CredAssure U1 foundations · dev only</p></div>
          <div className="keep-light rounded-full bg-ink-950 p-1"><ThemeToggle /></div>
        </header>

        <Card><CardHeader title="Colour tokens" sub="One token set; dark values swap under data-theme" />
          <div className="grid grid-cols-5 gap-3 p-5 sm:grid-cols-10">{SWATCHES.map(s => <div key={s}><div className={`h-12 rounded-xl ring-1 ring-line ${s}`} /><p className="mt-1 font-mono text-[10px] text-ink-600">{s.slice(3)}</p></div>)}</div></Card>

        <Card><CardHeader title="Type" />
          <div className="space-y-2 p-5"><p className="font-display text-4xl font-semibold text-ink-950">Validated need</p><p className="text-base text-ink-800">Body text in Inter, 14–16 px.</p><p className="num text-sm text-ink-600">Tabular figures: ₹1,42,00,000 · ₹30,00,000 · 12.84%</p></div></Card>

        <Card><CardHeader title="Figures" sub="Exact amount + ◈ provenance; ≈ short form only beside it" />
          <div className="flex flex-wrap gap-8 p-5 text-lg">
            <Figure value={{ display: '₹1,42,00,000', paise: 1420000000, key: 'wc.recommended_amount' }} label="Validated need" showApprox />
            <Figure value={{ display: '₹42,50,000', paise: 425000000 }} label="Lakh amount" showApprox />
            <Figure value={{ display: '₹75,000', paise: 7500000 }} label="Small amount" showApprox />
            <Figure value={{ display: '12.84%' }} label="APR" />
          </div>
          <p className="px-5 pb-5 text-sm text-ink-500">Gallery figures have no case, so each drawer reads "source not available yet".</p></Card>

        <Card><CardHeader title="Gate states" sub="Shape + text + tone, never colour alone" />
          <div className="flex flex-wrap gap-2 p-5">{GATES.map(g => <GateBadge key={g} d={g} />)}</div></Card>

        <div className="grid gap-6 lg:grid-cols-3">
          {[['Full lineage', lineageFull], ['Legacy fact: null producer, superseded', lineageLegacy], ['Reference rate: doc id only', lineageRefRate]].map(([t, l]) => (
            <Card key={t as string} className="overflow-hidden"><CardHeader title={t as string} /><LineageView l={l as typeof lineageFull} onOpenFact={() => undefined} /></Card>
          ))}
        </div>

        <Card><CardHeader title="Errors and empty states" />
          <div className="space-y-4 p-5">
            <ErrorBanner error={toProblem(409, { code: 'CONFLICT', detail: 'The case changed since you opened it.' })} />
            <ErrorBanner error={toProblem(500, { code: 'INTERNAL_ERROR', detail: 'Traceback (most recent call last)…' })} />
            <ErrorBanner error={new TypeError('Failed to fetch')} />
            <div><Label htmlFor="g-buffer" hint="(field error)">Minimum cash buffer</Label><Input id="g-buffer" aria-invalid aria-describedby="g-buffer-err" defaultValue="ten lakh" className="border-rose-700" /><p id="g-buffer-err" className="mt-1 text-sm text-rose-700">opening_position.json, row 1: min_cash_buffer must be an amount in rupees.</p></div>
            <EmptyState icon={FileSearch} title="No cases yet" hint="Create a case to start the readiness check." action={<Button>New case</Button>} />
          </div></Card>

        <Card><CardHeader title="Buttons and badges" />
          <div className="flex flex-wrap items-center gap-3 p-5"><Button>Primary</Button><Button variant="outline">Outline</Button><Button variant="success">Approve proposal</Button><Button variant="danger">Reject</Button><Button variant="ghost">Ghost</Button><Button loading>Running</Button><Badge tone="green">Comparable</Badge><Badge tone="red">Unaffordable</Badge><Badge tone="amber">Not re-audited</Badge></div></Card>
      </main>
    </ProvenanceProvider>
  );
}
