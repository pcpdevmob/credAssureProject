"""Qualification rules for the Employee Onboarding Agent (BRD v3.1, ONB-02).

BRD Q-03 says the exact criteria are "a synthetic rule set for the capstone": these are it.
All rule data lives here, so changing policy never means changing logic. Raise RULES_VERSION
with every change; each result and audit entry records the version that decided it.
"""

RULES_VERSION = "onboarding-rules-1.0"
TASK = "proposal_preparation"

# Roles allowed to prepare loan proposals.
AUTHORISED_ROLES = {
    "Finance Analyst",
    "Senior Finance Analyst",
    "Relationship Manager",
    "Finance Manager",
}

# Mandatory trainings: course_code -> (course name, validity in months; None = never expires)
REQUIRED_TRAININGS = {
    "INDUCTION": ("Company Induction", None),
    "COC": ("Code of Conduct Acknowledgement", 12),
    "INFOSEC": ("Information Security Awareness", 12),
    "FINDATA": ("Financial Data Handling and Privacy", 12),
    "WCPROC": ("Working-Capital and Credit Proposal Process", 24),
}

# Policies the preparer must have read and acknowledged (BRD v3.1 section 7, step 2):
# policy_code -> (policy name, validity in months)
REQUIRED_ACKNOWLEDGEMENTS = {
    "POL_CREDIT": ("Credit and Lending Policy", 12),
    "POL_DATA": ("Customer Data Protection Policy", 12),
}

# Optional case-intake checklist (from the 4-week execution guide). BRD v3.1 does not ask
# Gate 1 to check the case, so it is used only when a caller sends a checklist; the
# Working Capital stage checks data completeness. Keys are sent in lower case.
CASE_CHECKLIST = {
    "BUSINESS_IDENTITY": "Business identity present",
    "REQUESTED_AMOUNT": "Requested amount present",
    "PURCHASE_ORDER": "Purchase order available",
    "CASHFLOW_DATA": "Cash-flow data available",
}
