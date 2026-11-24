// UI-02, ADR 0040, ADR 0041: one place to drop every document of a new case. This only sorts files by type and routes
// each to the existing import: the Excel workbook (case data), the lender's own files (.json offer, .md KFS / schedule)
// and lender PDFs. A PDF is never saved here: it opens the ADR 0041 review, where a person checks every field.

export type PdfRole = 'offer' | 'kfs' | 'schedule';
export type PdfGroup = { offer: File; kfs?: File; schedule?: File };
export type Sorted = { workbooks: File[]; offers: File[]; kfsDocs: File[]; pdfs: { file: File; role: PdfRole }[]; unsupported: File[] };

export const ACCEPT = '.xlsx,.pdf,.json,.md,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
const ext = (name: string) => name.toLowerCase().split('.').pop() ?? '';

/** What a lender PDF is, from its file name: a schedule of charges, a Key Facts Statement, or else the offer letter. */
export function pdfRole(name: string): PdfRole {
  const n = name.toLowerCase();
  if (/(^|[^a-z])(sch|schedule|charges?|soc)([^a-z]|$)/.test(n)) return 'schedule';
  if (/(^|[^a-z])(kfs|key[\s_-]*facts?)([^a-z]|$)/.test(n)) return 'kfs';
  return 'offer';
}

export function sortFiles(files: File[]): Sorted {
  const s: Sorted = { workbooks: [], offers: [], kfsDocs: [], pdfs: [], unsupported: [] };
  for (const f of files) {
    const e = ext(f.name);
    if (e === 'xlsx') s.workbooks.push(f);
    else if (e === 'json') s.offers.push(f);
    else if (e === 'md') s.kfsDocs.push(f);
    else if (e === 'pdf') s.pdfs.push({ file: f, role: pdfRole(f.name) });
    else s.unsupported.push(f);
  }
  return s;
}

const STOP = new Set(['pdf', 'kfs', 'key', 'facts', 'fact', 'statement', 'sch', 'schedule', 'of', 'charges', 'charge', 'soc', 'offer', 'letter', 'sanction', 'loan', 'the', 'and', 'final', 'copy', 'signed', 'v1', 'v2']);
const tokens = (name: string) => new Set(name.toLowerCase().replace(/\.[a-z0-9]+$/, '').split(/[^a-z0-9]+/).filter(t => t.length > 1 && !STOP.has(t)));

/** One review per offer letter, with the KFS and schedule whose names share the most words with it (the lender's name,
 *  usually). With one letter, it takes the first KFS and schedule. Anything not matched is left for the person. */
export function groupPdfs(pdfs: { file: File; role: PdfRole }[]): { groups: PdfGroup[]; unmatched: File[] } {
  const groups: PdfGroup[] = pdfs.filter(p => p.role === 'offer').map(p => ({ offer: p.file }));
  const unmatched: File[] = [];
  for (const p of pdfs.filter(x => x.role !== 'offer')) {
    const slot = p.role as 'kfs' | 'schedule';
    const free = groups.filter(g => !g[slot]);
    let best: PdfGroup | undefined;
    if (groups.length === 1) best = free[0];
    else {
      const mine = tokens(p.file.name); let score = 0;
      for (const g of free) { const n = [...tokens(g.offer.name)].filter(t => mine.has(t)).length; if (n > score) { score = n; best = g; } }
    }
    if (best) best[slot] = p.file; else unmatched.push(p.file);
  }
  return { groups, unmatched };
}

/** Files chosen on the New case page, handed to the case's Documents tab once the case exists (this browser tab only). */
const pending = new Map<string, File[]>();
export const pendingUploads = {
  put: (caseId: string, files: File[]) => { if (files.length) pending.set(caseId, files); },
  take: (caseId: string): File[] => { const f = pending.get(caseId) ?? []; pending.delete(caseId); return f; },
};
