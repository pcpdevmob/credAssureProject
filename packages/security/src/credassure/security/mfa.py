"""Second factor (ADR 0038): TOTP per RFC 6238, one-time backup codes, the secret encrypted at rest.

- TOTP: HMAC-SHA1, 30-second steps, 6 digits, the current step ±1 for clock drift. A code is
  accepted only for a step later than the last one used (replay protection): `verify_totp` returns
  the step to store, or None.
- Backup codes: 8 random codes shown once; only argon2 hashes are stored and each works once.
- At rest the base32 secret is sealed with AES-256-GCM under MFA_ENCRYPTION_KEY (32 random bytes,
  base64), bound to the user id as associated data, so a sealed secret copied to another user
  does not open. A key that is missing or not 32 bytes fails closed.

Pure functions; no I/O. The clock is passed in so tests are deterministic.
"""

import base64
import hashlib
import hmac
import os
import secrets
import struct
from urllib.parse import quote

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .auth import hash_password, verify_password

STEP = 30
DIGITS = 6
DRIFT = 1  # steps either side
SECRET_BYTES = 20  # 160 bits, RFC 4226 recommendation
BACKUP_CODES = 8
ISSUER = "CredAssure"
_SEAL_VERSION = "v1"


class MfaError(Exception):
    """The MFA key or a sealed secret is unusable (configuration, never a user mistake)."""


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode().rstrip("=")


def _key(secret_b32: str) -> bytes:
    pad = "=" * (-len(secret_b32) % 8)
    return base64.b32decode(secret_b32.upper() + pad)


def totp_at(secret_b32: str, step: int, digits: int = DIGITS) -> str:
    """RFC 6238 / RFC 4226 dynamic truncation for one time step."""
    mac = hmac.new(_key(secret_b32), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    code = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % 10**digits).zfill(digits)


def step_of(now: float) -> int:
    return int(now // STEP)


def verify_totp(secret_b32: str, code: str, now: float, last_step: int | None) -> int | None:
    """The matching step if `code` is valid now (±DRIFT) and newer than `last_step`, else None."""
    code = code.strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    current = step_of(now)
    for step in range(current - DRIFT, current + DRIFT + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(totp_at(secret_b32, step), code):
            return step
    return None


def provisioning_uri(secret_b32: str, username: str) -> str:
    """otpauth:// URI for authenticator apps (Google Authenticator key-URI format)."""
    label = quote(f"{ISSUER}:{username}")
    return (
        f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(ISSUER)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={STEP}"
    )


# ---- backup codes -------------------------------------------------------------------------------
def new_backup_codes(n: int = BACKUP_CODES) -> tuple[list[str], list[str]]:
    """(codes to show once, argon2 hashes to store). Codes look like 'k3f9-x2m7' (40 bits)."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"  # no 0/o, 1/l/i
    codes = [
        "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2))
        for _ in range(n)
    ]
    return codes, [hash_password(c) for c in codes]


def use_backup_code(hashes: list[str], code: str) -> list[str] | None:
    """The remaining hashes if `code` matches one (that one is removed), else None."""
    code = code.strip().lower()
    for i, digest in enumerate(hashes):
        if verify_password(digest, code):
            return hashes[:i] + hashes[i + 1 :]
    return None


# ---- secret at rest -----------------------------------------------------------------------------
def load_key(b64: str | None) -> bytes:
    if not b64:
        raise MfaError("MFA_ENCRYPTION_KEY is not set")
    try:
        key = base64.b64decode(b64, validate=True)
    except ValueError as exc:
        raise MfaError("MFA_ENCRYPTION_KEY is not base64") from exc
    if len(key) != 32:
        raise MfaError("MFA_ENCRYPTION_KEY must be 32 bytes (base64 of 32 random bytes)")
    return key


def seal(key: bytes, user_id: str, secret_b32: str) -> str:
    nonce = os.urandom(12)
    box = AESGCM(key).encrypt(nonce, secret_b32.encode(), user_id.encode())
    return f"{_SEAL_VERSION}:{base64.b64encode(nonce + box).decode()}"


def unseal(key: bytes, user_id: str, sealed: str) -> str:
    version, _, body = sealed.partition(":")
    if version != _SEAL_VERSION:
        raise MfaError("unknown sealed-secret version")
    raw = base64.b64decode(body)
    try:
        return AESGCM(key).decrypt(raw[:12], raw[12:], user_id.encode()).decode()
    except InvalidTag as exc:
        raise MfaError("sealed secret does not open with this key and user") from exc
