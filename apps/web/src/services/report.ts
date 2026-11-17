// Report view and export (UI-08). Uses the existing report endpoint; the file is built from the text the gateway returned.
import { gw, ok } from '@/lib/gateway';

export type ReportFmt = 'md' | 'html';
export const reportService = {
  async get(caseId: string, fmt: ReportFmt = 'md'): Promise<string> {
    return await ok(gw.GET('/v1/cases/{case_id}/report', { params: { path: { case_id: caseId }, query: { fmt } }, parseAs: 'text' })) as unknown as string;
  },
  async download(caseId: string, fmt: ReportFmt): Promise<void> {
    const text = await reportService.get(caseId, fmt);
    const url = URL.createObjectURL(new Blob([text], { type: fmt === 'md' ? 'text/markdown' : 'text/html' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `${caseId}-report.${fmt}` });
    a.click(); setTimeout(() => URL.revokeObjectURL(url), 0);
  },
};
