/**
 * FinBridge AI design tokens: the ONE palette used everywhere (landing, login, app, charts).
 * "Midnight · Emerald · Champagne" on a warm ivory canvas.
 * Tailwind reads this file (tailwind.config.ts) and also emits these as CSS variables (--fb-*).
 * Charts import CHART from here. Do not hard-code colours elsewhere.
 */
const ink = { 50: '#F4F6FA', 100: '#E8ECF3', 200: '#CDD4E1', 300: '#A2ADC2', 400: '#647088', 500: '#525E75', 600: '#3A455C', 700: '#263149', 800: '#172036', 900: '#0E1628', 950: '#070C18' };
const brand = { 50: '#ECFDF5', 100: '#D1FAE5', 200: '#A7F3D0', 300: '#6EE7B7', 400: '#34D399', 500: '#10B981', 600: '#059669', 700: '#047857', 800: '#065F46', 900: '#064E3B', 950: '#022C22' };
const gold = { 50: '#FBF7EC', 100: '#F6ECCF', 200: '#F3E0AA', 300: '#EBCB7A', 400: '#DDB04F', 500: '#C3962E', 600: '#9C7419', 700: '#7A5A12', 800: '#5C430D', 900: '#3D2C08' };
const surface = { canvas: '#F6F5F0', card: '#FFFFFF', line: '#E7E4DB', sunken: '#EFEDE6' };
const state = { danger: '#BE123C', dangerSoft: '#FFF1F2', warn: '#B45309', warnSoft: '#FFFBEB' };
const CHART = {
  primary: brand[600], primarySoft: brand[200], secondary: gold[400], secondarySoft: gold[100],
  tertiary: ink[700], tertiarySoft: ink[200], muted: ink[200], grid: surface.line, axis: ink[500],
  positive: brand[500], negative: '#E11D48', warn: gold[500],
  series: [brand[600], gold[400], ink[700], brand[300], ink[300]],
};
module.exports = { ink, brand, gold, surface, state, CHART };
