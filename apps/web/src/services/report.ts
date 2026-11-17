// Report view, versions and export (UI-08, scope #6, #33). The gateway renders every version from the ledger fact
// versions it pinned and says when it is stale; the browser only displays it. Export downloads exactly what it returned.
import { gw, ok } from '@/lib/gateway';

export type ReportFmt = 'md' | 'html';
export type ReportFigure = { key: string; version: number; start: number; end: number; display: string };
export type ReportSection = { title: string; text: string; figures: ReportFigure[] };
export type ReportView = { case_id: string; version: number | null; latest_version: number | null; stale: boolean; reasons: string[]; sections: ReportSection[] };

export const reportService = {
  async get(caseId: string, fmt: ReportFmt = 'md'): Promise<string> {
    return await ok(gw.GET('/v1/cases/{case_id}/report', { params: { path: { case_id: caseId }, query: { fmt } }, parseAs: 'text' })) as unknown as string;
  },
  async view(caseId: string, version?: number): Promise<ReportView> {
    return await ok(gw.GET('/v1/cases/{case_id}/report', { params: { path: { case_id: caseId }, query: { fmt: 'json', version } } })) as unknown as ReportView;
  },
  /** A new version from the current figures (preparer only; the gateway enforces it). */
  async regenerate(caseId: string): Promise<{ version: number | null; stale: boolean; reasons: string[] }> {
    return await ok(gw.POST('/v1/cases/{case_id}/report', { params: { path: { case_id: caseId } } })) as never;
  },
  async download(caseId: string, fmt: ReportFmt): Promise<void> {
    const text = await reportService.get(caseId, fmt);
    const url = URL.createObjectURL(new Blob([text], { type: fmt === 'md' ? 'text/markdown' : 'text/html' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `${caseId}-report.${fmt}` });
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
  },
};

/** Split a section's text at its figures: plain strings and figures, in order (offsets come from the gateway). */
export function segments(s: ReportSection): (string | ReportFigure)[] {
  const out: (string | ReportFigure)[] = []; let at = 0;
  for (const f of [...s.figures].sort((x, y) => x.start - y.start)) {
    if (f.start < at || s.text.slice(f.start, f.end) !== f.display) continue; // overlapping or out of sync: show as text
    if (f.start > at) out.push(s.text.slice(at, f.start));
    out.push(f); at = f.end;
  }
  if (at < s.text.length) out.push(s.text.slice(at));
  return out;
}
