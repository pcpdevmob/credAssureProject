'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, ShoppingCart, IndianRupee, Info, Lock, FileStack } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardHeader, Input, Label, Button } from '@/components/ui';
import { MoneyInput } from '@/components/MoneyInput';
import ErrorBanner from '@/components/ErrorBanner';
import { caseService } from '@/services';
import { inrFromPaise, paiseFromInput } from '@/lib/money';
import { ApiProblem } from '@/lib/problem';
import { ACCEPT, pendingUploads } from '@/lib/intake';
const ORDER = '₹4,20,00,000', REQUEST = '2 crore';

export default function NewCase() {
  const u = useUser(); const r = useRouter(); const [busy, setBusy] = useState(false); const [err, setErr] = useState<unknown>();
  const [f, setF] = useState({ msmeName: 'Indus Circuitworks Pvt Ltd', orderRef: 'PO-AUR-3307', customerDueDate: '2027-03-15' });
  const [docs, setDocs] = useState<File[]>([]);
  const [order, setOrder] = useState(paiseFromInput(ORDER)); const [req, setReq] = useState(paiseFromInput(REQUEST));
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const fe = (field: string) => err instanceof ApiProblem ? err.fieldErrors.find(x => x.field === field)?.reason : undefined;
  if (u.role !== 'PREPARER') return <Card className="mx-auto mt-10 max-w-md p-8 text-center"><Lock className="mx-auto h-8 w-8 text-slate-400" /><p className="mt-3 font-semibold">Only Proposal Preparers can create cases.</p><p className="text-sm text-slate-500">Approvers review cases from the approval inbox.</p></Card>;
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); if (order === null || req === null) return; setBusy(true); setErr(undefined);
    try { const c = await caseService.create({ ...f, orderValuePaise: order, requestedPaise: req }, u); pendingUploads.put(c.id, docs); r.push(`/case/?id=${c.id}&tab=documents`); } catch (x) { setErr(x); setBusy(false); }
  };
  return (<>
    <PageHeader title="Create case" sub="Step 1 of the workflow. The Supervisor will run the readiness check as soon as you create it." />
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card><CardHeader title="MSME details" icon={<Building2 className="h-4 w-4" />} /><div className="grid gap-4 p-5 sm:grid-cols-2">
          <div className="sm:col-span-2"><Label htmlFor="msme">MSME legal name</Label><Input id="msme" required value={f.msmeName} onChange={set('msmeName')} /></div>
        </div></Card>
        <Card><CardHeader title="Order context" icon={<ShoppingCart className="h-4 w-4" />} /><div className="grid gap-4 p-5 sm:grid-cols-2">
          <div><Label htmlFor="po">PO reference</Label><Input id="po" required value={f.orderRef} onChange={set('orderRef')} /></div>
          <MoneyInput label="Order value" initial={ORDER} onPaise={setOrder} error={fe('order_value_paise')} />
          <div><Label htmlFor="due">Customer due date</Label><Input id="due" type="date" required value={f.customerDueDate} onChange={set('customerDueDate')} /></div>
        </div></Card>
        <Card><CardHeader title="Indicative financing request" icon={<IndianRupee className="h-4 w-4" />} /><div className="grid gap-4 p-5 sm:grid-cols-2">
          <MoneyInput label="Requested amount" initial={REQUEST} onPaise={setReq} error={fe('indicative_amount_paise')} />
          <div><Label htmlFor="cur">Currency</Label><Input id="cur" value="INR (₹)" disabled /></div>
        </div></Card>
        <Card><CardHeader title="Documents (optional)" sub="Add the case's Excel workbook and the lenders' PDFs now; they are read as soon as the case is created. You can also add them later." icon={<FileStack className="h-4 w-4" />} /><div className="space-y-2 p-5">
          <Label htmlFor="new-docs">Excel workbook (.xlsx) and lender PDFs (offer letter, Key Facts Statement, schedule of charges)</Label>
          <input id="new-docs" type="file" multiple accept={ACCEPT} className="max-w-full text-xs file:mr-2 file:rounded-full file:border-0 file:bg-ink-900 file:px-3 file:py-1.5 file:text-white"
            onChange={e => setDocs(Array.from(e.target.files ?? []))} />
          {docs.length > 0 && <ul className="list-disc pl-5 text-sm text-slate-700">{docs.map(d => <li key={d.name}>{d.name}</li>)}</ul>}
        </div></Card>
      </div>
      <div className="space-y-4">
        <Card className="sticky top-20 p-5">
          <p className="text-sm text-slate-500">Indicative request</p><p className="num mt-1 text-3xl font-bold text-slate-900">{req === null ? '—' : inrFromPaise(req)}</p>
          <div className="mt-4 flex gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-800"><Info className="h-4 w-4 shrink-0" />This is not the final loan amount. The Working Capital Advisory Agent calculates the actual need from validated cash-flow data, and approval routing uses that validated amount.</div>
          {err !== undefined && <ErrorBanner className="mt-3" error={err} />}
          <Button className="mt-5 w-full" size="lg" loading={busy} disabled={order === null || req === null}>Create case</Button>
        </Card>
      </div>
    </form>
  </>);
}
