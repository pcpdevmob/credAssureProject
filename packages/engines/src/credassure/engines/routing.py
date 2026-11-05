"""Approval routing on the validated amount (APR-01..03, BR-12). Pure.

Above the threshold (default ₹1,50,00,000) the VP Finance; below it the Director Finance;
exactly at it the configured boundary rule: hold for a human (default), director or vp.
"""

from decimal import Decimal
from typing import Literal

Route = Literal["director_finance", "vp_finance", "HELD"]
BoundaryRule = Literal["hold", "director", "vp"]
THRESHOLD = Decimal(15_000_000)
BOUNDARY: dict[BoundaryRule, Route] = {
    "hold": "HELD",
    "director": "director_finance",
    "vp": "vp_finance",
}


def route(amount: Decimal, rule: BoundaryRule = "hold", threshold: Decimal = THRESHOLD) -> Route:
    if not isinstance(amount, Decimal):
        raise TypeError("the routed amount is Decimal (BR-05)")
    if amount < 0:
        raise ValueError("the routed amount cannot be negative")
    if amount > threshold:
        return "vp_finance"
    if amount < threshold:
        return "director_finance"
    return BOUNDARY[rule]
