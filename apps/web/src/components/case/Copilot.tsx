// Ask CredAssure in the case tab (UI-06): the shared conversation (components/copilot/ChatView) scoped to this case.
import { MessageCircleQuestion } from 'lucide-react';
import { Card, CardHeader } from '../ui';
import ChatView from '../copilot/ChatView';

export default function Copilot({ caseId }: { caseId: string }) {
  return (<Card><CardHeader title="Ask CredAssure" sub="Answers cite their sources; numbers come from this case's ledger" icon={<MessageCircleQuestion className="h-4 w-4" />} />
    <div className="p-5"><ChatView caseId={caseId} /></div>
  </Card>);
}
