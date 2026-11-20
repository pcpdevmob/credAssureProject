"""Rail switch for the A6 ablation (plan v3.4 P8.5, ADR 0031 §4).

A6 runs safety_v2 with rails R1 (input), R2 (retrieval excerpt cap) and R4 (output PII re-scan)
off, to show what the rails themselves contribute. The gateway sets this once at start-up from
`ABLATION=A6`, which its settings refuse in the demo profile; every rail is on by default. The
Critic is not switched here: turning it off is ablation A2. R3 (tool allowlist) and R5 (trace
masking) never switch off.
"""

from collections.abc import Iterable

SWITCHABLE = frozenset({"R1", "R2", "R4"})
_off: frozenset[str] = frozenset()


def set_off(rails: Iterable[str]) -> None:
    global _off
    wanted = frozenset(rails)
    if not wanted <= SWITCHABLE:
        raise ValueError(f"only {sorted(SWITCHABLE)} can be switched off")
    _off = wanted


def on(rail: str) -> bool:
    return rail not in _off
