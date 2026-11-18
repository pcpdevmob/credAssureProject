import AppShell from '@/components/AppShell';
import CopilotLauncher from '@/components/copilot/CopilotLauncher';
export default function L({ children }: { children: React.ReactNode }) { return <AppShell>{children}<CopilotLauncher /></AppShell>; }
