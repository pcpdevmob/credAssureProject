"""Tool allowlist loaded from agents/registry.yaml (scope #24).

``yaml.safe_load`` only. A forbidden tool or collection raises ``RegistryError``
with a stable code from the error catalogue. This module does not run tools.
"""

from pathlib import Path
from typing import Any, cast

import yaml

from credassure.core.enums import AgentName
from credassure.core.errors import ApiErrorCode

TOOL_NAMES: tuple[str, ...] = (
    "get_hr_profile",
    "evaluate_onboarding_rules",
    "validate_case_files",
    "compute_cash_table",
    "compute_recommendation",
    "load_offers",
    "audit_offer",
    "price_offer",
    "check_affordability",
    "rank_offers",
    "lender_send_template",
    "search_knowledge",
    "search_regulations",
    "search_policies",
    "get_case_facts",
    "explain_blocker",
    "verify_claims",
    "route_proposal",
)


class RegistryError(Exception):
    """The caller may not use this tool or collection."""

    def __init__(self, code: ApiErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def authorize(
    agent: AgentName | str,
    tool: str,
    *,
    collection: str | None = None,
    case_id: str | None = None,
) -> None:
    """Raise ``RegistryError`` unless ``agent`` may call ``tool`` on ``collection``."""
    name = agent.value if isinstance(agent, AgentName) else agent
    allow = _allow(tool)
    rule = allow.get(name)
    if rule is None:
        raise RegistryError(ApiErrorCode.TOOL_NOT_ALLOWED)
    collections = rule.get("collections")
    if collections is None:
        if collection is not None:
            raise RegistryError(ApiErrorCode.COLLECTION_NOT_ALLOWED)
        return
    if collection is None or collection not in collections:
        raise RegistryError(ApiErrorCode.COLLECTION_NOT_ALLOWED)
    same_case = rule.get("same_case_collections") or []
    if collection in same_case and not case_id:
        raise RegistryError(ApiErrorCode.CASE_REQUIRED)


def authorize_fact(agent: AgentName | str, key: str, *, write: bool = False) -> None:
    """Raise ``RegistryError`` unless ``agent`` may read (or, with ``write``, write) fact ``key``.

    Deny by default: an agent without a ``ledger_prefixes`` entry may touch no fact.
    ``ledger_read_prefixes`` adds keys it may only read.
    """
    name = agent.value if isinstance(agent, AgentName) else agent
    loaded = _load()
    prefixes = loaded.get("ledger_prefixes") or {}
    reads = {} if write else loaded.get("ledger_read_prefixes") or {}
    if not isinstance(prefixes, dict) or not isinstance(reads, dict):
        raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
    allowed = [*(prefixes.get(name) or []), *(reads.get(name) or [])]
    if not any(key.startswith(str(p)) for p in allowed):
        raise RegistryError(ApiErrorCode.TOOL_NOT_ALLOWED)


def _allow(tool: str) -> dict[str, dict[str, list[str]]]:
    spec = _tools().get(tool)
    if not isinstance(spec, dict):
        raise RegistryError(ApiErrorCode.TOOL_NOT_ALLOWED)
    raw = spec.get("allow")
    if not isinstance(raw, dict):
        raise RegistryError(ApiErrorCode.TOOL_NOT_ALLOWED)
    return rules_from_allow(raw)


def rules_from_allow(raw: object) -> dict[str, dict[str, list[str]]]:
    """Turn one tool's ``allow`` map into rules. A bad shape fails closed."""
    if not isinstance(raw, dict):
        raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
    parsed: dict[str, dict[str, list[str]]] = {}
    for agent, rule in raw.items():
        if not isinstance(rule, dict):
            raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
        collections = rule.get("collections")
        if collections is None:
            parsed[str(agent)] = {}
            continue
        if not isinstance(collections, list):
            raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
        same = rule.get("same_case_collections")
        if same is None:
            same_list: list[object] = []
        elif isinstance(same, list):
            same_list = same
        else:
            raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
        parsed[str(agent)] = {
            "collections": [str(item) for item in collections],
            "same_case_collections": [str(item) for item in same_list],
        }
    return parsed


def _load() -> dict[str, Any]:
    with _registry_file().open(encoding="utf-8") as handle:
        loaded: Any = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
    return cast(dict[str, Any], loaded)


def _tools() -> dict[str, Any]:
    tools = _load().get("tools")
    if not isinstance(tools, dict):
        raise RegistryError(ApiErrorCode.VALIDATION_FAILED)
    return cast(dict[str, Any], tools)


def _registry_file() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "agents" / "registry.yaml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("agents/registry.yaml")
