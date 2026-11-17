import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MoneyInput } from '@/components/MoneyInput';
import Review, { INTERNAL, STALE_REASON } from '@/components/case/Review';
import { ProvenanceProvider } from '@/components/Figure';
import { caseService, toCase } from '@/services/cases';
import { CASE_ID, caseSummary } from '@/mocks/fixtures';
import type { User } from '@/types';

describe('MoneyInput', () => {
  it('shows the parsed amount in Indian grouping before submit and hands paise up', async () => {
    const onPaise = vi.fn();
    render(<MoneyInput label="Requested amount" onPaise={onPaise} />);
    await userEvent.type(screen.getByLabelText('Requested amount'), '1.42 crore');
    expect(screen.getByText('₹1,42,00,000')).toBeInTheDocument();
    expect(onPaise).toHaveBeenLastCalledWith(1420000000n);
    await userEvent.type(screen.getByLabelText('Requested amount'), 'x');
    expect(screen.getByText('Not a valid amount')).toBeInTheDocument();
    expect(onPaise).toHaveBeenLastCalledWith(null);
  });
});

describe('case list from the gateway', () => {
  it('takes totals and per-case validated amounts from the API, never summing in the browser', async () => {
    const { items, totals } = await caseService.summary();
    expect(items[0].recommendedAmount).toEqual({ display: '₹1,42,00,000', paise: 1420000000, key: 'wc.recommended_amount' });
    expect(totals.over_borrowing_avoided.display).toBe('₹58,00,000');
  });
});

describe('approval step-up', () => {
  const director: User = { id: 'd', name: 'Demo Director', email: 'd', role: 'DIRECTOR_FINANCE', employeeId: '' };
  it('states approval is internal and confirms only after the case ID is typed', async () => {
    const c = toCase(caseSummary as never);
    render(<ProvenanceProvider><Review c={c} need={c.recommendedAmount} user={director} onChange={() => undefined} /></ProvenanceProvider>);
    expect(screen.getAllByText(INTERNAL).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: 'Approve proposal' }));
    const confirm = screen.getByRole('button', { name: /Confirm: approve proposal/ });
    expect(confirm).toBeDisabled();
    await userEvent.type(screen.getByLabelText('Type the case ID to confirm'), CASE_ID);
    expect(confirm).toBeEnabled();
  });
  it('asks for the password only when the gateway answers STEP_UP_REQUIRED, then sends it (NFR-07)', async () => {
    const c = { ...toCase(caseSummary as never), stage: 'AWAITING_APPROVAL', routedTo: 'DIRECTOR_FINANCE' } as never;
    const { approvalService } = await import('@/services/approvals');
    const { ApiProblem } = await import('@/lib/problem');
    const decide = vi.spyOn(approvalService, 'decide')
      .mockRejectedValueOnce(new ApiProblem(403, 'STEP_UP_REQUIRED', { what: 'needs your password again', fix: '' }, []))
      .mockResolvedValueOnce(undefined);
    render(<ProvenanceProvider><Review c={c} user={director} onChange={() => undefined} /></ProvenanceProvider>);
    await userEvent.click(screen.getByRole('button', { name: 'Approve proposal' }));
    expect(screen.queryByLabelText('Your password')).toBeNull();
    await userEvent.type(screen.getByLabelText('Type the case ID to confirm'), CASE_ID);
    const confirm = screen.getByRole('button', { name: /Confirm: approve proposal/ });
    await userEvent.click(confirm);
    expect(decide.mock.calls[0][4]).toBeUndefined();
    expect(confirm).toBeDisabled(); // password now required
    await userEvent.type(screen.getByLabelText('Your password'), 'pw-123');
    await userEvent.click(confirm);
    expect(decide.mock.calls[1][4]).toBe('pw-123');
    decide.mockRestore();
  });
});

describe('stale report (ADR 0003 §3, Phase 10b)', () => {
  const director: User = { id: 'd', name: 'Demo Director', email: 'd', role: 'DIRECTOR_FINANCE', employeeId: '' };
  const preparer: User = { id: 'p', name: 'Demo Preparer', email: 'p', role: 'PREPARER', employeeId: 'E1' };
  const c = { ...toCase(caseSummary as never), stage: 'AWAITING_APPROVAL', routedTo: 'DIRECTOR_FINANCE' } as never;
  it('disables Approve with the reason; reject and return stay available', async () => {
    const { lendWiseService } = await import('@/services/lendwise');
    const w = vi.spyOn(lendWiseService, 'warnings').mockResolvedValue({ warnings: ['report_stale'], reportVersion: 1 });
    render(<ProvenanceProvider><Review c={c} user={director} onChange={() => undefined} /></ProvenanceProvider>);
    expect(await screen.findByText(STALE_REASON)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve proposal' })).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Regenerate report' })).toBeNull();
    await userEvent.click(screen.getByLabelText('Reject proposal'));
    await userEvent.type(screen.getByLabelText(/Comment/), 'figures moved');
    expect(screen.getByRole('button', { name: 'Reject proposal' })).toBeEnabled();
    w.mockRestore();
  });
  it('offers the preparer Regenerate, which makes a new version and re-checks', async () => {
    const { lendWiseService } = await import('@/services/lendwise');
    const { reportService } = await import('@/services/report');
    const w = vi.spyOn(lendWiseService, 'warnings').mockResolvedValueOnce({ warnings: ['report_stale'], reportVersion: 1 }).mockResolvedValue({ warnings: [], reportVersion: 2 });
    const r = vi.spyOn(reportService, 'regenerate').mockResolvedValue({ version: 2, stale: false, reasons: [] });
    const onChange = vi.fn();
    render(<ProvenanceProvider><Review c={c} user={preparer} onChange={onChange} /></ProvenanceProvider>);
    await userEvent.click(await screen.findByRole('button', { name: 'Regenerate report' }));
    expect(r).toHaveBeenCalledWith(CASE_ID);
    expect(onChange).toHaveBeenCalled();
    expect(await screen.findByText(/Awaiting decision/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Regenerate report' })).toBeNull();
    w.mockRestore(); r.mockRestore();
  });
});
