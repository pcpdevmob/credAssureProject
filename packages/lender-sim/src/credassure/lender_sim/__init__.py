"""Deterministic lender simulator (design-detail §3.2, LW-13, DATA_SPEC §3). In-process, scripted.

``ScriptedLender.send`` answers a ``fee_waiver_v1`` request from the lender's YAML script: a reply
text, and for a waiver a revised offer version with its schedule of charges (processing fee x
``processing_fee_share_kept``, version + 1). A refusal returns no revision. The reply text is
lender data: it may carry a planted instruction, and callers treat it as data only (BR-15).
There is no method that accepts, signs or submits anything (BR-13).
"""

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import yaml

from credassure.core.money import format_inr

PROCESSING_FEE = "Processing fee"
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
    ) -> Reply:
        if not _ID.match(lender_id) or template_id != "fee_waiver_v1" or not message:
            raise ValueError("unknown lender or template")
        script = yaml.safe_load((self.scripts_dir / f"{lender_id}.yaml").read_text("utf-8"))
        response = script["responses"][template_id]
        kept = Decimal(str(response["processing_fee_share_kept"]))
        if not 0 <= kept <= 1:
            raise ValueError(f"{lender_id}: processing_fee_share_kept must be within 0..1")
        text = str(response["reply_text"])
        fee = next((f for f in offer.get("fees", []) if f["name"] == PROCESSING_FEE), None)
        if kept == 1 or fee is None or not re.search(r"-v\d+$", str(offer["kfs_doc_id"])):
            return Reply(text)  # refusal, or nothing this script can revise
        revised = copy.deepcopy(dict(offer))
        version = int(revised["version"]) + 1
        revised["version"] = version
        revised["kfs_doc_id"] = re.sub(r"-v\d+$", f"-v{version}", str(revised["kfs_doc_id"]))
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


def _cell(fee: Mapping[str, Any]) -> str:
    value = Decimal(str(fee["value"]))
    gst = " + GST" if fee.get("gst_applicable", True) else ""
    if fee["basis"] == "pct_of_principal":
        pct = (value * 100).normalize()
        if -pct.as_tuple().exponent < 2:  # type: ignore[operator]  # at least two decimals
            pct = pct.quantize(Decimal("0.01"))
        return f"{format(pct, 'f')}% of the loan amount{gst}"
    return f"{format_inr(value)}{gst}"
