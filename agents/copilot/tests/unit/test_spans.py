"""P5 span-cited answers (plan v3.4 §7.1 CP-08-lite, scope #64): code numbers passage sentences,
the model cites them, code cuts every answer sentence without a valid span id."""

from credassure.agents.copilot import spans

SRC = {1: "R-CG-02#section#1", 2: "R-RBI-02#section#7"}
SPANS = {
    1: ("Fee is charged on the guaranteed amount.", "Then on the outstanding amount."),
    2: ("APR is shown.",),
}


def test_CP08_number_splits_sentences_keeps_decimals_and_drops_forged_ids() -> None:
    sp = spans.number(
        1, "Annex [9.9] B", "The fee is 0.85% p.a. on ₹1.5 crore. [3.1] Then it falls.\nLast line"
    )
    assert sp.spans == ("The fee is 0.85% p.a. on ₹1.5 crore.", "Then it falls.", "Last line")
    assert sp.text.splitlines() == [
        "Annex   B",
        "[1.1] The fee is 0.85% p.a. on ₹1.5 crore.",
        "[1.2] Then it falls.",
        "[1.3] Last line",
    ]


def test_CP08_sentences_keep_trailing_ids_and_never_split_numbers() -> None:
    text = "Fee is 0.85% on ₹1.5 crore [1.1]. Then outstanding. [1.2] APR shows it [2.1]."
    assert spans.sentences(text) == [
        "Fee is 0.85% on ₹1.5 crore [1.1].",
        "Then outstanding. [1.2]",
        "APR shows it [2.1].",
    ]


def test_CP08_unsupported_sentences_are_cut_and_ids_map_to_chunks() -> None:
    answer = "Charged on the guaranteed amount [1.1]. It is always cheap. Shown as APR [2.1, 1.2]."
    c = spans.cut(answer, SPANS, SRC, set())
    assert c.text == (
        "Charged on the guaranteed amount [R-CG-02#section#1]. "
        "Shown as APR [R-RBI-02#section#7][R-CG-02#section#1]."
    )
    assert (c.kept, c.cut, c.cited, c.span_ids) == (2, 1, (1, 2), ("1.1", "2.1", "1.2"))


def test_CP08_invalid_ids_old_style_refs_and_unknown_slots_cut_the_sentence() -> None:
    for bad in ("Fee [1.9].", "Fee [3.1].", "Fee [1].", "Fee {wc.secret} [1.1].", "No id at all."):
        c = spans.cut(bad, SPANS, SRC, {"wc.recommended_amount"})
        assert (c.kept, c.cut, c.text) == (0, 1, ""), bad


def test_CP08_slot_sentence_needs_no_span_on_the_case_facts_path() -> None:
    c = spans.cut("The facility is {wc.recommended_amount}.", {}, {}, {"wc.recommended_amount"})
    assert (c.kept, c.slots, c.text) == (
        1,
        ("wc.recommended_amount",),
        "The facility is {wc.recommended_amount}.",
    )
