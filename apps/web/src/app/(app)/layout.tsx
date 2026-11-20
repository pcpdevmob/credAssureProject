import AppShell from '@/components/AppShell';
import CopilotLauncher from '@/components/copilot/CopilotLauncher';
import ErrorReporter from '@/components/ErrorReporter';
export default function L({ children }: { children: React.ReactNode }) { return <AppShell><ErrorReporter />{children}<CopilotLauncher /></AppShell>; }
