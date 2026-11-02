"""SPEC-363 R5: preflight (somente leitura) do retrato pago no staging.

  uv run python scripts/staging/art_preflight.py --dsn-env RPG_STAGING_DB_URL --env-file .env.staging

Imprime JSON {switch_image, switch_actor, pricing_fresh, dynamic_art_env, creature_art_env,
price_estilhas, ok, causa} e sai com codigo != 0 quando a oferta `retrato.gerar` nao pode ser honrada.
Nunca imprime valor de env (so se a variavel esta ligada).
"""

from __future__ import annotations

import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[2]))

import argparse
import json
from collections.abc import Mapping, Sequence

_TRUE = {"1", "true", "yes", "on"}


def evaluate(
    *,
    switches: Mapping[str, bool],
    audit: Sequence[Mapping],
    pricing_fresh: bool,
    env: Mapping[str, str],
    price_estilhas: int | None,
) -> dict:
    """Pure core (testable with an in-memory store)."""
    switch_image = bool(switches.get("image_generation", True))
    last = next((r for r in audit if r.get("key") == "image_generation"), None)
    actor = (last or {}).get("actor_id") if not switch_image else None
    dynamic = str(env.get("RPG_DYNAMIC_ART_ENABLED", "")).strip().lower() in _TRUE
    creature = str(env.get("RPG_CREATURE_ART", "")).strip().lower() in {"on", *(_TRUE - {"on"})}
    causa: str | None = None
    if "image_generation" in {k.strip() for k in str(env.get("RPG_KILL_SWITCHES_OFF", "")).split(",")}:
        causa = "env_kill_switches_off"
    elif not switch_image:
        causa = "daily_cap" if str(actor or "").startswith("system:finops") else (
            "drill" if str(actor or "").startswith("drill") else "manual_off"
        )
    elif not pricing_fresh:
        causa = "pricing_stale"
    elif not dynamic:
        causa = "dynamic_art_env_off"
    elif not creature:
        causa = "creature_art_env_off"
    elif not price_estilhas:
        causa = "no_price"
    return {
        "switch_image": switch_image,
        "switch_actor": actor,
        "pricing_fresh": pricing_fresh,
        "dynamic_art_env": dynamic,
        "creature_art_env": creature,
        "price_estilhas": price_estilhas,
        "ok": causa is None,
        "causa": causa,
    }


def main(argv: Sequence[str] | None = None, *, store=None, price: int | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dsn-env", default="RPG_STAGING_DB_URL")
    p.add_argument("--env-file", default=".env.staging")
    args = p.parse_args(argv)
    import os

    from dotenv import dotenv_values

    env_file = dict(dotenv_values(args.env_file)) if _P(args.env_file).exists() else {}
    env = {**env_file, **os.environ}
    if store is None:
        dsn = env.get(args.dsn_env) or ""
        if not dsn:
            print(f"error: {args.dsn_env} is empty", file=sys.stderr)
            return 2
        from infrastructure.kill_switch_store import PostgresSwitchStore
        from infrastructure.postgres import PostgresPool

        pool = PostgresPool(dsn, max_size=2)
        store = PostgresSwitchStore(pool)
        try:
            from services.image_quotes import ImageQuoteRepository

            milli = ImageQuoteRepository(pool).peek_ceiling("monster")
            price = -(-int(milli) // 1000) if milli else None
        except Exception:  # noqa: BLE001 - leitura best-effort; None => causa no_price
            price = None
    from services.finops_alerts import require_paid_effect
    from services.shard_pricing import PricingUnavailable

    try:
        require_paid_effect("image")
        fresh = True
    except PricingUnavailable:
        fresh = False
    report = evaluate(
        switches=store.load(), audit=store.audit(20), pricing_fresh=fresh, env=env, price_estilhas=price
    )
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
