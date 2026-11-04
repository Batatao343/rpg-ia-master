"""SPEC-391 Etapa 1: arena do gate de letalidade do reforço no tabuleiro de cartas (offline, MockLLM).

Reproduzir (§8 da spec; um de cada vez, sem ``-n``):
    BASE="RPG_CARD_DECK=on RPG_ENEMY_DECKS=on RPG_ENEMY_INTENT=on"
    env $BASE RPG_COMBAT_REINFORCEMENTS=off bash scripts/dev/py.sh \
        docs/spec391/arena_reforco_cartas.py 20 --levels 3,5,8 --json > docs/spec391/gate-off.json
    env $BASE RPG_COMBAT_REINFORCEMENTS=on bash scripts/dev/py.sh \
        docs/spec391/arena_reforco_cartas.py 20 --levels 3,5,8 --json > docs/spec391/gate-on.json

O que mede: a célula ``lider_matilha`` (UM Elite de arquétipo ``lider_matilha`` sozinho, o pool de
``leader_pool()`` da arena da SPEC-285) contra o herói com o baralho COMPLETO da Postura
(``sim.full_deck``) e o bot de baralho completo (``sim.full_deck_decl``), que sempre mira o
primeiro inimigo vivo (o líder).

O laço é o de ``scripts/cards/sim.py::_fight`` (mesma semente global, mesmas pilhas, mesmo
``run_round``). Diferença única, só com ``RPG_COMBAT_REINFORCEMENTS`` ≠ ``off`` e com o fluxo de
Carta disponível:

- antes de ``cs.freeze``, o gatilho é planejado como ``agents.combat._plan_reinforcements``
  (``rf.plan_triggers`` com o orçamento ``encounter_budget(nível, perigo, 0)``; ``shadow`` não
  registra gatilho, como no nó);
- no fim de cada rodada, chama a MESMA função do nó, ``services.reinforcement_cards.advance_card_flow``.

Enquanto ``services/reinforcement_cards.py`` não existe, o import falha e a arena roda sem
reforço (stub ``off``): o arquivo não precisa ser editado depois (congelado desde a Etapa 1, R14).
A arena não espelha vitais nem saber do recém-chegado (``_mirror_vitals``/``_sync_enemy_knowledge``
do nó): não mudam o desfecho mecânico do ``run_round``.

Saída (``--json``): ``{"seeds", "levels", "classes", "mode", "card_flow", "pool", "cells", "total"}``.
Cada célula: ``fights/death/win/timeout/death_rate/win_rate/timeout_rate/avg_rounds/early_deaths``,
``per_class`` (mesmos contadores por Postura) e os contadores do fluxo ``telegraphed/called/fired/
cancelled`` (lidos do ``combat_meta["reinforcement"]`` ao fim de cada luta). Sem tempo de execução
no JSON (saída determinística; o tempo vai para o stderr).

Não edita ``sim.py`` nem a arena da 285: importa os dois como ``sim.py`` importa a 285.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import random
import sys
import time

os.environ.setdefault("RPG_FORCE_MOCK", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def _load(name: str, *parts: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *parts))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    prev_disable = logging.root.manager.disable  # a arena 285 desliga o log global ao importar
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    logging.disable(prev_disable)
    return mod


sim = _load("cards_sim_391", "scripts", "cards", "sim.py")
A = sim.A  # arena da SPEC-285 (hero, leader_pool, _instances, template_by_id, DANGER_BY_LEVEL)

import encounter_budget as eb  # noqa: E402
from services import card_piles, combat_flags  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402

LEADER_CELL = A.LEADER_CELL
CLASSES = A.CLASSES
MAX_ROUNDS = sim.MAX_ROUNDS
FLOW_COUNTERS = ("telegraphed", "called", "fired", "cancelled")


# --------------------------------------------------------------------------
# Fluxo do nó (import tolerante: sem o módulo, stub `off`)
# --------------------------------------------------------------------------
def card_flow():
    """``advance_card_flow`` do nó, ou ``None`` enquanto o módulo da Etapa 2 não existe."""
    try:
        from services.reinforcement_cards import advance_card_flow
    except ImportError:
        return None
    return advance_card_flow


def reinforce_mode() -> str:
    return combat_flags.mode("reinforcements")


def _plan(scene: dict, enemies: list[dict], level: int) -> None:
    """Mesmo planejamento de ``agents.combat._plan_reinforcements`` (antes de ``cs.freeze``)."""
    from services import reinforcements as rf

    danger = A.DANGER_BY_LEVEL.get(level, 4)
    budget = eb.encounter_budget(level, danger, 0)
    for trigger in rf.plan_triggers(enemies, budget, encounter_level=danger):
        cs.add_reinforcement_trigger(scene, trigger)


def _count_flow(meta: dict, counters: dict | None) -> None:
    if counters is None:
        return
    state = meta.get("reinforcement") or {}
    counters["telegraphed"] = counters.get("telegraphed", 0) + (
        state.get("telegraphed_round") is not None
    )
    counters["called"] = counters.get("called", 0) + (state.get("called_round") is not None)
    counters["fired"] = counters.get("fired", 0) + bool(state.get("fired"))
    counters["cancelled"] = counters.get("cancelled", 0) + bool(state.get("cancelled"))


# --------------------------------------------------------------------------
# Luta (laço de sim._fight + reforço do nó)
# --------------------------------------------------------------------------
def fight(bid, n, class_name, level, seed, deck, tag, counters=None):
    with sim.deck_env():
        return _fight(bid, n, class_name, level, seed, deck, tag, counters)


def _fight(bid, n, class_name, level, seed, deck, tag, counters=None):
    """Devolve ``("win"|"death"|"timeout", rodadas)``; ``counters`` acumula o fluxo do reforço."""
    meta: dict = {}
    try:
        return _loop(bid, n, class_name, level, seed, deck, tag, meta)
    finally:
        _count_flow(meta, counters)


def _loop(bid, n, class_name, level, seed, deck, tag, meta):
    mode, flow = reinforce_mode(), card_flow()
    use_flow = mode != "off" and flow is not None
    random.seed(f"{tag}|{level}|{class_name}|{bid}|{n}|{seed}")
    player = A.hero(class_name, level)
    deck = sorted(deck)
    player["deck"] = list(deck)
    player["prepared_cards"] = list(
        dict.fromkeys(list(deck) + (player.get("prepared_cards") or []))
    )
    enemies = A._instances(
        A.template_by_id(bid, encounter_level=A.DANGER_BY_LEVEL.get(level, 4)), n
    )
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    if use_flow and mode == "on":
        _plan(scene, enemies, level)
    cs.freeze(scene)
    rng = random.Random(seed)
    piles = card_piles.start_piles(player, seed)
    state = {"player": player, "_piles": piles, "_deck_mode": "on"}
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            return "win", rnd
        initiator = (
            "heroes"
            if rnd == 1 and level <= 2 and player["vitalidade"] >= player["max_vitalidade"]
            else None
        )
        decl = sim.full_deck_decl(player, piles, alive[0]["id"])
        out = orch.run_round(
            scene, actors, sides, state, declarations={"player": decl}, initiator=initiator, rng=rng
        )
        if (
            player.get("dead")
            or player.get("estado_terminal")
            or out.get("player_dead")
            or int(player.get("vitalidade", 0) or 0) <= 0
        ):
            return "death", rnd
        if out.get("ended"):
            return "win", rnd
        if use_flow:
            meta["round"] = rnd
            flow(scene, enemies, actors, sides, meta, rnd, mode=mode)
        card_piles.begin_round(piles)
    return "timeout", MAX_ROUNDS


# --------------------------------------------------------------------------
# Células
# --------------------------------------------------------------------------
def _empty() -> dict:
    return {"fights": 0, "death": 0, "win": 0, "timeout": 0, "rounds": 0, "early_deaths": 0}


def _add(cell: dict, outcome: str, rounds: int) -> None:
    cell["fights"] += 1
    cell[outcome] += 1
    cell["rounds"] += rounds
    cell["early_deaths"] += outcome == "death" and rounds <= 2


def _rates(cell: dict) -> dict:
    f = cell["fights"] or 1
    out = {k: v for k, v in cell.items() if k != "rounds"}
    out["death_rate"] = round(cell["death"] / f, 3)
    out["win_rate"] = round(cell["win"] / f, 3)
    out["timeout_rate"] = round(cell["timeout"] / f, 3)
    out["avg_rounds"] = round(cell["rounds"] / f, 2)
    return out


class _Acc:
    """Contadores brutos de uma célula (total e por Postura) e do fluxo do reforço."""

    def __init__(self) -> None:
        self.cell, self.per_class = _empty(), {}
        self.flow = dict.fromkeys(FLOW_COUNTERS, 0)

    def add(self, cls: str, outcome: str, rounds: int) -> None:
        _add(self.cell, outcome, rounds)
        _add(self.per_class.setdefault(cls, _empty()), outcome, rounds)

    def merge(self, other: _Acc) -> None:
        for k in self.cell:
            self.cell[k] += other.cell[k]
        for k in FLOW_COUNTERS:
            self.flow[k] += other.flow[k]
        for cls, pc in other.per_class.items():
            acc = self.per_class.setdefault(cls, _empty())
            for k in acc:
                acc[k] += pc[k]

    def report(self) -> dict:
        per_class = {c: _rates(v) for c, v in self.per_class.items()}
        return {**_rates(self.cell), "per_class": per_class, **self.flow}


def run_level(level: int, seeds, classes, pool: list[str]) -> _Acc:
    acc = _Acc()
    for cls in classes:
        deck = sim.full_deck(cls, level)
        for bid in pool:
            for seed in seeds:
                outcome, rounds = fight(bid, 1, cls, level, seed, deck, "391", acc.flow)
                acc.add(cls, outcome, rounds)
    return acc


def run(seeds, levels, classes=CLASSES) -> dict:
    pool = A.leader_pool()
    seeds = list(seeds)
    total, cells = _Acc(), {}
    for lv in levels:
        acc = run_level(lv, seeds, classes, pool)
        total.merge(acc)
        cells[f"L{lv}|{LEADER_CELL}"] = acc.report()
    return {
        "seeds": len(seeds),
        "levels": list(levels),
        "classes": list(classes),
        "mode": reinforce_mode(),
        "card_flow": card_flow() is not None,
        "pool": pool,
        "cells": cells,
        "total": total.report(),
    }


def _print_table(res: dict) -> None:
    print(f"modo={res['mode']} fluxo_carta={res['card_flow']} pool={len(res['pool'])}")
    for key, cell in [*res["cells"].items(), ("total", res["total"])]:
        flow = " ".join(f"{k}={cell[k]}" for k in FLOW_COUNTERS)
        print(
            f"{key:<22} lutas={cell['fights']:<4} morte={cell['death_rate']:.3f} "
            f"vitória={cell['win_rate']:.3f} timeout={cell['timeout_rate']:.3f} {flow}"
        )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("seeds", nargs="?", type=int, default=20)
    ap.add_argument("--levels", default="3,5,8")
    ap.add_argument("--classes", default=",".join(CLASSES))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    t0 = time.time()
    res = run(
        range(args.seeds),
        [int(x) for x in args.levels.split(",")],
        [c.strip() for c in args.classes.split(",") if c.strip()],
    )
    if args.json:
        print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    else:
        _print_table(res)
    print(f"elapsed_s={time.time() - t0:.1f}", file=sys.stderr)


if __name__ == "__main__":
    main()
