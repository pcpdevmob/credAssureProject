"""The onboarding rule book (ONB-02, BR-04; BRD Q-03: a synthetic rule set for the capstone).

The data the agent's own checker reads, and the plain words for each blocker: what is wrong, what to
do, and who fixes it (ONB-04). The same rules are implemented separately in
`engines.onboarding_rules`; the agent runs both and stops on any disagreement (SUP-05, BR-11).
Raise RULES_VERSION with any change to the rules (never to the wording alone).
Design: Mousita (PR #43); built against the frozen HR data and the 10 onboarding test items.
"""

from dataclasses import dataclass

from credassure.core.blockers import BlockerCode

RULES_VERSION = "onboarding-rules-1.0"
AUTHORISED_ROLES = frozenset({"credit_proposal_officer", "senior_finance_analyst"})
MANDATORY = ("AML-201", "DPDP-101", "FIN-101")  # course ids in hr.db training_records
POLICY_ID = "WC-POL"
POLICY_VERSION = "v3"

RULE_NAMES = {
    "role": "authorised preparer role",
    "AML-201": "AML/KYC training (AML-201)",
    "DPDP-101": "Data Protection training (DPDP-101)",
    "FIN-101": "Credit Policy training (FIN-101)",
    "policy_ack": "working-capital policy acknowledgement (WC-POL v3)",
}


@dataclass(frozen=True)
class BlockerText:
    message: str
    action: str
    who: str  # who fixes it: "you", "your manager" or "HR"


BLOCKERS: dict[BlockerCode, BlockerText] = {
    BlockerCode.ONB_ROLE_NOT_AUTHORISED: BlockerText(
        "Your HR role is not authorised to prepare loan proposals.",
        "Ask your manager to give this case to a credit proposal officer or a senior finance"
        " analyst.",
        "your manager",
    ),
    BlockerCode.ONB_TRAINING_EXPIRED: BlockerText(
        "This mandatory training has expired.",
        "Retake the course and ask HR to update your training record.",
        "you",
    ),
    BlockerCode.ONB_TRAINING_INCOMPLETE: BlockerText(
        "This mandatory training is not completed.",
        "Finish the course; HR records the completion.",
        "you",
    ),
    BlockerCode.ONB_TRAINING_MISSING: BlockerText(
        "HR has no record of this mandatory training.",
        "Ask HR to add your completion record, or enrol in the course.",
        "HR",
    ),
    BlockerCode.ONB_ACK_MISSING: BlockerText(
        "You have not acknowledged the working-capital policy.",
        "Read and acknowledge WC-POL v3 in the HR portal.",
        "you",
    ),
    BlockerCode.ONB_ACK_OLD_VERSION: BlockerText(
        "You acknowledged an older version of the working-capital policy.",
        "Read and acknowledge the current version, WC-POL v3.",
        "you",
    ),
}
NO_RECORD = BlockerText(
    "HR has no active record for the preparer of this case.",
    "Ask HR to create your employee record.",
    "HR",
)


def next_action(text: BlockerText) -> str:
    """What the preparer sees under "What to do": the action, then who fixes it."""
    return f"{text.action} Who fixes it: {text.who}."


def source_ref(emp_id: str, rule: str) -> str:
    """The HR record each rule was decided on (design-detail §2.4.2: ``hr.db:<table>:<id>``). For a
    training or acknowledgement the id is the key that was looked up, also when no row was found."""
    if rule == "role":
        return f"hr.db:employees:{emp_id}"
    if rule == "policy_ack":
        return f"hr.db:policy_acknowledgements:{emp_id}/{POLICY_ID}"
    return f"hr.db:training_records:{emp_id}/{rule}"
