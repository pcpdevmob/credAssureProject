"""Hash rule for the audit chain (OBJ-08): hash = sha256(prev_hash || canonical JSON)."""

import hashlib
import json
from typing import Any

GENESIS = "0" * 64


def canonical(payload: dict[str, Any]) -> dict[str, Any]:
    """The JSON round-trip of a payload, so the stored and hashed forms are identical."""
    result: dict[str, Any] = json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    return result


def row_hash(prev_hash: str, row: dict[str, Any]) -> str:
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev_hash + canonical).encode("utf-8")).hexdigest()


def hashed_fields(
    seq: int,
    tenant_id: str,
    case_id: str | None,
    actor: str,
    event_type: str,
    payload: dict[str, Any],
    ts: str,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "actor": actor,
        "event_type": event_type,
        "payload": payload,
        "ts": ts,
    }
