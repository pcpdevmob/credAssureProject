'use client';
// P9 safety panel (plan v3.4 §6, OWASP ASI09): what the guardrails did on this case, shown before the approver attests.
import { useEffect, useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { Card, CardHeader, Badge } from '../ui';
import { safetyService, type SafetySummary } from '@/services/safety';

const LABEL: Record<string, string> = { block: 'Blocked', redact: 'Redacted', flag: 'Injection flags', cap: 'Excerpts capped', critic_blocked: 'Critic blocks', critic_fallback: 'Template fallbacks', llm_fallback: 'Model fallbacks', gate_override: 'Gate overrides', injection_flagged: 'Injection flags' };
const TONE: Record<string, 'red' | 'amber' | 'blue' | 'slate'> = { block: 'red', critic_blocked: 'red', gate_override: 'red', flag: 'amber', injection_flagged: 'amber', redact: 'blue' };

export default function SafetyPanel({ caseId }: { caseId: string }) {
  const [s, setS] = useState<SafetySummary | null>(null); const [err, setErr] = useState(false);
  useEffect(() => { safetyService.get(caseId).then(setS).catch(() => setErr(true)); }, [caseId]);
  return (<Card><CardHeader title="Safety events" sub="What the guardrails and the Critic did on this case (codes only, never the text)" icon={<ShieldAlert className="h-4 w-4" />} />
    <div className="p-5 text-sm">
      {err && <p role="alert" className="text-rose-700">Could not load safety events. Reload before deciding.</p>}
      {s && (Object.keys(s.counts).length === 0
        ? <p className="text-ink-600">No blocks, redactions, injection flags or Critic findings on this case.</p>
        : <>
          <ul aria-label="Safety counts" className="flex flex-wrap gap-2">{Object.entries(s.counts).map(([k, n]) => <li key={k}><Badge tone={TONE[k] ?? 'slate'}>{LABEL[k] ?? k}: {n}</Badge></li>)}</ul>
          <ol className="mt-3 divide-y divide-line">{s.events.slice(-20).reverse().map(e => <li key={e.seq} className="py-2"><p className="font-mono text-[11px] text-ink-700">{e.rule ?? e.type}{e.action ? ` · ${e.action}` : ''}</p>{e.detail && <p className="text-xs text-ink-600">{e.detail}</p>}</li>)}</ol>
        </>)}
    </div></Card>);
}
