import AppShell from '@/components/AppShell';
import ErrorReporter from '@/components/ErrorReporter';
export default function L({ children }: { children: React.ReactNode }) { return <AppShell><ErrorReporter />{children}</AppShell>; }
