// Dates only (money lives in lib/money.ts). Fixed locale and time zone so every viewer sees the same calendar day.
const TZ = 'Asia/Kolkata';
export const dt = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: TZ });
export const d = (iso: string) => new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', timeZone: TZ });
