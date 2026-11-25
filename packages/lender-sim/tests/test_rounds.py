"""LW-15 rounds 2-3 (ADR 0037): rate-match and tenor-change replies from the v2 scripts."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from credassure.engines import loancost, offer_audit
from credassure.lender_sim import NO_SCRIPT, ScriptedLender

ROOT = Path(__file__).resolve().parents[3]
V1, V2 = ROOT / "data/frozen/v1", ROOT / "data/frozen/v2"
SIM = ScriptedLender(V2 / "lender_scripts")


def _offer(case: str, offer_id: str, **changes: Any) -> tuple[dict[str, Any], str]:
    offer = json.loads((V1 / "offers" / case / f"{offer_id}.v1.json").read_text())
    offer |= changes
    return offer, (V1 / "kfs" / f"{offer['kfs_doc_id']}-SCH.md").read_text()


def test_ADR0037_v2_fee_waiver_replies_equal_v1() -> None:
    for path in sorted((V1 / "lender_scripts").glob("L*.yaml")):
        v1 = yaml.safe_load(path.read_text())["responses"]["fee_waiver_v1"]
        v2 = yaml.safe_load((V2 / "lender_scripts" / path.name).read_text())["responses"]
        assert v2["fee_waiver_v1"] == v1
        assert set(v2) == {"fee_waiver_v1", "rate_match_v1", "tenor_change_v1"}


def test_ADR0037_v2_scripts_regenerate_byte_identical(tmp_path: Path) -> None:
    from credassure.datagen import lender_scripts_v2

    assert lender_scripts_v2.main(tmp_path) == 0
    assert (tmp_path / "SHA256SUMS").read_text() == (V2 / "SHA256SUMS").read_text()


def test_LW15_rate_match_lowers_the_rate_and_restates_an_instalment_that_audits() -> None:
    offer, sch = _offer("CA-2026-0006", "OF-06-B")
    offer |= {"lender_id": "L02", "rate_type": "fixed"}  # L02 matches in full
    cited = Decimal(offer["annual_rate"]) - Decimal("0.01")
    reply = SIM.send("L02", "rate_match_v1", "request", offer, sch, {"cited_rate": str(cited)})
    assert reply.offer is not None and reply.schedule is not None
    assert Decimal(reply.offer["annual_rate"]) == cited
    assert reply.offer["version"] == offer["version"] + 1
    assert reply.schedule[0] == f"{reply.offer['kfs_doc_id']}-SCH" and reply.schedule[1] == sch
    audit = offer_audit.audit(reply.offer, (), "small")
    assert "LW_INSTALMENT_MISMATCH" not in audit.flags
    assert abs(Decimal(reply.offer["stated_instalment"]) - loancost.instalment(reply.offer)) < 1


def test_LW15_partial_match_closes_half_the_gap_and_refusal_none() -> None:
    offer, sch = _offer("CA-2026-0001", "OF-01-B", rate_type="fixed", annual_rate="0.1300")
    half = SIM.send("L01", "rate_match_v1", "r", offer, sch, {"cited_rate": "0.1200"})
    assert half.offer is not None and half.offer["annual_rate"] == "0.1250"
    no = SIM.send("L03", "rate_match_v1", "r", offer, sch, {"cited_rate": "0.1200"})
    assert no.offer is None and "unable" in no.text
    floating = {**offer, "rate_type": "floating"}
    assert (
        SIM.send("L02", "rate_match_v1", "r", floating, sch, {"cited_rate": "0.12"}).offer is None
    )


def test_LW15_tenor_change_extends_moratorium_and_tenure_keeping_the_instalment() -> None:
    offer, sch = _offer("CA-2026-0006", "OF-06-C")
    reply = SIM.send("L01", "tenor_change_v1", "r", offer, sch, {"extra_months": 3})
    assert reply.offer is not None
    r = reply.offer
    assert r["moratorium_months"] == offer["moratorium_months"] + 3
    assert r["tenure_months"] == offer["tenure_months"] + 3
    assert r["stated_instalment"] == offer["stated_instalment"]
    audit = offer_audit.audit(r, (), "small")
    assert not {"LW_INSTALMENT_MISMATCH", "LW_SCHEDULE_DATE_MISMATCH"} & set(audit.flags)
    partial = SIM.send("L02", "tenor_change_v1", "r", offer, sch, {"extra_months": 5}).offer
    assert partial is not None and partial["moratorium_months"] == offer["moratorium_months"] + 2
    assert SIM.send("L03", "tenor_change_v1", "r", offer, sch, {"extra_months": 3}).offer is None


def test_LW15_v1_script_asked_a_round_2_question_gives_no_revision() -> None:
    offer, sch = _offer("CA-2026-0006", "OF-06-C")
    v1 = ScriptedLender(V1 / "lender_scripts")
    reply = v1.send("L01", "tenor_change_v1", "r", offer, sch, {"extra_months": 3})
    assert reply.offer is None and reply.text == NO_SCRIPT


def test_LW13_a_lender_without_a_script_does_not_reply() -> None:
    # An offer added through the PDF review form gets a generated lender id (no script): the
    # round is answered with no reply and no revision instead of failing the negotiation.
    offer, sch = _offer("CA-2026-0006", "OF-06-A", lender_id="ACB-7K2Q")
    for template, terms in (
        ("fee_waiver_v1", None),
        ("rate_match_v1", {"cited_rate": "0.09"}),
        ("tenor_change_v1", {"extra_months": 3}),
    ):
        reply = SIM.send("ACB-7K2Q", template, "r", offer, sch, terms)
        assert reply.offer is None and reply.schedule is None and reply.text == NO_SCRIPT


def test_BR15_round_2_injection_reply_is_text_only() -> None:
    offer, sch = _offer("CA-2026-0001", "OF-01-B", rate_type="fixed", annual_rate="0.1300")
    reply = SIM.send("L05", "rate_match_v1", "r", offer, sch, {"cited_rate": "0.1200"})
    assert "SYSTEM NOTE" in reply.text and reply.offer is not None
    assert reply.offer["annual_rate"] == "0.1250"  # the reply's words change nothing
