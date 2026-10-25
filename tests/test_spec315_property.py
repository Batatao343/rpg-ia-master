"""SPEC-315 Etapa 3 (propriedade): falso nunca materializa; verdadeiro materializa 1x.

200 seeds: sequencias aleatorias de acoes (viajar, buscar, descansar, aceitar quest) sobre
alegacoes de todos os tipos. O harness replica a costura do storyteller: so chama o
materializador quando `due_materialization` devolve a instancia.
"""

from __future__ import annotations

import random

import pytest

from services import rumor_adoption as ra
from services import rumors
from tests.spec315_helpers import CREATURE, adopted_row, set_flags, state

PLACES = ["floresta_sussurros", "pradaria_ruinas", "montanhas_afiadas", "nova_arcadia", "brekmar"]
KINDS = [
    ("esconderijo", ""),
    ("item_perdido", ""),
    ("perigo_na_estrada", ""),
    ("criatura_avistada", CREATURE),
]


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    set_flags(monkeypatch)
    monkeypatch.setenv("RPG_NPC_WORLD", "on")


@pytest.mark.parametrize("seed", range(200))
def test_false_never_true_exactly_once(seed, monkeypatch):
    rng = random.Random(seed)
    rows = []
    for i, (kind, ent) in enumerate(KINDS):
        for truth in (True, False):
            rows.append(
                adopted_row(
                    f"{kind[:4]}{i}{int(truth)}x" + "0" * 6,
                    kind,
                    rng.choice(PLACES),
                    truth=truth,
                    entity=ent,
                    born=rng.randint(0, 3),
                    expires=rng.randint(4, 14),
                )
            )
    # um row nao adotado (shadow/rejeitado) que parece verdadeiro: tambem nunca materializa
    rows.append({**adopted_row("shadowshadow0", "esconderijo", PLACES[0]), "adopted": False})
    calls = {"cache": 0, "enc": 0}
    real_mat, real_hint = ra.materialize, ra.encounter_hint

    def spy_mat(st, inst, day):
        calls["cache"] += 1
        assert inst["truth"] and inst["adopted"]
        return real_mat(st, inst, day)

    def spy_hint(st, inst, world, lvl, turn):
        calls["enc"] += 1
        assert inst["truth"] and inst["adopted"]
        return real_hint(st, inst, world, lvl, turn)

    monkeypatch.setattr(ra, "materialize", spy_mat)
    monkeypatch.setattr(ra, "encounter_hint", spy_hint)
    st = state(1, PLACES[-1], world_sim={"rumors": rows}, quests=[])
    done: dict[str, int] = {}
    day = 1
    for _ in range(40):
        action = rng.choice(["travel", "search", "rest", "quest"])
        day += rng.randint(0, 2)
        loc = rng.choice(PLACES)
        st = {
            **st,
            "world": {**st["world"], "current_location_id": loc, "world_clock": {"day": day}},
        }
        if action == "quest":
            st["quests"] = [
                {
                    "world_kind": "investigar_rumor",
                    "status": "active",
                    "lore_anchor": {"id": rng.choice(rows)["rumor_id"]},
                }
            ]
        trigger = {"travel": "travel", "search": "search", "rest": None, "quest": "quest"}[action]
        if trigger is None:
            continue
        inst = ra.due_materialization(st, trigger, loc, day, "procuro e vasculho")
        if inst is None:
            continue
        assert inst["truth"] and inst["adopted"]  # (a)
        assert int(inst["born_day"]) < day <= int(inst["expires_day"])
        if inst["claim"]["kind"] in ("esconderijo", "item_perdido"):
            upd, marked = ra.materialize(st, inst, day)
            mat = marked["materialization"]
            st = {**st, "world": upd["world"], "player": upd["player"]}
        else:
            hint = ra.encounter_hint(st, inst, st["world"], 1, day)
            if hint is None:
                continue
            mat = {"kind": "encounter", "enemy_id": hint["enemy_id"]}
        st["world_sim"] = ra.commit(st["world_sim"], inst["rumor_id"], day, mat)
        done[inst["rumor_id"]] = done.get(inst["rumor_id"], 0) + 1
    assert all(n == 1 for n in done.values())  # (c) nunca 2
    by_id = {r["rumor_id"]: r for r in st["world_sim"]["rumors"]}
    for rid, row in by_id.items():
        if row.get("materialized_day"):
            assert row["truth"] and row["adopted"] and done[rid] == 1  # (b)
        if not row["truth"] or not row["adopted"]:
            assert not row.get("materialized_day")  # (a)
    assert calls["cache"] + calls["enc"] >= len(done)
    assert rumors.mark_materialized(st["world_sim"], rows[1]["rumor_id"], 99, {}) is not None
