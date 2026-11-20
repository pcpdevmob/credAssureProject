// Dates only (money lives in lib/money.ts). Fixed locale and time zone so every viewer sees the same calendar day.
// A missing or unreadable date shows as an em dash, never "Invalid Date".
const TZ = 'Asia/Kolkata';
const parse = (iso?: string | null): Date | null => {
  if (!iso) return null;
  const t = new Date(/^\d{4}-\d{2}-\d{2}$/.test(iso) ? `${iso}T00:00:00+05:30` : iso); // a bare date is an Indian calendar day
  return Number.isNaN(t.getTime()) ? null : t;
};
export const dt = (iso?: string | null) => parse(iso)?.toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: TZ }) ?? '—';
export const d = (iso?: string | null) => parse(iso)?.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: TZ }) ?? '—';
/** "5 minutes ago", "yesterday", or the date when older than a week. */
export const ago = (iso?: string | null, now = Date.now()) => {
  const t = parse(iso); if (!t) return '—';
  const s = Math.round((now - t.getTime()) / 1000);
  if (s < 45) return 'just now';
  const m = Math.round(s / 60); if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`;
  const h = Math.round(m / 60); if (h < 24) return `${h} hour${h === 1 ? '' : 's'} ago`;
  const days = Math.round(h / 24); if (days === 1) return 'yesterday'; if (days < 7) return `${days} days ago`;
  return d(iso);
};
