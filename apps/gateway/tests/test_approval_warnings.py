"""APR-04 evidence: the approver is told when a negotiation round post-dates the verified comparison
or a revised offer did not pass re-audit (BR-09, ADR 0023)."""

from datetime import datetime, timedelta
from types import SimpleNamespace

from credassure.gateway.supervisor_service import approval_warnings

T0 = datetime(2026, 11, 16, 10, 0)


def fact(key: str, value: str, minutes: int = 0, version: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        key=key, value_text=value, version=version, created_at=T0 + timedelta(minutes=minutes)
    )


def test_APR04_no_negotiation_no_warning() -> None:
    assert approval_warnings([fact("lw.gate", "GO")]) == []


def test_APR04_round_after_the_comparison_is_in_progress() -> None:
    facts = [
        fact("lw.gate", "GO"),
        fact("lw.negotiation.status", "sent", 5),
        fact("lw.negotiation.concession_counts", "true", 5),
    ]
    assert approval_warnings(facts) == ["negotiation_in_progress"]


def test_APR04_round_before_the_latest_comparison_is_reflected() -> None:
    facts = [
        fact("lw.gate", "GO", 0, 1),
        fact("lw.negotiation.status", "sent", 5),
        fact("lw.negotiation.concession_counts", "true", 5),
        fact("lw.gate", "GO", 9, 2),  # the comparison re-ran after the round
    ]
    assert approval_warnings(facts) == []


def test_BR09_revision_that_failed_reaudit_is_flagged() -> None:
    facts = [
        fact("lw.gate", "GO", 9),
        fact("lw.negotiation.status", "sent", 5),
        fact("lw.negotiation.revised.version", "2", 5),
        fact("lw.negotiation.concession_counts", "false", 5),
    ]
    assert approval_warnings(facts) == ["revised_offer_not_reaudited"]
