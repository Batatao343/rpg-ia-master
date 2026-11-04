"""A arena da SPEC-285 faz `logging.disable(CRITICAL)` global ao ser importada.

Todo carregador dela precisa restaurar o estado anterior. Sem isso, um teste que importa o
carregador (ex.: `test_spec371_eval` via `scripts/fauna/arena_saber.py` →
`docs/spec332/arena_familias.py`) silencia o log do worker do xdist inteiro, e os testes de
log seguintes (`test_world_rejection_logs`, `test_turn_trace_logs`) falham por ordem.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOADS_ARENA = re.compile(r"spec285[\"'/\\, ]+[\"']?arena_lethality\.py")


def test_every_arena_285_loader_restores_logging_disable() -> None:
    offenders = []
    for path in [*ROOT.glob("docs/**/*.py"), *ROOT.glob("scripts/**/*.py")]:
        if path.name == "arena_lethality.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "exec_module" in text and LOADS_ARENA.search(text):
            if not re.search(r"logging\.disable\(\s*_?prev", text):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], f"carregam a arena 285 sem restaurar logging.disable: {offenders}"
