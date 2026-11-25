// Findings from the 24 Nov recorded walk-through (progress 9.6): the VP was refused once before the password and code
// fields appeared, and a lender document naming another case was reported as instruction-like text.
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Review, { STEP_UP_ABOVE_PAISE } from '@/components/case/Review';
import { ProvenanceProvider } from '@/components/Figure';
import { toCase } from '@/services/cases';
import { flagNotes } from '@/services/documents';
import { CASE_ID, caseSummary } from '@/mocks/fixtures';
import type { User } from '@/types';

const vp: User = { id: 'v', name: 'Demo VP', email: 'v', role: 'VP_FINANCE', employeeId: '', mfaEnabled: true };
const director: User = { id: 'd', name: 'Demo Director', email: 'd', role: 'DIRECTOR_FINANCE', employeeId: '', mfaEnabled: true };

async function openApprove(user: User, need: { display: string; paise: number }) {
  const c = { ...toCase(caseSummary as never), stage: 'AWAITING_APPROVAL', routedTo: user.role === 'VP_FINANCE' ? 'VP_FINANCE' : 'DIRECTOR_FINANCE' } as never;
  render(<ProvenanceProvider><Review c={c} need={need} user={user} onChange={() => undefined} /></ProvenanceProvider>);
  await userEvent.click(screen.getByLabelText(/I reviewed the accuracy checks/));
  await userEvent.click(screen.getByRole('button', { name: 'Approve proposal' }));
}

describe('NFR-07, AUTH-10: approval above ₹1.5 crore asks for password and code up front', () => {
  it('shows both fields before the first confirm and sends them on the first call', async () => {
    const { approvalService } = await import('@/services/approvals');
    const decide = vi.spyOn(approvalService, 'decide').mockResolvedValueOnce(undefined);
    await openApprove(vp, { display: '₹1,75,00,000', paise: 1_750_000_000 });
    expect(screen.getByText(/Above ₹1.5 crore, confirm with your password and a code/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Type the case ID to confirm'), CASE_ID);
    const confirm = screen.getByRole('button', { name: /Confirm: approve proposal/ });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Your password'), 'pw-123');
    expect(confirm).toBeDisabled(); // the code too
    await userEvent.type(screen.getByLabelText('Code from your authenticator app'), '123456');
    await userEvent.click(confirm);
    expect(decide).toHaveBeenCalledTimes(1);
    expect(decide.mock.calls[0][4]).toBe('pw-123');
    expect(decide.mock.calls[0][7]).toBe('123456');
    decide.mockRestore();
  });
  it('does not ask at or below ₹1.5 crore (the server decides; STEP_UP_REQUIRED still opens the fields)', async () => {
    await openApprove(director, { display: '₹1,50,00,000', paise: STEP_UP_ABOVE_PAISE });
    expect(screen.queryByLabelText('Your password')).toBeNull();
    expect(screen.queryByLabelText('Code from your authenticator app')).toBeNull();
  });
});

describe('BR-01, APR-02, ADR 0021: a ₹0 funding need', () => {
  it('tells the approver that approving confirms no new facility, not a loan', () => {
    const c = { ...toCase(caseSummary as never), stage: 'AWAITING_APPROVAL', routedTo: 'DIRECTOR_FINANCE' } as never;
    render(<ProvenanceProvider><Review c={c} need={{ display: '₹0', paise: 0 }} user={director} onChange={() => undefined} /></ProvenanceProvider>);
    expect(screen.getByText('No loan needed')).toBeInTheDocument();
    expect(screen.getByText(/Approving confirms that no new facility is sought; it does not approve a loan/)).toBeInTheDocument();
  });
  it('is not shown when there is a need', () => {
    const c = { ...toCase(caseSummary as never), stage: 'AWAITING_APPROVAL', routedTo: 'DIRECTOR_FINANCE' } as never;
    render(<ProvenanceProvider><Review c={c} need={{ display: '₹1,42,00,000', paise: 1_420_000_000 }} user={director} onChange={() => undefined} /></ProvenanceProvider>);
    expect(screen.queryByText('No loan needed')).toBeNull();
  });
});

describe('BR-15, BR-14: upload notices', () => {
  it('a case-number mismatch is not reported as instruction-like text', () => {
    expect(flagNotes(['KFS_CASE_MISMATCH'])).toEqual({ flagged: false, otherCase: true });
    expect(flagNotes(['ROLE_SWITCH', 'KFS_CASE_MISMATCH'])).toEqual({ flagged: true, otherCase: true });
    expect(flagNotes([])).toEqual({ flagged: false, otherCase: false });
    expect(flagNotes(undefined)).toEqual({ flagged: false, otherCase: false });
  });
});
