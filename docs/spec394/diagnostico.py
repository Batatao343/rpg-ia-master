"""SPEC-394 R3: braco de diagnostico. Reverte, so neste processo, o `if not _can_act(actor): return`
da SPEC-387 (1e208ac9) em _resolve_actor_turn_inner e mede os ids. Nao e criterio.

Uso: bash scripts/dev/py.sh docs/spec394/diagnostico.py --patch|--sem-patch ids...
"""

from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
_s = importlib.util.spec_from_file_location("arena394", ROOT / "scripts/bestiario/arena.py")
arena = importlib.util.module_from_spec(_s)
_s.loader.exec_module(arena)  # type: ignore[union-attr]

from services import conflict_orchestrator as orch  # noqa: E402


def reverter_387() -> None:
    src = inspect.getsource(orch._resolve_actor_turn_inner)
    novo, n = re.subn(
        r"\n        if not _can_act\(actor\):  # SPEC-387:[^\n]*\n[^\n]*\n            return\n",
        "\n",
        src,
    )
    assert n == 1, n
    exec(compile(novo, "<patched>", "exec"), orch.__dict__)


def main() -> None:
    patch = sys.argv[1] == "--patch"
    if patch:
        reverter_387()
    if sys.argv[1] == "--abissal-sem-fuga":  # braco 2: tira o `muito_ferido: flee` do e208f189
        from services import tactical_profile as tp

        tp._ENEMY_ARCHETYPE_ACTIONS["abissal"] = {"sempre": "attack"}
    best = __import__("json").loads((ROOT / "data/bestiary.json").read_text("utf-8"))
    for bid in sys.argv[2:]:
        cells = arena.medir(bid, best[bid]["categoria"], 40, ["off", "on"])
        print("PATCH" if patch else "MAIN ", bid, cells, flush=True)


if __name__ == "__main__":
    main()
