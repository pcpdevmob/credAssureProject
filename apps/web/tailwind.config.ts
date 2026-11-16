import type { Config } from 'tailwindcss';
import plugin from 'tailwindcss/plugin';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { ink, brand, gold, rose, surface, state, dark } = require('./src/styles/tokens.js');

type Scale = Record<string, string>;
const rgb = (hex: string) => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16)).join(' ');

/** One theme's variables: `--fbc-*` channels (Tailwind alpha) and `--fb-*` full colours (plain CSS in globals.css). */
function vars(scales: Record<string, Scale>, flat: Scale): Record<string, string> {
  const out: Record<string, string> = {};
  const put = (n: string, hex: string) => { out[`--fbc-${n}`] = rgb(hex); out[`--fb-${n}`] = `rgb(${rgb(hex)})`; };
  for (const [n, s] of Object.entries(scales)) for (const [k, v] of Object.entries(s)) put(`${n}-${k}`, v);
  for (const [k, v] of Object.entries(flat)) put(k, v);
  return out;
}
const light = vars({ ink, brand, gold, rose }, { ...surface, ...state });
const night = vars({ ink: dark.ink, brand: dark.brand, gold: dark.gold, rose: dark.rose }, { ...dark.surface, ...dark.state });
// The sidebar and midnight panels stay dark in both themes: they keep the light-theme values of `ink` (a fixed midnight scale).
const midnight = vars({ midnight: ink }, {});

const ref = (n: string, s: Scale) => Object.fromEntries(Object.keys(s).map(k => [k, `rgb(var(--fbc-${n}-${k}) / <alpha-value>)`]));
const one = (n: string) => `rgb(var(--fbc-${n}) / <alpha-value>)`;
const inkV = ref('ink', ink), brandV = ref('brand', brand), goldV = ref('gold', gold), roseV = ref('rose', rose);

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: { extend: {
    fontFamily: { sans: ['var(--font-inter)', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], display: ['var(--font-sora)', 'var(--font-inter)', 'ui-sans-serif', 'sans-serif'] },
    // One palette. Legacy names are aliased onto it so every page shares the same colours; `white` is the card surface.
    colors: { ink: inkV, slate: inkV, gray: inkV, midnight: ref('midnight', ink), brand: brandV, emerald: brandV, green: brandV, blue: brandV, indigo: brandV, gold: goldV, violet: goldV, amber: goldV, rose: roseV, red: roseV,
      white: one('card'), canvas: one('canvas'), line: one('line'), sunken: one('sunken'), card: one('card') },
    keyframes: { fadein: { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } } },
    animation: { fadein: 'fadein .35s ease-out both' },
  } },
  plugins: [plugin(({ addBase }) => addBase({
    ':root': { ...light, ...midnight, colorScheme: 'light' },
    // `.keep-light` pins a subtree (sidebar, midnight panels, landing) to the light values, which are designed dark-on-midnight.
    '.keep-light': { ...light, colorScheme: 'light' },
    ':root[data-theme="dark"]': { ...night, colorScheme: 'dark' },
    '@media (prefers-color-scheme: dark)': { ':root:not([data-theme="light"])': { ...night, colorScheme: 'dark' } },
  }))],
};
export default config;
