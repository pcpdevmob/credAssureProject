"""Slot narratives: code renders every figure and direction word (BR-05, WC-07, ONB-04)."""

import re
from decimal import Decimal

import pytest

from credassure.core import slots

S = {
    "wc.need": "₹1,42,00,000",
    "cmp.dir": "lower than",
    "wc.req": "₹2,00,00,000",
    "wc.span": "10 weeks",
}


def test_slots_rendered_with_canonical_values() -> None:
    out = slots.render("The need of {wc.need} is {cmp.dir} the request of {wc.req}.", S)
    assert out == "The need of ₹1,42,00,000 is lower than the request of ₹2,00,00,000."


@pytest.mark.parametrize(
    "draft",
    [
        "The need is ₹1,10,0,000.",  # a raw figure, the 9b failure mode
        "The need {wc.need} peaks in week 9.",  # digit outside a slot
        "The need {wc.need} is 12% higher.",
        "The need {wc.need} is two crore.",  # number words
        "The need {wc.unknown}.",  # unknown slot
        "The need {wc.need} {broken.",  # stray brace
        "No slots at all.",
        "The need {wc.need} is lower than {wc.req}.",  # direction not from code
        "The offer is cheaper and affordable at {wc.need}.",
        "Cash is short for {wc.span} weeks at {wc.need}.",  # repeated word after rendering
    ],
)
def test_draft_with_any_figure_outside_a_slot_is_rejected(draft: str) -> None:
    assert slots.render(draft, S) is None


def test_required_forbidden_and_banned() -> None:
    assert slots.render("{wc.need}.", S, required=["wc.req"]) is None
    assert slots.render("{wc.need} and {wc.req}.", S, forbidden=["wc.req"]) is None
    assert slots.render("{wc.need}, approved.", S, banned=re.compile("approv")) is None


def test_formatters() -> None:
    assert slots.rate(Decimal("0.17564")) == "17.56%"
    assert slots.money(Decimal("14200000")) == "₹1,42,00,000"
    assert slots.compare(Decimal(1), Decimal(2)) == "lower than"
    assert slots.compare(Decimal(2), Decimal(2)) == "equal to"
