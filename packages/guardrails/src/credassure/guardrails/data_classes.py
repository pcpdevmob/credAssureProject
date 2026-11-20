"""Data classes C1 to C4 (ADR 0030 §1, scope #59).

C1 public (corpus) · C2 internal (synthetic policies, prompts) · C3 confidential (case financials,
offers, KFS: the active case only; traces carry ledger references, not values) · C4 restricted
(personal identifiers: never to the model, logs or traces). Every PII kind the redactor knows has a
class, and an unknown kind is treated as C4 (fail closed).
"""

from enum import StrEnum


class DataClass(StrEnum):
    C1 = "C1_public"
    C2 = "C2_internal"
    C3 = "C3_confidential"
    C4 = "C4_restricted"


PII_CLASS: dict[str, DataClass] = {
    "AADHAAR": DataClass.C4,
    "PAN": DataClass.C4,
    "ACCOUNT": DataClass.C4,
    "CARD": DataClass.C4,
    "PHONE": DataClass.C4,
    "EMAIL": DataClass.C4,
    "UPI": DataClass.C4,
    "IFSC": DataClass.C3,  # a branch code, not a person; masked in free text all the same
    "GSTIN": DataClass.C3,  # a business identifier
    "UDYAM": DataClass.C3,  # a business identifier
}

COLLECTION_CLASS: dict[str, DataClass] = {
    "public": DataClass.C1,
    "policy": DataClass.C2,
    "kfs": DataClass.C3,
}


def of_pii(kind: str) -> DataClass:
    return PII_CLASS.get(kind, DataClass.C4)


def of_collection(collection: str) -> DataClass:
    return COLLECTION_CLASS.get(collection, DataClass.C3)  # unknown corpus text: confidential
