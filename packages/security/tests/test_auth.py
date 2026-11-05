"""Phase 5 auth: argon2, JWT, case visibility (SUP-08, BR-14) and maker-checker (APR-05)."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from credassure.security import auth
from credassure.security.auth import CaseRef, Principal, Role

SECRET = "x" * 32
NOW = datetime(2026, 11, 15, 10, 0, tzinfo=UTC)

PREP_A = Principal("u-prep-a", Role.PREPARER, "default")
PREP_B = Principal("u-prep-b", Role.PREPARER, "default")
DIRECTOR = Principal("u-dir", Role.DIRECTOR_FINANCE, "default")
VP = Principal("u-vp", Role.VP_FINANCE, "default")
EVALUATOR = Principal("u-eval", Role.EVALUATOR, "default")

CASE_A_DIRECTOR = CaseRef(
    "CA-2026-0001", "default", "u-prep-a", "director_finance", "AWAITING_APPROVAL"
)
CASE_A_VP = CaseRef("CA-2026-0002", "default", "u-prep-a", "vp_finance", "AWAITING_APPROVAL")
CASE_HELD = CaseRef("CA-2026-0010", "default", "u-prep-a", "HELD", "HELD")
CASE_UNROUTED = CaseRef("CA-2026-0003", "default", "u-prep-a", None, "CREATED")
CASE_OTHER_TENANT = CaseRef(
    "CA-2026-0001", "tenant-2", "u-prep-a", "director_finance", "AWAITING_APPROVAL"
)


def test_NFR07_argon2_hash_verifies_and_rejects() -> None:
    digest = auth.hash_password("correct horse")
    assert digest.startswith("$argon2id$") and "correct horse" not in digest
    assert auth.verify_password(digest, "correct horse")
    assert not auth.verify_password(digest, "wrong")
    assert not auth.verify_password("not-a-hash", "correct horse")


def test_NFR07_jwt_round_trip_carries_role_and_tenant() -> None:
    token = auth.issue_token(PREP_A, SECRET, minutes=30, now=NOW)
    assert auth.verify_token(token, SECRET, now=NOW + timedelta(minutes=29)) == PREP_A


@pytest.mark.parametrize(
    "mutate",
    [
        lambda t: t,  # expired (checked at +31 min)
        lambda t: t[:-2] + ("AA" if t[-2:] != "AA" else "BB"),  # tampered signature
    ],
)
def test_NFR07_jwt_rejects_expired_and_tampered(mutate: object) -> None:
    token = auth.issue_token(PREP_A, SECRET, minutes=30, now=NOW)
    with pytest.raises(auth.AuthError):
        auth.verify_token(mutate(token), SECRET, now=NOW + timedelta(minutes=31))  # type: ignore[operator]


def test_NFR07_jwt_rejects_wrong_secret_alg_none_and_unknown_role() -> None:
    token = auth.issue_token(PREP_A, SECRET, minutes=30, now=NOW)
    with pytest.raises(auth.AuthError):
        auth.verify_token(token, "y" * 32, now=NOW)
    unsigned = jwt.encode(
        {"sub": "u", "role": "evaluator", "tenant": "default", "exp": NOW + timedelta(hours=1)},
        key=None,
        algorithm="none",
    )
    with pytest.raises(auth.AuthError):
        auth.verify_token(unsigned, SECRET, now=NOW)
    forged_role = jwt.encode(
        {"sub": "u", "role": "admin", "tenant": "default", "exp": NOW + timedelta(hours=1)},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(auth.AuthError):
        auth.verify_token(forged_role, SECRET, now=NOW)


def test_NFR07_short_secret_is_refused() -> None:
    with pytest.raises(auth.AuthError):
        auth.issue_token(PREP_A, "short", minutes=30, now=NOW)


# SUP-08: 3/3 isolation cases
def test_SUP08_1_preparer_cannot_read_another_preparers_case() -> None:
    assert auth.can_view_case(PREP_A, CASE_A_DIRECTOR)
    assert not auth.can_view_case(PREP_B, CASE_A_DIRECTOR)


def test_SUP08_2_no_one_reads_across_tenants() -> None:
    for who in (PREP_A, DIRECTOR, VP, EVALUATOR):
        assert not auth.can_view_case(who, CASE_OTHER_TENANT)


def test_SUP08_3_approver_sees_only_cases_routed_to_their_role() -> None:
    assert auth.can_view_case(DIRECTOR, CASE_A_DIRECTOR)
    assert not auth.can_view_case(DIRECTOR, CASE_A_VP)
    assert not auth.can_view_case(DIRECTOR, CASE_UNROUTED)
    assert auth.can_view_case(VP, CASE_A_VP) and auth.can_view_case(VP, CASE_HELD)
    assert auth.can_view_case(EVALUATOR, CASE_UNROUTED)


def test_APR05_only_the_routed_role_decides_and_never_the_preparer() -> None:
    assert auth.can_decide(DIRECTOR, CASE_A_DIRECTOR)
    assert not auth.can_decide(DIRECTOR, CASE_A_VP)  # director on a VP case
    assert auth.can_decide(VP, CASE_HELD)  # held boundary cases go to the VP (BRD §5.1)
    assert not auth.can_decide(DIRECTOR, CASE_HELD)
    assert not auth.can_decide(VP, CASE_UNROUTED)
    for who in (PREP_A, PREP_B, EVALUATOR):
        assert not auth.can_decide(who, CASE_A_DIRECTOR)


def test_APR05_maker_checker_refuses_self_approval_even_for_an_approver_role() -> None:
    self_prepared = CaseRef(
        "CA-2026-0004", "default", DIRECTOR.user_id, "director_finance", "AWAITING_APPROVAL"
    )
    assert not auth.can_decide(DIRECTOR, self_prepared)


def test_NFR07_require_role_raises_for_other_roles() -> None:
    auth.require_role(VP, Role.DIRECTOR_FINANCE, Role.VP_FINANCE)
    with pytest.raises(auth.ForbiddenError):
        auth.require_role(PREP_A, Role.DIRECTOR_FINANCE, Role.VP_FINANCE)


def test_APR04_decided_or_not_yet_routed_cases_take_no_decision() -> None:
    for status in ("APPROVED", "REJECTED", "RETURNED", "CREATED"):
        case = CaseRef("CA-2026-0001", "default", "u-prep-a", "director_finance", status)
        assert not auth.can_decide(DIRECTOR, case)


def test_NFR07_token_lifetime_is_capped_and_verify_checks_secret() -> None:
    with pytest.raises(auth.AuthError):
        auth.issue_token(PREP_A, SECRET, minutes=24 * 60, now=NOW)
    token = auth.issue_token(PREP_A, SECRET, minutes=30, now=NOW)
    with pytest.raises(auth.AuthError):
        auth.verify_token(token, "short", now=NOW)
    no_aud = jwt.encode(
        {"sub": "u", "role": "preparer", "tenant": "default", "exp": NOW + timedelta(hours=1)},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(auth.AuthError):
        auth.verify_token(no_aud, SECRET, now=NOW)
