// P9 RAI UI (plan v3.4 §6): AI-generated badge, approver attestation, safety panel, audit chain badge.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API, reply } from '@/mocks/handlers';
import { mapChat } from '@/services/copilot';
import { mapSafety } from '@/services/safety';
import { approvalService } from '@/services/approvals';
import SafetyPanel from '@/components/case/SafetyPanel';
import { AiBadge } from '@/components/ui';
import type { CaseRecord } from '@/types';

describe('P9 AI-generated badge', () => {
  it('marks only model-drafted copilot answers', () => {
    expect(mapChat(reply({ source: 'model' }) as never).aiDrafted).toBe(true);
    expect(mapChat(reply({ source: 'code' }) as never).aiDrafted).toBe(false);
    expect(mapChat(reply() as never).aiDrafted).toBe(false); // unknown source: no claim either way
  });
  it('renders a text label, not colour alone', () => {
    render(<AiBadge />);
    expect(screen.getByText('AI-generated draft')).toBeTruthy();
  });
});

describe('P9 approver attestation', () => {
  it('sends attested only for approve', async () => {
    const bodies: Record<string, unknown>[] = [];
    server.use(http.post(`${API}/v1/cases/:id/decision`, async ({ request }) => { bodies.push(await request.json() as Record<string, unknown>); return HttpResponse.json({ status: 'APPROVED' }); }));
    await approvalService.decide({ id: 'CA-1', rowVersion: 3 } as CaseRecord, 'APPROVED', '', undefined, undefined, null, true);
    await approvalService.decide({ id: 'CA-1', rowVersion: 3 } as CaseRecord, 'REJECTED', 'no', undefined, undefined, null, true);
    expect(bodies[0].attested).toBe(true);
    expect(bodies[1].attested).toBe(false);
  });
});

describe('P9 safety panel', () => {
  it('shows counts and codes, never text', async () => {
    server.use(http.get(`${API}/v1/cases/:id/safety`, () => HttpResponse.json({
      case_id: 'CA-1', counts: { block: 1, redact: 2 },
      events: [{ seq: 4, ts: '2026-11-18T09:00:00Z', event_type: 'GUARDRAIL_EVENT', rail: 'R1', rule_id: 'R1.upload_pii_refused', action: 'block', kinds: ['PAN'], count: 1 }],
    })));
    render(<SafetyPanel caseId="CA-1" />);
    expect(await screen.findByText('Blocked: 1')).toBeTruthy();
    expect(screen.getByText('Redacted: 2')).toBeTruthy();
    expect(screen.getByText(/R1.upload_pii_refused/)).toBeTruthy();
    expect(screen.getByText('kinds: PAN')).toBeTruthy();
  });
  it('says so when nothing happened', async () => {
    server.use(http.get(`${API}/v1/cases/:id/safety`, () => HttpResponse.json({ case_id: 'CA-1', counts: {}, events: [] })));
    render(<SafetyPanel caseId="CA-1" />);
    expect(await screen.findByText(/No blocks, redactions/)).toBeTruthy();
  });
  it('maps lists to readable detail', () => {
    const s = mapSafety({ counts: {}, events: [{ seq: 1, ts: 't', event_type: 'CRITIC_BLOCKED', stage: 'lendwise', codes: ['VER_UNMATCHED_NUMBER'] }] });
    expect(s.events[0].detail).toBe('codes: VER_UNMATCHED_NUMBER · stage: lendwise');
  });
});
