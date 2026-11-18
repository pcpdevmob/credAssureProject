'use client';
// Sends uncaught browser errors and unhandled promise rejections to the gateway's error log (services/telemetry.ts).
import { useEffect } from 'react';
import { reportClientError } from '@/services/telemetry';

export default function ErrorReporter() {
  useEffect(() => {
    const onError = (e: ErrorEvent) => reportClientError('error', e.error ?? e.message);
    const onRejection = (e: PromiseRejectionEvent) => reportClientError('unhandledrejection', e.reason);
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => { window.removeEventListener('error', onError); window.removeEventListener('unhandledrejection', onRejection); };
  }, []);
  return null;
}
