"""Deterministic lender simulator (design-detail §3.2, LW-13/15, DATA_SPEC §3, ADR 0037).
In-process, scripted.

``ScriptedLender.send`` answers a request from the lender's YAML script: a reply text, and for a
concession a revised offer version (version + 1) with its schedule of charges.

- ``fee_waiver_v1``: processing fee x ``processing_fee_share_kept``; the schedule row changes.
- ``rate_match_v1`` (``terms["cited_rate"]``): annual rate lowered by ``rate_gap_closed`` of the
  gap to the cited rate (4 decimals, half-up); the lender restates its instalment to the rupee.
- ``tenor_change_v1`` (``terms["extra_months"]``): moratorium and tenure both longer by up to
  ``max_extra_months``, first repayment moved to match; the instalment is unchanged.

A refusal, or a script without a reply for the template (a v1 script asked a round-2 question),
returns no revision. The reply text is lender data: it may carry a planted instruction, and callers
treat it as data only (BR-15). There is no method that accepts, signs or submits anything (BR-13).
"""

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from pathlib import Path
from typing import Any

import yaml

from credassure.core.money import MONEY, format_inr

PROCESSING_FEE = "Processing fee"
TEMPLATES = ("fee_waiver_v1", "rate_match_v1", "tenor_change_v1")
NO_SCRIPT = "The lender has not replied to this request."
_ID = re.compile(r"^[A-Za-z0-9-]{1,40}$")


@dataclass(frozen=True)
class Reply:
    text: str
    offer: dict[str, Any] | None = None  # the revised version, if any
    schedule: tuple[str, str] | None = None  # (doc_id, schedule text) of the revision


class ScriptedLender:
    """``LenderGateway``: one YAML script per lender in ``scripts_dir``."""

    def __init__(self, scripts_dir: Path) -> None:
        self.scripts_dir = scripts_dir

    def send(
        self,
        lender_id: str,
        template_id: str,
        message: str,
        offer: Mapping[str, Any],
        schedule: str,
        terms: Mapping[str, Any] | None = None,
    ) -> Reply:
        if not _ID.match(lender_id) or template_id not in TEMPLATES or not message:
            raise ValueError("unknown lender or template")
        script = yaml.safe_load((self.scripts_dir / f"{lender_id}.yaml").read_text("utf-8"))
        response = (script.get("responses") or {}).get(template_id)
        if response is None:
            return Reply(NO_SCRIPT)
        text = str(response["reply_text"])
        if not re.search(r"-v\d+$", str(offer["kfs_doc_id"])):
            return Reply(text)  # nothing this script can version
        if template_id == "rate_match_v1":
            return self._rate(response, text, offer, schedule, terms or {})
        if template_id == "tenor_change_v1":
            return self._tenor(response, text, offer, schedule, terms or {})
        kept = Decimal(str(response["processing_fee_share_kept"]))
        if not 0 <= kept <= 1:
            raise ValueError(f"{lender_id}: processing_fee_share_kept must be within 0..1")
        fee = next((f for f in offer.get("fees", []) if f["name"] == PROCESSING_FEE), None)
        if kept == 1 or fee is None:
            return Reply(text)  # refusal, or nothing this script can revise
        revised = _next_version(offer)
        cell = ""
        for fee in revised.get("fees", []):
            if fee["name"] == PROCESSING_FEE:
                value = Decimal(str(fee["value"])) * kept
                if fee["basis"] == "fixed":  # rupees: paise, half-up (ADR 0010)
                    value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                fee["value"] = format(value.normalize(), "f")
                cell = _cell(fee)
        doc_id = f"{revised['kfs_doc_id']}-SCH"
        new_schedule = re.sub(
            rf"^\|\s*{PROCESSING_FEE}\s*\|\s*(\w+)\s*\|[^\n]*\|$",
            lambda m: f"| {PROCESSING_FEE} | {m.group(1)} | {cell} |",
            schedule,
            flags=re.MULTILINE,
        )
        return Reply(text, revised, (doc_id, new_schedule))

    @staticmethod
    def _rate(
        response: Mapping[str, Any],
        text: str,
        offer: Mapping[str, Any],
        schedule: str,
        terms: Mapping[str, Any],
    ) -> Reply:
        closed = Decimal(str(response["rate_gap_closed"]))
        if not 0 <= closed <= 1:
            raise ValueError("rate_gap_closed must be within 0..1")
        current, cited = Decimal(str(offer["annual_rate"])), Decimal(str(terms["cited_rate"]))
        if closed == 0 or offer.get("rate_type") != "fixed" or cited >= current:
            return Reply(text)
        new = (current - (current - cited) * closed).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        revised = _next_version(offer)
        revised["annual_rate"] = format(new, "f")
        revised["stated_instalment"] = _instalment(revised)
        return Reply(text, revised, (f"{revised['kfs_doc_id']}-SCH", schedule))

    @staticmethod
    def _tenor(
        response: Mapping[str, Any],
        text: str,
        offer: Mapping[str, Any],
        schedule: str,
        terms: Mapping[str, Any],
    ) -> Reply:
        granted = min(int(response["max_extra_months"]), int(terms["extra_months"]))
        if granted <= 0:
            return Reply(text)
        revised = _next_version(offer)
        revised["moratorium_months"] = int(offer.get("moratorium_months", 0)) + granted
        revised["tenure_months"] = int(offer["tenure_months"]) + granted
        disbursal = date.fromisoformat(str(offer["disbursal_date"]))
        first = _add_months(disbursal, int(revised["moratorium_months"]) + 1)
        revised["first_repayment_date"] = first.isoformat()
        return Reply(text, revised, (f"{revised['kfs_doc_id']}-SCH", schedule))


def _next_version(offer: Mapping[str, Any]) -> dict[str, Any]:
    revised = copy.deepcopy(dict(offer))
    version = int(revised["version"]) + 1
    revised["version"] = version
    revised["kfs_doc_id"] = re.sub(r"-v\d+$", f"-v{version}", str(revised["kfs_doc_id"]))
    return revised


def _add_months(day: date, months: int) -> date:
    """The lender's calendar: the day capped at 28, as every schedule in the frozen data."""
    month0 = day.month - 1 + months
    return date(day.year + month0 // 12, month0 % 12 + 1, min(day.day, 28))


def _instalment(offer: Mapping[str, Any]) -> str:
    """The lender's own restated instalment after a rate change, to the rupee (half-up)."""
    with localcontext(MONEY):
        principal = Decimal(str(offer["principal"]))
        monthly = Decimal(str(offer["annual_rate"])) / 12
        n = int(offer["tenure_months"]) - int(offer.get("moratorium_months", 0))
        if offer["repayment"]["method"] == "equal_principal":
            value = principal / n + principal * monthly
        else:
            growth = (1 + monthly) ** n
            value = principal * monthly * growth / (growth - 1)
    return format(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP), "f")


def _cell(fee: Mapping[str, Any]) -> str:
    value = Decimal(str(fee["value"]))
    gst = " + GST" if fee.get("gst_applicable", True) else ""
    if fee["basis"] == "pct_of_principal":
        pct = (value * 100).normalize()
        if -pct.as_tuple().exponent < 2:  # type: ignore[operator]  # at least two decimals
            pct = pct.quantize(Decimal("0.01"))
        return f"{format(pct, 'f')}% of the loan amount{gst}"
    return f"{format_inr(value)}{gst}"
