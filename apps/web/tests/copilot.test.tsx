// ADR 0035: Ask CredAssure on every page — help citations, follow-ups, ratings, history and reset (CP-07, CP-10..12).
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API, reply, sse } from '@/mocks/handlers';
import ChatView from '@/components/copilot/ChatView';
import CopilotPanel from '@/components/copilot/CopilotPanel';
import { helpHref, mapChat } from '@/services/copilot';

const ask = async (q: string, label = 'Your question') => { await userEvent.type(await screen.findByLabelText(label), q); await userEvent.click(screen.getByRole('button', { name: /Ask$/ })); };
const HELP = { chunk_id: 'HELP-ai-safety#personal-data', doc_id: 'HELP-ai-safety', title: 'AI safety and your data', section: 'Personal data', effective_from: null, collection: 'help', href: '/help/#ai-safety' };

describe('Ask CredAssure everywhere', () => {
  it('accepts only an in-app help anchor as a citation link', () => {
    expect(helpHref('/help/#ai-safety')).toBe('/help/#ai-safety');
    for (const bad of ['javascript:alert(1)', 'https://evil.example/help/#x', '/help/#x"onclick', '//evil/help/#x', null]) expect(helpHref(bad)).toBeNull();
    const r = mapChat({ ...reply({ citations: [{ ...HELP, href: 'javascript:alert(1)' }] }), followups: ['a', 'b', 'c', 'd'] } as never);
    expect(r.citations[0].href).toBeNull(); expect(r.followups).toHaveLength(3);
  });

  it('answers without a case, links help citations to the help centre and offers follow-ups', async () => {
    let body: Record<string, unknown> = {};
    server.use(http.post(`${API}/v1/copilot/chat/stream`, async ({ request }) => { body = await request.json() as Record<string, unknown>;
      return sse(reply({ answer: 'Identifiers are removed [HELP-ai-safety#personal-data].', citations: [HELP], intent: 'help', followups: ['What does the AI decide, and what does code decide?'] })); }));
    render(<ChatView caseId={null} />);
    expect(await screen.findByText(/Open a case to ask about its figures/)).toBeTruthy();
    await ask('How is my data handled?');
    expect(body).toEqual({ message: 'How is my data handled?' }); // no case_id outside a case
    const link = await screen.findByRole('link', { name: /Help: AI safety and your data/ });
    expect(link.getAttribute('href')).toBe('/help/#ai-safety');
    let next: Record<string, unknown> = {};
    server.use(http.post(`${API}/v1/copilot/chat/stream`, async ({ request }) => { next = await request.json() as Record<string, unknown>; return sse(reply()); }));
    await userEvent.click(within(screen.getByLabelText('Suggested questions')).getByRole('button', { name: /What does the AI decide/ }));
    await screen.findAllByText(/Key Facts Statement discloses/);
    expect(next.message).toBe('What does the AI decide, and what does code decide?');
  });

  it('sends the case id inside a case, restores history and starts a new conversation', async () => {
    let sent: Record<string, unknown> = {}; let reset = false;
    server.use(
      http.get(`${API}/v1/cases/:id/chat`, () => HttpResponse.json({ case_id: 'CA-1', messages: [{ role: 'user', text: 'Earlier question', trace_id: 't0' }, { role: 'assistant', text: 'Earlier answer', trace_id: 't0' }] })),
      http.post(`${API}/v1/cases/:id/chat/reset`, () => { reset = true; return HttpResponse.json({ case_id: 'CA-1', messages: [] }); }),
      http.post(`${API}/v1/copilot/chat/stream`, async ({ request }) => { sent = await request.json() as Record<string, unknown>; return sse(reply()); }),
    );
    render(<ChatView caseId="CA-1" />);
    expect(await screen.findByText('Earlier answer')).toBeTruthy();
    expect(screen.getByText(/Earlier in this conversation/)).toBeTruthy();
    await ask('What is the status of this case?');
    expect(sent).toEqual({ message: 'What is the status of this case?', case_id: 'CA-1' });
    await userEvent.click(await screen.findByRole('button', { name: /New conversation/ }));
    expect(reset).toBe(true);
    expect(screen.queryByText('Earlier answer')).toBeNull();
  });

  it('records a thumbs-down with a fixed reason only', async () => {
    let fb: Record<string, unknown> = {};
    server.use(http.post(`${API}/v1/copilot/feedback`, async ({ request }) => { fb = await request.json() as Record<string, unknown>; return HttpResponse.json({ recorded: true }); }));
    render(<ChatView caseId={null} />);
    await ask('What is a KFS?', 'Your question');
    await userEvent.click(await screen.findByRole('button', { name: 'Not helpful' }));
    await userEvent.click(within(screen.getByRole('group', { name: 'What was wrong?' })).getByRole('button', { name: 'Not cited' }));
    expect(await screen.findByText(/rating was recorded/)).toBeTruthy();
    expect(fb).toEqual({ trace_id: 't-1', rating: 'down', reason: 'not_cited' });
  });

  it('opens as a labelled dialog that says what it is scoped to', async () => {
    render(<CopilotPanel open onOpenChange={() => undefined} caseId="CA-2026-0016" />);
    const dlg = await screen.findByRole('dialog', { name: 'Ask CredAssure' });
    expect(dlg.textContent).toMatch(/Scoped to case CA-2026-0016/);
  });
});
