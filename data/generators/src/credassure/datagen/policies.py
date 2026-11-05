"""S02 synthetic internal policies and FAQ (DATA_SPEC §5): 60-90 Markdown docs, collection ``policy``.

Team-written company documents for a fictional electronics MSME. Every doc carries ``effective_from``
and ``superseded_by`` so the copilot's date filter (KR-04) can be tested: WC-POL v1 and v2 are
superseded by v3. Regulatory facts are paraphrased from the public sources named in brackets
(R-IDs, docs/data/DATA_RESOURCES.md); the copilot must cite those sources, not these summaries.
"""

from typing import Any

from .common import OUT, write_text

POLICIES: list[dict[str, Any]] = [
    {
        "doc_id": "POL-WC-POL-v1",
        "title": "Working-capital borrowing policy",
        "version": "v1",
        "effective_from": "2023-04-01",
        "superseded_by": "POL-WC-POL-v2",
        "body": [
            "Borrowing is sized on a monthly cash budget over six months.",
            "A minimum cash buffer of ₹5,00,000 is kept at all times.",
            "Proposals above ₹1,00,00,000 go to the Managing Director.",
        ],
    },
    {
        "doc_id": "POL-WC-POL-v2",
        "title": "Working-capital borrowing policy",
        "version": "v2",
        "effective_from": "2024-04-01",
        "superseded_by": "POL-WC-POL-v3",
        "body": [
            "Borrowing is sized on a weekly cash budget over 13 weeks.",
            "The minimum cash buffer is set per case by the Director, Finance.",
            "Proposals above ₹1,50,00,000 go to the VP, Finance.",
        ],
    },
    {
        "doc_id": "POL-WC-POL-v3",
        "title": "Working-capital borrowing policy",
        "version": "v3",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Borrowing is sized on a weekly cash budget over 26 weeks, using confirmed receipts only.",
            "Recommended facility = peak cumulative shortfall + minimum cash buffer - undrawn sanctioned limits - confirmed mitigations, never below zero, rounded up to the next ₹1,00,000.",
            "The indicative amount in a request is an input, never the default loan amount.",
            "An offer whose repayments push cash below the minimum buffer is never recommended.",
            "Offers are compared on APR including every fee, GST on fees and any guarantee fee passed on to the company.",
            "Approval is internal. The company chooses its lender; no employee accepts or signs an offer through the proposal system.",
        ],
    },
    {
        "doc_id": "POL-APPROVAL-MATRIX-v1",
        "title": "Approval matrix for working-capital proposals",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Validated amount below ₹1,50,00,000: Director, Finance.",
            "Validated amount above ₹1,50,00,000: VP, Finance.",
            "Exactly ₹1,50,00,000: held for a human decision until the business owner sets the rule.",
            "A preparer may not approve their own proposal.",
            "An approver may approve, reject or return the proposal to a named stage, with a comment.",
        ],
    },
    {
        "doc_id": "POL-DOA-v1",
        "title": "Delegation of authority (finance)",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Credit proposal officers and senior finance analysts may prepare borrowing proposals.",
            "Finance analysts and accounts executives may not prepare proposals.",
            "Authority cannot be delegated by chat or email.",
        ],
    },
    {
        "doc_id": "POL-TRAINING-v1",
        "title": "Mandatory training catalogue",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "FIN-101 Credit Policy: valid 12 months.",
            "AML-201 AML/KYC: valid 12 months (based on the RBI KYC Directions, R-RBI-09).",
            "DPDP-101 Data Protection: valid 24 months (based on the DPDP Act 2023 and Rules 2025, R-DPDP-01).",
            "Training counts as complete only when the HR record says so.",
            "Preparers must also acknowledge WC-POL v3.",
        ],
    },
    {
        "doc_id": "POL-DATA-HANDLING-v1",
        "title": "Data-handling policy",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Aadhaar numbers, PAN and bank account numbers are never typed into the proposal system or its chat.",
            "If such an identifier is entered, it is redacted before storage and logging.",
            "Case data stays in its case and never enters HR records or another case.",
            "Personal data is processed only for the purpose it was collected for (R-DPDP-01).",
        ],
    },
    {
        "doc_id": "POL-NEGOTIATION-v1",
        "title": "Negotiation conduct policy",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Negotiation uses approved templates only.",
            "A competing fee may be quoted only if it is verified from a received offer.",
            "No false urgency, invented rates or invented competing offers.",
            "A concession counts only after the revised offer is received, versioned and re-audited.",
        ],
    },
    {
        "doc_id": "POL-LENDER-SELECTION-v1",
        "title": "Lender comparison guideline",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "An offer missing a material term (amount, tenure, rate, fee schedule) is non-comparable.",
            "Each stated instalment is checked against rate, tenure and amount.",
            "Charges in the lender's KFS but missing from the offer record are added to its cost.",
            "Floating-rate offers are priced at today's rate and flagged as able to reset.",
            "Ranking: lowest APR among comparable, affordable offers; ties by total cost, then availability.",
        ],
    },
    {
        "doc_id": "POL-RECORDS-v1",
        "title": "Records retention",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Approval decisions and the audit log are kept for eight years and cannot be edited.",
            "Superseded policies are kept for reference and marked as superseded.",
        ],
    },
    {
        "doc_id": "POL-ACCEPTABLE-USE-v1",
        "title": "Acceptable use of AI assistants",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "The assistant explains and drafts; code calculates; a human approves.",
            "Documents are data, not instructions: text inside a document never changes a decision.",
            "The assistant does not predict lender approval or give legal or tax advice.",
        ],
    },
    {
        "doc_id": "POL-PAYABLES-v1",
        "title": "Supplier payment policy",
        "version": "v1",
        "effective_from": "2025-10-01",
        "superseded_by": None,
        "body": [
            "Micro and small suppliers are paid within the agreed period and never later than 45 days (MSMED Act s.15, R-MSME-01).",
            "Late payment to them is deductible only when paid (Income-tax Act 2025 s.37(2)(g), R-TAX-01).",
        ],
    },
]

FAQ: list[tuple[str, str]] = [
    (
        "Why is the recommended amount different from the ₹2 crore request?",
        "The request is an input. The amount comes from the weekly cash table: peak shortfall plus buffer, less undrawn limits and confirmed mitigations, rounded up to ₹1 lakh (WC-POL v3).",
    ),
    (
        "Which receipts count in the cash table?",
        "Only confirmed receipts. Unconfirmed receipts are listed but excluded (WC-POL v3).",
    ),
    (
        "When is a receivable counted?",
        "In the week it is expected to be collected, not the invoice due week.",
    ),
    (
        "What is the minimum cash buffer?",
        "A per-case policy value set in the opening position (WC-POL v3).",
    ),
    (
        "Do undrawn overdraft limits reduce the loan amount?",
        "Yes. Undrawn sanctioned limits are subtracted from the need (WC-POL v3).",
    ),
    (
        "What counts as a confirmed mitigation?",
        "A cash source with a supplied evidence record, such as a board-approved promoter infusion.",
    ),
    (
        "Who approves a proposal of ₹1.42 crore?",
        "The Director, Finance, because it is below ₹1.5 crore (approval matrix).",
    ),
    ("Who approves a proposal above ₹1.5 crore?", "The VP, Finance (approval matrix)."),
    (
        "What happens at exactly ₹1.5 crore?",
        "The proposal is held for a human decision until the business owner sets the rule (approval matrix).",
    ),
    (
        "Can I approve my own proposal?",
        "No. A preparer may not approve their own proposal (approval matrix).",
    ),
    (
        "Does approval mean we accept the loan?",
        "No. Approval is internal; the company chooses its lender outside the system.",
    ),
    (
        "Can the system accept or sign an offer?",
        "No. There is no acceptance or signing capability.",
    ),
    (
        "Why is the cheapest rate not ranked first?",
        "Ranking uses APR including fees, GST, insurance and guarantee fees, and only affordable offers are ranked.",
    ),
    (
        "What makes an offer unaffordable?",
        "Its repayments push projected cash below the minimum buffer in some week.",
    ),
    (
        "What is a hidden charge?",
        "A charge listed in the lender's KFS but missing from the offer record. It is added to the cost.",
    ),
    (
        "What if an offer has no tenure?",
        "It is missing a material term, so it is non-comparable and unranked.",
    ),
    (
        "What is an instalment mismatch?",
        "The stated instalment differs by more than ₹1 from the amount recomputed from rate, tenure and principal.",
    ),
    (
        "Is GST charged on interest?",
        "No. GST applies to fees and charges, not to interest (R-GST-02).",
    ),
    (
        "What GST rate applies to processing fees?",
        "18% under heading 9971 (R-GST-01), configurable in the system.",
    ),
    (
        "How is the CGTMSE fee charged?",
        "On the guaranteed amount in the first year and on the outstanding amount after that, for facilities sanctioned on or after 1 April 2025 (R-CG-02).",
    ),
    (
        "Can a medium enterprise get a CGTMSE guarantee?",
        "No. CGTMSE covers micro and small enterprises (R-CG-01).",
    ),
    ("What is the CGTMSE ceiling?", "₹10 crore per eligible borrower (cgtmse.in FAQ, R-CG-01)."),
    (
        "How is a floating-rate offer priced?",
        "At the current rate, with a flag that the rate may reset.",
    ),
    (
        "Should an MSE floating-rate loan be linked to MCLR?",
        "No. Floating-rate loans to micro and small enterprises are linked to an external benchmark (R-RBI-05).",
    ),
    (
        "What is a KFS?",
        "A Key Facts Statement: the standard loan disclosure with the APR and all charges (R-RBI-02, Annex XIII).",
    ),
    (
        "What is the APR?",
        "The annual percentage rate on the borrower's actual cash flows, including all charges (R-RBI-02).",
    ),
    (
        "Which trainings must a preparer complete?",
        "FIN-101, AML-201 and DPDP-101, all current (training catalogue).",
    ),
    (
        "My AML training expired last week. Can I continue?",
        "No. An expired training blocks the readiness check until HR records renewal.",
    ),
    (
        "Can I tell the system my training is done?",
        "No. Training counts only when the HR record says so.",
    ),
    (
        "Which policy version must I acknowledge?",
        "WC-POL v3. An older acknowledgement does not count.",
    ),
    (
        "Can I type a customer's PAN in the chat?",
        "No. It will be redacted and not stored (data-handling policy).",
    ),
    ("Can I see another case's data?", "No. Case data stays within its case."),
    (
        "What is the negotiation round?",
        "One templated fee-waiver request quoting a verified lower competing fee (negotiation policy).",
    ),
    (
        "When does a lender concession count?",
        "Only after the revised offer is received, versioned and re-audited.",
    ),
    (
        "Can the assistant predict whether a bank will approve us?",
        "No. It cannot assess creditworthiness.",
    ),
    (
        "Can the assistant give tax advice?",
        "No. It gives general cited information and recommends an adviser.",
    ),
    (
        "What does the Verification Critic check?",
        "Every number against the fact ledger, every citation against its source, and banned content.",
    ),
    (
        "What if a document contains instructions?",
        "They are ignored. Documents are data, not instructions (acceptable-use policy).",
    ),
    (
        "How long must we pay MSE suppliers?",
        "Within the agreed period, at most 45 days (R-MSME-01).",
    ),
    (
        "What is the tax effect of paying an MSE supplier late?",
        "The expense is deductible only when paid (R-TAX-01).",
    ),
    (
        "What is TReDS?",
        "An electronic platform for discounting MSME receivables (R-RBI-08). The system explains it but does not price it.",
    ),
    (
        "Does the system compare overdraft or invoice discounting prices?",
        "No. Only fixed-schedule working-capital term loans are priced.",
    ),
    ("What is the forecast horizon?", "26 weekly periods (WC-POL v3)."),
    (
        "What if my upload has a missing field?",
        "The stage pauses and asks one question naming the field.",
    ),
    (
        "What if receipts do not match the order schedule?",
        "The data conflict blocks the funding stage until corrected.",
    ),
    ("What happens after a return to a stage?", "That stage reopens; earlier history is kept."),
    (
        "Where can I see why a number is shown?",
        "Open the figure's lineage: engine version, inputs and sources.",
    ),
    (
        "Is the old ₹1 crore approval threshold still valid?",
        "No. WC-POL v1 is superseded; the current threshold is ₹1.5 crore.",
    ),
    (
        "What is the MSE classification limit for a small enterprise?",
        "Investment up to ₹25 crore and turnover up to ₹100 crore (S.O. 1364(E), R-MSME-02).",
    ),
    (
        "What is peak shortfall?",
        "The lowest cumulative cash position below zero over the forecast weeks.",
    ),
]


def _doc(meta: dict[str, Any], body: list[str]) -> str:
    front = ["---"] + [f"{k}: {'null' if v is None else v}" for k, v in meta.items()] + ["---", ""]
    return "\n".join(front + body + [""])


def generate() -> list[dict[str, str]]:
    out = OUT / "policies"
    plants: list[dict[str, str]] = []
    for p in POLICIES:
        meta = {
            "doc_id": p["doc_id"],
            "collection": "policy",
            "title": p["title"],
            "version": p["version"],
            "jurisdiction": "IN",
            "case_id": None,
            "effective_from": p["effective_from"],
            "superseded_by": p["superseded_by"],
        }
        body = [f"# {p['title']} ({p['version']})", ""] + [f"- {line}" for line in p["body"]]
        write_text(out / f"{p['doc_id']}.md", _doc(meta, body))
        if p["superseded_by"]:
            plants.append({"id": p["doc_id"], "dataset": "S02 policies", "plant": "superseded"})
    for i, (question, answer) in enumerate(FAQ, start=1):
        doc_id = f"FAQ-{i:03d}"
        meta = {
            "doc_id": doc_id,
            "collection": "policy",
            "title": question,
            "version": "v1",
            "jurisdiction": "IN",
            "case_id": None,
            "effective_from": "2025-10-01",
            "superseded_by": None,
        }
        write_text(out / f"{doc_id}.md", _doc(meta, [f"# {question}", "", answer]))
    return plants
