"""Synthetic image quote funding for the ephemeral local audit stack only."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from scripts.start_local_api import _supabase_status


def fund_audit_portrait(user_id: UUID) -> None:
    """Publish local test pricing and credit one synthetic audit account."""
    from psycopg.types.json import Jsonb
    from infrastructure.contracts import Principal
    from infrastructure.postgres import PostgresPool
    from infrastructure.wallet import PostgresWallet
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
    from services.usage_metering import RATE_CARD_VERSION
    status = _supabase_status()
    db_url = status["DB_URL"]
    parsed = urlsplit(db_url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != 55322:
        raise RuntimeError("audit image finance requires local Postgres on port 55322")
    profile_id = os.environ["RPG_IMAGE_PRICE_PROFILE"]
    if not profile_id.startswith("audit-image-"):
        raise RuntimeError("audit image pricing profile must be synthetic")
    version_id = f"{profile_id}-version"
    now = datetime.now(timezone.utc)
    pool = PostgresPool(db_url)
    try:
        with pool.connection() as connection, connection.transaction():
            connection.execute("""insert into app.pricing_versions
                (version_id,shard_budget_unit_brl,fx_usd_brl,fx_source,fx_observed_at,
                 fx_max_age_seconds,fx_buffer_rate,rate_card_version,rate_card_sha256,
                 rate_card_source,rate_card_observed_at,rate_card_max_age_seconds,channel_fees)
                values (%s,0.03,5,'synthetic local audit',%s,864000,0.1,%s,%s,
                        'installed local rate card',%s,864000,%s)
                on conflict (version_id) do nothing""",
                (version_id, now, RATE_CARD_VERSION, INSTALLED_RATE_CARD_SHA256,
                 INSTALLED_RATE_CARD_OBSERVED_AT,
                 Jsonb({"web": {"percentage": "0.04", "fixed_brl": "0.20"}})))
            connection.execute("""insert into app.image_price_profiles
                (profile_id,pricing_version_id,model,size,max_provider_usd,source,expires_at)
                values (%s,%s,'gpt-image-2-2026-04-21','1024x1536',0.02,
                        'synthetic local audit only',%s)
                on conflict (profile_id) do nothing""",
                (profile_id, version_id, now + timedelta(hours=1)))
        PostgresWallet(pool).adjust_admin(
            Principal(user_id, "local-audit", str(user_id)),
            adjustment_id=str(uuid4()), signed_milli=1000,
            actor_id=uuid4(), reason="synthetic local image audit credit",
        )
    finally:
        pool.close()
