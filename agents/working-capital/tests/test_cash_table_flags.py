"""WC-04: shortfall and below-buffer flags come from the API, not the browser."""

from credassure.agents.working_capital.api.router import flag_rows


def test_flags_follow_cumulative_against_zero_and_buffer() -> None:
    rows = [
        {"week": w, "inflow": "0", "outflow": "0", "cumulative": c}
        for w, c in ((1, "2838300"), (2, "205200"), (3, "-1116700"), (9, "-16200000"))
    ]
    out = flag_rows(rows, "1000000", lambda t: t)
    assert [r["shortfall"] for r in out] == [False, False, True, True]
    assert [r["below_buffer"] for r in out] == [False, True, True, True]


def test_unknown_buffer_leaves_below_buffer_unknown() -> None:
    out = flag_rows(
        [{"week": 1, "inflow": "0", "outflow": "0", "cumulative": "5"}], None, lambda t: t
    )
    assert out[0]["below_buffer"] is None
