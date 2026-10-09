"""Backend-only read of immutable published pricing records.

Publishing commercial data is an operator migration, never a client endpoint.
No wallet writes happen here; SPEC-184 will use this catalog and its version IDs.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from services.shard_pricing import (
    PricingUnavailable, PurchaseQuote, PurchaseSku, quote_purchase, version_from_record,
)


def quote_published_sku(connection, sku_id: str, *, at: datetime) -> PurchaseQuote:
    """Only the SKU identifier is supplied by a caller; price comes from SQL."""
    row = connection.execute(
        """select sku_id,channel,gross_brl,shard_milli,pricing_version_id
        from app.purchase_skus where sku_id=%s""", (sku_id,),
    ).fetchone()
    if row is None:
        raise PricingUnavailable("SKU não publicado")
    version = connection.execute(
        "select * from app.pricing_versions where version_id=%s",
        (row["pricing_version_id"],),
    ).fetchone()
    if version is None:
        raise PricingUnavailable("versão de pricing ausente")
    sku = PurchaseSku(
        row["sku_id"], row["channel"], Decimal(row["gross_brl"]),
        row["shard_milli"], row["pricing_version_id"],
    )
    return quote_purchase(sku, version_from_record(version), at=at)
