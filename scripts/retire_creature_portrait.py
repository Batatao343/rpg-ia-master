"""SPEC-352 R13: retira um retrato de criatura compartilhado (moderação pelo operador).

Passa `ready` -> `retired`, apaga os objetos compartilhados e libera a chave para uma nova cotação.
Só `rpg_admin` (o runtime de sistema). Sem UI. Uso:

    bash scripts/dev/py.sh scripts/retire_creature_portrait.py "tipo:enemy_goblin" --reason "imagem imprópria"
"""

from __future__ import annotations

import argparse
import json

from infrastructure.runtime import build_runtime
from services.creature_portraits import PostgresPortraitRegistry


def retire(runtime, portrait_key: str, reason: str) -> dict:
    registry = PostgresPortraitRegistry(runtime.game_store.pool)
    keys = registry.retire(portrait_key=portrait_key, reason=reason)
    shared = getattr(runtime, "shared_blob_store", None)
    deleted = 0
    failed: list[str] = []
    for key in keys:
        if shared is not None and shared.delete(key):
            deleted += 1
        else:
            failed.append(key)
    return {
        "portrait_key": portrait_key,
        "status": "retired",
        "objects_deleted": deleted,
        "objects_failed": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("portrait_key")
    parser.add_argument("--reason", required=True, help="motivo da retirada (vai para o registro)")
    args = parser.parse_args()
    if not args.reason.strip():
        parser.error("--reason não pode ser vazio")
    result = retire(build_runtime(), args.portrait_key, args.reason.strip())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not result["objects_failed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
