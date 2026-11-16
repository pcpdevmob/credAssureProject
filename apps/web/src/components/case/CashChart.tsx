'use client';
import { Bar, BarChart, Cell, ReferenceDot, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts';
import type { CashTable } from '@/types';
import { approx, inrFromPaise } from '@/lib/money';

// The 26-week cash position (WC-03/04). The gateway decides which weeks are in shortfall and which are below the buffer;
// this component only draws them. Meaning is carried by shape and text (hatch, dashed line, diamond), never colour alone.

/** One sentence for assistive tech and the caption; every number is a gateway display string. */
export function chartSummary(t: CashTable, peakDisplay: string): string {
  const weeks = t.rows.filter(r => r.shortfall).map(r => r.week);
  const lowest = t.peakWeek === null ? '' : ` Lowest point in week ${t.peakWeek} (peak shortfall ${peakDisplay}).`;
  const buf = t.buffer ? ` Minimum cash buffer ${t.buffer.display}.` : '';
  return `${t.rows.length}-week cumulative cash. ${weeks.length ? `Cash is below zero in ${weeks.length} weeks: ${weeks.join(', ')}.` : 'Cash never falls below zero.'}${lowest}${buf}`;
}

const tick = (p: number) => (approx(p)?.replace('≈ ', '') ?? inrFromPaise(p));

// ponytail: weekly rows are plain figures; only the aggregates (peak, buffer, bridge) are ledger facts with lineage.
export default function CashChart({ cash, peakDisplay }: { cash: CashTable; peakDisplay: string }) {
  const data = cash.rows.map(r => ({ week: r.week, v: r.cumulative.paise ?? 0, shortfall: r.shortfall }));
  const peak = data.find(d => d.week === cash.peakWeek);
  const bufferPaise = cash.buffer?.paise;
  const summary = chartSummary(cash, peakDisplay);
  return (<div>
    <p className="mb-2 text-sm text-ink-700">{summary}</p>
    <div role="img" aria-label={summary} className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 12, right: 12, bottom: 4, left: 4 }} accessibilityLayer={false}>
          <defs>
            <pattern id="shortfall-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
              <rect width="6" height="6" fill="var(--fb-rose-100)" /><line x1="0" y1="0" x2="0" y2="6" stroke="var(--fb-rose-700)" strokeWidth="2.5" />
            </pattern>
          </defs>
          <XAxis dataKey="week" tick={{ fontSize: 12, fill: 'var(--fb-ink-600)' }} tickLine={false} interval="preserveStartEnd" minTickGap={12} label={{ value: 'Week', position: 'insideBottomRight', offset: -2, fontSize: 12, fill: 'var(--fb-ink-600)' }} />
          <YAxis tickFormatter={tick} width={80} domain={[(min: number) => Math.floor(min * 1.3), 'auto']} tick={{ fontSize: 12, fill: 'var(--fb-ink-600)' }} tickLine={false} axisLine={false} />
          <ReferenceLine y={0} stroke="var(--fb-ink-500)" />
          {bufferPaise !== undefined && <ReferenceLine y={bufferPaise} stroke="var(--fb-gold-600)" strokeWidth={2} strokeDasharray="6 4" />}
          <Bar dataKey="v" isAnimationActive={false}>
            {data.map(d => <Cell key={d.week} fill={d.shortfall ? 'url(#shortfall-hatch)' : 'var(--fb-brand-600)'} stroke={d.shortfall ? 'var(--fb-rose-700)' : undefined} />)}
          </Bar>
          {peak && <ReferenceDot x={peak.week} y={peak.v} r={0} ifOverflow="extendDomain"
            label={{ value: `◆ Peak shortfall, week ${peak.week}`, position: 'bottom', fontSize: 12, fontWeight: 600, fill: 'var(--fb-rose-700)' }} />}
        </BarChart>
      </ResponsiveContainer>
    </div>
    <ul aria-label="Chart key" className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-700">
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block h-3 w-3 rounded-sm bg-brand-600" />Cash at or above zero</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block h-3 w-3 rounded-sm border border-rose-700" style={{ background: 'repeating-linear-gradient(45deg, var(--fb-rose-100) 0 3px, var(--fb-rose-700) 3px 5px)' }} />Shortfall week (below zero)</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="inline-block w-5 border-t-2 border-dashed border-gold-600" />Minimum cash buffer{cash.buffer ? ` ${cash.buffer.display}` : ''}</li>
      <li className="flex items-center gap-1.5"><span aria-hidden className="text-rose-700">◆</span>Peak shortfall week</li>
    </ul>
    <details className="mt-3 rounded-xl border border-line">
      <summary className="cursor-pointer px-4 py-2 text-sm font-medium text-ink-800">Weekly cash table</summary>
      <div className="max-h-96 overflow-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Weekly inflow, outflow and cumulative cash, with shortfall and buffer status</caption>
          <thead className="sticky top-0 bg-sunken text-left text-xs text-ink-600"><tr><th scope="col" className="px-4 py-2">Week</th><th scope="col" className="px-2 py-2 text-right">Inflow</th><th scope="col" className="px-2 py-2 text-right">Outflow</th><th scope="col" className="px-2 py-2 text-right">Cumulative</th><th scope="col" className="px-4 py-2">Status</th></tr></thead>
          <tbody>{cash.rows.map(r => (
            <tr key={r.week} className="border-t border-line">
              <th scope="row" className="num px-4 py-1.5 text-left font-medium">{r.week}</th>
              <td className="num px-2 py-1.5 text-right">{r.inflow.display}</td>
              <td className="num px-2 py-1.5 text-right">{r.outflow.display}</td>
              <td className="num px-2 py-1.5 text-right font-medium">{r.cumulative.display}</td>
              <td className="px-4 py-1.5 text-xs">{r.week === cash.peakWeek ? '◆ Peak shortfall' : r.shortfall ? '▨ Shortfall' : r.belowBuffer ? 'Below buffer' : 'OK'}</td>
            </tr>))}</tbody>
        </table>
      </div>
    </details>
  </div>);
}
