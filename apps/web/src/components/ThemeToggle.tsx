'use client';
import { useEffect, useState } from 'react';
import { Monitor, Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/utils';

// Per-viewer convenience only (never case data); the inline script in app/layout.tsx applies it before paint.
export const THEME_KEY = 'credassure:theme';
type Theme = 'system' | 'light' | 'dark';
const OPTIONS: [Theme, string, typeof Sun][] = [['system', 'System theme', Monitor], ['light', 'Light theme', Sun], ['dark', 'Dark theme', Moon]];

export function applyTheme(t: Theme) {
  const root = document.documentElement;
  if (t === 'system') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', t);
  try { if (t === 'system') localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, t); } catch { /* storage blocked */ }
}

export default function ThemeToggle({ className }: { className?: string }) {
  const [theme, setTheme] = useState<Theme>('system');
  useEffect(() => { const t = document.documentElement.getAttribute('data-theme'); if (t === 'light' || t === 'dark') setTheme(t); }, []);
  return (
    <div role="radiogroup" aria-label="Colour theme" className={cn('inline-flex rounded-full bg-white/5 p-0.5 ring-1 ring-white/10', className)}>
      {OPTIONS.map(([t, label, Icon]) => (
        <button key={t} type="button" role="radio" aria-checked={theme === t} aria-label={label} title={label}
          onClick={() => { setTheme(t); applyTheme(t); }}
          className={cn('grid h-8 w-8 place-items-center rounded-full text-ink-300 transition hover:text-white', theme === t && 'bg-white text-ink-950 hover:text-ink-950')}>
          <Icon className="h-4 w-4" />
        </button>
      ))}
    </div>
  );
}
