"""P8.3 protected-attribute denylist (scope #67): field-name matching only."""

import pytest

from credassure.guardrails import protected


@pytest.mark.parametrize(
    "name",
    [
        "gender",
        "Promoter_Gender",
        "ownerReligion",
        "caste",
        "SC/ST caste",
        "date_of_birth",
        "DOB",
        "dateOfBirth",
        "age",
        "marital_status",
        "disability_flag",
        "community",
        "race",
    ],
)
def test_scope67_protected_names_match(name: str) -> None:
    assert protected.matches(name)


@pytest.mark.parametrize(
    "name",
    [
        "customer",
        "supplier",
        "category",
        "inventory_age",
        "average",
        "page",
        "stage",
        "trace_id",
        "home_state",
        "msme_supplier",
        "enterprise_class",
        "lender_type",
        "racecourse",
    ],
)
def test_scope67_ordinary_names_do_not_match(name: str) -> None:
    assert not protected.matches(name)


def test_scope67_find_walks_json_keys_and_csv_header_only() -> None:
    assert protected.find('{"a": {"gender": "x"}, "b": [{"Caste": 1}]}', is_json=True) == [
        "gender",
        "Caste",
    ]
    assert protected.find("invoice_id,religion\nINV-1,gender\n", is_json=False) == ["religion"]
    assert protected.find('{"customer_name": "Gender Neutral Ltd"}', is_json=True) == []
    assert protected.find("{not json", is_json=True) == []
