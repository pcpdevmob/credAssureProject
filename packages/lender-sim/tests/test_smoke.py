"""Lender simulator (LW-13): scripted, deterministic, and equal to the frozen revised versions."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from credassure.lender_sim import ScriptedLender

DATA = Path(__file__).resolve().parents[3] / "data/frozen/v1"
SIM = ScriptedLender(DATA / "lender_scripts")


def _send(case: str, offer_id: str):  # type: ignore[no-untyped-def]
    offer = json.loads((DATA / "offers" / case / f"{offer_id}.v1.json").read_text())
    sch = (DATA / "kfs" / f"{offer['kfs_doc_id']}-SCH.md").read_text()
    return offer, SIM.send(offer["lender_id"], "fee_waiver_v1", "request", offer, sch)


@pytest.mark.parametrize(
    ("case", "offer_id"),
    [("CA-2026-0001", "OF-01-A"), ("CA-2026-0006", "OF-06-A"), ("CA-2026-0003", "OF-03-A")],
)
def test_LW13_revision_equals_the_frozen_v2(case: str, offer_id: str) -> None:
    _, reply = _send(case, offer_id)
    frozen = json.loads((DATA / "offers" / case / f"{offer_id}.v2.json").read_text())
    assert reply.offer is not None and reply.schedule is not None
    got = {k: v for k, v in reply.offer.items() if k != "issue_date"}
    want = {k: v for k, v in frozen.items() if k != "issue_date"}
    fee = lambda o: next(f for f in o["fees"] if f["name"] == "Processing fee")  # noqa: E731
    assert Decimal(fee(got)["value"]) == Decimal(fee(want)["value"])
    assert {k: v for k, v in got.items() if k != "fees"} == {
        k: v for k, v in want.items() if k != "fees"
    }
    doc, text = reply.schedule
    frozen_rows = (DATA / "kfs" / f"{doc}.md").read_text().split("| Charge |")[1]
    assert text.split("| Charge |")[1] == frozen_rows


def test_LW13_refusal_returns_no_revision() -> None:
    _, reply = _send("CA-2026-0009", "OF-09-C")
    assert reply.offer is None and "unable" in reply.text


def test_BR13_simulator_has_no_acceptance_method() -> None:
    assert not [m for m in dir(SIM) if any(w in m for w in ("accept", "sign", "submit"))]


def test_LW13_fixed_fee_revision_is_paise_and_plain(tmp_path: Path) -> None:
    (tmp_path / "LX.yaml").write_text(
        "responses:\n  fee_waiver_v1: {processing_fee_share_kept: '0.333', reply_text: ok}\n"
    )
    offer = {
        "version": 1,
        "kfs_doc_id": "KFS-X-v1",
        "fees": [
            {"name": "Processing fee", "basis": "fixed", "value": "50000", "gst_applicable": True}
        ],
    }
    sch = "| Processing fee | upfront | ₹50,000 + GST |"
    reply = ScriptedLender(tmp_path).send("LX", "fee_waiver_v1", "m", offer, sch)
    assert reply.offer is not None and reply.offer["fees"][0]["value"] == "16650"
    assert reply.schedule == ("KFS-X-v2-SCH", "| Processing fee | upfront | ₹16,650 + GST |")
    (tmp_path / "LY.yaml").write_text(
        "responses:\n  fee_waiver_v1: {processing_fee_share_kept: '-1', reply_text: ok}\n"
    )
    with pytest.raises(ValueError):
        ScriptedLender(tmp_path).send("LY", "fee_waiver_v1", "m", offer, sch)
