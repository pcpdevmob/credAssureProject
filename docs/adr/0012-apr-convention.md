# ADR 0012 — APR annualisation convention
Status: Accepted · 2026-11-04
Decision: APR = periodic IRR on borrower cash flows × number of periods per year (nominal), computed on the net amount received, per the RBI KFS
framework (now Annex XIII of the Commercial Banks – Responsible Business Conduct Directions 2025). Commentary on the April 2024 KFS circular
states the APR is the IRR, not XIRR or an effective rate compounded to a year.
Verification: `packages/engines/tests/test_apr_rbi_annex_b.py` reproduces the RBI Annex B worked example (sanctioned amount, fees, EMI schedule → APR)
to 0.01 pp. If it fails under nominal and passes under effective, switch the default and amend this ADR.
Switch: `APR_CONVENTION=nominal|effective` (effective used only for sensitivity in the report).

Update 2026-11-05 (checked against the published example; fixture `evaluation/gold/fixtures/rbi_kfs_apr_illustration.yaml`, S21):
RBI's worked example (₹20,000 sanctioned, ₹400 fees, net ₹19,600 disbursed, 24 monthly EMIs at 15% fixed, published APR 17.07%;
RBI/2024-25/18 Annex B = RBC Directions 2025 para 348) reproduces as **17.07% nominal** using the unrounded EMI ₹969.73.
Effective annualisation gives 18.47%, so nominal is confirmed. Using the displayed rounded EMI ₹970 gives 17.10%, which fails
the 0.01 pp tolerance, so the engine test must price the exact EMI; displayed instalments are rounded only for output.
