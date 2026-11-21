// Case data upload (UI-02): JSON/CSV case files, offer JSON and KFS Markdown, validated field by field on the server.
// A rejected file throws an ApiProblem whose fieldErrors carry field, row and reason. There is no list endpoint yet.
import { gw, ok } from '@/lib/gateway';
import { toProblem } from '@/lib/problem';
import type { OfferDraft, ChargeRow } from '@/lib/offerPdf';

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

/** What the case holds now (GET /v1/cases/{id}/files): the newest upload per case-file kind, plus lender documents. */
export type StoredFile = { kind: typeof FILE_KINDS[number]; uploadedAt: string | null; rows: number; data: unknown };
export type StoredDoc = { kind: 'offer' | 'kfs'; name: string; detail: string; uploadedAt: string | null };
export const caseFiles = {
  async list(caseId: string): Promise<{ files: StoredFile[]; documents: StoredDoc[] }> {
    const r = await ok(gw.GET('/v1/cases/{case_id}/files', { params: { path: { case_id: caseId } } })) as unknown as { files: { kind: StoredFile['kind']; uploaded_at: string | null; rows: number; data: unknown }[]; documents: { kind: 'offer' | 'kfs'; name: string; detail: string; uploaded_at: string | null }[] };
    return { files: r.files.map(f => ({ kind: f.kind, uploadedAt: f.uploaded_at, rows: f.rows, data: f.data })), documents: r.documents.map(d => ({ kind: d.kind, name: d.name, detail: d.detail, uploadedAt: d.uploaded_at })) };
  },
  /** A form's file, sent through the same upload endpoint (and the same validation) as a file the person picks. */
  save: (caseId: string, kind: FileKind, name: string, text: string) =>
    documentService.upload(caseId, new File([text], name, { type: name.endsWith('.json') ? 'application/json' : 'text/csv' }), kind),
};

/** ADR 0040: the case Excel workbook. The gateway converts it to the same JSON/CSV files and stores each through the same
 * upload check; on any error nothing is stored and each error names sheet (field prefix), Excel row and column. */
export type Imported = { name: string; kind: FileKind; rows: number; flagged: boolean };
export const workbookService = {
  async upload(caseId: string, file: File): Promise<Imported[]> {
    const body = new FormData(); body.append('file', new File([file], file.name, { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }));
    const r = await ok(gw.POST('/v1/cases/{case_id}/workbook', { params: { path: { case_id: caseId } }, body: body as never, bodySerializer: (b: unknown) => b as FormData } as never)) as unknown as { files: { name: string; kind: FileKind; rows: number; injection_flags?: unknown[] }[] };
    return r.files.map(f => ({ name: f.name, kind: f.kind, rows: f.rows, flagged: !!f.injection_flags?.length }));
  },
  /** Blank template (default) or the demo case filled in, downloaded with the signed-in user's token. */
  async template(example = false): Promise<void> {
    const { data, response } = await gw.GET('/v1/templates/case.xlsx', { params: { query: { example } }, parseAs: 'blob' } as never) as { data: Blob; response: Response };
    if (!response.ok) throw toProblem(response.status, undefined);
    const url = URL.createObjectURL(data);
    Object.assign(document.createElement('a'), { href: url, download: example ? 'credassure-case-example.xlsx' : 'credassure-case-template.xlsx' }).click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  },
};

/** ADR 0041: lender PDFs. `read` returns the PDF text and a draft (nothing stored); the person reviews it, then the offer is
 * saved with caseFiles.save('offer') and the KFS / schedule with saveKfs, both through the ordinary upload check. */
export type PdfDoc = 'offer' | 'kfs' | 'schedule';
export type PdfRead = { text: string; draft: OfferDraft & { rows?: ChargeRow[] } };
export const pdfService = {
  async read(caseId: string, doc: PdfDoc, file: File): Promise<PdfRead> {
    const body = new FormData(); body.append('file', new File([file], file.name, { type: 'application/pdf' }));
    const r = await ok(gw.POST('/v1/cases/{case_id}/pdf', { params: { path: { case_id: caseId }, query: { doc } }, body: body as never, bodySerializer: (b: unknown) => b as FormData } as never)) as unknown as PdfRead;
    return r;
  },
  saveKfs: (caseId: string, body: { kfs_doc_id: string; offer_id: string; version: number; which: 'kfs' | 'schedule'; title: string; text: string; rows: ChargeRow[] }) =>
    ok(gw.POST('/v1/cases/{case_id}/kfs-document', { params: { path: { case_id: caseId } }, body })),
};
