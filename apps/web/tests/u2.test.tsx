import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MoneyInput } from '@/components/MoneyInput';
import Review, { INTERNAL } from '@/components/case/Review';
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
});
