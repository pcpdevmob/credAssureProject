"""VER-02, DATA_SPEC §8.7 (S24): all 12 planted bad citations are blocked with the expected code,
against the real indexed corpus (skipped when `make ingest` has not built var/corpus.db)."""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from credassure.agents.critic.verify import verify
from credassure.retrieval.search import Filters, resolve

ROOT = Path(__file__).resolve().parents[3]
DB = ROOT / "var" / "corpus.db"
PLANTS = [json.loads(line) for line in (ROOT / "evaluation/fixtures/v1/bad_citations.jsonl").open()]


@pytest.fixture(scope="module")
def known() -> dict[str, str | None]:
    manifest = yaml.safe_load((ROOT / "data/corpus/manifest.yaml").read_text(encoding="utf-8"))
    return {d["doc_id"]: d.get("superseded_by") for d in manifest["documents"]}


@pytest.mark.skipif(not DB.exists(), reason="corpus not ingested (make ingest)")
@pytest.mark.parametrize("plant", PLANTS, ids=[p["id"] for p in PLANTS])
def test_VER02_S24_every_planted_bad_citation_is_blocked(
    plant: dict[str, str], known: dict[str, str | None]
) -> None:

    def resolver(ids: list[str]) -> dict[str, tuple[str, str]]:
        return resolve(
            DB,
            ids,
            case_id=plant["case_id"],
            tenant_id="demo",
            filters=Filters(as_of=date(2026, 11, 15)),
            known=known,
        )

    found = verify(plant["draft"], facts={}, resolve=resolver)
    assert [f.code.value for f in found] == [plant["expected"]], (plant["defect"], found)
