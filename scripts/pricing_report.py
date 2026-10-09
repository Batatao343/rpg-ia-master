"""Offline, non-commercial pricing calculator for SPEC-183.

Never accepts a client purchase request or writes a wallet. Inputs are local
simulation files; published SKU values must instead come from the DB catalog.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

from services.shard_pricing import (
    PricingUnavailable, PurchaseSku, contribution_report, quote_purchase,
    quote_usage, version_from_record,
)
from services.usage_metering import UsageEvent


def _encode(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(type(value).__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulação local, sem oferta ou cobrança")
    parser.add_argument("--version-json", required=True, type=Path)
    parser.add_argument("--sku-json", required=True, type=Path)
    parser.add_argument("--usage-usd", help="custo sintético reportado, somente simulação")
    parser.add_argument("--fixed-infra-brl", default="0")
    parser.add_argument("--at", help="instante ISO-8601 para teste de frescor")
    args = parser.parse_args(argv)
    try:
        version = version_from_record(json.loads(args.version_json.read_text(encoding="utf-8")))
        sku_data = json.loads(args.sku_json.read_text(encoding="utf-8"))
        if not isinstance(sku_data["gross_brl"], str):
            raise PricingUnavailable("preço do SKU precisa ser texto decimal")
        sku = PurchaseSku(
            sku_data["sku_id"], sku_data["channel"],
            Decimal(sku_data["gross_brl"]), sku_data["shard_milli"],
            sku_data["pricing_version"],
        )
        at = datetime.fromisoformat(args.at.replace("Z", "+00:00")) if args.at else datetime.now(timezone.utc)
        purchase = quote_purchase(sku, version, at=at)
        report = contribution_report([purchase], fixed_infra_brl=Decimal(args.fixed_infra_brl))
        result: dict = {"simulation_only": True, "purchase": asdict(purchase), "report": report}
        if args.usage_usd is not None:
            simulated = UsageEvent(
                event_id=uuid4(), operation_id=uuid4(), component="cli-simulation",
                attempt_ordinal=0, category="other", provider="simulated", model="simulated",
                outcome="success", input_units=None, output_units=None, cached_units=None,
                audio_units=None, image_units=None, cost_usd=Decimal(args.usage_usd),
                cost_basis="provider_reported", pricing_version="cli-simulation",
                billing_exact=True,
            )
            result["usage_assumption"] = "synthetic provider-reported cost; not billable evidence"
            result["usage"] = asdict(quote_usage([simulated], version, at=at))
    except (PricingUnavailable, ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"pricing unavailable: {type(exc).__name__}: {exc}\n")
    print(json.dumps(result, default=_encode, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
