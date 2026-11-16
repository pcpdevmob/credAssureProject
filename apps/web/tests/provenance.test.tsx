import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Figure, ProvenanceProvider } from '@/components/Figure';
import ErrorBanner from '@/components/ErrorBanner';
import { toProblem } from '@/lib/problem';
import { CASE_ID } from '@/mocks/fixtures';

const open = async (key: string | undefined, label = 'Validated need') => {
  render(<ProvenanceProvider><Figure value={{ display: '₹1,42,00,000', paise: 1420000000, key }} label={label} caseId={CASE_ID} showApprox /></ProvenanceProvider>);
  const btn = screen.getByRole('button', { name: /₹1,42,00,000/ });
  await userEvent.click(btn);
  return { btn, dialog: await screen.findByRole('dialog') };
};

describe('Figure', () => {
  it('shows the exact amount, the ≈ reading and an accessible name', () => {
    render(<ProvenanceProvider><Figure value={{ display: '₹1,42,00,000', paise: 1420000000, key: 'wc.recommended_amount' }} label="Validated need" caseId={CASE_ID} showApprox /></ProvenanceProvider>);
    expect(screen.getByRole('button', { name: 'Validated need: ₹1,42,00,000, show source' })).toBeInTheDocument();
    expect(screen.getByText('≈ ₹1.42 Cr')).toBeInTheDocument();
  });
  it('without a ledger key says the source is not available yet', async () => {
    const { dialog } = await open(undefined);
    expect(within(dialog).getByText(/Source not available yet/)).toBeInTheDocument();
  });
});

describe('Provenance drawer on the lineage endpoint', () => {
  it('renders the full chain and returns focus on close', async () => {
    const { btn, dialog } = await open('wc.recommended_amount');
    expect(await within(dialog).findByText('wc.recommended_amount · v2 · INR')).toBeInTheDocument();
    expect(within(dialog).getByText(/records no formula line/)).toBeInTheDocument();
    expect(within(dialog).getByText('sha 3a9f0c1d2e4b')).toBeInTheDocument();
    expect(within(dialog).getAllByText('working_capital', { selector: 'dd' })).toHaveLength(2);
    expect(within(dialog).getByRole('button', { name: /Copy trace ID/ })).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close source panel' }));
    expect(btn).toHaveFocus();
  });
  it('follows an input fact and goes back', async () => {
    const { dialog } = await open('wc.recommended_amount');
    await userEvent.click(await within(dialog).findByRole('button', { name: /wc\.peak_shortfall/ }));
    expect(await within(dialog).findByText(/Superseded by v2/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Back to previous figure' }));
    expect(await within(dialog).findByText('wc.recommended_amount · v2 · INR')).toBeInTheDocument();
  });
  it('handles a null producer, no passages and no audit', async () => {
    const { dialog } = await open('wc.peak_shortfall');
    expect(await within(dialog).findByText(/Producer not recorded/)).toBeInTheDocument();
    expect(within(dialog).getByText('No document passages cited.')).toBeInTheDocument();
    expect(within(dialog).getByText('No audit event linked.')).toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: /Copy trace ID/ })).toBeNull();
  });
  it('handles a passage with no title, section or chunk and a partial producer', async () => {
    const { dialog } = await open('lw.reference.eblr');
    expect(await within(dialog).findByText(/Untitled document/)).toBeInTheDocument();
    expect(within(dialog).getAllByText('not recorded')).toHaveLength(2);
  });
  it('maps a 404 problem to a banner, never raw JSON', async () => {
    const { dialog } = await open('wc.nope');
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('No fact wc.nope on this case.');
    expect(dialog).not.toHaveTextContent('"type"');
  });
});

it('ErrorBanner shows what happened and the fix', () => {
  render(<ErrorBanner error={toProblem(409, { code: 'CONFLICT', detail: 'The case changed.' })} />);
  expect(screen.getByRole('alert')).toHaveTextContent('The case changed.Someone changed this case. Reload it and try again.');
});
