"""Card-combat eval adapter (SPEC-380 R2).

Calls the public product APIs of the card combat (`services.conflict_damage`,
`services.card_effects`, `services.conflict_turn`, `services.conflict_orchestrator`,
`services.enemy_intent`) on fixture-built actors and returns ONLY the projection the
case declares in `input.projection`. Expected values live in the dataset; nothing here
derives them. Every case must pin the four flags the path reads (`input.flags`); the
adapter sets them for the call and restores env and the global `random` afterwards.
"""

from __future__ import annotations

import copy
import os
import random
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from evals.core.adapters import AdapterCase, AdapterError, AdapterOutput

REQUIRED_FLAGS = ("RPG_ENEMY_INTENT", "RPG_CARD_DECK", "RPG_ENEMY_DECKS", "RPG_RUNTIME_PROFILE")
_MISSING = object()


@contextmanager
def _pinned(flags: Any, seed: int) -> Iterator[None]:
    if not isinstance(flags, dict):
        raise AdapterError("cards_combat requires input.flags object")
    missing = [name for name in REQUIRED_FLAGS if not isinstance(flags.get(name), str)]
    if missing:
        raise AdapterError("cards_combat input.flags missing: " + ", ".join(missing))
    saved_env = {name: os.environ.get(name) for name in REQUIRED_FLAGS}
    saved_random = random.getstate()
    try:
        for name in REQUIRED_FLAGS:
            os.environ[name] = flags[name]
        random.seed(seed)
        yield
    finally:
        random.setstate(saved_random)
        for name, value in saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


class _ScriptedRng:
    """Cyclic `randint` sequence, the same device as `tests/test_conflito_turno.py::_Rng`."""

    def __init__(self, values: list[int]) -> None:
        if not values or not all(isinstance(v, int) for v in values):
            raise AdapterError("rng.sequence must be a non-empty list of ints")
        self.values, self.i = values, 0

    def randint(self, a: int, b: int) -> int:
        value = self.values[self.i % len(self.values)]
        self.i += 1
        return value


def _rng(spec: Any):
    if isinstance(spec, dict) and "sequence" in spec:
        return _ScriptedRng(list(spec["sequence"]))
    if isinstance(spec, dict) and isinstance(spec.get("seed"), int):
        return random.Random(spec["seed"])
    raise AdapterError("cards_combat requires input.rng {sequence:[...]} or {seed:int}")


def _combatant(raw: dict[str, Any]) -> dict[str, Any]:
    """Raw v4 sheet with the defaults of the conflict tests' `_combatant`/`_target`."""
    import gamedata

    actor = copy.deepcopy(raw)
    fill_critical = bool(actor.pop("fill_critical_but_one", False))
    corpo = int((actor.get("virtudes") or {}).get("corpo", 2))
    actor.setdefault("max_vitalidade", gamedata.vitalidade_para_corpo(corpo))
    actor.setdefault("vitalidade", actor["max_vitalidade"])
    actor.setdefault("ferimento_espacos", gamedata.espacos_ferimento_para_corpo(corpo))
    actor.setdefault("ferimentos", {"leve": [], "grave": [], "critico": []})
    actor.setdefault("active_conditions", [])
    if fill_critical:
        slots = int(actor["ferimento_espacos"]["critico"]) - 1
        actor["ferimentos"]["critico"] = [
            {"regiao": f"r{i}", "categoria": "critico"} for i in range(slots)
        ]
    return actor


def _build_actors(spec: Any) -> dict[str, dict[str, Any]]:
    from services import conflict_orchestrator as orch

    if not isinstance(spec, dict) or not spec:
        raise AdapterError("cards_combat requires input.actors object")
    actors: dict[str, dict[str, Any]] = {}
    for actor_id, row in spec.items():
        kind, sheet = row.get("kind"), copy.deepcopy(row.get("sheet") or {})
        if kind == "combatant":
            actors[actor_id] = _combatant(sheet)
        elif kind in ("player", "enemy", "ally"):
            actors[actor_id] = orch.ensure_combat_sheet(
                sheet, is_player=kind == "player", is_ally=kind == "ally"
            )
        else:
            raise AdapterError(f"unknown actor kind {kind!r} for {actor_id}")
        for condition in row.get("conditions") or []:
            import combat_mechanics as cm

            cm.apply_condition(actors[actor_id], copy.deepcopy(condition))
    return actors


def _build_scene(spec: Any, actor_ids: list[str]) -> dict[str, Any]:
    from services import conflict_scene as cs

    spec = spec if isinstance(spec, dict) else {}
    scene = cs.new_scene()
    for actor_id in actor_ids:
        if spec.get("distance_state"):
            cs.place(scene, actor_id, distance_state=spec["distance_state"])
        else:
            cs.place(scene, actor_id)
    if spec.get("freeze", True):
        cs.freeze(scene)
    for hidden in spec.get("hide") or []:
        cs.hide(scene, hidden["id"], source=hidden["source"], observers=hidden["observers"])
    return scene


def _actor_view(actor: dict[str, Any]) -> dict[str, Any]:
    conditions = actor.get("active_conditions") or []
    armor = actor.get("armor") or {}
    return {
        "vitalidade": actor.get("vitalidade"),
        "max_vitalidade": actor.get("max_vitalidade"),
        "perdeu_vitalidade": (actor.get("vitalidade") or 0) < (actor.get("max_vitalidade") or 0),
        "entropy": actor.get("entropy"),
        "dead": bool(actor.get("dead")),
        "last_stand_pending": bool(actor.get("last_stand_pending")),
        "estado_terminal": bool(actor.get("estado_terminal")),
        "condicoes": sorted(str(c.get("name")) for c in conditions),
        "palavras_chave": sorted(str(c["keyword"]) for c in conditions if c.get("keyword")),
        "dots": sorted(int(c.get("dot", 0) or 0) for c in conditions if c.get("dot")),
        "tem_dot": any(int(c.get("dot", 0) or 0) > 0 for c in conditions),
        "integridade_atual": armor.get("integridade_atual"),
        "armadura_comprometida": armor.get("comprometida"),
    }


def _views(actors: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {actor_id: _actor_view(actor) for actor_id, actor in actors.items()}


def _op_damage(case_input: dict[str, Any]) -> dict[str, Any]:
    from services import conflict_damage as cd

    target = _combatant(case_input.get("target") or {})
    damage = case_input.get("damage") or {}
    if not isinstance(damage.get("damage_base"), int) or not damage.get("damage_type"):
        raise AdapterError("damage requires input.damage {damage_base:int, damage_type}")
    res = cd.resolve_damage_and_wounds(
        target, damage_base=damage["damage_base"], damage_type=str(damage["damage_type"])
    )
    return {
        "dano_final": res.get("dano_final"),
        "imune": bool(res.get("imune")),
        "protegido": bool(res.get("protegido")),
        "ferimento": bool(res.get("wound")),
        "target": _actor_view(target),
    }


def _op_resolve_card(case_input: dict[str, Any]) -> dict[str, Any]:
    from services import card_effects as fx

    actors = _build_actors(case_input.get("actors"))
    scene = _build_scene(case_input.get("scene"), list(actors))
    card = case_input.get("card")
    if not isinstance(card, dict) or not card.get("id"):
        raise AdapterError("resolve_card requires an inline input.card with id")
    ctx = fx.Ctx(
        scene=scene,
        actors_by_id=actors,
        sides=case_input.get("sides"),
        rng=_rng(case_input.get("rng")),
    )
    out: dict[str, Any] = {"logs": []}
    events = fx.resolve_card(
        ctx, copy.deepcopy(card), case_input["actor_id"], case_input.get("target_id"), out
    )
    return {"keywords": [ev.get("keyword") for ev in events], "actors": _views(actors)}


def _op_resolve_turn(case_input: dict[str, Any]) -> dict[str, Any]:
    from services import conflict_turn as ct

    actors = _build_actors(case_input.get("actors"))
    scene = _build_scene(case_input.get("scene"), list(actors))
    state_actor = case_input.get("state_actor")
    state = {"player": actors[state_actor]} if state_actor else None
    if state is not None and case_input.get("state_scene"):
        state["combat"] = {"scene": scene}
    out = ct.resolve_turn(
        scene,
        actors,
        copy.deepcopy(case_input.get("declaration")),
        state=state,
        rng=_rng(case_input.get("rng")),
        sides=case_input.get("sides"),
    )
    attacks = out.get("attacks") or []
    return {
        "ok": out.get("ok", True),
        "n_attacks": len(attacks),
        "attacks": [{"acerto": a.get("acerto"), "target_id": a.get("target_id")} for a in attacks],
        "terminal": sorted(out.get("terminal") or []),
        "deaths": sorted(out.get("deaths") or []),
        "actors": _views(actors),
    }


def _op_round(case_input: dict[str, Any]) -> dict[str, Any]:
    from services import conflict_orchestrator as orch

    actors = _build_actors(case_input.get("actors"))
    scene = _build_scene(case_input.get("scene"), list(actors))
    sides = case_input.get("sides") or {}
    rng = _rng(case_input.get("rng"))
    max_rounds = int(case_input.get("max_rounds") or 0)
    if not 1 <= max_rounds <= 20:
        raise AdapterError("round requires 1 <= input.max_rounds <= 20")
    ended = player_dead = False
    fallen: set[str] = set()
    for _ in range(max_rounds):
        out = orch.run_round(
            scene,
            actors,
            sides,
            {"player": actors["player"]},
            declarations={"player": copy.deepcopy(case_input.get("declaration"))},
            rng=rng,
        )
        fallen |= set(out.get("deaths") or [])
        ended, player_dead = bool(out.get("ended")), bool(out.get("player_dead"))
        if ended or player_dead:
            break
    fallen |= {aid for aid, a in actors.items() if a.get("dead") or a.get("status") == "morto"}
    winner = "enemy" if player_dead else "hero" if ended else None
    return {
        "ended": ended,
        "player_dead": player_dead,
        "caidos": sorted(fallen),
        "vencedor": winner,
        "actors": _views(actors),
    }


def _op_intent(case_input: dict[str, Any]) -> dict[str, Any]:
    from services import enemy_intent as ei

    actors = _build_actors(case_input.get("actors"))
    intent = copy.deepcopy(case_input.get("intent"))
    level = case_input.get("knowledge_level")
    if not isinstance(intent, dict) or level not in ("desconhecida", "conhecida", "estudada"):
        raise AdapterError("intent requires input.intent object and a valid knowledge_level")
    view = ei.public_intent(intent, level, actors_by_id=actors)
    faixa = view.get("faixa")
    return {
        "tipo": view.get("tipo"),
        "alvo_id": view.get("alvo_id"),
        "carta_nome": view.get("carta_nome"),
        "revela_carta": view.get("carta_nome") is not None,
        "faixa_presente": faixa is not None,
        "faixa_ordenada": bool(faixa) and faixa[0] <= faixa[1],
        "valor_estimado_presente": view.get("valor_estimado") is not None,
        "valor_estimado_e_minimo": bool(faixa) and view.get("valor_estimado") == faixa[0],
        "sinal_presente": bool(view.get("sinal")),
        "campos_internos": sorted(set(view) & {"declaration", "carta_id", "idx"}),
    }


def _op_folego(case_input: dict[str, Any]) -> dict[str, Any]:
    from services import card_effects as fx
    from services import cards

    if isinstance(case_input.get("card"), dict):
        card = copy.deepcopy(case_input["card"])
    else:
        card = copy.deepcopy(cards.all_cards().get(str(case_input.get("card_id"))))
        if card is None:
            raise AdapterError(f"unknown card_id {case_input.get('card_id')!r}")
    return {"custo_folego": fx.custo_folego(card)}


_OPERATIONS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "damage": _op_damage,
    "resolve_card": _op_resolve_card,
    "resolve_turn": _op_resolve_turn,
    "round": _op_round,
    "intent": _op_intent,
    "folego": _op_folego,
}


def _read(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return copy.deepcopy(current)


def _project(actual: dict[str, Any], paths: Any) -> dict[str, Any]:
    if not isinstance(paths, list) or not paths or not all(isinstance(p, str) and p for p in paths):
        raise AdapterError("cards_combat requires non-empty input.projection")
    projected = {path: _read(actual, path) for path in paths}
    missing = [path for path, value in projected.items() if value is _MISSING]
    if missing:
        raise AdapterError("cards_combat projection path not produced: " + ", ".join(missing))
    return projected


class CardsCombatAdapter:
    """Damage, Cards, turn, round, Presságio and Fôlego cost through product APIs."""

    adapter_id = "cards_combat"

    def execute(self, case: AdapterCase) -> AdapterOutput:
        if not isinstance(case.input, dict):
            raise AdapterError("cards_combat requires object input")
        operation = _OPERATIONS.get(str(case.input.get("operation")))
        if operation is None:
            raise AdapterError(f"unknown cards_combat operation {case.input.get('operation')!r}")
        with _pinned(case.input.get("flags"), int(case.input.get("global_seed", 7))):
            actual = operation(case.input)
        return AdapterOutput(actual=_project(actual, case.input.get("projection")))


__all__ = ["CardsCombatAdapter", "REQUIRED_FLAGS"]
