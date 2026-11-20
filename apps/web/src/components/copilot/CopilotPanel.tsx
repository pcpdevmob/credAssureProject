// The side panel behind the Ask CredAssure button (ADR 0035): an accessible dialog around the shared conversation.
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { Button } from '../ui';
import ChatView from './ChatView';

export default function CopilotPanel({ open, onOpenChange, caseId }: { open: boolean; onOpenChange: (o: boolean) => void; caseId: string | null }) {
  return (<Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-40 bg-ink-950/30" />
    <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col overflow-y-auto bg-card p-5 shadow-xl">
      <div className="flex items-start justify-between gap-3">
        <div><Dialog.Title className="font-display text-lg font-semibold text-ink-950">Ask CredAssure</Dialog.Title>
          <Dialog.Description className="mt-0.5 text-sm text-ink-700">{caseId ? `Scoped to case ${caseId}: its status, blockers and figures, plus help, rules and policies.` : 'Help, rules and policies. Open a case to ask about its status or figures.'}</Dialog.Description></div>
        <Dialog.Close asChild><Button variant="outline" size="sm" aria-label="Close Ask CredAssure"><X aria-hidden className="h-4 w-4" /></Button></Dialog.Close>
      </div>
      <div className="mt-4 flex-1"><ChatView caseId={caseId} /></div>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>);
}
