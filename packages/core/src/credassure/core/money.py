"""Exact money helpers (BR-05, scope #8).

Display formatting is separate from the value. Engines keep ``Decimal``; paise are
the integer form for later storage. No ``float``.
"""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext
from decimal import Context as DecimalContext

MONEY: DecimalContext = DecimalContext(prec=34, rounding=ROUND_HALF_UP)
_PAISE = Decimal("0.01")
_LAKH = Decimal("100000")
_HUNDRED = Decimal(100)


def _require_decimal(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise TypeError("money values are Decimal, never float")
    return value


def to_paise(rupees: Decimal) -> int:
    """Convert rupees to integer paise, half-up (BR-05)."""
    amount = _require_decimal(rupees)
    with localcontext(MONEY):
        return int((amount * _HUNDRED).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def from_paise(paise: int) -> Decimal:
    """Convert integer paise back to rupees with two decimal places (BR-05)."""
    if not isinstance(paise, int) or isinstance(paise, bool):
        raise TypeError("paise are an int")
    with localcontext(MONEY):
        return (Decimal(paise) / _HUNDRED).quantize(_PAISE)


def format_inr(amount: Decimal) -> str:
    """Indian grouping. Whole rupees omit paise; a fraction shows two digits (BR-05)."""
    value = _require_decimal(amount)
    with localcontext(MONEY):
        quantized = value.quantize(_PAISE, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    rendered = format(abs(quantized), "f")
    whole_digits, frac = rendered.split(".")
    grouped = _indian_group(whole_digits)
    if int(frac):
        return f"{sign}₹{grouped}.{frac}"
    return f"{sign}₹{grouped}"


def round_up_to_lakh(amount: Decimal) -> Decimal:
    """Ceiling to the next ₹1,00,000. An exact multiple stays put (BR-05, WC recommendation)."""
    value = _require_decimal(amount)
    if value < 0:
        raise ValueError("round_up_to_lakh rejects a negative amount")
    with localcontext(MONEY):
        units = (value / _LAKH).to_integral_value(rounding=ROUND_CEILING)
        return units * _LAKH


def _indian_group(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    head, last = digits[:-3], digits[-3:]
    parts: list[str] = []
    while head:
        parts.append(head[-2:])
        head = head[:-2]
    parts.reverse()
    return ",".join([*parts, last])
