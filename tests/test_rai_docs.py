"""P10 (scope #69): the system card and threat model exist, cover the plan's outline and every test
they name exists. Mirrors tests/test_owasp_asi_mapping.py for the OWASP/ASI page."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = re.compile(r"`([\w./-]+\.py)::(\w+)`")
SUTRAS = (
    "Trust is the Foundation",
    "People First",
    "Innovation over Restraint",
    "Fairness and Equity",
    "Accountability",
    "Understandable by Design",
    "Safety, Resilience and Sustainability",
)


def _missing(doc: Path) -> list[str]:
    out = []
    for path, name in sorted(set(REF.findall(doc.read_text(encoding="utf-8")))):
        f = ROOT / path
        if not f.is_file() or not re.search(rf"^def {name}\(", f.read_text(), re.M):
            out.append(f"{path}::{name}")
    return out


def test_scope69_threat_model_names_only_tests_that_exist() -> None:
    doc = ROOT / "docs/THREAT_MODEL.md"
    assert len(REF.findall(doc.read_text())) >= 30
    assert _missing(doc) == []


def test_scope69_system_card_has_the_outline_sutras_and_dpdp_gap() -> None:
    doc = ROOT / "docs/SYSTEM_CARD.md"
    text = doc.read_text(encoding="utf-8")
    for heading in (
        "Intended use", "Out-of-scope", "Models", "Data provenance", "Human-in-the-loop",
        "Refusal policy", "Guardrail", "OWASP", "Evaluation", "Failure taxonomy",
        "Limitations", "Sutra", "DPDP", "Contact",
    ):
        assert re.search(rf"^##+ .*{heading}", text, re.M | re.I), heading
    for sutra in SUTRAS:
        assert sutra in text, sutra
    assert _missing(doc) == []
