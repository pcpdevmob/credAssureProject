'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Building2, ShoppingCart, IndianRupee, Info, Lock } from 'lucide-react';
import { useUser } from '@/components/AppShell';
import { PageHeader } from '@/components/PageHeader';
import { Card, CardHeader, Input, Label, Button } from '@/components/ui';
import { caseService } from '@/services';
import { inr, inrShort } from '@/lib/format';

export default function NewCase() {
  const u = useUser(); const r = useRouter(); const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const [f, setF] = useState({ msmeName: 'Indus Circuitworks Pvt Ltd', orderRef: 'PO-AUR-3307', orderValue: 42000000, customerDueDate: '2027-03-15', requestedAmount: 20000000 });
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.type === 'number' ? +e.target.value : e.target.value });
  if (u.role !== 'PREPARER') return <Card className="mx-auto mt-10 max-w-md p-8 text-center"><Lock className="mx-auto h-8 w-8 text-slate-400" /><p className="mt-3 font-semibold">Only Proposal Preparers can create cases.</p><p className="text-sm text-slate-500">Approvers review cases from the approval inbox.</p></Card>;
  const submit = async (e: React.FormEvent) => { e.preventDefault(); setBusy(true); try { const c = await caseService.create(f, u); r.push(`/case/?id=${c.id}&tab=documents`); } catch (x) { setErr((x as Error).message); setBusy(false); } };
  return (<>
    <PageHeader title="Create case" sub="Step 1 of the workflow. The Supervisor will run the readiness check as soon as you create it." />
    <form onSubmit={submit} className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card><CardHeader title="MSME details" icon={<Building2 className="h-4 w-4" />} /><div className="grid gap-4 p-5 sm:grid-cols-2">
          <div className="sm:col-span-2"><Label>MSME legal name</Label><Input required value={f.msmeName} onChange={set('msmeName')} /></div>
        </div></Card>
        <Card><CardHeader title="Order context" icon={<ShoppingCart className="h-4 w-4" />} /><div className="grid gap-4 p-5 sm:grid-cols-2">
          <div><Label>PO reference</Label><Input required value={f.orderRef} onChange={set('orderRef')} /></div>
          <div><Label hint={inrShort(f.orderValue)}>Order value (₹)</Label><Input type="number" min={0} required value={f.orderValue} onChange={set('orderValue')} /></div>
          <div><Label>Customer due date</Label><Input type="date" required value={f.customerDueDate} onChange={set('customerDueDate')} /></div>
        </div></Card>
        <Card><CardHeader title="Indicative financing request" icon={<IndianRupee className="h-4 w-4" />} /><div className="grid gap-4 p-5 sm:grid-cols-2">
          <div><Label hint={inrShort(f.requestedAmount)}>Requested amount (₹)</Label><Input type="number" min={0} required value={f.requestedAmount} onChange={set('requestedAmount')} /></div>
          <div><Label>Currency</Label><Input value="INR (₹)" disabled /></div>
        </div></Card>
      </div>
      <div className="space-y-4">
        <Card className="sticky top-20 p-5">
          <p className="text-sm text-slate-500">Indicative request</p><p className="num mt-1 text-3xl font-bold text-slate-900">{inr(f.requestedAmount)}</p>
          <div className="mt-4 flex gap-2 rounded-xl bg-amber-50 p-3 text-xs text-amber-800"><Info className="h-4 w-4 shrink-0" />This is not the final loan amount. The Working Capital Advisory Agent calculates the actual need from validated cash-flow data, and approval routing uses that validated amount.</div>
          {err && <p role="alert" className="mt-3 rounded-xl bg-rose-50 p-3 text-sm text-rose-700">{err}</p>}
          <Button className="mt-5 w-full" size="lg" loading={busy}>Create case</Button>
        </Card>
      </div>
    </form>
  </>);
}
