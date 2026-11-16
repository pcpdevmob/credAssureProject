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
  LW_OFFER_INVALID: 'The offer file is invalid.',
};
export const flagText = (code: string) => FLAG_TEXT[code] ?? code;
// Flags that make an offer unusable as a recommendation.
export const BLOCKING = new Set(['LW_NOT_AFFORDABLE', 'LW_LATE_OR_SHORT', 'LW_MISSING_MATERIAL_TERM', 'LW_OFFER_INVALID']);
