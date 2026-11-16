// Server-sent events from GET /v1/jobs/{id}/events. EventSource cannot send the bearer header, so the stream is read
// through the generated client and parsed here. Pure: text in, complete events out, the unfinished tail kept.
export type SseEvent = { event: string; data: unknown };

export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const parts = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = parts.pop() ?? '';
  const events: SseEvent[] = [];
  for (const part of parts) {
    let event = 'message'; let data = '';
    for (const line of part.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data += line.slice(5).trim();
    }
    if (!data) continue;
    try { events.push({ event, data: JSON.parse(data) }); } catch { /* not JSON: the gateway only sends JSON, so drop it */ }
  }
  return { events, rest };
}
