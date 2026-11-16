// Case data upload (UI-02): JSON/CSV case files, offer JSON and KFS Markdown, validated field by field on the server.
// A rejected file throws an ApiProblem whose fieldErrors carry field, row and reason. There is no list endpoint yet.
import { gw, ok } from '@/lib/gateway';

export const FILE_KINDS = ['order', 'opening_position', 'costs', 'receipts', 'receivables', 'payables', 'inventory'] as const;
export type FileKind = typeof FILE_KINDS[number] | 'offer' | 'kfs';
export type Uploaded = { rows: number; flagged: boolean };

const TYPE = (name: string) => name.endsWith('.json') ? 'application/json' : name.endsWith('.md') ? 'text/markdown' : 'text/csv';

export const documentService = {
  async upload(caseId: string, file: File, kind: FileKind): Promise<Uploaded> {
    // The part's type comes from the extension: browsers send '' for .md and vnd.ms-excel for .csv on some systems.
    const body = new FormData(); body.append('file', new File([file], file.name, { type: TYPE(file.name) }));
    const r = await ok(gw.POST('/v1/cases/{case_id}/files', { params: { path: { case_id: caseId }, query: { kind } as never }, body: body as never, bodySerializer: (b: unknown) => b as FormData } as never)) as unknown as { rows?: number; injection_flags?: unknown[] };
    return { rows: r.rows ?? 0, flagged: !!r.injection_flags?.length };
  },
  /** Offers are JSON, KFS documents and schedules of charges are Markdown. */
  kindOf: (name: string): FileKind | null => name.endsWith('.json') ? 'offer' : name.endsWith('.md') ? 'kfs' : null,
};
