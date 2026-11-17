"""scripts/openapi_diff.py (scope #28): breaking changes fail, additions pass."""

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest

_spec = importlib.util.spec_from_file_location(
    "openapi_diff", Path(__file__).parent.parent / "scripts" / "openapi_diff.py"
)
assert _spec and _spec.loader
od = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(od)

BASE: dict[str, Any] = {
    "paths": {
        "/v1/cases/{id}": {
            "get": {
                "parameters": [{"name": "id", "in": "path", "required": True}],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Case"}}
                        }
                    }
                },
            },
            "post": {
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"comment": {"type": "string"}},
                                "required": [],
                            }
                        }
                    },
                },
                "responses": {"202": {"content": {"application/json": {"schema": {}}}}},
            },
        }
    },
    "components": {
        "schemas": {
            "Case": {
                "type": "object",
                "properties": {"status": {"type": "string"}, "amount": {"type": "integer"}},
            }
        }
    },
}


def _changed(edit: Any) -> list[str]:
    head = copy.deepcopy(BASE)
    edit(head)
    return od.diff(BASE, head)


def test_scope28_identical_and_additive_changes_pass() -> None:
    assert od.diff(BASE, BASE) == []

    def add(h: dict[str, Any]) -> None:
        h["paths"]["/v1/new"] = {"get": {"responses": {}}}
        h["components"]["schemas"]["Case"]["properties"]["route"] = {"type": "string"}
        h["paths"]["/v1/cases/{id}"]["get"]["parameters"].append(
            {"name": "fmt", "in": "query", "required": False}
        )

    assert _changed(add) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda h: h["paths"].pop("/v1/cases/{id}"), "removed path"),
        (lambda h: h["paths"]["/v1/cases/{id}"].pop("post"), "removed operation POST"),
        (lambda h: h["paths"]["/v1/cases/{id}"]["get"].update(responses={}), "removed response"),
        (
            lambda h: h["components"]["schemas"]["Case"]["properties"].pop("amount"),
            "removed response property amount",
        ),
        (
            lambda h: h["components"]["schemas"]["Case"]["properties"].update(
                amount={"type": "string"}
            ),
            "response property amount changed type",
        ),
        (
            lambda h: h["paths"]["/v1/cases/{id}"]["get"]["parameters"].append(
                {"name": "x", "in": "query", "required": True}
            ),
            "new required parameter x",
        ),
        (
            lambda h: h["paths"]["/v1/cases/{id}"]["post"]["requestBody"]["content"][
                "application/json"
            ]["schema"].update(required=["comment"]),
            "new required request property comment",
        ),
    ],
)
def test_scope28_breaking_change_is_reported(edit: Any, expected: str) -> None:
    found = _changed(edit)
    assert any(expected in f for f in found), found


def test_scope28_200_to_202_with_compatible_body_is_not_breaking() -> None:
    def to_202(h: dict[str, Any]) -> None:
        get = h["paths"]["/v1/cases/{id}"]["get"]
        get["responses"] = {"202": get["responses"]["200"]}

    assert _changed(to_202) == []
