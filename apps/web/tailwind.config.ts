import type { Config } from 'tailwindcss';
import plugin from 'tailwindcss/plugin';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { ink, brand, gold, surface, state } = require('./src/styles/tokens.js');
const vars: Record<string, string> = {};
for (const [n, s] of Object.entries({ ink, brand, gold }) as [string, Record<string, string>][]) for (const [k, v] of Object.entries(s)) vars[`--fb-${n}-${k}`] = v;
for (const [k, v] of Object.entries({ ...surface, ...state }) as [string, string][]) vars[`--fb-${k}`] = v;
const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: { extend: {
    fontFamily: { sans: ['var(--font-inter)', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], display: ['var(--font-sora)', 'var(--font-inter)', 'ui-sans-serif', 'sans-serif'] },
    // One palette. Legacy names are aliased onto it so every page shares the same colours.
    colors: { ink, midnight: ink, slate: ink, gray: ink, brand, emerald: brand, green: brand, blue: brand, indigo: brand, gold, violet: gold, amber: gold, canvas: surface.canvas, line: surface.line, sunken: surface.sunken },
    keyframes: { fadein: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } } },
    animation: { fadein: 'fadein .35s ease-out both' },
  } },
  plugins: [plugin(({ addBase }) => addBase({ ':root': vars }))],
};
export default config;
