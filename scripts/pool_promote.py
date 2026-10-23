"""Roda o job de promoção do pool compartilhado no perfil legacy (SPEC-297 R3).

Uso: bash scripts/dev/py.sh scripts/pool_promote.py
Nunca roda dentro do turno; com RPG_SHARED_POOL=off não faz nada.
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from services.shared_pool import get_store, pool_mode  # noqa: E402
from workers.shared_pool_jobs import promote_due_job  # noqa: E402


def main() -> int:
    if pool_mode() == "off":
        print(json.dumps({"skipped": "RPG_SHARED_POOL=off"}))
        return 0
    print(json.dumps(promote_due_job(get_store())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
