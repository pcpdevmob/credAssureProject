"""Versioned input schemas. ``schema_version`` is ``1.0`` on every model."""

from credassure.core.schemas.case_files import (
    ConfirmedMitigation,
    CostRow,
    CreditLine,
    InventoryRow,
    OpeningPosition,
    OrderFile,
    PayableRow,
    ReceiptRow,
    ReceivableRow,
)
from credassure.core.schemas.hr import HrProfile, TrainingRecord
from credassure.core.schemas.kfs import KfsFee, KfsMetadata
from credassure.core.schemas.offer import Guarantee, Insurance, Offer, OfferFee, Repayment

__all__ = [
    "ConfirmedMitigation",
    "CostRow",
    "CreditLine",
    "Guarantee",
    "HrProfile",
    "Insurance",
    "InventoryRow",
    "KfsFee",
    "KfsMetadata",
    "Offer",
    "OfferFee",
    "OpeningPosition",
    "OrderFile",
    "PayableRow",
    "ReceiptRow",
    "ReceivableRow",
    "Repayment",
    "TrainingRecord",
]
