// Every money field: free text in, exact paise out (lib/money.ts paiseFromInput), with the parsed amount shown beside the
// input before submit. The parent gets null while the text is not a valid amount.
import { useId, useState } from 'react';
import { Input, Label } from './ui';
import { approx, inrFromPaise, paiseFromInput } from '@/lib/money';

export function MoneyInput({ label, initial = '', onPaise, error }: { label: string; initial?: string; onPaise: (p: bigint | null) => void; error?: string }) {
  const id = useId(); const [text, setText] = useState(initial);
  const p = text.trim() ? paiseFromInput(text) : null;
  return (<div>
    <Label htmlFor={id}>{label}</Label>
    <Input id={id} inputMode="decimal" autoComplete="off" required value={text} aria-describedby={`${id}-read`} aria-invalid={!!error || (!!text.trim() && p === null)}
      placeholder="e.g. ₹2,00,00,000 or 2 crore" onChange={e => { setText(e.target.value); const t = e.target.value.trim(); onPaise(t ? paiseFromInput(t) : null); }} />
    <p id={`${id}-read`} aria-live="polite" className="num mt-1.5 text-sm text-ink-700">
      {!text.trim() ? 'Enter an amount in rupees, lakh or crore.' : p === null ? <span className="text-rose-700">Not a valid amount</span> : <>Reads as <b>{inrFromPaise(p)}</b>{approx(p) && <span className="text-ink-500"> ({approx(p)})</span>}</>}
    </p>
    {error && <p role="alert" className="mt-1 text-sm text-rose-700">{error}</p>}
  </div>);
}
