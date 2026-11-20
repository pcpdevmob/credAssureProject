'use client';
// What a user sees when a page crashes: plain words, the request ID to quote, and a way back. Never a stack trace.
import { useEffect } from 'react';
import { reportClientError } from '@/services/telemetry';

export default function CrashScreen({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { reportClientError('render', error, error.digest); }, [error]);
  const rid = (error as { requestId?: string }).requestId; // set on an ApiProblem; duck-typed to keep this chunk small
  return (
    <div role="alert" className="mx-auto mt-16 max-w-lg rounded-2xl bg-card p-8 text-center ring-1 ring-line">
      <h1 className="mt-4 text-xl font-bold">This page stopped working</h1>
      <p className="mt-2 text-sm text-ink-700">The error was recorded. Try again; if it keeps happening, tell the evaluator what you were doing{rid || error.digest ? ' and quote the reference below' : ''}.</p>
      {(rid || error.digest) && <p className="mt-3 text-xs text-ink-600">Reference: <code className="select-all font-mono">{rid ?? error.digest}</code></p>}
      <div className="mt-6 flex justify-center gap-3">
        <button type="button" onClick={reset} className="inline-flex items-center gap-2 rounded-xl bg-brand-700 px-4 py-2 text-sm font-semibold text-white">Try again</button>
        <a href="/dashboard/" className="rounded-xl px-4 py-2 text-sm font-semibold text-brand-700 ring-1 ring-inset ring-line">Go to dashboard</a>
      </div>
    </div>
  );
}
