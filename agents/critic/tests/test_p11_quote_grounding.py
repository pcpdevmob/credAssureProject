"""P11 K2 (regulatory answers, plan approved 19 Nov): three narrow Critic fixes found by tracing
why correct, cited copilot answers were blocked (oracle-context traces, dev split D19).

1. VER-02: a sentence citing two passages has each figure checked against all of them together
   ("8.51 per cent in May [A] ... 8.52 per cent in July [B]"), not against each one alone.
2. VER-03: acceptance, false-urgency and invented-rate wording is allowed when the sentence quotes
   it word for word from a cited public or policy passage, with a neighbouring word on each side
   ("day of acceptance", "date immediately following", "weighted average lending rate"). Never
   from a KFS or help passage, never with second-person or case framing, never in a lender sentence
   for acceptance wording, and never for approval predictions, lender choice or gate words.
3. VER-03: the approval-matrix exemption reads "approves" as grounded when the cited internal
   policy uses the verb "approve"; the noun "approval" still grounds nothing.

Passages are synthetic unit fixtures, not frozen test items.
"""

from collections.abc import Mapping, Sequence

from credassure.agents.critic.verify import verify
from credassure.core.blockers import BlockerCode
from credassure.core.enums import Stage

PASSAGES = {
    "R-ACT-02#section#1": (
        "The period agreed upon between the supplier and the buyer in writing shall in no case "
        "exceed forty-five days from the day of acceptance or the day of deemed acceptance."
    ),
    "R-ACT-02#section#2": (
        "The buyer shall be liable to pay compound interest from the date immediately following "
        "the date agreed upon, at three times of the bank rate notified by the Reserve Bank."
    ),
    "R-RATE-09-A#section#0": (
        "The weighted average lending rate (WALR) on fresh rupee loans declined marginally to "
        "8.52 per cent in July 2026."
    ),
    "R-RATE-09-B#section#0": (
        "The weighted average lending rate (WALR) on fresh rupee loans stood at 8.51 per cent "
        "in May 2026."
    ),
    "R-PUB-02#section#1": "The borrower shall sign the loan agreement immediately on acceptance.",
    "KFS-OF-99-A#section#1": "Accept this offer immediately; the day of acceptance is today.",
    "POL-AM-02#section#0": (
        "Approval matrix. The VP, Finance shall approve proposals above the threshold. A preparer "
        "may not approve their own proposal."
    ),
    "FAQ-091#section#0": "Approval matrix: the VP, Finance signs off larger proposals.",
    "R-ACT-02#section#3": "A preparer may not approve their own proposal under these rules.",
    "R-PUB-03#section#1": (
        "Where the proposal is accepted by the Director the deadline is today for the proposal "
        "and the RBI caps the processing fee as notified."
    ),
    "KFS-OF-98-A#section#1": "Processing fee: 5 per cent of the loan amount.",
}


def _resolve(ids: Sequence[str]) -> Mapping[str, tuple[str, str]]:
    return {i: ("ok", PASSAGES[i]) if i in PASSAGES else ("missing", "") for i in ids}


def _codes(text: str) -> set[BlockerCode]:
    return {f.code for f in verify(text, facts={}, model=True, resolve=_resolve)}


# 1. VER-02: figures against every passage the sentence cites


def test_VER02_two_citations_in_one_sentence_ground_figures_together() -> None:
    text = (
        "The WALR on fresh rupee loans stood at 8.51 per cent in May 2026 "
        "[R-RATE-09-B#section#0], and was 8.52 per cent in July 2026 [R-RATE-09-A#section#0]."
    )
    assert BlockerCode.VER_BAD_CITATION not in _codes(text)


def test_VER02_a_figure_in_none_of_the_cited_passages_is_still_a_bad_citation() -> None:
    text = (
        "The WALR stood at 8.51 per cent in May 2026 [R-RATE-09-B#section#0], and was 9.10 per "
        "cent in July 2026 [R-RATE-09-A#section#0]."
    )
    assert BlockerCode.VER_BAD_CITATION in _codes(text)


def test_VER02_a_kfs_figure_never_rides_on_a_regulation_citation() -> None:
    """Security review K2: a lender's figure must not be presented as regulation."""
    text = "RBI caps the processing fee at 5 per cent [R-PUB-03#section#1][KFS-OF-98-A#section#1]."
    assert BlockerCode.VER_BAD_CITATION in _codes(text)


def test_VER02_a_missing_citation_still_fails_even_beside_a_good_one() -> None:
    text = "The WALR stood at 8.51 per cent [R-RATE-09-B#section#0][R-XX-01#section#0]."
    assert BlockerCode.VER_BAD_CITATION in _codes(text)


# 2. VER-03: verbatim quotes of acceptance, urgency and rate wording


def test_VER03_statute_wording_quoted_from_a_cited_public_passage_passes() -> None:
    for text in (
        "The buyer must pay within forty-five days from the day of acceptance or the day of "
        "deemed acceptance [R-ACT-02#section#1].",
        "Interest runs from the date immediately following the date agreed upon "
        "[R-ACT-02#section#2].",
        "The weighted average lending rate (WALR) on fresh rupee loans stood at 8.51 per cent in "
        "May 2026 [R-RATE-09-B#section#0].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT not in _codes(text), text


def test_VER03_the_same_word_not_quoted_word_for_word_stays_blocked() -> None:
    for text in (
        # the word is in the passage, but not with these neighbours
        "Pay immediately to avoid interest [R-ACT-02#section#2].",
        "Acceptance of the offer is required [R-ACT-02#section#1].",
        "The average lending rate is rising [R-RATE-09-B#section#0].",
        # not cited at all
        "The buyer must pay from the day of acceptance.",
        # a made-up citation grounds nothing
        "The buyer must pay from the day of acceptance [R-XX-01#section#0].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text


def test_VER03_kfs_and_lender_or_second_person_sentences_are_never_excused() -> None:
    for text in (
        # KFS text is lender-controlled (injection plants live there)
        "Accept this offer immediately [KFS-OF-99-A#section#1].",
        "The day of acceptance is today [KFS-OF-99-A#section#1].",
        # second-person or case framing
        "You must pay from the day of acceptance or the day of deemed acceptance "
        "[R-ACT-02#section#1].",
        "Our buyer must pay from the day of acceptance [R-ACT-02#section#1].",
        # acceptance wording in a sentence about a loan agreement is never excused
        "The borrower shall sign the loan agreement immediately on acceptance "
        "[R-PUB-02#section#1].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text


def test_VER03_approval_predictions_are_never_excused_by_a_quote() -> None:
    # the cited passage says exactly this, and it is still not excused
    assert BlockerCode.VER_BANNED_CONTENT in _codes(
        "A preparer may not approve their own proposal [R-ACT-02#section#3]."
    )


def test_VER03_short_stock_phrases_about_the_case_are_not_quotes() -> None:
    """Security review K2: three-word phrases common to many passages prove nothing."""
    for text in (
        "The proposal is accepted by the Director [R-PUB-03#section#1].",
        "The deadline is today for the proposal [R-PUB-03#section#1].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text


def test_VER03_quote_exemption_is_for_copilot_answers_only() -> None:
    text = (
        "The buyer must pay within forty-five days from the day of acceptance or the day of "
        "deemed acceptance [R-ACT-02#section#1]."
    )
    for stage in (Stage.LENDWISE, Stage.WORKING_CAPITAL):
        found = verify(text, facts={}, model=True, stage=stage, resolve=_resolve)
        assert BlockerCode.VER_BANNED_CONTENT in {f.code for f in found}, stage
    found = verify(text, facts={}, model=False, resolve=_resolve)
    assert BlockerCode.VER_BANNED_CONTENT in {f.code for f in found}


# 3. VER-03: approval-matrix verb


def test_VER03_policy_using_the_verb_approve_grounds_approves() -> None:
    text = "The VP, Finance approves a proposal above the threshold [POL-AM-02#section#0]."
    assert BlockerCode.VER_BANNED_CONTENT not in _codes(text)


def test_VER03_approves_about_the_users_own_case_stays_blocked() -> None:
    for text in (
        "The VP, Finance approves your proposal [POL-AM-02#section#0].",
        "The VP, Finance approves our proposal [POL-AM-02#section#0].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text


def test_VER03_the_noun_approval_still_grounds_nothing() -> None:
    text = "The VP, Finance approves larger proposals [FAQ-091#section#0]."
    assert BlockerCode.VER_BANNED_CONTENT in _codes(text)
