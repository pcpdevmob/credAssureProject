'use client';
// Route-level error boundary for every signed-in page (ARCHITECTURE §8.10): the shell and menu stay usable.
import CrashScreen from '@/components/CrashScreen';
export default function AppError(props: { error: Error & { digest?: string }; reset: () => void }) { return <CrashScreen {...props} />; }
