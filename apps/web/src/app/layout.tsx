import './globals.css';
import { Inter, Sora } from 'next/font/google';
const inter = Inter({ subsets: ['latin'], variable: '--font-inter', display: 'swap' });
const sora = Sora({ subsets: ['latin'], variable: '--font-sora', display: 'swap', weight: ['500', '600', '700', '800'] });
import type { Metadata, Viewport } from 'next';
export const metadata: Metadata = { title: 'FinBridge AI — Working-capital proposal workflow', description: 'IIT capstone prototype (synthetic data)' };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#070C18' };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en-IN" className={`${inter.variable} ${sora.variable}`}><body>{children}</body></html>;
}
