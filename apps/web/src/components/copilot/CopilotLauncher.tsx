// The Ask CredAssure button on every page (ADR 0035). Only the button ships with each route; the panel and the conversation
// load when the person first opens it, so the assistant costs every page a few hundred bytes. Inside a case page the panel
// is scoped to that case (from the URL); everywhere else it answers product, rule and policy questions only.
'use client';
import dynamic from 'next/dynamic';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { MessageCircleQuestion } from 'lucide-react';

const CopilotPanel = dynamic(() => import('./CopilotPanel'), { ssr: false });
const CASE_ID = /^[A-Za-z0-9-]{1,16}$/;

export default function CopilotLauncher() {
  const [open, setOpen] = useState(false); const [loaded, setLoaded] = useState(false); const [caseId, setCaseId] = useState<string | null>(null);
  const path = usePathname();
  useEffect(() => {
    const id = path.startsWith('/case') ? new URLSearchParams(window.location.search).get('id') : null;
    setCaseId(id && CASE_ID.test(id) ? id : null);
  }, [path, open]);
  return (<>
    <button type="button" onClick={() => { setLoaded(true); setOpen(true); }} aria-haspopup="dialog" aria-expanded={open}
      className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full bg-ink-950 px-4 py-3 text-sm font-semibold text-white shadow-lg ring-1 ring-white/10 hover:bg-ink-900 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-400/50 keep-light">
      <MessageCircleQuestion aria-hidden className="h-4 w-4" />Ask CredAssure</button>
    {loaded && <CopilotPanel open={open} onOpenChange={setOpen} caseId={caseId} />}
  </>);
}
