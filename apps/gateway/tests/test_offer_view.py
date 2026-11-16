"""UI-05: the gateway, not the browser, says which offer has the lowest APR (BR-05).

The flag is named `cheapest_headline_rate` but means the lowest APR; every tied offer carries it."""

from credassure.gateway.supervisor_service import offer_view


def facts(**aprs: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for oid, apr in aprs.items():
        name = oid.replace("_", "-")
        out[f"lw.{name}.v1.comparable"] = "true"
        if apr is not None:
            out[f"lw.{name}.v1.apr"] = apr
    return out


def flagged(view: dict) -> list[str]:  # type: ignore[type-arg]
    return [o["offer_id"] for o in view["offers"] if o["cheapest_headline_rate"]]


def test_demo_offers_flag_only_the_lowest_apr() -> None:
    view = offer_view(facts(OF_01_A="0.1756", OF_01_B="0.1300", OF_01_C="0.1187"))
    assert flagged(view) == ["OF-01-C"]


def test_a_tie_flags_every_tied_offer() -> None:
    assert flagged(offer_view(facts(OF_01_A="0.13", OF_01_B="0.13", OF_01_C="0.15"))) == [
        "OF-01-A",
        "OF-01-B",
    ]


def test_full_precision_decides_not_the_two_decimal_display() -> None:
    view = offer_view(facts(OF_01_A="0.130049", OF_01_B="0.130001"))
    assert [o["apr_pct"] for o in view["offers"]] == ["13.00", "13.00"]
    assert flagged(view) == ["OF-01-B"]


def test_an_offer_without_an_apr_is_never_flagged_and_does_not_break_the_minimum() -> None:
    view = offer_view(facts(OF_01_A=None, OF_01_B="0.13"))
    assert flagged(view) == ["OF-01-B"]
    assert view["offers"][0]["cheapest_headline_rate"] is False


def test_no_apr_anywhere_flags_nothing() -> None:
    assert flagged(offer_view(facts(OF_01_A=None, OF_01_B=None))) == []
    assert offer_view({})["offers"] == []
