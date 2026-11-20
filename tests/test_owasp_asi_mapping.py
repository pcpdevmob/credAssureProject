"""Plan v3.4 P8.2 exit check (scope #66): every OWASP LLM (2026) and ASI (2026) row in
docs/security/owasp-asi-mapping.md exists and names at least one test that exists."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPPING = ROOT / "docs" / "security" / "owasp-asi-mapping.md"
REF = re.compile(r"`([\w./-]+\.py)::(\w+)`")
IDS = [f"LLM{i:02d}" for i in range(1, 11)] + [f"ASI{i:02d}" for i in range(1, 11)]


def _rows() -> dict[str, list[tuple[str, str]]]:
    rows: dict[str, list[tuple[str, str]]] = {}
    for line in MAPPING.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*((?:LLM|ASI)\d\d)\b", line)
        if m:
            rows[m.group(1)] = REF.findall(line)
    return rows


def test_scope66_every_owasp_and_asi_risk_has_a_row_with_a_test() -> None:
    rows = _rows()
    assert sorted(rows) == sorted(IDS)
    assert [rid for rid, refs in rows.items() if not refs] == []


def test_scope66_every_named_test_exists() -> None:
    missing = []
    refs = set(REF.findall(MAPPING.read_text(encoding="utf-8")))
    for path, name in sorted(refs):
        file = ROOT / path
        if not file.is_file() or not re.search(rf"^def {name}\(", file.read_text(), re.M):
            missing.append(f"{path}::{name}")
    assert missing == []
