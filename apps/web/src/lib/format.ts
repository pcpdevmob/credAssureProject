// Indian number formatting helpers (lakh / crore).
export const inr = (n: number, digits = 0) =>
  '₹' + n.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits });
export const inrShort = (n: number) => {
  const a = Math.abs(n), s = n < 0 ? '-' : '';
  if (a >= 1e7) return `${s}₹${(a / 1e7).toFixed(2)} Cr`;
  if (a >= 1e5) return `${s}₹${(a / 1e5).toFixed(2)} L`;
  return s + inr(a);
};
export const pct = (n: number, d = 2) => `${n.toFixed(d)}%`;
export const dt = (iso: string) => new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
export const d = (iso: string) => new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
