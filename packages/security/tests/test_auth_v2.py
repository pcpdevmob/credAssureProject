"""ADR 0038: staged and versioned tokens, TOTP (RFC 6238 vectors), backup codes, sealed secrets,
password policy, and the admin role kept away from cases."""

import base64
import os
from datetime import UTC, datetime

import pytest

from credassure.security import mfa, password_policy
from credassure.security.auth import (
    BUSINESS_ROLES,
    AuthError,
    CaseRef,
    Principal,
    Role,
    Stage,
    can_decide,
    can_view_case,
    issue_token,
    verify_token,
)

SECRET = "s" * 40
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode()  # RFC 6238 Appendix B, SHA1


@pytest.mark.parametrize(
    ("t", "code"),
    [
        (59, "94287082"),
        (1111111109, "07081804"),
        (1111111111, "14050471"),
        (1234567890, "89005924"),
        (2000000000, "69279037"),
        (20000000000, "65353130"),
    ],
)
def test_ADR0038_totp_matches_rfc6238_test_vectors(t: int, code: str) -> None:
    assert mfa.totp_at(RFC_SECRET, mfa.step_of(t), digits=8) == code


def test_ADR0038_totp_accepts_drift_of_one_step_and_refuses_replay() -> None:
    now = 1_800_000_000.0
    secret = mfa.new_secret()
    step = mfa.step_of(now)
    code = mfa.totp_at(secret, step)
    assert mfa.verify_totp(secret, code, now, None) == step
    assert mfa.verify_totp(secret, code, now, step) is None  # same code twice: replay
    assert mfa.verify_totp(secret, mfa.totp_at(secret, step - 1), now, None) == step - 1
    assert mfa.verify_totp(secret, mfa.totp_at(secret, step - 2), now, None) is None
    assert mfa.verify_totp(secret, "12345", now, None) is None
    assert mfa.verify_totp(secret, "abcdef", now, None) is None
    later = mfa.totp_at(secret, step + 1)
    assert mfa.verify_totp(secret, later, now, step) == step + 1  # a newer step still works


def test_ADR0038_backup_codes_work_once_and_only_hashes_are_kept() -> None:
    codes, hashes = mfa.new_backup_codes()
    assert len(codes) == len(set(codes)) == 8 and all(c not in hashes for c in codes)
    left = mfa.use_backup_code(hashes, codes[3].upper())
    assert left is not None and len(left) == 7
    assert mfa.use_backup_code(left, codes[3]) is None
    assert mfa.use_backup_code(left, "nope-nope") is None


def test_ADR0038_sealed_secret_opens_only_with_its_key_and_user() -> None:
    key = os.urandom(32)
    sealed = mfa.seal(key, "u-1", "JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in sealed
    assert mfa.unseal(key, "u-1", sealed) == "JBSWY3DPEHPK3PXP"
    with pytest.raises(mfa.MfaError):
        mfa.unseal(key, "u-2", sealed)  # copied to another user's row
    with pytest.raises(mfa.MfaError):
        mfa.unseal(os.urandom(32), "u-1", sealed)
    with pytest.raises(mfa.MfaError):
        mfa.unseal(key, "u-1", "v1:not*base64")


def test_ADR0038_mfa_key_fails_closed() -> None:
    with pytest.raises(mfa.MfaError):
        mfa.load_key(None)
    with pytest.raises(mfa.MfaError):
        mfa.load_key("not base64!")
    with pytest.raises(mfa.MfaError):
        mfa.load_key(base64.b64encode(b"short").decode())
    assert len(mfa.load_key(base64.b64encode(os.urandom(32)).decode())) == 32


def test_ADR0038_provisioning_uri_names_issuer_and_user() -> None:
    uri = mfa.provisioning_uri("JBSWY3DPEHPK3PXP", "anita.director")
    assert uri.startswith("otpauth://totp/CredAssure%3Aanita.director?secret=JBSWY3DPEHPK3PXP")
    assert "issuer=CredAssure" in uri and "period=30" in uri


@pytest.mark.parametrize(
    ("password", "reason"),
    [
        ("short-one", "at least 12"),
        ("Password@2026", "too common"),
        ("aaaaaaaaaaaaaaaa", "two different"),
        ("anita.director-2026x", "username"),
        ("director-word-2026", "username"),
    ],
)
def test_ADR0038_password_policy_refuses(password: str, reason: str) -> None:
    found = password_policy.problems(password, "anita.director")
    assert any(reason in p for p in found), found


def test_ADR0038_password_policy_accepts_a_long_passphrase_and_refuses_reuse() -> None:
    assert password_policy.problems("brass-otter-rainfall-41", "anita.director") == []
    again = password_policy.problems(
        "brass-otter-rainfall-41", "x", current="brass-otter-rainfall-41"
    )
    assert any("not just used" in p for p in again)


def test_ADR0038_tokens_carry_stage_version_and_second_factor() -> None:
    who = Principal("u-1", Role.VP_FINANCE, "default", Stage.MFA, 3, False)
    back = verify_token(issue_token(who, SECRET, 5), SECRET)
    assert back == who
    full = Principal("u-1", Role.VP_FINANCE, "default", Stage.FULL, 4, True)
    assert verify_token(issue_token(full, SECRET, 5), SECRET) == full


def test_ADR0038_a_pre_adr_token_without_stage_reads_as_full_version_zero() -> None:
    import jwt

    now = datetime.now(UTC)
    claims = {
        "iss": "credassure",
        "aud": "credassure",
        "sub": "u-1",
        "role": "preparer",
        "tenant": "default",
        "iat": now,
        "exp": now.timestamp() + 60,
    }
    old = jwt.encode(claims, SECRET, algorithm="HS256")
    assert verify_token(old, SECRET) == Principal("u-1", Role.PREPARER, "default")


def test_ADR0038_a_forged_version_type_is_refused() -> None:
    import jwt

    now = datetime.now(UTC)
    claims = {
        "iss": "credassure",
        "aud": "credassure",
        "sub": "u-1",
        "role": "preparer",
        "tenant": "default",
        "iat": now,
        "exp": now.timestamp() + 60,
        "ver": "7",
    }
    with pytest.raises(AuthError):
        verify_token(jwt.encode(claims, SECRET, algorithm="HS256"), SECRET)


def test_ADR0038_user_admin_never_sees_or_decides_a_case() -> None:
    admin = Principal("u-a", Role.USER_ADMIN, "default")
    case = CaseRef("CA-1", "default", "u-p", "vp_finance", "AWAITING_APPROVAL")
    assert Role.USER_ADMIN not in BUSINESS_ROLES
    assert not can_view_case(admin, case) and not can_decide(admin, case)
