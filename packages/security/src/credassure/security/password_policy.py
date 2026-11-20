"""Password rules (ADR 0038, NIST SP 800-63B §5.1.1.2 style): length and a deny-list, no
composition rules. Returns the reasons a password is refused, in plain words; empty means OK.
"""

import re

MIN_LENGTH = 12
MAX_LENGTH = 256

# A short deny-list of the most common choices and product words; checked case-insensitively and
# with trailing digits and symbols removed ("Password@2026" is "password").
COMMON = frozenset(
    {
        "password",
        "passw0rd",
        "p@ssword",
        "p@ssw0rd",
        "qwerty",
        "qwertyuiop",
        "asdfghjkl",
        "letmein",
        "welcome",
        "admin",
        "administrator",
        "iloveyou",
        "monkey",
        "dragon",
        "football",
        "baseball",
        "sunshine",
        "princess",
        "trustno",
        "changeme",
        "default",
        "secret",
        "abc123",
        "abcdef",
        "abcdefgh",
        "abcdefghijkl",
        "123456789",
        "1234567890",
        "credassure",
        "finbridge",
        "finance",
        "director",
        "preparer",
        "approver",
        "india",
        "mumbai",
        "pune",
        "loan",
        "lender",
        "msme",
    }
)
_TAIL = re.compile(r"[\d\W_]+$")


def problems(password: str, username: str = "", *, current: str | None = None) -> list[str]:
    out: list[str] = []
    if len(password) < MIN_LENGTH:
        out.append(f"use at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        out.append(f"use at most {MAX_LENGTH} characters")
    low = password.lower()
    core = _TAIL.sub("", low)
    if low in COMMON or core in COMMON:
        out.append("this password is too common")
    if len(set(low)) <= 2:
        out.append("use more than two different characters")
    name = username.lower()
    if name and (name in low or any(len(p) >= 4 and p in low for p in re.split(r"[._-]", name))):
        out.append("do not include your username")
    if current is not None and password == current:
        out.append("choose a password you have not just used")
    return out
