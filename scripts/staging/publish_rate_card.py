"""SPEC-409 R1.5: publish the renewed LLM rate card to staging (append-only rows).

``app.pricing_versions`` rows are immutable and pinned to the card's sha256 + ``observed_at``;
renewing ``data/pricing/rate_card_*.json`` therefore needs a NEW version id, a SKU that points at
it and new ``image_price_profiles`` (copied from the previous profiles, so model/size/ceiling are
never invented). Nothing runs without ``--confirm-staging`` and a DSN that matches the ref;
``--dry-run`` only prints the plan. Production is out of scope.
"""

from __future__ import annotations

import argparse
import json
import os

from scripts.staging import common
from scripts.staging.synthetic_data import WALLET_PRICING, WALLET_SKU, seed_wallet_prereqs

DEFAULT_PRICING_ID = WALLET_PRICING
SOURCE_PROFILES = {"portrait": "staging-326-portrait", "scene": "staging-326-scene"}
PROFILE_SOURCE = "SPEC-409 renewal of the SPEC-326 staging profile (same model/size/ceiling)"
_PROFILE_SQL = """insert into app.image_price_profiles
  (profile_id, pricing_version_id, model, size, max_provider_usd, source, expires_at)
select %s, %s, model, size, max_provider_usd, %s, now() + interval '90 days'
from app.image_price_profiles where profile_id = %s
on conflict (profile_id) do nothing"""


def profile_ids(pricing_id: str) -> dict[str, str]:
    return {kind: f"{pricing_id}-{kind}" for kind in SOURCE_PROFILES}


def profile_statements(pricing_id: str) -> list[tuple[str, tuple[str, ...]]]:
    ids = profile_ids(pricing_id)
    return [
        (_PROFILE_SQL, (ids[kind], pricing_id, PROFILE_SOURCE, old))
        for kind, old in SOURCE_PROFILES.items()
    ]


def describe_plan(pricing_id: str) -> dict:
    from services.shard_pricing import INSTALLED_RATE_CARD_OBSERVED_AT, INSTALLED_RATE_CARD_SHA256
    from services.usage_metering import RATE_CARD_VERSION

    return {
        "pricing_version_id": pricing_id,
        "sku_id": WALLET_SKU,
        "rate_card_version": RATE_CARD_VERSION,
        "rate_card_sha256": INSTALLED_RATE_CARD_SHA256,
        "rate_card_observed_at": INSTALLED_RATE_CARD_OBSERVED_AT.isoformat(),
        "image_price_profiles": profile_ids(pricing_id),
        "copied_from": SOURCE_PROFILES,
    }


def publish(dsn: str, pricing_id: str) -> dict:
    import psycopg

    seed_wallet_prereqs(dsn, pricing_id=pricing_id)
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as conn:
        for sql, params in profile_statements(pricing_id):
            conn.execute(sql, params)
        rows = conn.execute(
            "select profile_id, pricing_version_id, model, expires_at"
            " from app.image_price_profiles where pricing_version_id = %s order by 1",
            (pricing_id,),
        ).fetchall()
    return {**describe_plan(pricing_id), "profiles_in_db": [list(map(str, r)) for r in rows]}


def main(argv: list[str] | None = None) -> int:
    common.load_dotenv_quietly()
    p = argparse.ArgumentParser(description="Publish the renewed rate card to staging (SPEC-409)")
    p.add_argument("--confirm-staging", metavar="REF")
    p.add_argument("--pricing-id", default=DEFAULT_PRICING_ID)
    p.add_argument("--dry-run", action="store_true", help="print the plan; touch nothing")
    p.add_argument("--out")
    a = p.parse_args(argv)
    if a.dry_run:
        print(json.dumps(describe_plan(a.pricing_id), indent=2))
        return 0
    ref = common.require_staging(a.confirm_staging)
    common.assert_ref_in(ref, RPG_STAGING_DB_URL=common.env_required("RPG_STAGING_DB_URL"))
    result = publish(os.environ["RPG_STAGING_DB_URL"], a.pricing_id)
    print(common.write_evidence("publish_rate_card", {"project_ref": ref, **result}, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
