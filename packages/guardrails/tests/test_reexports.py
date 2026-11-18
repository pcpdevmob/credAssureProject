"""ADR 0029 step 1: the move keeps every old import path pointing at the same objects."""

from credassure.agents.copilot import policy
from credassure.guardrails import excerpt, injection, pii, refusal, spotlight
from credassure.security import injection as old_injection
from credassure.security import pii as old_pii
from credassure.security import spotlight as old_spotlight


def test_scope55_old_paths_reexport_the_guardrails_objects() -> None:
    assert old_pii.redact is pii.redact and old_pii.find is pii.find
    assert old_pii.redact_value is pii.redact_value and old_pii.verhoeff_valid is pii.verhoeff_valid
    assert old_injection.scan is injection.scan
    assert old_spotlight.spotlight is spotlight.spotlight
    assert policy.check is refusal.check and policy.ABSTAIN == refusal.ABSTAIN


def test_scope55_excerpt_cap_unchanged() -> None:
    assert excerpt.EXCERPT_LIMIT == 600
    bases = excerpt.FULL_TEXT_BASES
    assert bases == frozenset({"L1", "L2", "L5"})
    text = "a" * 700 + " moratorium " + "b" * 700
    window = excerpt.excerpt(text, "the moratorium clause")
    assert len(window) == 600 and "moratorium" in window
