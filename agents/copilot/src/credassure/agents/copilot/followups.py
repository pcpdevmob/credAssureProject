"""CP-12 follow-up suggestions (ADR 0035). Fixed questions chosen by code from the intent of the
turn, never written by the model: a suggestion cannot carry an injected instruction, a figure or a
promise, and every one is a question this copilot can route.
"""

from credassure.agents.copilot import intent as it

MAX = 3
_BY_INTENT: dict[str, tuple[str, ...]] = {
    it.HELP: (
        "How does CredAssure handle personal data?",
        "What does the AI decide, and what does code decide?",
        "Where do I see why a case is blocked?",
    ),
    it.STATUS: (
        "Why is this case blocked?",
        "What is the recommended amount for this case?",
        "Who approves this case?",
    ),
    it.BLOCKER: (
        "What is the status of this case?",
        "How do I upload a corrected file?",
        "What happens after I press Resume?",
    ),
    it.FIGURES: (
        "Why is the recommended amount different from the request?",
        "Why is the cheapest-looking lender not ranked first?",
        "What is the status of this case?",
    ),
    it.REGULATORY: (
        "What is a Key Facts Statement?",
        "How is the CGTMSE guarantee fee charged?",
        "Is GST charged on loan processing fees?",
    ),
    it.POLICY: (
        "What does the approval matrix say about the ₹1.5 crore threshold?",
        "Who can approve a proposal?",
        "What is a Key Facts Statement?",
    ),
    it.DATA_CORRECTION: (  # SUP-02
        "How do I upload a corrected file?",
        "What happens after I press Resume?",
        "What is the status of this case?",
    ),
    it.APPROVAL_ACTION: (
        "Who approves this case?",
        "Who can approve a proposal?",
        "What is the status of this case?",
    ),
}
_SAFE_DEFAULT = (
    "What can Ask CredAssure help with?",
    "How does CredAssure handle personal data?",
    "What is a Key Facts Statement?",
)


def suggest(intent: str | None, *, has_case: bool, asked: str) -> list[str]:
    """Up to three follow-ups for the turn; case questions only inside a case; never the question
    just asked."""
    pool = _BY_INTENT.get(intent or "", _SAFE_DEFAULT)
    out = []
    for q in pool:
        if not has_case and it.case_needed(q):
            continue
        if q.strip().lower() == asked.strip().lower():
            continue
        out.append(q)
    if len(out) < MAX:
        out += [q for q in _SAFE_DEFAULT if q not in out and q.lower() != asked.strip().lower()]
    return out[:MAX]
