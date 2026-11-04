# ADR 0012 — APR annualisation convention
Status: Accepted · 2026-11-04
Decision: APR = periodic IRR on borrower cash flows × number of periods per year (nominal), computed on the net amount received, per the RBI KFS
framework (now Annex XIII of the Commercial Banks – Responsible Business Conduct Directions 2025). Commentary on the April 2024 KFS circular
states the APR is the IRR, not XIRR or an effective rate compounded to a year.
Verification: `packages/engines/tests/test_apr_rbi_annex_b.py` reproduces the RBI Annex B worked example (sanctioned amount, fees, EMI schedule → APR)
to 0.01 pp. If it fails under nominal and passes under effective, switch the default and amend this ADR.
Switch: `APR_CONVENTION=nominal|effective` (effective used only for sensitivity in the report).
