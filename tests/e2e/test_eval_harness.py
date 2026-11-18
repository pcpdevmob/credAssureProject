"""P7 harness mechanics (Phase 11, API-01): one item of each non-copilot kind through the API with
FakeLLM scores against the frozen gold. Not a score of the system: the model is fake."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient

from credassure.engines.routing import route
from credassure.evaluation import harness

PASSWORD = "fixture-password-123"  # tests/e2e/conftest.py
IDS = {"T026", "T036", "T051", "T066", "T071", "T072", "T077", "T085", "T093", "T099"}


def test_scope15_P7_harness_scores_items_through_the_api(
    make_client: Callable[..., tuple[TestClient, Any]],
) -> None:
    client, _ = make_client(True, rate_limit="100000/minute")
    items = [i for i in harness.load() if i["id"] in IDS]
    h = harness.Harness(client, PASSWORD, route_fn=lambda a, r: str(route(Decimal(a), r)))  # type: ignore[arg-type]
    rows = h.run(items)
    assert {r.id: (r.passed, r.detail) for r in rows if not r.passed} == {}
    s = harness.summary(rows)
    assert s["passed"] == len(IDS) and s["taxonomy"] == {}
