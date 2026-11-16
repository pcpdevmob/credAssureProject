import type { LucideIcon } from 'lucide-react';
import { Inbox } from 'lucide-react';
import { cn } from '@/lib/utils';

/** A quiet "nothing here yet" panel: what is missing and the one action that fills it. */
export default function EmptyState({ title, hint, icon: Icon = Inbox, action, className }: { title: string; hint?: string; icon?: LucideIcon; action?: React.ReactNode; className?: string }) {
  return (
    <div className={cn('grid place-items-center rounded-[24px] border border-dashed border-ink-300 px-6 py-12 text-center', className)}>
      <span className="grid h-11 w-11 place-items-center rounded-full bg-sunken text-ink-500"><Icon aria-hidden className="h-5 w-5" /></span>
      <p className="mt-3 font-semibold text-ink-900">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-sm text-ink-500">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
