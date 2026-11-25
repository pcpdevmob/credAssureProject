// ADR 0041: an offer read from PDFs. The draft becomes a form the person checks; the reviewed form becomes the same offer
// JSON a typed upload sends. Nothing is saved until the person confirms they checked every field.
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';
import { buildOffer, reviewFromDraft, type OfferDraft } from '@/lib/offerPdf';
import PdfOffer from '@/components/case/PdfOffer';

const DRAFT: OfferDraft = {
  model: 'used', dropped: 1,
  fields: {
    lender_name: { value: 'Kaveri Finance Bank', quote: 'Kaveri Finance Bank' },
    principal: { value: '15700000', quote: 'Rs. 1,57,00,000' },
    annual_rate: { value: '0.1045', quote: '10.45% p.a.' },
    rate_type: { value: 'fixed', quote: 'fixed' },
    tenure_months: { value: 12, quote: '12 months' },
    moratorium_months: { value: 3, quote: '3 months' },
    repayment_method: { value: 'emi', quote: 'EMI' },
    disbursal_date: { value: '2026-11-18', quote: '18-11-2026' },
    first_repayment_date: { value: '2027-03-18', quote: '18-03-2027' },
  },
  fees: [{ name: 'Processing fee', timing: 'upfront', basis: 'pct_of_principal', value: '0.0235', gst_applicable: true, quote: '2.35% of the loan amount + GST' }],
};

describe('ADR 0041 offer from PDF', () => {
  it('turns the reviewed draft into schema 1.0 offer JSON with exact values', () => {
    const r = reviewFromDraft(DRAFT);
    expect(r.values.principal).toBe('₹1,57,00,000');
    expect(r.values.annual_rate).toBe('10.45');
    const b = buildOffer(r, 'AB12');
    expect(b.missing).toEqual([]);
    const o = JSON.parse(b.json!);
    expect(o).toMatchObject({ offer_id: 'OF-AB12', kfs_doc_id: 'KFS-OF-AB12-v1', lender_id: 'KFB-AB12', principal: '15700000', annual_rate: '0.1045',
      tenure_months: 12, repayment: { frequency: 'monthly', method: 'emi' }, fees: [{ name: 'Processing fee', basis: 'pct_of_principal', value: '0.0235', timing: 'upfront', gst_applicable: true }] });
    expect(o.benchmark).toBeUndefined();
  });
  it('accepts lakh and crore, flags bad input, and lists missing terms instead of guessing', () => {
    const r = reviewFromDraft(null);
    r.values.lender_name = 'Kaveri Finance Bank'; r.values.principal = '1.57 crore'; r.values.annual_rate = 'ten';
    const bad = buildOffer(r, 'X1');
    expect(bad.json).toBeUndefined(); expect(bad.problems.annual_rate).toMatch(/percentage/);
    r.values.annual_rate = '10.45';
    const ok = buildOffer(r, 'X1');
    expect(JSON.parse(ok.json!).principal).toBe('15700000');
    expect(ok.missing).toEqual(expect.arrayContaining(['Tenure (months)', 'Fees']));
    expect(JSON.parse(ok.json!).fees).toBeUndefined(); // no fees stated ≠ "no fees"
    r.noFees = true; expect(JSON.parse(buildOffer(r, 'X1').json!).fees).toEqual([]);
  });
  it('shows where each value was found and saves only after the person confirms', async () => {
    let saved: string | null = null;
    server.use(
      http.post(`${API}/v1/cases/:id/pdf`, () => HttpResponse.json({ case_id: 'CA-1', doc: 'offer', sha256: 'x', text: 't', draft: DRAFT })),
      http.post(`${API}/v1/cases/:id/files`, async ({ request }) => { saved = await ((await request.formData()).get('file') as File).text(); return HttpResponse.json({ rows: 1 }, { status: 201 }); }),
    );
    render(<PdfOffer caseId="CA-1" onSaved={() => {}} />);
    await userEvent.upload(screen.getByLabelText(/offer letter or sanction letter/), new File(['%PDF-1.4'], 'letter.pdf', { type: 'application/pdf' }));
    expect(await screen.findByText(/Found in the PDF: “Rs. 1,57,00,000”/)).toBeInTheDocument();
    expect(screen.getByText(/1 suggestion\(s\) were left out/)).toBeInTheDocument();
    const save = screen.getByRole('button', { name: /Save this offer/ });
    expect(save).toBeDisabled();
    await userEvent.click(screen.getByLabelText(/I checked every field/));
    await userEvent.click(save);
    expect(await screen.findByText(/was saved/)).toBeInTheDocument();
    expect(JSON.parse(saved!)).toMatchObject({ principal: '15700000', lender_name: 'Kaveri Finance Bank' });
  });
  it('gives every offer saved from the same form its own id, so a second offer never replaces the first', async () => {
    const saved: string[] = [];
    server.use(
      http.post(`${API}/v1/cases/:id/pdf`, () => HttpResponse.json({ case_id: 'CA-1', doc: 'offer', sha256: 'x', text: 't', draft: DRAFT })),
      http.post(`${API}/v1/cases/:id/files`, async ({ request }) => { saved.push(await ((await request.formData()).get('file') as File).text()); return HttpResponse.json({ rows: 1 }, { status: 201 }); }),
    );
    render(<PdfOffer caseId="CA-1" onSaved={() => {}} />);
    for (let n = 1; n <= 2; n++) {
      await userEvent.upload(screen.getByLabelText(/offer letter or sanction letter/), new File(['%PDF-1.4'], `letter${n}.pdf`, { type: 'application/pdf' }));
      await screen.findByText(/Found in the PDF: “Rs. 1,57,00,000”/);
      await userEvent.click(screen.getByLabelText(/I checked every field/));
      await userEvent.click(screen.getByRole('button', { name: /Save this offer/ }));
      await screen.findByText(/was saved/);
    }
    const [a, b] = saved.map(t => JSON.parse(t) as { offer_id: string; kfs_doc_id: string });
    expect(a.offer_id).not.toBe(b.offer_id);
    expect(a.kfs_doc_id).not.toBe(b.kfs_doc_id);
  });
});
