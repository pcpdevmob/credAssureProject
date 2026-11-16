import { AlertTriangle } from 'lucide-react';
import { bannerOf } from '@/lib/problem';
import { cn } from '@/lib/utils';

/** What happened and how to fix it. Takes any thrown value; never renders raw JSON or a stack trace. */
export default function ErrorBanner({ error, className, action }: { error: unknown; className?: string; action?: React.ReactNode }) {
  const b = bannerOf(error);
  return (
    <div role="alert" className={cn('flex gap-3 rounded-2xl bg-rose-50 p-4 text-sm ring-1 ring-inset ring-rose-200', className)}>
      <AlertTriangle aria-hidden className="mt-0.5 h-5 w-5 shrink-0 text-rose-700" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-rose-700">{b.what}</p>
        <p className="mt-0.5 text-ink-700">{b.fix}</p>
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}
