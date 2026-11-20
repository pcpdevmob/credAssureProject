'use client';
// P9 safety panel (plan v3.4 §6, OWASP ASI09): what the guardrails did on this case, shown before the approver attests.
import { useEffect, useState } from 'react';
import { ShieldAlert } from 'lucide-react';
import { Card, CardHeader, Badge } from '../ui';
import { safetyService, type SafetySummary } from '@/services/safety';

const LABEL: Record<string, string> = { block: 'Blocked', redact: 'Redacted', flag: 'Flagged for review', cap: 'Quotes shortened', critic_blocked: 'Drafts held back by the accuracy check', critic_fallback: 'Fixed wording used', llm_fallback: 'AI unavailable, fixed wording used', gate_override: 'Steps stopped by the double-check', injection_flagged: 'Documents flagged for review' };
/** What each safety rule did, in plain words (the code stays visible underneath for evaluators). */
export const RULE_TEXT: Record<string, string> = {
  'R1.chat_pii_redacted': 'A personal ID number typed in the chat was hidden.',
  'R1.upload_case_mismatch': 'A lender document names a different case number. It was kept and flagged.',
  'R1.upload_injection_flagged': 'A file contained text that looks like instructions to the system. It was ignored.',
  'R1.upload_pii_refused': 'A file with a personal ID number (PAN, Aadhaar or bank account) was refused.',
  'R1.upload_protected_attribute': 'A file with a personal attribute (such as religion or caste) was refused; these are never used.',
  'R2.citation_excerpt_capped': 'A quoted passage was shortened.',
  'R2.passage_injection_flagged': 'A source document contained instruction-like text. It was treated as data only.',
  'R3.loop_detected': 'A repeated step was stopped.', 'R3.tool_not_allowed': 'A step that is not allowed was refused.',
  'R4.critic_blocked': 'The accuracy check held back a draft whose figure or source did not match.',
  'R4.model_io_pii_redacted': 'Personal details were hidden from the AI.',
};
const TYPE_TEXT: Record<string, string> = {
  CRITIC_BLOCKED: 'The accuracy check held back a draft whose figure or source did not match.', CRITIC_FALLBACK: 'A fixed, pre-approved wording was used instead of an AI draft.',
  LLM_FALLBACK: 'The AI was unavailable, so fixed wording was used. Figures are unaffected.', GATE_OVERRIDE: 'A double-check disagreed with a step, so the step was stopped.',
  INJECTION_FLAGGED: 'A file contained suspicious or out-of-place text. It was kept as data and ignored.',
};
const TONE: Record<string, 'red' | 'amber' | 'blue' | 'slate'> = { block: 'red', critic_blocked: 'red', gate_override: 'red', flag: 'amber', injection_flagged: 'amber', redact: 'blue' };

export default function SafetyPanel({ caseId }: { caseId: string }) {
  const [s, setS] = useState<SafetySummary | null>(null); const [err, setErr] = useState(false);
  useEffect(() => { safetyService.get(caseId).then(setS).catch(() => setErr(true)); }, [caseId]);
  return (<Card><CardHeader title="Safety checks on this case" sub="What the safety rules and the accuracy check did. The blocked text itself is never shown or stored." icon={<ShieldAlert className="h-4 w-4" />} />
    <div className="p-5 text-sm">
      {err && <p role="alert" className="text-rose-700">Could not load safety events. Reload before deciding.</p>}
      {s && (Object.keys(s.counts).length === 0
        ? <p className="text-ink-600">Nothing was blocked, hidden or flagged on this case.</p>
        : <>
          <ul aria-label="Safety counts" className="flex flex-wrap gap-2">{Object.entries(s.counts).map(([k, n]) => <li key={k}><Badge tone={TONE[k] ?? 'slate'}>{LABEL[k] ?? k}: {n}</Badge></li>)}</ul>
          <ol className="mt-3 divide-y divide-line">{s.events.slice(-20).reverse().map(e => <li key={e.seq} className="py-2"><p className="text-sm text-ink-900">{(e.rule && RULE_TEXT[e.rule]) ?? (e.type === 'INJECTION_FLAGGED' && e.detail === 'flags: KFS_CASE_MISMATCH' ? RULE_TEXT['R1.upload_case_mismatch'] : TYPE_TEXT[e.type]) ?? 'A safety rule acted on this case.'}</p><p className="font-mono text-[11px] text-ink-500">{e.rule ?? e.type}{e.action ? ` · ${e.action}` : ''}{e.detail && <span className="ml-1">· {e.detail}</span>}</p></li>)}</ol>
        </>)}
    </div></Card>);
}
