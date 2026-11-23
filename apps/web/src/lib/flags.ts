// Plain-language text for LendWise flag codes (the code decides; this only explains). Unknown codes show as written.
export const FLAG_TEXT: Record<string, string> = {
  LW_NOT_AFFORDABLE: 'Not affordable: repayments push cash below the minimum buffer.',
  LW_LATE_OR_SHORT: 'Funds arrive too late or fall short of the recommended amount.',
  LW_HIDDEN_CHARGE: 'Hidden charge: the key facts statement lists a charge missing from the offer record.',
  LW_INSTALMENT_MISMATCH: 'Stated instalment does not match the rate, tenure and amount.',
  LW_MISSING_MATERIAL_TERM: 'A material term is missing, so the offer cannot be compared.',
  LW_RATE_MAY_RESET: 'Floating rate: it may reset.',
  LW_BENCHMARK_NOT_EXTERNAL: 'Floating rate not linked to an external benchmark.',
  LW_CGTMSE_INELIGIBLE: 'Guarantee fee on an enterprise the scheme does not cover.',
  LW_OFFER_INVALID: 'A term of this offer cannot be priced, so the offer is not compared.',
};
// LW-01: which term to correct on an offer flagged LW_OFFER_INVALID (the gateway names the terms; this only explains).
export const INVALID_TERM_TEXT: Record<string, string> = {
  principal: 'The loan amount must be more than zero.',
  annual_rate: 'The interest rate must be more than 0% and at most 100% a year.',
  tenure_months: 'The tenure must be between 1 and 360 months.',
  moratorium_months: 'The moratorium must be shorter than the tenure.',
  fees: 'A fee is negative, or more than 100% of the loan amount.',
  'insurance.premium': 'The insurance premium cannot be negative.',
  'insurance.financed': 'Insurance added to the loan (financed) is not priced. Enter the premium as paid upfront, or ask the lender for a corrected offer.',
  'guarantee.basis': 'This guarantee-fee basis is not priced. Only "guaranteed amount in year 1, then the outstanding amount" is.',
  'guarantee.annual_fee_pct': 'The guarantee fee must be between 0% and 100% a year.',
  pricing: 'No yearly cost could be worked out from these terms. Check the amounts and dates.',
};
export const invalidTermText = (term: string) => INVALID_TERM_TEXT[term] ?? `Check “${term}”.`;
export const flagText = (code: string) => FLAG_TEXT[code] ?? code;
// Flags that make an offer unusable as a recommendation.
export const BLOCKING = new Set(['LW_NOT_AFFORDABLE', 'LW_LATE_OR_SHORT', 'LW_MISSING_MATERIAL_TERM', 'LW_OFFER_INVALID']);
