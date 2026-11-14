// Case data upload (UI-02): JSON/CSV only, validated field by field on the server. There is no list endpoint yet.
import type { UploadedDoc } from '@/types';
import { gw, ok } from '@/lib/gateway';

export interface DocumentService { list(caseId: string): Promise<UploadedDoc[]>; upload(caseId: string, file: File, kind: string): Promise<UploadedDoc> }
export const FILE_KINDS = ['order', 'opening_position', 'costs', 'receipts', 'receivables', 'payables', 'inventory'] as const;

export const documentService: DocumentService = {
  async list() { return []; },
  async upload(caseId, file, kind) {
    const text = await file.text();
    const r = await ok(gw.POST('/v1/cases/{case_id}/files', { params: { path: { case_id: caseId }, query: { kind } as never }, body: text as never, bodySerializer: (b: unknown) => b as string, headers: { 'Content-Type': file.name.endsWith('.json') ? 'application/json' : 'text/csv' } } as never)) as unknown as { rows: number; injection_flags: unknown[] };
    return { id: `${kind}-${Date.now()}`, caseId, name: file.name, kind: file.name.endsWith('.json') ? 'JSON' : 'CSV', docType: kind, sizeKb: Math.max(1, Math.round(file.size / 1024)), status: r.injection_flags.length ? 'FLAGGED' : 'EXTRACTED', fields: r.rows, warnings: r.injection_flags.length ? ['Instruction-like text detected and ignored (untrusted content)'] : [], uploadedAt: new Date().toISOString() };
  },
};
