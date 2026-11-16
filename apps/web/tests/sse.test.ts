import { describe, expect, it } from 'vitest';
import { parseSse } from '@/lib/sse';

describe('parseSse: gateway job events (ADR 0007)', () => {
  it('splits complete events and keeps the partial tail', () => {
    const r = parseSse('event: stage\ndata: {"stage":"onboarding","decision":"GO","attempt":1}\n\nevent: end\ndata: {"status":"succ');
    expect(r.events).toEqual([{ event: 'stage', data: { stage: 'onboarding', decision: 'GO', attempt: 1 } }]);
    expect(r.rest).toBe('event: end\ndata: {"status":"succ');
    expect(parseSse(r.rest + 'eeded","outcome":"PAUSED"}\n\n').events).toEqual([{ event: 'end', data: { status: 'succeeded', outcome: 'PAUSED' } }]);
  });
  it('accepts CRLF and skips comments and unparseable data', () => {
    expect(parseSse(': keep-alive\r\n\r\nevent: stage\r\ndata: not json\r\n\r\nevent: end\r\ndata: {}\r\n\r\n').events).toEqual([{ event: 'end', data: {} }]);
  });
});
