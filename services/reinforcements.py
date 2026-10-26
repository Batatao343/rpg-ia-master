"""services/reinforcements.py - reforco de `lider_matilha` (SPEC-325 R16, D4).

Python decide, nunca LLM. Na preparacao da cena (antes de `cs.freeze`) todo lider de
matilha registra 1 gatilho. Na 1a vez que o lider fica com Vitalidade <= 50 % o log
publica o AVISO; ao fim da rodada seguinte, se o lider ainda age, chega 1 inimigo
`distante` (1 vez por conflito). Matar, incapacitar ou fazer o lider fugir antes da
chegada cancela o reforco. O reforco so existe para o narrador/API depois do aviso.

`advance` e a unica porta usada pelo no de combate e pela arena da SPEC-285.
"""

from __future__ import annotations

from typing import Any

from observability.telemetry import log_event as _log_event
from services import conflict_scene as cs

ARCHETYPE = "lider_matilha"
WARN_RATIO = 0.5
_NEUTRAL_FLAGS = ("dead", "fled", "surrendered", "captured", "incapacitated")


def is_leader(enemy: dict | None) -> bool:
    e = enemy or {}
    return ARCHETYPE in (str(e.get("arquetipo") or ""), str(e.get("tactical_archetype") or ""))


def acts(enemy: dict | None) -> bool:
    """O lider ainda esta de pe e no jogo (nem morto, fugido, rendido, capturado ou caido)."""
    e = enemy or {}
    if not e or any(e.get(flag) for flag in _NEUTRAL_FLAGS):
        return False
    return str(e.get("status") or "ativo") == "ativo"


def _ratio(enemy: dict) -> float:
    maximum = int(enemy.get("max_vitalidade", 0) or 0)
    if maximum <= 0:
        return 1.0
    return int(enemy.get("vitalidade", maximum) or 0) / maximum


def _base_id(enemy: dict) -> str:
    from services.encounter_manifest import _base_id as base

    return str(enemy.get("archetype_id") or base(enemy.get("id", "")))


def plan_triggers(enemies: list[dict], budget: int, *, encounter_level: int = 1) -> list[dict]:
    """1 gatilho por lider de matilha (antes de congelar a cena). `budget` = orcamento do
    encontro, usado depois para limitar o reforco ao que sobra."""
    out: list[dict] = []
    for enemy in enemies:
        if not isinstance(enemy, dict) or not is_leader(enemy):
            continue
        out.append(
            {
                "id": f"reinf_{enemy.get('id')}",
                "kind": ARCHETYPE,
                "leader_id": str(enemy.get("id")),
                "base_id": _base_id(enemy),
                "faction": str(enemy.get("faction") or enemy.get("faction_id") or ""),
                "budget": int(budget),
                "encounter_level": int(encounter_level),
                "participants": {},
                "objects": [],
            }
        )
    return out


def _template_for(trigger: dict) -> dict | None:
    """Lacaio da MESMA faccao do lider; sem ele, copia do template do lider rebaixada a lacaio."""
    from agents.bestiary import load_bestiary, template_by_id

    level = int(trigger.get("encounter_level", 1) or 1)
    faction = str(trigger.get("faction") or "")
    if faction:
        for bid, entry in sorted(load_bestiary().items()):
            if (
                str(entry.get("categoria") or "").lower() == "lacaio"
                and str(entry.get("faction") or entry.get("faction_id") or "") == faction
                and bid != trigger.get("base_id")
            ):
                template = template_by_id(bid, encounter_level=level)
                if template:
                    return template
    template = template_by_id(str(trigger.get("base_id") or ""), encounter_level=level)
    if template:
        template["categoria"] = "lacaio"
        template["type"] = "lacaio"
    return template


def spawn(trigger: dict, combat_meta: dict, enemies: list[dict] | None = None) -> list[dict]:
    """Instancia o reforco (id unico `<base>_r<N>`, contador em `combat_meta`); lista vazia se o
    orcamento restante do encontro nao comporta o inimigo."""
    import encounter_budget as eb
    from services import conflict_orchestrator as orch

    template = _template_for(trigger)
    if not template:
        return []
    cost = eb.tier_cost(template)
    living = sum(eb.tier_cost(e) for e in (enemies or []) if acts(e))
    if int(trigger.get("budget", 0) or 0) - living < cost:
        return []
    base = str(template.get("id") or "enemy")
    counters = combat_meta.setdefault("next_by_template", {})
    number = int(counters.get(base, 0) or 0) + 1
    counters[base] = number
    inst = dict(template)
    inst["id"] = f"{base}_r{number}"
    inst["archetype_id"] = base
    inst["name"] = f"{template.get('name', 'Inimigo')} (reforço)"
    inst["status"] = "ativo"
    return [orch.ensure_combat_sheet(inst)]


def check(scene: dict, actors_by_id: dict, combat_meta: dict, round_: int) -> dict[str, list]:
    """Decisao pura da rodada: `warn` (lider cruzou 50 %), `fire` (chegou a hora) ou `cancel`."""
    res: dict[str, list] = {"warn": [], "fire": [], "cancel": []}
    state = combat_meta.get("reinforcement") or {}
    if state.get("fired") or state.get("cancelled"):
        return res
    triggers = [t for t in scene.get("reinforcement_triggers") or [] if t.get("kind") == ARCHETYPE]
    if state.get("warned_round") is not None:
        trig = next((t for t in triggers if t.get("id") == state.get("trigger_id")), None)
        if trig is None or not acts(actors_by_id.get(str(trig.get("leader_id")))):
            res["cancel"].append(trig or {"id": state.get("trigger_id")})
        elif int(round_) > int(state["warned_round"]):
            res["fire"].append(trig)
        return res
    for trig in triggers:
        leader = actors_by_id.get(str(trig.get("leader_id")))
        if acts(leader) and _ratio(leader) <= WARN_RATIO:
            res["warn"].append(trig)
            break
    return res


def _arrival_position(scene: dict, leader_id: str) -> dict:
    zone = ((scene.get("positions") or {}).get(leader_id) or {}).get("zone_id") or "z0"
    tmp = cs.new_scene([{"id": zone, "name": zone, "connections": []}])
    cs.place(tmp, "_", zone_id=zone, distance_state="distante")
    return tmp["positions"]["_"]


def advance(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    round_: int,
    *,
    mode: str = "on",
) -> dict[str, Any]:
    """Fim de rodada: avisa, cancela ou faz chegar o reforco, mutando `enemies`/`actors_by_id`/
    `sides["enemy"]`/posicoes da cena e `combat_meta["reinforcement"]`. `shadow` so registra o
    que aconteceria (nada muda). Devolve `{"logs", "spawned", "warned"}`."""
    res: dict[str, Any] = {"logs": [], "spawned": [], "warned": False}
    if mode == "shadow":
        if any(is_leader(e) and acts(e) and _ratio(e) <= WARN_RATIO for e in enemies):
            _log_event("combat", "reinforcements_shadow", phase="would_warn")
        return res
    if mode != "on":
        return res
    decision = check(scene, actors_by_id, combat_meta, round_)
    state = dict(combat_meta.get("reinforcement") or {})
    if decision["cancel"]:
        state["cancelled"] = True
        combat_meta["reinforcement"] = state
        _log_event("combat", "reinforcements_cancelled", level="info")
        return res
    for trig in decision["warn"]:
        leader = actors_by_id.get(str(trig["leader_id"])) or {}
        combat_meta["reinforcement"] = {
            "trigger_id": trig["id"],
            "leader_id": trig["leader_id"],
            "warned_round": int(round_),
            "fired": False,
        }
        res["warned"] = True
        res["logs"].append(
            f"{leader.get('name', 'O líder')} está ferido e chama os seus: "
            "passos se aproximam ao longe."
        )
        _log_event("combat", "reinforcements_warned", level="info")
    for trig in decision["fire"]:
        new = spawn(trig, combat_meta, enemies)
        if not new:
            state["cancelled"] = True
            combat_meta["reinforcement"] = state
            _log_event("combat", "reinforcements_cancelled", level="info", cause="budget")
            continue
        pos = _arrival_position(scene, str(trig["leader_id"]))
        for enemy in new:
            trig.setdefault("participants", {})[enemy["id"]] = dict(pos)
        cs.fire_reinforcement(scene, str(trig["id"]))
        for enemy in new:
            enemies.append(enemy)
            actors_by_id[enemy["id"]] = enemy
            sides.setdefault("enemy", []).append(enemy["id"])
            res["logs"].append(f"{enemy.get('name', 'Um inimigo')} chega correndo, vindo de longe.")
        res["spawned"] = new
        combat_meta["reinforcement"] = {**state, "fired": True}
        _log_event("combat", "reinforcements_fired", level="info")
    return res
