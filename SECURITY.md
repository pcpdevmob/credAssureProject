# Security

CredAssure is a capstone project that uses synthetic data only. It has no real borrower, employee or lender data and
never accepts, signs or submits a lender offer.

## Reporting a problem
Open a private issue for the maintainers (or message the integration lead) with steps to reproduce. Do not include real
personal identifiers (Aadhaar, PAN, account numbers) in reports.

## Where the controls are described
- Threat model: `docs/adr/0002-threat-model.md`
- Guardrails: `.cursor/rules/10-security-guardrails.mdc`
- Secrets: environment only (`.env`, gitignored); gitleaks runs in pre-commit and CI.
