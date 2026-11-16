/**
 * CredAssure design tokens: the ONE palette used everywhere (landing, login, app, charts).
 * "Midnight · Emerald · Champagne" on a warm ivory canvas.
 * Tailwind reads this file (tailwind.config.ts) and also emits these as CSS variables (--fb-*).
 * Charts import CHART from here. Do not hard-code colours elsewhere.
 */
const ink = { 50: '#F4F6FA', 100: '#E8ECF3', 200: '#CDD4E1', 300: '#A2ADC2', 400: '#647088', 500: '#525E75', 600: '#3A455C', 700: '#263149', 800: '#172036', 900: '#0E1628', 950: '#070C18' };
const brand = { 50: '#ECFDF5', 100: '#D1FAE5', 200: '#A7F3D0', 300: '#6EE7B7', 400: '#34D399', 500: '#10B981', 600: '#059669', 700: '#047857', 800: '#065F46', 900: '#064E3B', 950: '#022C22' };
const gold = { 50: '#FBF7EC', 100: '#F6ECCF', 200: '#F3E0AA', 300: '#EBCB7A', 400: '#DDB04F', 500: '#C3962E', 600: '#9C7419', 700: '#7A5A12', 800: '#5C430D', 900: '#3D2C08' };
const surface = { canvas: '#F6F5F0', card: '#FFFFFF', line: '#E7E4DB', sunken: '#EFEDE6' };
const state = { danger: '#BE123C', dangerSoft: '#FFF1F2', warn: '#B45309', warnSoft: '#FFFBEB' };
const rose = { 50: '#FFF1F2', 100: '#FFE4E6', 200: '#FECDD3', 300: '#FDA4AF', 400: '#FB7185', 500: '#F43F5E', 600: '#E11D48', 700: '#BE123C', 800: '#9F1239', 900: '#881337' };

/**
 * Dark theme: the same token names with new values (docs/ui/design-plan.md §2). Scales are re-mapped by role, so
 * `text-ink-800` stays "body text" and `bg-white` (→ card) stays "surface" in both themes. Contrast checked by axe in U1.
 */
const dark = {
  ink: { 50: '#0B1222', 100: '#131C30', 200: '#263149', 300: '#3A455C', 400: '#8592A8', 500: '#A2ADC2', 600: '#B8C1D2', 700: '#CDD4E1', 800: '#E8ECF3', 900: '#EEF1F6', 950: '#F4F6FA' },
  brand: { 50: '#04261D', 100: '#063D2F', 200: '#065F46', 300: '#047857', 400: '#10B981', 500: '#34D399', 600: '#34D399', 700: '#34D399', 800: '#6EE7B7', 900: '#A7F3D0', 950: '#D1FAE5' },
  gold: { 50: '#2A1F07', 100: '#3D2C08', 200: '#5C430D', 300: '#7A5A12', 400: '#DDB04F', 500: '#C3962E', 600: '#DDB04F', 700: '#EBCB7A', 800: '#F3E0AA', 900: '#F6ECCF' },
  rose: { 50: '#3B0A17', 100: '#4C0519', 200: '#881337', 300: '#9F1239', 400: '#FB7185', 500: '#FB7185', 600: '#FB7185', 700: '#FB7185', 800: '#FDA4AF', 900: '#FECDD3' },
  surface: { canvas: '#070C18', card: '#0E1628', line: '#263149', sunken: '#0B1222' },
  state: { danger: '#FB7185', dangerSoft: '#3B0A17', warn: '#EBCB7A', warnSoft: '#2A1F07' },
};
const CHART = {
  primary: brand[600], primarySoft: brand[200], secondary: gold[400], secondarySoft: gold[100],
  tertiary: ink[700], tertiarySoft: ink[200], muted: ink[200], grid: surface.line, axis: ink[500],
  positive: brand[500], negative: '#E11D48', warn: gold[500],
  series: [brand[600], gold[400], ink[700], brand[300], ink[300]],
};
module.exports = { ink, brand, gold, rose, surface, state, dark, CHART };
