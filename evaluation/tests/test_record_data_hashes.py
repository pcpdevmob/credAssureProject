"""Scope #13 / #37 (K11): every run record and release bundle names each frozen data version it used.

Since ADR 0037 the lender simulator reads `data/frozen/v2/lender_scripts`, so a record that hashes only
v1 cannot say which lender replies produced a negotiation result."""

import hashlib
import sys

from credassure.evaluation import record
from credassure.evaluation.gold.data import REPO

sys.path.insert(0, str(REPO / "scripts"))
import release

SUMS = ("data/frozen/v1/SHA256SUMS", "data/frozen/v2/SHA256SUMS")


def _sha(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def test_scope13_data_hashes_cover_every_frozen_version() -> None:
    assert record.data_hashes() == {rel: _sha(rel) for rel in SUMS}


def test_scope13_run_record_keeps_data_hash_v1_and_adds_every_version() -> None:
    rec = record.run_record("m", "http://localhost:11434/v1", {}, 1, "s1")
    assert rec["data_hash"] == _sha("data/frozen/v1/SHA256SUMS")  # unchanged meaning
    assert rec["data_hashes"] == {rel: _sha(rel) for rel in SUMS}


def test_scope37_release_hashes_the_v2_data_manifest() -> None:
    assert set(SUMS) <= set(release.HASHED)
