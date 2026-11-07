"""Ledger errors the API maps to HTTP 409 (importable without the write module)."""


class ConflictError(Exception):
    """Optimistic-concurrency or business-rule conflict (the API answers 409)."""
