"""9e: cited copilot prose is anchored by its passage; flagged words pass only when the passage
says them (word pair), so predictions and invented reasons are still blocked (VER-02, VER-03)."""

from collections.abc import Mapping, Sequence

from credassure.agents.critic.verify import verify
from credassure.core.blockers import BlockerCode

PASSAGE = (
    "For facilities sanctioned on or after 1 April 2025 the annual guarantee fee is charged on the "
    "guaranteed amount in the first year and on the outstanding amount thereafter. Proposals are "
    "approved by the member lending institution."
)


def _resolve(ids: Sequence[str]) -> Mapping[str, tuple[str, str]]:
    return {i: ("ok", PASSAGE) if i == "R-CG-02#section#1" else ("missing", "") for i in ids}


def _codes(text: str) -> set[BlockerCode]:
    return {f.code for f in verify(text, facts={}, model=True, resolve=_resolve)}


def test_VER02_cited_sentence_quoting_its_passage_passes() -> None:
    text = (
        "The fee is charged on the guaranteed amount in the first year and on the outstanding "
        "amount thereafter [R-CG-02#section#1]."
    )
    assert _codes(text) == set()


def test_VER03_prediction_not_in_the_passage_is_still_blocked() -> None:
    assert BlockerCode.VER_BANNED_CONTENT in _codes(
        "Your loan will be approved [R-CG-02#section#1]."
    )


def test_VER03_reason_word_not_in_the_passage_is_still_blocked() -> None:
    assert BlockerCode.VER_UNSUPPORTED_REASON in _codes(
        "This fee is better for you [R-CG-02#section#1]."
    )


def test_VER02_uncited_model_sentence_still_needs_a_slot() -> None:
    assert BlockerCode.VER_UNSUPPORTED_REASON in _codes("The fee is charged yearly.")


def test_VER02_bad_citation_grounds_nothing() -> None:
    codes = _codes("The fee is charged on the guaranteed amount [R-XX-99#section#1].")
    assert BlockerCode.VER_BAD_CITATION in codes and BlockerCode.VER_BANNED_CONTENT in codes


def test_VER03_prediction_whose_word_pair_is_in_the_passage_is_still_blocked() -> None:
    """Security review 9e: "approved by" is in the passage, but a prediction is never excused."""
    for text in (
        "Your loan will be approved by the member lending institution [R-CG-02#section#1].",
        "Your loan is guaranteed amount approved by them [R-CG-02#section#1].",
    ):
        assert BlockerCode.VER_BANNED_CONTENT in _codes(text), text
