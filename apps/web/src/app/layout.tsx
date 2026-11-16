import './globals.css';
import { Inter, Sora } from 'next/font/google';
const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const sora = Sora({ subsets: ['latin'], variable: '--font-sora', display: 'swap', weight: ['500', '600', '700', '800'] });
import type { Metadata, Viewport } from 'next';
export const metadata: Metadata = { title: { default: 'CredAssure — Working-capital proposal workflow', template: '%s · CredAssure' }, description: 'CredAssure: verified working-capital loan proposals for an electronics MSME. IIT Kharagpur capstone prototype (synthetic data).', applicationName: 'CredAssure' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#070C18' };
// Applies a saved light/dark choice before first paint (no flash). Static string, no user input.
const THEME_SCRIPT = `try{var t=localStorage.getItem('credassure:theme');if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t)}catch(e){}`;
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${inter.variable} ${sora.variable}`} suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} /></head>
      <body>{children}</body>
    </html>
  );
}
