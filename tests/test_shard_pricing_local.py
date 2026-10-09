"""SPEC-183 optional local Postgres storage and authority checks."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import uuid4

import pytest

from infrastructure.pricing_catalog import quote_published_sku
from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
from services.usage_metering import RATE_CARD_VERSION


pytestmark = pytest.mark.infra_local


class _Rollback(Exception):
    pass


def test_catalog_roundtrip_immutable_and_backend_read_only() -> None:
    psycopg = pytest.importorskip("psycopg")
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb

    dsn = os.getenv("RPG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("RPG_TEST_DATABASE_URL ausente")
    version_id = "simulation-" + str(uuid4())
    sku_id = "simulation-" + str(uuid4())
    now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)
    card_observed = INSTALLED_RATE_CARD_OBSERVED_AT
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        if connection.execute("select to_regclass('app.pricing_versions') as table_name").fetchone()["table_name"] is None:
            pytest.skip("migration SPEC-183 não aplicada")
        with pytest.raises(_Rollback):
            with connection.transaction():
                connection.execute(
                    """insert into app.pricing_versions
                    (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,
                     fx_observed_at,fx_max_age_seconds,fx_buffer_rate,
                     rate_card_version,rate_card_sha256,rate_card_source,rate_card_observed_at,
                     rate_card_max_age_seconds,channel_fees)
                    values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (version_id, "0.03", "5", "simulated FX", now, 86400, "0.10",
                     RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256, "installed rate card", card_observed, 86400,
                     Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"},
                            "play": {"percentage": "0.10", "fixed_brl": "0"}})),
                )
                connection.execute(
                    """insert into app.purchase_skus
                    (sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli)
                    values (%s,%s,'web',%s,10.50,311)""",
                    (sku_id, version_id, sku_id),
                )
                quote = quote_published_sku(connection, sku_id, at=now)
                assert quote.pricing_version == version_id
                assert quote.gross_brl == 10.50
                assert quote.shard_milli_granted == 311
                with pytest.raises(psycopg.Error):
                    with connection.transaction():
                        connection.execute(
                            "update app.pricing_versions set fx_usd_brl=6 where version_id=%s",
                            (version_id,),
                        )
                with pytest.raises(psycopg.Error):
                    with connection.transaction():
                        connection.execute("delete from app.purchase_skus where sku_id=%s", (sku_id,))
                with pytest.raises(psycopg.Error):
                    with connection.transaction():
                        connection.execute(
                            """insert into app.pricing_versions
                            (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,
                             fx_observed_at,fx_max_age_seconds,fx_buffer_rate,
                             rate_card_version,rate_card_sha256,rate_card_source,rate_card_observed_at,
                             rate_card_max_age_seconds,channel_fees)
                            select %s,shard_budget_unit_brl,fx_usd_brl,fx_source,
                             fx_observed_at,fx_max_age_seconds,fx_buffer_rate,
                             rate_card_version,rate_card_sha256,rate_card_source,rate_card_observed_at,
                             rate_card_max_age_seconds,
                             '{"web":{"percentage":"1.2","fixed_brl":"0"}}'::jsonb
                            from app.pricing_versions where version_id=%s""",
                            (version_id + "-bad", version_id),
                        )
                with pytest.raises(psycopg.Error):
                    with connection.transaction():
                        connection.execute("set local role rpg_api")
                        assert connection.execute(
                            "select sku_id from app.purchase_skus where sku_id=%s", (sku_id,),
                        ).fetchone()["sku_id"] == sku_id
                        connection.execute(
                            "insert into app.purchase_skus "
                            "(sku_id,pricing_version_id,channel,store_product_id,gross_brl,shard_milli) "
                            "values (%s,%s,'web',%s,10.50,311)",
                            (sku_id + "-other", version_id, sku_id + "-other"),
                        )
                raise _Rollback
