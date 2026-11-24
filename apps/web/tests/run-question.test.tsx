import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
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

  it('shows the lender file upload, names the file and hides the case-data forms', () => {
    panel(SCHEDULE);
    expect(screen.getByTestId('stage-question')).toHaveTextContent('KFS-OF-07-A-v1-SCH');
    expect(screen.getByTestId('lender-file-needed')).toHaveTextContent('File needed: KFS-OF-07-A-v1-SCH.md');
    const input = screen.getByLabelText(/Choose the lender’s file or files/);
    expect(input).toHaveAttribute('accept', '.json,.md');
    expect(screen.queryByText('Section to correct')).not.toBeInTheDocument(); // the bug: it offered "Opening cash and credit lines"
    expect(screen.getByText(/Add the lender’s file below, then press Continue/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
  });

  it('keeps the case-data form for a case-data question', () => {
    panel('Which customer invoice is INV-12 a duplicate of?');
    expect(screen.getByText('Section to correct')).toBeInTheDocument();
    expect(screen.queryByTestId('lender-file-needed')).not.toBeInTheDocument();
  });
});
