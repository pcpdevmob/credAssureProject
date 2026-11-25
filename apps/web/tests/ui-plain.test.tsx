// UI thread (20 Nov): non-technical operator. Case-data forms build the same files the upload endpoint takes; readiness,
// history and dates read in plain words; nothing shows "Invalid Date".
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from './setup';
import { API } from '@/mocks/handlers';
import { FORMS, blankState, build, fractionFromPercent, isBlankRow, percentFromFraction, placeServerError, plainText, rowsFromPaste, stateFromStored } from '@/lib/caseForms';
import { d, dt } from '@/lib/format';
import { factLabel } from '@/lib/plain';
import { describe as describeEvent } from '@/components/case/History';
import Readiness from '@/components/case/Readiness';
import DataEditor from '@/components/case/DataEditor';
import type { HistoryEvent } from '@/types';

describe('dates', () => {
  it('never renders Invalid Date', () => {
    expect(d('')).toBe('—'); expect(dt(undefined)).toBe('—'); expect(d('not a date')).toBe('—');
    expect(d('2027-05-15')).toBe('15 May 2027');
    expect(dt('2026-11-20T13:46:32.396609+00:00')).toMatch(/20 Nov 2026, 07:16 pm/i);
  });
});

describe('case-data forms', () => {
  it('percent is a decimal shift, no float arithmetic', () => {
    expect(percentFromFraction('0.1')).toBe('10'); expect(percentFromFraction('0.125')).toBe('12.5');
    expect(fractionFromPercent('10')).toBe('0.1'); expect(fractionFromPercent('12.5')).toBe('0.125'); expect(fractionFromPercent('5')).toBe('0.05');
    expect(fractionFromPercent('ten')).toBeNull();
  });
  it('round-trips a stored order to the same JSON the gateway stored', () => {
    const stored = { schema_version: '1.0', order_ref: 'PO-1', customer_name: 'C', order_value: '32000000', currency: 'INR', po_date: '2026-11-04', delivery_weeks: [3, 6, 9], payment_terms_days: 45, advance_pct: '0.1', enterprise_class: 'small', investment: '120000000', turnover: '830000000', home_state: 'IN-MH' };
    const s = stateFromStored(FORMS.order, stored);
    expect(s.values.order_value).toBe('₹3,20,00,000'); expect(s.values.advance_pct).toBe('10');
    expect(JSON.parse(build(FORMS.order, s).text!)).toEqual(stored);
  });
  it('accepts lakh and crore in a table and writes plain rupees to the CSV', () => {
    const out = build(FORMS.receipts, { values: {}, tables: { rows: [{ week: '1', source: 'order_advance', amount: '1.5 lakh', confirmed: 'true' }, { week: '', source: '', amount: '', confirmed: '' }] } });
    expect(out.text).toBe('week,source,amount,confirmed\n1,order_advance,150000,true\n');
  });
  it('reports what to fix, by row and field, before anything is sent', () => {
    const out = build(FORMS.costs, { values: {}, tables: { rows: [{ week: 'one', category: 'labour', amount: 'lots' }] } });
    expect(out.text).toBeUndefined();
    expect(out.problems.map(p => [p.row, p.field])).toEqual([[1, 'week'], [1, 'amount']]);
  });
  it('places gateway errors on the field and row they name', () => {
    expect(placeServerError(FORMS.opening_position, { field: 'credit_lines.0.sanctioned', reason: 'x' })).toMatchObject({ path: 'credit_lines', row: 1, field: 'sanctioned' });
    expect(placeServerError(FORMS.costs, { field: 'amount', row: 3, reason: 'x' })).toMatchObject({ path: 'rows', row: 3, field: 'amount' });
  });
  it('takes rows pasted from a spreadsheet, skipping the header', () => {
    expect(rowsFromPaste(FORMS.receipts.fields, 'Week\tFrom\tAmount\tConfirmed?\n2\tOrder advance\t1,00,000\tYes')).toEqual([{ week: '2', source: 'order_advance', amount: '1,00,000', confirmed: 'true' }]);
  });
  it('rewrites file and field names in stage questions', () => {
    expect(plainText('What is the min cash buffer for this case? Please upload opening_position.json with it filled in.'))
      .toBe('What is the minimum cash buffer for this case? Please add it in “Opening cash and credit lines”.');
    expect(plainText('Order receipts do not add up to the order value. Can you upload a corrected receipts.csv?'))
      .toBe('Order receipts do not add up to the order value. Can you correct “Expected receipts”?');
  });
  it('ignores the starting row of a new table: its preset choice is not typed data', () => {
    const start = blankState(FORMS.costs).tables.rows[0];
    expect(start.category).toBe('components');
    expect(isBlankRow(FORMS.costs.fields, start)).toBe(true);
    expect(isBlankRow(FORMS.costs.fields, { ...start, category: 'labour' })).toBe(false);
    const out = build(FORMS.costs, { values: {}, tables: { rows: [start, { week: '1', category: 'labour', amount: '3,65,000' }] } });
    expect(out.problems).toEqual([]);
    expect(out.text).toBe('week,category,amount\n1,labour,365000\n');
  });
  it('pastes rows into a new table and saves them without the empty starting row', async () => {
    let sent = '';
    server.use(http.post(`${API}/v1/cases/:id/files`, async ({ request }) => {
      sent = await ((await request.formData()).get('file') as File).text();
      return HttpResponse.json({ kind: 'costs', rows: 2, flagged: false }, { status: 201 });
    }));
    render(<DataEditor caseId="CA-1" kind="costs" stored={undefined} canEdit />);
    await userEvent.click(screen.getByRole('button', { name: /Paste rows from Excel/ }));
    await userEvent.click(screen.getByRole('textbox', { name: /Copy the rows/ }));
    await userEvent.paste('Week\tCost type\tAmount\n1\tComponents\t13,38,300\n1\tLabour\t3,65,000');
    await userEvent.click(screen.getByRole('button', { name: /Add these rows/ }));
    await userEvent.click(screen.getByRole('button', { name: /Save weekly costs/ }));
    expect(sent).toBe('week,category,amount\n1,components,1338300\n1,labour,365000\n');
  });
  it('saves through the upload endpoint and shows gateway errors in plain words on the field', async () => {
    let sent = '';
    server.use(http.post(`${API}/v1/cases/:id/files`, async ({ request }) => {
      sent = await ((await request.formData()).get('file') as File).text();
      return HttpResponse.json({ type: 'about:blank', title: 'x', status: 422, code: 'VALIDATION_FAILED', detail: 'costs failed validation', errors: [{ field: 'amount', row: 1, reason: 'Input should be a valid decimal' }] }, { status: 422 });
    }));
    render(<DataEditor caseId="CA-1" kind="costs" stored={[{ week: 1, category: 'labour', amount: '365000' }]} canEdit />);
    await userEvent.click(screen.getByRole('button', { name: /Save weekly costs/ }));
    expect(sent).toBe('week,category,amount\n1,labour,365000\n');
    expect(await screen.findByText('Use an amount such as 1,42,000 or 1.42 lakh')).toBeTruthy();
    expect(screen.getByLabelText('Amount, row 1').getAttribute('aria-invalid')).toBe('true');
  });
});

describe('readiness and history in plain words', () => {
  it('lists each rule with its HR evidence', () => {
    render(<Readiness r={{ decision: 'NO_GO', checkedAt: '2026-11-20T13:46:32+00:00', attempt: 1, question: null,
      preparer: { empId: 'E009', name: 'Ravi Synthetic-09', role: 'finance_analyst', department: 'Finance', active: true },
      rules: [{ rule: 'role', outcome: 'FAIL', kind: 'role', role: 'finance_analyst' }, { rule: 'FIN-101', outcome: 'PASS', kind: 'training', training: { status: 'completed', completed_on: '2026-04-11', expires_on: '2027-04-11' } }],
      blockers: [{ message: 'authorised preparer role [role]: Your HR role is not authorised to prepare loan proposals.', nextAction: 'Ask a credit proposal officer to prepare this case.' }] }} />);
    expect(screen.getByText('Ravi Synthetic-09')).toBeTruthy();
    expect(screen.getByText('Blocked')).toBeTruthy();
    expect(screen.getByText('1 of 2 checks passed')).toBeTruthy();
    expect(screen.getByText('HR role: Finance analyst')).toBeTruthy();
    expect(screen.getByText(/valid until 11 Apr 2027/)).toBeTruthy();
    expect(within(screen.getByRole('alert')).getByText(/What to do: Ask a credit proposal officer/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Invalid Date|\[role\]/);
  });
  it('words audit events', () => {
    const e = (type: string, details: Record<string, unknown>, role: string | null = null): HistoryEvent => ({ seq: 1, ts: '2026-11-20T13:46:32+00:00', type, actor: 'u', actorName: 'asha', actorRole: role, details });
    expect(describeEvent(e('STAGE_COMPLETED', { stage: 'working_capital', decision: 'NEEDS_INPUT' })).text).toBe('Funding need: needs information.');
    expect(describeEvent(e('ROUTED', { route: 'vp_finance' })).text).toBe('Sent for approval to the VP, Finance.');
    expect(describeEvent(e('DECISION_RECORDED', { decision: 'return', return_stage: 'lendwise', comment: 'Fix offer B' }, 'director_finance')))
      .toMatchObject({ text: 'asha (Director, Finance) returned the proposal, returning it to lender comparison.', note: 'Comment: “Fix offer B”' });
    const fact = ['lw', 'OF-01-A', 'v2', 'apr'].join('.'); // a ledger key, built so secret scanners do not read it as a credential
    expect(describeEvent(e('FACT_WRITTEN', { key: fact })).key).toBe(false);
  });
  it('names ledger figures', () => {
    expect(factLabel('wc.recommended_amount')).toBe('Validated funding need');
    expect(factLabel('lw.OF-01-B.v2.total_repayment')).toBe('Offer OF-01-B total repayment');
    expect(factLabel('onb.rule.FIN-101')).toBe('Credit policy training');
  });
});

describe('Excel workbook import (ADR 0040)', () => {
  it('shows sheet, row and column for each error and says nothing was imported', async () => {
    const Documents = (await import('@/components/case/Documents')).default;
    server.use(
      http.get(`${API}/v1/cases/:id/files`, () => HttpResponse.json({ case_id: 'CA-1', files: [], documents: [] })),
      http.post(`${API}/v1/cases/:id/workbook`, () => HttpResponse.json({ type: 'about:blank', title: 'x', status: 422, code: 'VALIDATION_FAILED', detail: 'workbook failed validation', errors: [{ field: 'costs.amount', row: 5, reason: 'Input should be a valid decimal' }] }, { status: 422 })),
    );
    render(<Documents caseId="CA-1" canEdit />);
    await userEvent.upload(screen.getByLabelText(/Upload the filled workbook/), new File(['x'], 'case.xlsx'));
    expect(await screen.findByText(/Nothing was imported from case.xlsx/)).toBeTruthy();
    expect(screen.getByText(/Sheet “Weekly costs”, row 5/)).toBeTruthy();
    expect(screen.getByText(/Use an amount such as/)).toBeTruthy();
  });
  it('lists what was imported', async () => {
    const Documents = (await import('@/components/case/Documents')).default;
    server.use(
      http.get(`${API}/v1/cases/:id/files`, () => HttpResponse.json({ case_id: 'CA-1', files: [], documents: [] })),
      http.post(`${API}/v1/cases/:id/workbook`, () => HttpResponse.json({ case_id: 'CA-1', files: [{ name: 'costs.csv', kind: 'costs', rows: 156, injection_flags: [] }, { name: 'offers/OF-01-A.v1.json', kind: 'offer', rows: 1, injection_flags: [] }] }, { status: 201 })),
    );
    render(<Documents caseId="CA-1" canEdit />);
    await userEvent.upload(screen.getByLabelText(/Upload the filled workbook/), new File(['x'], 'case.xlsx'));
    expect(await screen.findByText('Weekly costs: 156 rows')).toBeTruthy();
    expect(screen.getByText(/1 lender offer/)).toBeTruthy();
  });
});
