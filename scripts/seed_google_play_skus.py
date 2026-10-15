"""Mirror published Stripe (channel 'web') SKUs as 'google_play' SKUs (SPEC-194). Dry-run by default.

  uv run python scripts/seed_google_play_skus.py            # prints the plan
  uv run python scripts/seed_google_play_skus.py --apply    # inserts (idempotent, ON CONFLICT DO NOTHING)

Play product id = sku_id lowercased, [^a-z0-9_.] -> '_' (documented; must match Play Console, SPEC-198).
Only pricing versions whose channel_fees already contain 'google_play' are mirrored (R9: the fee tier
must be confirmed before production). purchase_skus rows are immutable; re-running never changes them.
"""
from __future__ import annotations

import sys
from pathlib import Path as _P

sys.path.insert(0, str(_P(__file__).resolve().parents[1]))

import argparse
import json
import re
from typing import Sequence

PRODUCT_RE = re.compile(r"[a-z0-9][a-z0-9_.]{0,127}")


def product_id_for(sku_id: str) -> str:
    pid = re.sub(r"[^a-z0-9_.]", "_", sku_id.lower()).strip("_.")
    if not PRODUCT_RE.fullmatch(pid):
        raise ValueError(f"sku sem product id Play valido: {sku_id}")
    return pid


def plan(web_rows: Sequence[dict], existing_products: set[str]) -> list[dict]:
    out = []
    for r in web_rows:
        if "google_play" not in (r.get("channel_fees") or {}):
            out.append({"skip": r["sku_id"], "reason": "pricing_version_without_google_play_fee"})
            continue
        pid = product_id_for(r["sku_id"])
        out.append({"sku_id": f"gp_{r['sku_id']}"[:120], "pricing_version_id": r["pricing_version_id"],
                    "channel": "google_play", "store_product_id": pid, "gross_brl": str(r["gross_brl"]),
                    "shard_milli": int(r["shard_milli"]), "exists": pid in existing_products})
    return out


def main(argv: Sequence[str] | None = None, *, pool=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    if pool is None:
        from infrastructure.runtime import get_runtime
        pool = get_runtime().game_store.pool
    with pool.connection() as db:
        web = [dict(r) for r in db.execute(
            "select s.sku_id,s.pricing_version_id,s.gross_brl,s.shard_milli,v.channel_fees "
            "from app.purchase_skus s join app.pricing_versions v on v.version_id=s.pricing_version_id "
            "where s.channel='web' order by s.sku_id").fetchall()]
        have = {r["store_product_id"] for r in db.execute(
            "select store_product_id from app.purchase_skus where channel='google_play'").fetchall()}
        rows = plan(web, have)
        print(json.dumps({"apply": args.apply, "plan": rows}, indent=2))
        if args.apply:
            with db.transaction():
                for r in rows:
                    if "skip" in r or r["exists"]:
                        continue
                    db.execute("insert into app.purchase_skus (sku_id,pricing_version_id,channel,"
                               "store_product_id,gross_brl,shard_milli) values (%s,%s,%s,%s,%s,%s) "
                               "on conflict do nothing",
                               (r["sku_id"], r["pricing_version_id"], r["channel"], r["store_product_id"],
                                r["gross_brl"], r["shard_milli"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
