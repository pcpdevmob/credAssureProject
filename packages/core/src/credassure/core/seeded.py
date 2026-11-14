"""Seeded synthetic cases (DATA_SPEC §2): they live under their own tenant, and live case IDs are
allocated after the highest seeded one, so a new case never shares an ID with a seeded case or
its synthetic KFS documents (BR-14, SUP-08)."""

SEED_TENANT = "demo"
# Highest seeded case number per year: data/frozen/v1/cases/CA-2026-0001 .. CA-2026-0015.
# A ledger test fails if the frozen data and this table drift apart.
SEEDED_CASE_MAX: dict[int, int] = {2026: 15}
