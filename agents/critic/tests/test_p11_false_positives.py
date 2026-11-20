"""P11 (G4 diagnosis): two Critic false positives on correct, cited answers, fixed narrowly.

1. VER-02: an Act writes a period in words ("forty-five days"); a cited "45 days" must match it.
2. VER-03: an internal approval-matrix fact ("the Director, Finance approves ...") quoted from a
   cited internal policy passage is not an approval prediction. Predictions, lender sentences,
   public or KFS sources and uncited text stay blocked.

Passages here are synthetic unit fixtures, not frozen test items (tuning never uses the frozen set).
"""

from collections.abc import Mapping, Sequence

from credassure.agents.critic.verify import verify
from credassure.core.blockers import BlockerCode

PASSAGES = {
    "R-ACT-01#section#1": (
        "The agreed period shall in no case exceed forty-five days from acceptance."
    ),
    "R-ACT-01#section#2": "The agreed period shall in no case exceed forty days from acceptance.",
    "R-ACT-01#section#3": "One of the members may refer the dispute to the council.",
    "R-PUB-01#section#1": "The board approves the scheme and its approval matrix each year.",
    "POL-AM-01#section#1": (
        "Approval matrix. The Director, Finance approves proposals below the threshold; the "
        "VP, Finance approves proposals above it. Approvals are recorded in the inbox."
    ),
    "FAQ-090#section#0": "Who signs off a proposal? The VP, Finance (approval matrix).",
    "POL-AM-01#section#2": "Proposals are approved by the routed approver after review.",
}


def _resolve(ids: Sequence[str]) -> Mapping[str, tuple[str, str]]:
    return {i: ("ok", PASSAGES[i]) if i in PASSAGES else ("missing", "") for i in ids}


def _codes(text: str) -> set[BlockerCode]:
    return {f.code for f in verify(text, facts={}, model=True, resolve=_resolve)}


def test_VER02_figure_written_in_words_in_the_passage_matches() -> None:
    assert _codes("The agreed period cannot exceed 45 days [R-ACT-01#section#1].") == set()


def test_VER02_a_different_word_figure_is_still_a_bad_citation() -> None:
    codes = _codes("The agreed period cannot exceed 45 days [R-ACT-01#section#2].")
    assert BlockerCode.VER_BAD_CITATION in codes


def test_VER02_a_number_word_without_a_period_unit_supports_nothing() -> None:
    codes = _codes("A member may refer the dispute within 1 day [R-ACT-01#section#3].")
    assert BlockerCode.VER_BAD_CITATION in codes


def test_VER03_approval_matrix_fact_from_a_cited_policy_passes() -> None:
    for text in (
        "The VP, Finance approves proposals above the threshold [POL-AM-01#section#1].",
        "The VP, Finance is named in the approval matrix [FAQ-090#section#0].",
        "Approvals are recorded in the inbox [POL-AM-01#section#1].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT not in _codes(text), text


def test_VER03_predictions_and_lender_sentences_stay_blocked_even_from_policy() -> None:
    for text in (
        # "approved" is the prediction form, even though the policy passage says it
        "Your proposal will be approved by the routed approver [POL-AM-01#section#2].",
        "The VP, Finance will approve it [POL-AM-01#section#1].",
        # a lender or bank is never the subject of an excused approval
        "The lender approves proposals above the threshold [POL-AM-01#section#1].",
        "The bank approves proposals above the threshold [POL-AM-01#section#1].",
        # other approval-prediction words in the same rule are never excused
        "The VP, Finance approves it; it is likely to be cleared [POL-AM-01#section#1].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text


def test_VER03_approval_wording_outside_internal_policy_stays_blocked() -> None:
    for text in (
        # a public document says "approves", but only internal policy grounds the word
        "The board approves the scheme each year [R-PUB-01#section#1].",
        # mixed sources: a public passage rides along with a policy one
        "The VP, Finance approves proposals [POL-AM-01#section#1][R-PUB-01#section#1].",
        # the cited policy passage does not use the word
        "The VP, Finance approves proposals [FAQ-090#section#0].",
        # a made-up policy id grounds nothing
        "The VP, Finance approves proposals [POL-XX-99#section#1].",
        # not cited at all
        "The VP, Finance approves proposals above the threshold.",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text
