"""Heuristic prompt-injection scanner for retrieved text, KFS documents, uploads and lender
replies (BR-15, OWASP LLM01). A hit is flagged and audited; the text is still treated as data and
nothing in it is obeyed. Routing and gates never read document text, so a miss here cannot change
an outcome; the scanner exists for evidence and for the A5 ablation.
"""

import base64
import binascii
import re

# Zero-width and bidi-control code points, built from numbers so the source holds none (B613).
_HIDDEN = "".join(map(chr, [*range(0x200B, 0x2010), *range(0x202A, 0x202F), 0x2060, 0xFEFF]))

_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "role_switch",
        re.compile(
            r"(?im)^\s*(system|assistant|developer)\s*:"
            r"|\b(system|assistant)\s+(note|override|message|prompt|instruction)s?\b"
            r"|<\|[a-z_]+\|>|\[/?INST\]|<</?SYS>>"
            r"|\byou\s+are\s+now\b|\b(admin|developer|god|jailbreak)\s+mode\b"
        ),
    ),
    (
        "ignore_instructions",
        re.compile(
            r"(?i)\b(ignore|disregard|forget|skip|bypass|override)\b[^.\n]{0,40}?"
            r"\b(instructions?|rules?|prompts?|checks?|verification|comparison|polic(y|ies)|guardrails?)\b"
            # Hinglish object-verb order (found by the P2 pattern tests): "sab checks skip karo"
            r"|\b(instructions?|rules?|checks?|verification|polic(y|ies))\b[^.\n]{0,20}?"
            r"\b(skip|ignore|bypass|override)\s+(karo|kar\s*do|kijiye|kardo)\b"
        ),
    ),
    (
        "addressed_to_model",
        re.compile(
            r"(?i)\b(note|message|instructions?)\s+(to|for)\s+(the\s+)?"
            r"(ai|assistant|model|llm|agent|chatbot)\b"
        ),
    ),
    (
        "action_command",
        re.compile(
            r"(?i)\b(rank|mark|recommend|route)\s+(this|the|it|only)\b[^.\n]{0,30}?"
            r"\b(first|approved|affordable|only|vp|director)\b"
            r"|\bapprove\s+(this|the)\s+(proposal|case|loan|offer)\b"
            r"|\bpre-?approved\b|\baccept\s+(this|the)\s+offer\b"
        ),
    ),
    (
        "tool_call",
        re.compile(
            r"(?i)\b(call|invoke|run|execute)\s+(the\s+)?(tool|function)\b"
            r"|\b(route_proposal|function_call|tool_calls?)\b"
        ),
    ),
    ("hidden_characters", re.compile(f"[{re.escape(_HIDDEN)}]")),
)
_B64 = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_HEX = re.compile(r"\b(?:[0-9a-fA-F]{2}){20,}\b")


def _decoded(blob: str) -> str | None:
    try:
        raw = bytes.fromhex(blob) if _HEX.fullmatch(blob) else base64.b64decode(blob, validate=True)
        return raw.decode("utf-8")
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None


def scan(text: str, *, _depth: int = 0) -> list[str]:
    """Sorted flag names found in `text`; empty when clean."""
    flags = {name for name, rule in _RULES if rule.search(text)}
    if _depth == 0:  # an encoded blob is flagged only if its plain text is itself an injection
        for m in [*_B64.finditer(text), *_HEX.finditer(text)]:
            plain = _decoded(m.group())
            if plain and scan(plain, _depth=1):
                flags.add("encoded_payload")
    return sorted(flags)
