// One upload step for a case (progress 9.7): files are sorted by type and sent to the imports that already exist; lender
// PDFs open the ADR 0041 review and nothing from a PDF is saved before the person checks it.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import QuickUpload from '@/components/case/QuickUpload';
import { groupPdfs, pdfRole, pendingUploads, sortFiles } from '@/lib/intake';
import { caseFiles, documentService, pdfService, workbookService } from '@/services/documents';

const file = (name: string) => new File(['x'], name);

describe('sorting the files (UI-02)', () => {
  it('names a lender PDF from its file name', () => {
    expect(pdfRole('Acme Bank - Schedule of Charges.pdf')).toBe('schedule');
    expect(pdfRole('KFS-OF-07-A-v1-SCH.pdf')).toBe('schedule');
    expect(pdfRole('acme_kfs.pdf')).toBe('kfs');
    expect(pdfRole('Acme Key Facts Statement.pdf')).toBe('kfs');
    expect(pdfRole('Acme sanction letter.pdf')).toBe('offer');
  });
  it('sorts by type and keeps anything else out', () => {
    const s = sortFiles([file('case.xlsx'), file('OF-1.v1.json'), file('KFS-OF-1-v1.md'), file('a.pdf'), file('bank.csv')]);
    expect([s.workbooks.length, s.offers.length, s.kfsDocs.length, s.pdfs.length, s.unsupported.map(f => f.name)]).toEqual([1, 1, 1, 1, ['bank.csv']]);
  });
  it('pairs each KFS and schedule with the offer letter of the same lender', () => {
    const pdfs = ['Acme offer letter.pdf', 'Bharat offer letter.pdf', 'Bharat KFS.pdf', 'Acme schedule of charges.pdf', 'Zed KFS.pdf']
      .map(n => ({ file: file(n), role: pdfRole(n) }));
    const { groups, unmatched } = groupPdfs(pdfs);
    expect(groups.map(g => [g.offer.name, g.kfs?.name, g.schedule?.name])).toEqual([
      ['Acme offer letter.pdf', undefined, 'Acme schedule of charges.pdf'], ['Bharat offer letter.pdf', 'Bharat KFS.pdf', undefined]]);
    expect(unmatched.map(f => f.name)).toEqual(['Zed KFS.pdf']);
  });
  it('with one offer letter, its KFS and schedule go with it whatever their names', () => {
    const { groups } = groupPdfs(['letter.pdf', 'kfs.pdf', 'schedule.pdf'].map(n => ({ file: file(n), role: pdfRole(n) })));
    expect(groups).toHaveLength(1);
    expect([groups[0].kfs?.name, groups[0].schedule?.name]).toEqual(['kfs.pdf', 'schedule.pdf']);
  });
});

describe('the one-step upload card', () => {
  afterEach(() => vi.restoreAllMocks());
  it('sends the workbook, then offers, then KFS files to the existing imports; PDFs open the review and save nothing', async () => {
    const order: string[] = [];
    vi.spyOn(workbookService, 'upload').mockImplementation(async (_c, f) => { order.push(f.name); return [{ name: 'order.json', kind: 'order', rows: 1, flagged: false, otherCase: false }]; });
    vi.spyOn(documentService, 'upload').mockImplementation(async (_c, f) => { order.push(f.name); return { rows: 1, flagged: false, otherCase: f.name.startsWith('KFS') }; });
    const read = vi.spyOn(pdfService, 'read').mockResolvedValue({ text: 'text', draft: { fields: {}, fees: [], dropped: 0, model: 'off' } as never });
    const save = vi.spyOn(caseFiles, 'save'); const saveKfs = vi.spyOn(pdfService, 'saveKfs');
    const changed = vi.fn();
    pendingUploads.put('CA-1', [file('KFS-OF-1-v1.md'), file('Acme offer letter.pdf'), file('OF-1.v1.json'), file('case.xlsx'), file('Acme KFS.pdf'), file('notes.txt')]);
    render(<QuickUpload caseId="CA-1" onChanged={changed} />);
    expect(await screen.findByText(/case.xlsx: case data imported/)).toBeInTheDocument();
    await waitFor(() => expect(order).toEqual(['case.xlsx', 'OF-1.v1.json', 'KFS-OF-1-v1.md']));
    expect(screen.getByText(/notes.txt: not read/)).toBeInTheDocument();
    expect(await screen.findByText(/names a different case number/)).toBeInTheDocument();
    expect(await screen.findByText(/Check the offer from Acme offer letter.pdf/)).toBeInTheDocument();
    await waitFor(() => expect(read.mock.calls.map(c => [c[1], (c[2] as File).name])).toEqual([['offer', 'Acme offer letter.pdf'], ['kfs', 'Acme KFS.pdf']]));
    expect(await screen.findByText(/Key Facts Statement: Acme KFS.pdf/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Save this offer/ })).toBeDisabled(); // only after "I checked every field"
    expect(save).not.toHaveBeenCalled(); expect(saveKfs).not.toHaveBeenCalled();
    expect(changed).toHaveBeenCalled();
    expect(pendingUploads.take('CA-1')).toEqual([]); // handed over once
  });
  it('more files can be added with the picker', async () => {
    const up = vi.spyOn(documentService, 'upload').mockResolvedValue({ rows: 1, flagged: false, otherCase: false });
    render(<QuickUpload caseId="CA-2" onChanged={() => undefined} />);
    await userEvent.upload(screen.getByLabelText(/Choose files/), [file('OF-2.v1.json')]);
    expect(await screen.findByText(/OF-2.v1.json: lender offer added/)).toBeInTheDocument();
    expect(up).toHaveBeenCalledWith('CA-2', expect.any(File), 'offer');
  });
});
