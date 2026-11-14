'use client';
import type { FundingAssessment } from '@/types';
import { Card, CardHeader, GateBadge } from '../ui';
import { Area, AreaChart, Bar, CartesianGrid, ComposedChart, Legend, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis, PieChart, Pie, Cell } from 'recharts';
import { CHART, ink, brand, gold } from '@/styles/tokens';
import { TrendingDown, Info, AlertTriangle } from 'lucide-react';
import { inr, inrShort } from '@/lib/format';
const C = CHART.series;
export default function Funding({ a }: { a: FundingAssessment }) {
  const data = a.periods.map(p => ({ ...p, outflow: -(p.materialOut + p.labourOut + p.overheadOut + p.logisticsOut) }));
  const diff = a.requestedAmount - a.recommendedAmount;
  const tip = (v: number) => inrShort(v);
  return (<div className="space-y-6">
    <div className="grid gap-4 md:grid-cols-3">
      <Card className="p-5"><p className="text-sm text-slate-500">Requested (indicative)</p><p className="num mt-1 text-2xl font-semibold text-slate-400 line-through decoration-slate-300">{inr(a.requestedAmount)}</p><p className="text-xs text-slate-500">{inrShort(a.requestedAmount)} · entered by preparer</p></Card>
      <Card className="relative overflow-hidden p-5 ring-2 ring-brand-500"><div className="absolute right-0 top-0 h-24 w-24 rounded-full bg-brand-500/10 blur-2xl" /><p className="text-sm text-brand-700">Validated funding need</p><p className="num mt-1 text-2xl font-bold text-slate-900">{inr(a.recommendedAmount)}</p><div className="mt-1 flex items-center gap-2 text-xs"><GateBadge d={a.decision} /><span className="text-slate-500">{inrShort(a.recommendedAmount)}</span></div></Card>
      <Card className="p-5"><p className="text-sm text-slate-500">Difference vs request</p><p className={`num mt-1 flex items-center gap-1 text-2xl font-semibold ${diff >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}><TrendingDown className="h-5 w-5" />{inrShort(Math.abs(diff))}</p><p className="text-xs text-slate-500">{diff >= 0 ? 'less borrowing than requested' : 'more than requested'} ({((diff / a.requestedAmount) * 100).toFixed(1)}%)</p></Card>
    </div>
    <div className="grid gap-6 xl:grid-cols-3">
      <Card className="xl:col-span-2"><CardHeader title="Projected cash position" sub={`${a.horizonMonths}-month horizon · peak shortfall ${inrShort(a.peakShortfall)} in ${a.peakPeriod}`} />
        <div className="h-80 p-3"><ResponsiveContainer><ComposedChart data={data} margin={{ left: 8, right: 8 }}>
          <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={CHART.primary} stopOpacity={0.35} /><stop offset="100%" stopColor={CHART.primary} stopOpacity={0} /></linearGradient></defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={CHART.grid} /><XAxis dataKey="period" tick={{ fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis tickFormatter={tip} tick={{ fontSize: 11 }} width={70} axisLine={false} tickLine={false} /><Tooltip formatter={(v: number) => inr(v)} /><Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="receipts" name="Receipts" fill={CHART.positive} radius={[6, 6, 0, 0]} barSize={18} /><Bar dataKey="outflow" name="Outflows" fill={CHART.negative} radius={[0, 0, 6, 6]} barSize={18} />
          <Area type="monotone" dataKey="closingCash" name="Closing cash" stroke={CHART.tertiary} strokeWidth={2.5} fill="url(#g)" />
          <ReferenceLine y={0} stroke={ink[300]} /><ReferenceLine y={a.minCashBuffer} stroke={CHART.warn} strokeDasharray="5 5" label={{ value: 'Min buffer', fontSize: 11, fill: gold[700], position: 'insideTopRight' }} />
        </ComposedChart></ResponsiveContainer></div></Card>
      <Card><CardHeader title="How the need is calculated" sub="Deterministic, reproducible" />
        <div className="space-y-2 p-5 text-sm num">
          <div className="flex justify-between"><span className="text-slate-500">Peak cash shortfall ({a.peakPeriod})</span><span>{inr(a.peakShortfall)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">+ Minimum cash buffer</span><span>{inr(a.minCashBuffer)}</span></div>
          <div className="flex justify-between"><span className="text-slate-500">− Existing unused facility</span><span>({inr(a.existingFacility)})</span></div>
          <div className="flex justify-between border-t border-slate-100 pt-2 font-semibold"><span>Recommended facility</span><span className="text-brand-700">{inr(a.recommendedAmount)}</span></div>
        </div>
        <div className="h-44"><ResponsiveContainer><PieChart><Pie data={a.drivers} dataKey="amount" nameKey="label" innerRadius={42} outerRadius={70} paddingAngle={3}>{a.drivers.map((_, i) => <Cell key={i} fill={C[i]} />)}</Pie><Tooltip formatter={(v: number) => inrShort(v)} /></PieChart></ResponsiveContainer></div>
        <ul className="space-y-1 px-5 pb-5 text-xs">{a.drivers.map((d, i) => <li key={d.label} className="flex justify-between"><span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: C[i] }} />{d.label}</span><span className="num">{inrShort(d.amount)}</span></li>)}</ul>
      </Card>
    </div>
    <div className="grid gap-6 lg:grid-cols-2">
      <Card><CardHeader title="Period-by-period cash flow" /><div className="overflow-x-auto"><table className="w-full text-sm num"><thead><tr className="text-left text-xs uppercase text-slate-500"><th className="px-4 py-2">Period</th><th className="px-3 py-2 text-right">Opening</th><th className="px-3 py-2 text-right">Receipts</th><th className="px-3 py-2 text-right">Outflows</th><th className="px-4 py-2 text-right">Closing</th></tr></thead>
        <tbody>{data.map(p => <tr key={p.period} className={`border-t border-slate-50 ${p.period === a.peakPeriod ? 'bg-rose-50/60' : ''}`}><td className="px-4 py-2 font-medium">{p.period}</td><td className="px-3 py-2 text-right">{inrShort(p.openingCash)}</td><td className="px-3 py-2 text-right text-emerald-600">{inrShort(p.receipts)}</td><td className="px-3 py-2 text-right text-rose-600">{inrShort(-p.outflow)}</td><td className={`px-4 py-2 text-right font-semibold ${p.closingCash < 0 ? 'text-rose-600' : ''}`}>{inrShort(p.closingCash)}</td></tr>)}</tbody></table></div></Card>
      <Card><CardHeader title="Assumptions & warnings" icon={<Info className="h-4 w-4" />} /><ul className="space-y-2 p-5 text-sm">{a.assumptions.map(x => <li key={x} className="flex gap-2"><Info className="mt-0.5 h-4 w-4 shrink-0 text-brand-500" />{x}</li>)}{a.warnings.map(x => <li key={x} className="flex gap-2 text-amber-700"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{x}</li>)}</ul></Card>
    </div>
  </div>);
}
