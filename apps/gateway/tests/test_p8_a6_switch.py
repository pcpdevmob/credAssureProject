"""P8.5 A6 ablation (ADR 0031 §4): ABLATION=A6 turns rails R1, R2 and R4 off for the safety_v2
comparison run, never in the demo profile; every other app has every rail on."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from pydantic import ValidationError

from credassure.guardrails import switch

NEW_CASE = {
    "msme_name": "Demo Electronics Pvt Ltd",
    "order_ref": "PO-A6",
    "order_value_paise": 3_20_00_000_00,
    "indicative_amount_paise": 2_00_00_000_00,
    "due_date": "2027-05-15",
}
PAN_CSV = b"invoice_id,customer,amount,due_week,expected_week\nINV-1,BQZPK4821M,100000,3,4\n"


@pytest.fixture(autouse=True)
def _rails_back_on() -> Iterator[None]:
    yield
    switch.set_off(())


def _upload(client: Any, login: Callable[..., dict[str, str]]) -> int:
    h = login(client, "prep.e001")
    case_id = client.post("/v1/cases", json=NEW_CASE, headers=h).json()["case_id"]
    r = client.post(
        f"/v1/cases/{case_id}/files",
        params={"kind": "receivables"},
        files={"file": ("receivables.csv", PAN_CSV, "text/csv")},
        headers=h,
    )
    return int(r.status_code)


def test_P8_A6_turns_r1_off_and_a_normal_app_turns_it_back_on(
    make_client: Callable[..., Any], login: Callable[..., dict[str, str]]
) -> None:
    ablated = make_client(ablation="A6")
    assert not switch.on("R1") and not switch.on("R2") and not switch.on("R4")
    assert _upload(ablated, login) == 201  # the identifier is no longer refused
    normal = make_client()
    assert switch.on("R1") and switch.on("R2") and switch.on("R4")
    assert _upload(normal, login) == 422


def test_P8_A6_is_refused_in_the_demo_profile() -> None:
    from credassure.gateway.settings import Settings

    with pytest.raises(ValidationError, match="A6"):
        Settings(_env_file=None, app_env="demo", jwt_secret="x" * 40, ablation="A6")  # type: ignore[call-arg]


def test_P8_only_r1_r2_r4_can_be_switched_off() -> None:
    with pytest.raises(ValueError, match="only"):
        switch.set_off({"R3"})
