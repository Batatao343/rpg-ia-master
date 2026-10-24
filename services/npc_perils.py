"""SPEC-304 R12-R19: exposição, perigo, telegrama, intervenção e destino de NPCs off-screen.

Funções (quase) puras: tudo é seeded por `world_engine.day_rng`, nada lê nível, ficha, ouro
nem inventário do herói. A posição do herói só entra para NUNCA expor/matar um NPC no local
dele (R12/R18) e para a intervenção (R16). Os eventos devolvidos são propostas
`source="engine"` com `actor_id="world"` (R19): a SPEC-298 e a SPEC-300 não os contam como
feito do jogador. Quem aplica no estado é `services/npc_world.py` (owner de `npc_sim`).
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from services import location_states as ls
from services import world_director as wd
from services import world_pressures as wp

CRISIS_STATES = ("cerco", "praga", "ocupado", "ruina", "corrompido")
_KIND_BY_STATE = {
    "cerco": "cerco",
    "praga": "praga",
    "corrompido": "abismo",
    "ocupado": "cativeiro",
    "ruina": "emboscada",
}
PERIODS_PER_DAY = 5  # len(world_utils.PERIODS)
FATES = ("morto", "ferido", "capturado", "escapou")


def cfg() -> dict:
    return wp._load_json("npc_world.json")


def const(name: str) -> Any:
    return cfg()["constants"][name]


def peril_id(game_id: str, npc: str, opened_day: int) -> str:
    return hashlib.sha256(f"{game_id}|{npc}|{opened_day}".encode()).hexdigest()[:16]


def engine_event(
    game_id: str,
    day: int,
    etype: str,
    target: str,
    payload: dict,
    *,
    actor: str = "world",
    extra: str = "",
) -> dict:
    """Proposta do motor (R19: `actor_id` nunca é o jogador). `event_id` determinístico."""
    return {
        "type": etype,
        "actor_id": actor,
        "target_id": target,
        "detail": "",
        "payload": payload,
        "source": "engine",
        "event_id": wd.event_id(game_id, etype, day, target, extra),
    }


# --- exposição (R12) ---------------------------------------------------------------


def danger_at(world: dict, projection: dict, location_id: str) -> int:
    """Perigo efetivo do local no dia: base do mapa (+ override) + `danger_delta` do estado."""
    from world_utils import _effective_danger

    base = _effective_danger(world or {}, location_id, with_state=False)
    row = ((projection or {}).get("location_states") or {}).get(ls._resolve_id(location_id))
    row = row if isinstance(row, dict) and row.get("state") else None
    return base + ls.danger_delta(row, location_id)


def crisis_state_at(projection: dict, location_id: str) -> str:
    row = ((projection or {}).get("location_states") or {}).get(ls._resolve_id(location_id)) or {}
    state = str(row.get("state") or "")
    return state if state in CRISIS_STATES else ""


def _family(location_id: str) -> set[str]:
    locs = wp._map_index()[0]
    fam = {location_id}
    loc = locs.get(location_id) or {}
    if loc.get("parent_id"):
        fam.add(str(loc["parent_id"]))
    fam |= {lid for lid, other in locs.items() if other.get("parent_id") == location_id}
    return fam


def at_player(player_loc: str, location_id: str) -> bool:
    return bool(player_loc and location_id and location_id in _family(player_loc))


def exposure(
    state: dict, npc_key: str, pos: dict, day: int, *, player_loc: str | None = None
) -> tuple[bool, str, int]:
    """(exposto, tipo de perigo, perigo). Nunca expõe quem está no local do jogador."""
    del npc_key, day
    world = (state or {}).get("world") or {}
    proj = (state or {}).get("world_projection") or {}
    here = world.get("current_location_id", "") if player_loc is None else player_loc
    loc = str((pos or {}).get("location_id") or "")
    if not loc:  # viajante: exposto se uma das pontas tem perigo >= 4
        for end in (pos.get("travel_from"), pos.get("travel_to")):
            if end and not at_player(str(here), str(end)):
                d = danger_at(world, proj, str(end))
                if d >= 4:
                    return True, "emboscada", d
        return False, "", 0
    if at_player(str(here), loc):
        return False, "", 0
    d = danger_at(world, proj, loc)
    st = crisis_state_at(proj, loc)
    if st:
        return True, _KIND_BY_STATE[st], d
    if d >= int(const("PERIL_MIN_DANGER")):
        return True, "emboscada", d
    return False, "", d


def peril_location(pos: dict, world: dict, projection: dict) -> str:
    """Local do perigo: o próprio local; viajante -> a ponta mais perigosa."""
    loc = str((pos or {}).get("location_id") or "")
    if loc:
        return loc
    ends = [e for e in (pos.get("travel_from"), pos.get("travel_to")) if e]
    return max(ends, key=lambda e: (danger_at(world, projection, str(e)), str(e)), default="")


# --- abertura (R13-R15) ------------------------------------------------------------


def hazard(danger: int, state_name: str, archetype: str) -> float:
    c = cfg()
    base = float(c["BASE_HAZARD"].get(str(max(3, min(4, int(danger)))), 0.0))
    return (
        base
        * float(c["CRISIS_MULT"].get(state_name, 1.0))
        * float(c["ROLE_MULT"].get(archetype, 1.0))
    )


def active_count(sim: dict) -> int:
    return sum(1 for p in sim.get("perils") or [] if not p.get("resolution"))


def has_open(sim: dict, npc: str) -> bool:
    return any(p.get("npc_id") == npc and not p.get("resolution") for p in sim.get("perils") or [])


def in_cooldown(entry: dict, day: int) -> bool:
    last = entry.get("last_peril_end_day")
    return last is not None and int(day) - int(last) < int(const("PERIL_COOLDOWN_DAYS"))


def maybe_open(
    state: dict,
    sim: dict,
    npc_key: str,
    day: int,
    rng: Any,
    *,
    entry: dict,
    major: bool = False,
    leader: bool = False,
    dsim: dict | None = None,
    shadow: bool = False,
    player_loc: str | None = None,
    protected: bool = False,
) -> tuple[dict | None, list[dict]]:
    """Sorteia a abertura de um perigo para o NPC (R13). Devolve `(peril, eventos)`.

    Perigo maior só abre se o diretor conceder vaga (R14: anúncio agora, `request_crisis_slot`
    quando maturar em `earliest_day`) e, para líder, respeitando o intervalo de mortes.
    O telegrama (`npc_peril_warning`) sai no MESMO dia, com `location_id` sempre (R15)."""
    pos = entry.get("pos") or {}
    roll = rng.random()  # sempre sorteia: o fluxo do rng não depende dos tetos
    window_roll = rng.randint(*[int(x) for x in const("PERIL_WINDOW")])
    exposed, kind, danger = exposure(state, npc_key, pos, day, player_loc=player_loc)
    if not exposed or has_open(sim, npc_key) or in_cooldown(entry, day):
        return None, []
    if active_count(sim) >= int(const("MAX_ACTIVE_PERILS")):
        return None, []
    world = (state or {}).get("world") or {}
    proj = (state or {}).get("world_projection") or {}
    loc = peril_location(pos, world, proj)
    state_name = crisis_state_at(proj, loc)
    p = hazard(danger, state_name, str(entry.get("archetype") or "sedentario"))
    if protected:  # em casa, entre os seus: bem mais seguro que viajante/companheiro largado
        p *= float(cfg().get("HOME_MULT", 1.0))
    if roll >= p:
        return None, []
    region = wp.region_of(loc)
    game_id = str((state or {}).get("game_id", ""))
    crisis_id = ""
    if major:
        if shadow or dsim is None:
            pass  # sombra: não consome o orçamento real do diretor
        else:
            rec = wd.announce(dsim, day, region, wd.NPC_PERIL_KIND, rng, game_id=game_id)
            if rec is None:
                return None, []
            rec["location_id"] = loc
            crisis_id = str(rec["crisis_id"])
    earliest = int(day) + int(const("TELEGRAPH_MIN_DAYS"))
    pid = peril_id(game_id, npc_key, day)
    channel = "pedido_de_ajuda" if major else "rumor"
    ev = engine_event(
        game_id,
        day,
        "npc_peril_warning",
        npc_key,
        {
            "peril_id": pid,
            "kind": _peril_kind(kind, state_name),
            "location_id": loc,
            "region_id": region,
            "opened_day": int(day),
            "earliest_day": earliest,
            "deadline_day": earliest + window_roll,
            "channel": channel,
        },
        extra=pid,
    )
    peril = {
        "peril_id": pid,
        "npc_id": npc_key,
        "major": bool(major),
        "leader": bool(leader),
        "kind": ev["payload"]["kind"],
        "danger": int(danger),
        "location_id": loc,
        "region_id": region,
        "opened_day": int(day),
        "earliest_day": earliest,
        "deadline_day": earliest + window_roll,
        "extensions": 0,
        "channel": channel,
        "warning_event_id": ev["event_id"],
        "perceived_day": None,
        "resolution": "",
        "resolved_day": None,
        "crisis_id": crisis_id,
        "slot_day": None,
    }
    sim.setdefault("perils", []).append(peril)
    return peril, [ev]


def _peril_kind(kind: str, state_name: str) -> str:
    return kind if kind else _KIND_BY_STATE.get(state_name, "emboscada")


def delivery_day(peril: dict, player_loc: str) -> int:
    """Dia em que o mensageiro (canal d) acha o jogador (R15), limitado ao prazo - 1."""
    from services import world_distance

    periods = world_distance.travel_periods(str(peril.get("location_id") or ""), player_loc)
    travel = math.ceil((periods or 0) / PERIODS_PER_DAY)
    return min(int(peril["opened_day"]) + travel, int(peril["deadline_day"]) - 1)


# --- vaga do diretor (R14) ---------------------------------------------------------


def try_slot(dsim: dict | None, peril: dict, day: int) -> bool:
    """Perigo maior abre de verdade (ocupa a vaga) a partir de `earliest_day`."""
    if not peril.get("major") or dsim is None:
        return True
    if peril.get("slot_day") is not None:
        return True
    if int(day) < int(peril["earliest_day"]):
        return False
    if wd.request_crisis_slot(dsim, day, str(peril["region_id"]), wd.NPC_PERIL_KIND):
        peril["slot_day"] = int(day)
        return True
    return False


def end_slot(dsim: dict | None, peril: dict, day: int, resolution: str) -> None:
    if dsim is None or not peril.get("crisis_id"):
        return
    for rec in dsim.get("crises", []):
        if rec.get("crisis_id") == peril["crisis_id"] and rec.get("end_day") is None:
            wd.end_crisis(dsim, rec, day, resolution)


# --- intervenção (R16) e destino (R17/R18) -----------------------------------------


def check_intervention(state: dict, peril: dict, day: int, player_ref_loc: str) -> bool:
    """O jogador chegou ao local do perigo, ou (companheiro) o chamou de volta."""
    del day
    if at_player(player_ref_loc, str(peril.get("location_id") or "")):
        return True
    from services.companion_soul import comp_id

    for comp in (state or {}).get("party") or []:
        if isinstance(comp, dict) and comp_id(comp) == peril.get("npc_id"):
            return bool(comp.get("active"))
    return False


def perceived(peril: dict, day: int) -> bool:
    """R17: o telegrama foi percebido pelo menos 1 dia de jogo antes do prazo."""
    pd = peril.get("perceived_day")
    return pd is not None and int(pd) <= int(peril["deadline_day"]) - 1


def lethal_allowed(peril: dict, sim: dict, day: int, slot_ok: bool) -> bool:
    if peril.get("major") and (not perceived(peril, day) or not slot_ok):
        return False
    if peril.get("leader"):
        last = sim.get("last_leader_death_day")
        if last is not None and int(day) - int(last) < int(const("LEADER_DEATH_GAP_DAYS")):
            return False
    return True


def pick_fate(peril: dict, rng: Any, *, lethal: bool) -> str:
    c = cfg()
    weights = dict(c["fate_weights"].get(peril.get("kind"), c["fate_weights"]["emboscada"]))
    step = float(c.get("danger_morto_step", 0.0))
    weights["morto"] = float(weights.get("morto", 0)) * (
        1.0 + step * max(0, int(peril.get("danger", 3)) - 3)
    )
    if not lethal:
        weights["morto"] = 0
    roll = rng.random()
    total = sum(float(weights.get(f, 0)) for f in FATES)
    if total <= 0:
        return "escapou"
    acc = 0.0
    for fate in FATES:
        acc += float(weights.get(fate, 0)) / total
        if roll < acc:
            return fate
    return "escapou"


def fate_events(
    state: dict,
    peril: dict,
    fate: str,
    day: int,
    *,
    graph_npc: bool,
    captor: str = "",
) -> list[dict]:
    """Eventos do destino (R18). Morte de NPC do grafo = `npc_killed` (caminho canônico);
    demais (inclui NPC gerado) = `npc_offscreen_fate`. Ator: "world" ou a facção captora."""
    game_id = str((state or {}).get("game_id", ""))
    npc = str(peril["npc_id"])
    base = {
        "offscreen": True,
        "peril_id": peril["peril_id"],
        "location_id": peril["location_id"],
        "cause": peril["kind"],
        "fate": fate,
        "day": int(day),
    }
    if fate == "morto" and graph_npc:
        return [engine_event(game_id, day, "npc_killed", npc, base, extra=peril["peril_id"])]
    payload = dict(base)
    actor = "world"
    if fate == "ferido":
        payload["until_day"] = int(day) + int(const("WOUND_DAYS"))
    elif fate == "capturado":
        payload["captor_faction_id"] = captor
        payload["held_at_location_id"] = peril["location_id"]
        actor = captor or "world"
    return [
        engine_event(
            game_id, day, "npc_offscreen_fate", npc, payload, actor=actor, extra=peril["peril_id"]
        )
    ]


def resolve(
    state: dict,
    peril: dict,
    day: int,
    rng: Any,
    *,
    sim: dict,
    dsim: dict | None,
    graph_npc: bool,
    companion: bool,
    captor: str = "",
) -> tuple[dict, list[dict], dict]:
    """Sorteia e aplica o destino no `deadline_day` (R18). `(perigo, eventos, patch SPEC-300)`.

    Companheiro afastado passa por `apply_companion_fate` (recusa sem telegrama -> vira
    intervenção, R16). Nunca lê o jogador; só o chamador garante que ele não está no local."""
    slot_ok = try_slot(dsim, peril, day)
    lethal = lethal_allowed(peril, sim, day, slot_ok)
    fate = pick_fate(peril, rng, lethal=lethal)
    patch: dict = {}
    events: list[dict] = []
    if companion:
        from services import companion_soul as cs

        if fate in ("ferido", "capturado", "morto"):
            try:
                patch = cs.apply_companion_fate(state, str(peril["npc_id"]), fate, day)
            except cs.FateNotTelegraphed:
                peril["resolution"] = "intervencao"
                peril["resolved_day"] = int(day)
                return peril, [], {}
            patch.pop("chronicle", None)  # a morte só entra na crônica quando PERCEBIDA (R23)
    events = fate_events(state, peril, fate, day, graph_npc=graph_npc, captor=captor)
    peril["resolution"] = fate
    peril["resolved_day"] = int(day)
    end_slot(dsim, peril, day, "recuperou")
    return peril, events, patch
