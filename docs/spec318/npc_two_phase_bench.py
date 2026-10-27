"""SPEC-318 R1 isolado: custo de _with_new_npc no caminho do narrador, ficha completa (off) x esboco (on), LLM real."""

import json
import os
import statistics as st
import sys
import time

sys.path.insert(0, ".")
os.environ.pop("RPG_FORCE_MOCK", None)
from agents import storyteller

NAMES = [
    "Bruno Ferrador",
    "Lia das Ervas",
    "Tico Aguadeiro",
    "Sargento Varo",
    "Dona Inês",
    "Pescador Abel",
]
res = {}
for mode, stub in (("off", False), ("on", True)):
    ts = []
    for i, n in enumerate(NAMES):
        name = f"{n} {mode}{i}"
        t = time.perf_counter()
        out = {}
        npcs = storyteller._with_new_npc(
            {},
            name,
            "Nova Arcádia",
            f"{name} se aproxima e cumprimenta você na praça.",
            game_id="bench318",
            home_id="nova_arcadia",
            turn=3,
            stub_only=stub,
            outcome_out=out,
        )
        ts.append(round((time.perf_counter() - t) * 1000))
        sheet = next(iter(npcs.values()), {}) if npcs else {}
        res.setdefault(mode + "_status", []).append(
            sheet.get("sheet_status", "full") if sheet else ("fail" if out else "none")
        )
    res[mode + "_ms"] = ts
    res[mode + "_p50_ms"] = st.median(ts)
print(json.dumps(res, ensure_ascii=False))
