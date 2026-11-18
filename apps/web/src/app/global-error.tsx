'use client';
// Last-resort boundary for any page outside (app) and for a crash in the root layout itself; renders its own <html> and <body>.
import './globals.css';
import CrashScreen from '@/components/CrashScreen';
export default function GlobalError(props: { error: Error & { digest?: string }; reset: () => void }) {
  return <html lang="en-IN"><body><CrashScreen {...props} /></body></html>;
}
