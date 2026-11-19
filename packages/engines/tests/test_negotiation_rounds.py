"""LW-15 rounds 2-3 (ADR 0037): rate-match and tenor-change move planners and concession rules."""

from datetime import date
from decimal import Decimal
from typing import Any

from credassure.engines import negotiation as n
from credassure.engines.calendar import week_of

WEEK1 = date(2026, 11, 16)


def offer(oid: str, rate: str, **kw: Any) -> dict[str, Any]:
    return {
        "offer_id": oid,
        "lender_id": "L" + oid[-1],
        "annual_rate": rate,
        "rate_type": kw.pop("rate_type", "fixed"),
        "disbursal_date": kw.pop("disbursal_date", "2027-02-01"),
        "moratorium_months": kw.pop("moratorium_months", 0),
        **kw,
    }


def standing(
    o: dict[str, Any], *, eligible: bool = True, rank: int | None = None, **kw: Any
) -> n.Standing:
    return n.Standing(
        o,
        kw.pop("comparable", True),
        eligible,
        rank,
        kw.pop("apr", None),
        frozenset(kw.pop("flags", ())),
    )


def test_LW15_rate_match_targets_best_ranked_dearer_fixed_offer_and_cites_lowest_rate() -> None:
    a, b, c = offer("OF-1-A", "0.13"), offer("OF-1-B", "0.12"), offer("OF-1-C", "0.11")
    m = n.rate_match([standing(a, rank=1), standing(b, rank=2), standing(c, rank=3)])
    assert m == n.RateMatch("OF-1-A", "LA", Decimal("0.13"), Decimal("0.11"), "OF-1-C")


def test_LW15_rate_match_skips_the_cheapest_rate_and_floating_offers() -> None:
    a = offer("OF-1-A", "0.10")  # rank 1 but already the lowest rate
    b = offer("OF-1-B", "0.14", rate_type="floating")  # resets: never a target
    c = offer("OF-1-C", "0.12")
    m = n.rate_match([standing(a, rank=1), standing(b, rank=2), standing(c, rank=3)])
    assert m is not None and m.target_offer == "OF-1-C" and m.competing_offer == "OF-1-A"


def test_LW15_rate_match_needs_two_eligible_offers_and_a_dearer_one() -> None:
    a, b = offer("OF-1-A", "0.12"), offer("OF-1-B", "0.11")
    assert n.rate_match([standing(a, rank=1), standing(b, eligible=False)]) is None
    same = [standing(offer("OF-1-A", "0.12"), rank=1), standing(offer("OF-1-B", "0.12"), rank=2)]
    assert n.rate_match(same) is None


def test_LW15_tenor_change_moves_first_repayment_past_the_cash_low_point() -> None:
    o = offer("OF-1-C", "0.11")  # disbursal 1 Feb 2027, first due 1 Mar 2027
    peak = week_of(date(2027, 4, 10), WEEK1)
    m = n.tenor_change(
        [standing(o, eligible=False, apr=Decimal("0.11"), flags={"LW_NOT_AFFORDABLE"})], WEEK1, peak
    )
    assert m is not None and m.target_offer == "OF-1-C"
    assert m.current_first == date(2027, 3, 1) and m.requested_first == date(2027, 5, 1)
    assert m.extra_months == 2 and week_of(m.requested_first, WEEK1) > peak


def test_LW15_tenor_change_picks_the_cheapest_unaffordable_offer() -> None:
    cheap = offer("OF-1-A", "0.10")
    dear = offer("OF-1-B", "0.15")
    flags = {"LW_NOT_AFFORDABLE"}
    m = n.tenor_change(
        [
            standing(dear, eligible=False, apr=Decimal("0.15"), flags=flags),
            standing(cheap, eligible=False, apr=Decimal("0.10"), flags=flags),
        ],
        WEEK1,
        week_of(date(2027, 3, 10), WEEK1),
    )
    assert m is not None and m.target_offer == "OF-1-A"


def test_LW15_tenor_change_has_no_move_when_it_cannot_help() -> None:
    o = offer("OF-1-C", "0.11")
    unaffordable = {"LW_NOT_AFFORDABLE"}
    late_low = week_of(date(2028, 1, 1), WEEK1)  # more than six extra months needed
    assert (
        n.tenor_change([standing(o, eligible=False, flags=unaffordable)], WEEK1, late_low) is None
    )
    early_low = week_of(date(2027, 2, 10), WEEK1)  # already repays after the low point
    assert (
        n.tenor_change([standing(o, eligible=False, flags=unaffordable)], WEEK1, early_low) is None
    )
    late_only = {"LW_LATE_OR_SHORT"}  # a longer moratorium does not fix a late disbursal
    assert n.tenor_change([standing(o, eligible=False, flags=late_only)], WEEK1, early_low) is None
    noncomparable = standing(o, eligible=False, comparable=False, flags=unaffordable)
    assert n.tenor_change([noncomparable], WEEK1, week_of(date(2027, 4, 10), WEEK1)) is None


def test_LW13_BR09_rounds_2_3_concessions_count_only_after_reaudit_and_when_better() -> None:
    o = offer("OF-1-A", "0.13", moratorium_months=0)
    cheaper, same = offer("OF-1-A", "0.12"), offer("OF-1-A", "0.13")
    assert n.rate_counts(o, cheaper, True)
    assert not n.rate_counts(o, cheaper, False)  # did not re-audit as comparable
    assert not n.rate_counts(o, same, True) and not n.rate_counts(o, None, True)
    longer = offer("OF-1-A", "0.13", moratorium_months=2)
    assert n.tenor_counts(o, longer, True) and not n.tenor_counts(o, longer, False)
    assert not n.tenor_counts(o, same, True)


def test_LW15_moves_are_fixed_and_three_at_most() -> None:
    assert n.MOVES == ("fee_waiver_v1", "rate_match_v1", "tenor_change_v1")
    assert n.MAX_ROUNDS == len(n.MOVES) == 3
