import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';
import { MissingDocPdf, lenderDocOf } from '@/components/case/PdfOffer';
import RunPanel, { fileAskedFor, lenderFileAskedFor } from '@/components/case/RunPanel';
import { toCase } from '@/services/cases';
import { caseSummary } from '@/mocks/fixtures';
import type { WorkflowGate } from '@/types';

const SCHEDULE = 'Can you upload the schedule of charges KFS-OF-07-A-v1-SCH for this case?';
const gates = [{ id: 'lendwise', name: 'Lender comparison', decision: 'NEEDS_INPUT' }] as unknown as WorkflowGate[];
const panel = (question: string) => {
  const c = { ...toCase(caseSummary as never), stage: 'LENDWISE', question } as never;
  return render(<RunPanel c={c} gates={gates} canRun live={null} setLive={() => undefined} onDone={() => undefined} />);
};

describe('which form a stage question opens (SUP-06)', () => {
  it('reads the lender file a lender-comparison question asks for', () => {
    expect(lenderFileAskedFor(SCHEDULE)).toBe('KFS-OF-07-A-v1-SCH.md');
    expect(lenderFileAskedFor('Can you upload the lender offers for this case (one JSON file per offer)?')).toBe('');
    expect(lenderFileAskedFor('opening_position.json has no min_cash_buffer; what is it?')).toBeNull();
    expect(fileAskedFor('opening_position.json has no min_cash_buffer; what is it?')).toBe('opening_position');
    expect(lenderFileAskedFor('Which customer invoice is INV-12 a duplicate of?')).toBeNull();
    expect(lenderFileAskedFor(null)).toBeNull();
  });

  it('shows the lender file upload and the PDF route, names the file and hides the case-data forms', async () => {
    panel(SCHEDULE);
    expect(screen.getByTestId('stage-question')).toHaveTextContent('KFS-OF-07-A-v1-SCH');
    expect(screen.getByTestId('lender-file-needed')).toHaveTextContent('File needed: KFS-OF-07-A-v1-SCH.md');
    expect(screen.getByLabelText(/Or, if you have it as a file already/)).toHaveAttribute('accept', '.json,.md');
    expect(await screen.findByLabelText('The lender\'s schedule of charges for OF-07-A (PDF)')).toHaveAttribute('accept', '.pdf,application/pdf');
    expect(screen.queryByText('Section to correct')).not.toBeInTheDocument(); // the bug: it offered "Opening cash and credit lines"
    expect(screen.getByText(/Add the lender’s file below, then press Continue/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
  });

  it('asks for lender files in general when no document is named', () => {
    panel('Can you upload the lender offers for this case (one JSON file per offer)?');
    expect(screen.getByLabelText(/Choose the lender’s file or files/)).toHaveAttribute('accept', '.json,.md');
    expect(screen.getByTestId('lender-file-needed')).toHaveTextContent("from the lender's PDFs on the Case data tab");
  });

  it('keeps the case-data form for a case-data question', () => {
    panel('Which customer invoice is INV-12 a duplicate of?');
    expect(screen.getByText('Section to correct')).toBeInTheDocument();
    expect(screen.queryByTestId('lender-file-needed')).not.toBeInTheDocument();
  });
});

describe('the missing document from the lender’s PDF (ADR 0041)', () => {
  it('maps a document id to its offer', () => {
    expect(lenderDocOf('KFS-OF-07-A-v1-SCH')).toEqual({ kfsDocId: 'KFS-OF-07-A-v1', offerId: 'OF-07-A', version: 1, which: 'schedule' });
    expect(lenderDocOf('KFS-OF-07-B-v2')).toEqual({ kfsDocId: 'KFS-OF-07-B-v2', offerId: 'OF-07-B', version: 2, which: 'kfs' });
    expect(lenderDocOf('nonsense')).toBeNull();
  });

  it('reads the schedule PDF, lets the person check the charges, and saves it under the offer already in the case', async () => {
    let saved: Record<string, unknown> | undefined;
    server.use(
      http.post(`${API}/v1/cases/:id/pdf`, ({ request }) => {
        expect(new URL(request.url).searchParams.get('doc')).toBe('schedule');
        return HttpResponse.json({ case_id: 'CA-1', doc: 'schedule', sha256: 'x', text: 'Processing fee 0.86% + GST',
          draft: { model: 'used', fields: {}, fees: [], rows: [{ name: 'Processing fee', timing: 'upfront', amount: '0.86% of the loan amount + GST' }] } });
      }),
      http.post(`${API}/v1/cases/:id/kfs-document`, async ({ request }) => { saved = await request.json() as Record<string, unknown>; return HttpResponse.json({ rows: 1 }, { status: 201 }); }),
    );
    render(<MissingDocPdf caseId="CA-1" docId="KFS-OF-07-A-v1-SCH" />);
    await userEvent.upload(screen.getByLabelText('The lender\'s schedule of charges for OF-07-A (PDF)'), new File(['%PDF'], 'sch.pdf', { type: 'application/pdf' }));
    expect(await screen.findByDisplayValue('Processing fee')).toBeInTheDocument();
    const save = screen.getByRole('button', { name: /Save the schedule of charges/ });
    expect(save).toBeDisabled(); // nothing is saved before the person confirms
    await userEvent.click(screen.getByLabelText(/I checked this against the lender/));
    await userEvent.click(save);
    expect(await screen.findByRole('status')).toHaveTextContent('The schedule of charges for OF-07-A was saved');
    expect(saved).toMatchObject({ kfs_doc_id: 'KFS-OF-07-A-v1', offer_id: 'OF-07-A', version: 1, which: 'schedule',
      rows: [{ name: 'Processing fee', timing: 'upfront', amount: '0.86% of the loan amount + GST' }] });
  });
});
