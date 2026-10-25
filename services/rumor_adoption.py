"""services/rumor_adoption.py — SPEC-315: o motor adota a alegacao de um boato.

A LLM propoe um boato (SPEC-312) e, opcionalmente, uma ``RumorClaim`` num vocabulario FECHADO
(esconderijo, item_perdido, perigo_na_estrada, criatura_avistada, npc_em_local). Aqui o Python:

1. valida a alegacao (local real e distante, cânone, segredo, anti-direcao, orcamento);
2. sorteia a verdade UMA vez (``day_rng``), com vies so do estado do MUNDO (nunca do heroi);
3. se verdadeira, materializa exatamente uma vez pelos writers que ja existem (achado de
   exploracao, encontro forcado, agenda de NPC) — so quando o heroi chega/investiga;
4. falsa nunca materializa.

Puro: sem LLM e sem ``random`` global. Dono do ``world_sim.rumors`` continua ``services.rumors``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from observability.telemetry import log_event

MODES = ("off", "shadow", "on")
DEFAULT_MODE = "shadow"  # D7: shadow ate o smoke real
KINDS = ("esconderijo", "item_perdido", "perigo_na_estrada", "criatura_avistada", "npc_em_local")
LOOT_KINDS = ("esconderijo", "item_perdido")
ENCOUNTER_KINDS = ("perigo_na_estrada", "criatura_avistada")
_DATA = Path(__file__).resolve().parent.parent / "data" / "world"


# --- modo e dados -------------------------------------------------------------------


def mode() -> str:
    """`RPG_RUMORS_ADOPTED`; exige `RPG_RUMORS=on` e `RPG_RUMORS_PROPOSED=on` (senao `off`)."""
    raw = os.getenv("RPG_RUMORS_ADOPTED", "").strip().lower()
    m = raw if raw in MODES else DEFAULT_MODE
    if m == "off":
        return "off"
    from services import rumors

    if rumors.mode() != "on" or rumors.proposed_mode() != "on":
        return "off"
    return m


@lru_cache(maxsize=1)
def config() -> dict:
    return json.loads((_DATA / "rumor_adopt_config.json").read_text(encoding="utf-8"))


def const(name: str) -> Any:
    return config()["constants"][name]


def _get(o: Any, key: str, default: Any = "") -> Any:
    return o.get(key, default) if isinstance(o, dict) else getattr(o, key, default)


def claim_dict(claim: Any) -> dict:
    """Forma interna e minima da alegacao (so os 3 campos do vocabulario fechado)."""
    return {
        "kind": str(_get(claim, "kind") or ""),
        "location_id": str(_get(claim, "location_id") or ""),
        "entity_id": str(_get(claim, "entity_id") or ""),
    }


def _sim(state: dict) -> dict:
    return (state or {}).get("world_sim") or {}


def _day_of(state: dict) -> int:
    return int((((state or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)


def _here(state: dict) -> str:
    return str((((state or {}).get("world")) or {}).get("current_location_id") or "")


def _fold(text: str) -> str:
    from services.rumors import _fold as f

    return f(text)


def _loc(location_id: str) -> dict:
    from services import world_pressures as wp

    return wp._map_index()[0].get(location_id) or {}


def _entity(eid: str) -> dict:
    from services import graph_resolver as gr

    ent = gr.get_entity(eid)
    return ent if isinstance(ent, dict) else {}


# --- fação secreta (gate da SPEC-314) ------------------------------------------------


def _faction_hidden(state: dict, fid: str) -> bool:
    """True se `fid` e fação secreta que o jogador ainda nao conhece (R7, gate da SPEC-314)."""
    from services import faction_gate

    return faction_gate.is_secret(fid) and not faction_gate.known_to_player(state, fid)


def _is_faction(eid: str) -> bool:
    return str(_entity(eid).get("type") or "") == "faction"


# --- validacao (R3-R9, R12, R13) -----------------------------------------------------


def _recent_player_inputs(state: dict) -> list[str]:
    from langchain_core.messages import HumanMessage

    n = int(const("STEER_INPUTS"))
    msgs = [m for m in (state or {}).get("messages") or [] if isinstance(m, HumanMessage)]
    return [str(m.content or "") for m in msgs[-n:]]


def _npc_row(state: dict, ref: str) -> tuple[str, dict]:
    from services import npc_world

    return npc_world._row_for(state, ref)


def _npc_unavailable(state: dict, ref: str) -> bool:
    """R5 npc_em_local: morto, capturado, party, escolta, perigo aberto, lider ou fora do elenco."""
    from services import npc_perils, npc_world

    if npc_world.mode() != "on" or npc_world.is_leader(ref):
        return True
    key, row = _npc_row(state, ref)
    sim = (state or {}).get(npc_world.sim_key()) or {}
    entry = (sim.get("npcs") or {}).get(ref)
    if not isinstance(entry, dict) or entry.get("dead") or entry.get("escort"):
        return True
    if npc_world._is_dead(state, ref, row, sim) or npc_world.dead_graph_npc(
        state, row or {"id": ref}
    ):
        return True
    if str((row or {}).get("status") or "") == "capturado" or entry.get("status") == "capturado":
        return True
    if entry.get("status") or entry.get("frozen"):
        return True
    if ref in npc_world._party_by_id(state) or npc_perils.has_open(sim, ref):
        return True
    return False


def _entity_known(state: dict, kind: str, eid: str) -> bool:
    import gamedata

    if kind == "criatura_avistada":
        return eid in (gamedata.BESTIARY or {})
    ent = _entity(eid)
    if str(ent.get("type") or "") == "npc":
        return True
    _k, row = _npc_row(state, eid)
    return bool(row)


def _canon_reason(state: dict, claim: dict, day: int) -> str:
    import gamedata
    from encounter_budget import is_boss
    from services import rumors

    kind, loc_id, eid = claim["kind"], claim["location_id"], claim["entity_id"]
    world = (state or {}).get("world") or {}
    if kind in LOOT_KINDS:
        if loc_id in (world.get("looted_locations") or []) or _loc(loc_id).get("treasure"):
            return "canon"
        for r in _sim(state).get("rumors") or []:
            c = r.get("claim") if isinstance(r, dict) else None
            if (
                isinstance(c, dict)
                and c.get("kind") in LOOT_KINDS
                and c.get("location_id") == loc_id
                and not r.get("resolution")
                and int(r.get("expires_day", 0)) >= int(day)
            ):
                return "canon"
    elif kind == "perigo_na_estrada":
        if rumors._settlement(loc_id):
            return "canon"
    elif kind == "criatura_avistada":
        entry = (gamedata.BESTIARY or {}).get(eid) or {}
        if not entry or is_boss(entry):
            return "canon"
    elif kind == "npc_em_local":
        if _npc_unavailable(state, eid):
            return "canon"
    return ""


def _secret_reason(state: dict, claim: dict) -> str:
    from services import memory_provenance as mp
    from services.world_validators import canonical_secret_detail

    loc_id, eid = claim["location_id"], claim["entity_id"]
    proj = (state or {}).get("world_projection") or {}
    for gid in (loc_id, eid):
        if not gid:
            continue
        ent = _entity(gid)
        if ent and str(ent.get("visibility") or "public") != "public":
            return "secret"
        if gid == eid and ent and canonical_secret_detail(gid, proj):
            return "secret"  # a entidade tem aresta oculta (lugar so tem a visibilidade)
    names = " ".join(
        str(n)
        for n in (
            _loc(loc_id).get("name"),
            _entity(eid).get("name") if eid else "",
        )
        if n
    )
    if names and mp.find_strict_unrevealed(names, state or {}):
        return "secret"
    # R7: fação (ou NPC de fação) secreta e desconhecida do jogador
    if eid:
        fid = eid if _is_faction(eid) else ""
        if not fid and claim["kind"] == "npc_em_local":
            from services import npc_world

            fid = npc_world.npc_faction(state, eid)
        if fid and _faction_hidden(state, fid):
            return "secret"
    return ""


def validate_claim(state: dict, claim: Any, day: int, *, quarantined: bool = False) -> str:
    """ "" (valida) ou o motivo da rejeicao. Nunca levanta."""
    from services import world_distance
    from services import world_perception as wperc

    if quarantined:
        return "quarantine"
    c = claim_dict(claim)
    kind, loc_id, eid = c["kind"], c["location_id"], c["entity_id"]
    if kind not in KINDS:
        return "kind"
    if not loc_id or not _loc(loc_id):
        return "location"
    wants_entity = kind in ("criatura_avistada", "npc_em_local")
    if wants_entity != bool(eid) or (wants_entity and not _entity_known(state, kind, eid)):
        return "entity_kind"
    here = _here(state)
    if not here or loc_id in wperc._family(here):
        return "here"
    if world_distance.travel_periods(here, loc_id) is None:
        return "unreachable"
    bad = _canon_reason(state, c, day)
    if bad:
        return bad
    bad = _secret_reason(state, c)
    if bad:
        return bad
    if kind in LOOT_KINDS:
        from services.shared_pool import name_typed_by_player

        if name_typed_by_player(str(_loc(loc_id).get("name") or ""), _recent_player_inputs(state)):
            return "player_steered"
    return _budget_reason(state, c, day)


def _budget_reason(state: dict, claim: dict, day: int) -> str:
    """R12/R13: mesmo intervalo da 312 + tetos proprios; achado verdadeiro limitado ANTES do sorteio."""
    from services import rumors

    sim = _sim(state)
    last = int(sim.get("rumor_last_perceived_day", 0) or 0)
    if last and int(day) - last < int(rumors.const("RUMOR_MIN_GAP_DAYS")):
        return "gap"
    window = int(const("ADOPT_WINDOW_DAYS"))
    recent = [int(d) for d in sim.get("adopt_log") or [] if int(day) - int(d) < window]
    if len(recent) >= int(const("ADOPTED_PER_WINDOW")):
        return "budget"
    rows = [r for r in sim.get("rumors") or [] if isinstance(r, dict) and r.get("adopted")]
    active = [r for r in rows if not r.get("resolution") and int(r.get("expires_day", 0)) >= day]
    if len(active) >= int(const("ADOPTED_ACTIVE_MAX")):
        return "budget"
    if claim["kind"] in LOOT_KINDS:
        span = int(const("LOOT_WINDOW_DAYS"))
        finds = [int(d) for d in sim.get("find_log") or [] if int(day) - int(d) < span]
        if len(finds) >= int(const("LOOT_TRUE_PER_WINDOW")):
            return "budget"
    return ""


# --- verdade (R10/R11) ----------------------------------------------------------------


def _region_of(location_id: str) -> str:
    from services import world_pressures as wp

    return wp.region_of(location_id)


def _npc_arrives_in_ttl(state: dict, ref: str, loc_id: str, day: int) -> bool:
    from services import npc_world
    from services import rumors as rum

    sim = (state or {}).get(npc_world.sim_key()) or {}
    entry = (sim.get("npcs") or {}).get(ref) or {}
    pos = entry.get("pos") or {}
    src = str(pos.get("location_id") or pos.get("travel_to") or "")
    if not src:
        return False
    if src == loc_id:
        return True
    arrive, ok = npc_world._travel(src, loc_id, int(day))
    return bool(ok and arrive is not None and arrive <= int(day) + int(rum.const("RUMOR_TTL_DAYS")))


def truth_p(state: dict, claim: Any, day: int | None = None) -> float:
    """Probabilidade de a alegacao ser verdadeira. NUNCA le o heroi (nivel, ouro, ficha)."""
    c = claim_dict(claim)
    kind, loc_id, eid = c["kind"], c["location_id"], c["entity_id"]
    p = float(config()["truth_base"].get(kind, 0.0))
    d = _day_of(state) if day is None else int(day)
    if kind == "perigo_na_estrada":
        region = _region_of(loc_id)
        band = ((_sim(state).get("bands") or {}).get(region) or {}).get("guerra", "normal")
        proj = (state or {}).get("world_projection") or {}
        blocked = any(loc_id in (r.get("a"), r.get("b")) for r in proj.get("blocked_routes") or [])
        if band in ("sinal", "crise") or blocked:
            p += float(const("ROAD_WAR_BONUS"))
        p = min(p, float(const("TRUTH_CAP")))
    elif kind == "criatura_avistada":
        import gamedata
        from services import ecology

        region = _region_of(loc_id)
        entry = (gamedata.BESTIARY or {}).get(eid) or {}
        if region not in (entry.get("regions") or []):
            return 0.0
        turn = int((((state or {}).get("world")) or {}).get("turn_count", 0) or 0)
        if eid in ecology.suppressed_creatures(
            region, gamedata.BESTIARY or {}, (state or {}).get("bestiary_knowledge"), turn
        ):
            return 0.0
    elif kind == "npc_em_local":
        if not _npc_arrives_in_ttl(state, eid, loc_id, d):
            return 0.0
    return max(0.0, min(1.0, p))


def _playtest_forced() -> bool:
    """`world_sim["forced_adopt"]` so vale no harness (`RPG_PLAYTEST_FORCED_ADOPT=1`)."""
    return os.getenv("RPG_PLAYTEST_FORCED_ADOPT", "").strip() == "1"


def _truth_roll(state: dict, rumor_id: str, day: int, claim: dict) -> bool:
    from services.world_engine import day_rng

    forced_rows = _sim(state).get("forced_adopt") if _playtest_forced() else None
    for forced in forced_rows or []:  # cenario dirigido do playtest
        if (
            isinstance(forced, dict)
            and forced.get("kind") == claim["kind"]
            and forced.get("location_id") == claim["location_id"]
        ):
            return bool(forced.get("truth"))

    rng = day_rng(str((state or {}).get("game_id") or ""), int(day), "rumor_adopt:" + rumor_id)
    return rng.random() < truth_p(state, claim, day)


# --- adocao ---------------------------------------------------------------------------


def adopt(state: dict, inst: dict, claim: Any, day: int) -> tuple[dict, dict | None]:
    """`(instancia, npc_sim novo | None)`. `off`/rejeitada/`shadow`: a instancia volta como a da
    312 (falsa, sem quest). `on` aceita: grava `claim`, `adopted`, `truth` sorteada UMA vez."""
    m = mode()
    if m == "off" or claim is None:
        return inst, None
    c = claim_dict(claim)
    log_event("rumor_adopt", "proposed", level="info", kind=c["kind"])
    why = validate_claim(state, c, day)
    if why:
        log_event("rumor_adopt", "rejected", level="info", kind=c["kind"], reason=why)
        return inst, None
    truth = _truth_roll(state, str(inst.get("rumor_id")), day, c)
    if m == "shadow":
        log_event("rumor_adopt", "shadow", level="info", kind=c["kind"], truth=truth, reason="")
        return inst, None
    out = {
        **inst,
        "claim": c,
        "adopted": True,
        "truth": bool(truth),
        "quest_eligible": True,
        "location_id": c["location_id"],
        "materialized_day": 0,
    }
    log_event("rumor_adopt", "adopted", level="info", kind=c["kind"])
    npc_sim = None
    if truth and c["kind"] == "npc_em_local":
        from services import npc_world

        base = dict((state or {}).get(npc_world.sim_key()) or {})
        npc_sim = npc_world.schedule_visit(
            base,
            c["entity_id"],
            c["location_id"],
            int(day),
            int(out["expires_day"]),
            out["rumor_id"],
        )
    return out, npc_sim


def process(state: dict, proposal: Any, inst: dict, day: int, extra: dict) -> dict:
    """Gancho de `rumors._apply_proposal`: adota a alegacao do `ProposedRumor` (se houver).
    `extra` recebe `npc_sim` (agenda de NPC) e `adopted` (para o `adopt_log`)."""
    claim = _get(proposal, "claim", None)
    if claim is None:
        return inst
    new, npc_sim = adopt(state, inst, claim, day)
    if npc_sim is not None:
        extra["npc_sim"] = npc_sim
        extra["npc_sim_key"] = _npc_sim_key()
    if new.get("adopted"):
        extra["adopted"] = True
    return new


def _npc_sim_key() -> str:
    from services import npc_world

    return npc_world.sim_key()


# --- materializacao (R14-R20) -----------------------------------------------------------


def _is_search(text: str) -> bool:
    low = _fold(text)
    return any(v in low for v in config()["search_vocab"])


def search_intent(text: str) -> bool:
    return _is_search(text or "")


def nothing_found(state: dict, location_id: str, text: str) -> bool:
    """True se o heroi BUSCA no alvo de uma alegacao de achado adotada que NAO entrega nada agora
    (falsa, ou verdadeira ainda fora da janela/gatilho). O narrador recebe o fato "nada aqui"."""
    if mode() != "on" or not _is_search(text or ""):
        return False
    from services import world_perception as wperc

    for r in _sim(state).get("rumors") or []:
        if not isinstance(r, dict) or not r.get("adopted") or r.get("materialized_day"):
            continue
        c = r.get("claim") or {}
        if c.get("kind") in LOOT_KINDS and location_id in wperc._family(
            str(c.get("location_id") or "")
        ):
            return True
    return False


def _has_investigation_quest(state: dict, rumor_id: str) -> bool:
    for q in (state or {}).get("quests") or []:
        if (
            isinstance(q, dict)
            and q.get("world_kind") == "investigar_rumor"
            and str(q.get("status") or "active") == "active"
            and str((q.get("lore_anchor") or {}).get("id") or "") == rumor_id
        ):
            return True
    return False


def _still_valid(state: dict, inst: dict) -> bool:
    """R19: nada contradiz a projection entre a adocao e a chegada."""
    from services import npc_world, rumors

    c = inst.get("claim") or {}
    kind, loc_id, eid = c.get("kind"), c.get("location_id"), c.get("entity_id")
    world = (state or {}).get("world") or {}
    if kind in LOOT_KINDS:
        return loc_id not in (world.get("looted_locations") or [])
    if kind == "criatura_avistada":
        return not rumors._entity_dead(state, str(eid))
    if kind == "npc_em_local":
        key, row = _npc_row(state, str(eid))
        sim = (state or {}).get(npc_world.sim_key()) or {}
        entry = (sim.get("npcs") or {}).get(eid) or {}
        return (
            bool(entry.get("rumor_visit"))
            and not npc_world._is_dead(state, str(eid), row, sim)
            and npc_world.present_here(state, key or str(eid), str(loc_id))
        )
    return True


def due_materialization(
    state: dict, trigger: str, location_id: str, day: int, text: str = ""
) -> dict | None:
    """Instancia que materializa AGORA (ou None). Verdadeira, adotada, nunca materializada, dentro
    da janela `born_day + 1 .. expires_day`, no gatilho certo (R14/R18). Nunca devolve falsa."""
    if mode() != "on":
        return None
    from services import world_perception as wperc

    for r in _sim(state).get("rumors") or []:
        if not isinstance(r, dict) or not r.get("adopted") or not r.get("truth"):
            continue
        if r.get("materialized_day") or r.get("resolution"):
            continue
        if not int(r.get("born_day", 0)) < int(day) <= int(r.get("expires_day", 0)):
            continue
        c = r.get("claim") or {}
        kind, target = str(c.get("kind") or ""), str(c.get("location_id") or "")
        if not target or location_id not in wperc._family(target):
            continue
        if kind in LOOT_KINDS:
            ok = trigger == "quest" and _has_investigation_quest(state, str(r.get("rumor_id")))
            ok = ok or (trigger == "search" and _is_search(text))
        elif kind in ENCOUNTER_KINDS:
            ok = trigger == "travel"
        elif kind == "npc_em_local":
            ok = trigger in ("travel", "present")  # herói chegou, ou o NPC chegou depois
        else:
            ok = False
        if ok and _still_valid(state, r):
            return r
    return None


TIER_ORDER = ("comum", "bom", "raro", "excepcional")


def find_tier(state: dict, inst: dict, loc: dict) -> str:
    """Loteria do TAMANHO do achado (D6): 1 sorteio por `day_rng` (chave da familia do sorteio de
    verdade, outro sal), sobe 1 degrau em local de perigo alto. Nunca le o heroi."""
    from services.world_engine import day_rng

    tiers = config()["find_tiers"]
    rng = day_rng(
        str((state or {}).get("game_id") or ""),
        int(inst.get("born_day", 0) or 0),
        "rumor_tier:" + str(inst.get("rumor_id")),
    )
    total = sum(float(tiers[t]["weight"]) for t in TIER_ORDER)
    u, acc, pick = rng.random() * total, 0.0, TIER_ORDER[-1]
    for t in TIER_ORDER:
        acc += float(tiers[t]["weight"])
        if u < acc:
            pick = t
            break
    if int((loc or {}).get("danger", 1) or 1) >= int(const("DANGER_TIER_BUMP_AT")):
        pick = TIER_ORDER[min(len(TIER_ORDER) - 1, TIER_ORDER.index(pick) + 1)]
    return pick


def materialize(state: dict, inst: dict, day: int) -> tuple[dict, dict]:
    """Achado (`esconderijo`/`item_perdido`) ou chegada ao NPC agendado. Devolve
    `(updates, instancia marcada)`; updates: `player`, `world`, `note`, `events` (claim de unico).
    Encontros usam `encounter_hint` + `commit` (so contam quando o encontro realmente dispara)."""
    from copy import deepcopy

    from services import exploration
    from services.world_engine import day_rng

    c = inst.get("claim") or {}
    kind = str(c.get("kind") or "")
    mat: dict = {"kind": "npc", "npc_ref": str(c.get("entity_id") or "")}
    updates: dict = {}
    if kind in LOOT_KINDS:
        player = deepcopy((state or {}).get("player") or {})
        world = deepcopy((state or {}).get("world") or {})
        loc = _loc(str(c.get("location_id") or ""))
        rng = day_rng(
            str((state or {}).get("game_id") or ""),
            int(day),
            "rumor_cache:" + str(inst["rumor_id"]),
        )
        tier_id = find_tier(state, inst, loc)
        note, got = exploration.grant_rumor_cache(
            player,
            world,
            loc,
            rng,
            kind=kind,
            projection=(state or {}).get("world_projection"),
            gold_max=int(const("ADOPTED_GOLD_MAX")),
            bestiary_knowledge=(state or {}).get("bestiary_knowledge"),
            turn=int((world or {}).get("turn_count", 0) or 0),
            tier=config()["find_tiers"][tier_id],
            tier_id=tier_id,
        )
        events = list(got.pop("_events", []) or [])
        updates = {"player": player, "world": world, "note": note, "events": events}
        mat = {"kind": "cache", **got}
    marked = {**inst, "materialized_day": int(day), "materialization": mat}
    return updates, marked


def encounter_hint(
    state: dict, inst: dict, world: dict, player_level: int, turn: int
) -> dict | None:
    """`rumor_hint` de `check_encounter` (forma do `law_hint`). A forca vem de
    `forced_encounter_danger` (escala pelo nivel; apex nao). Sem criatura valida -> None."""
    import gamedata
    from world_utils import effective_danger, forced_encounter_danger, pick_encounter_enemy

    c = inst.get("claim") or {}
    kind = str(c.get("kind") or "")
    loc = gamedata.get_location(str(world.get("current_location_id") or "")) or {}
    eff = forced_encounter_danger(loc, effective_danger(world), player_level)
    if kind == "criatura_avistada":
        entry = (gamedata.BESTIARY or {}).get(str(c.get("entity_id") or ""))
    else:
        from services.world_engine import day_rng

        rng = day_rng(
            str((state or {}).get("game_id") or ""),
            int(((world.get("world_clock") or {}).get("day", 1)) or 1),
            "rumor_enc:" + str(inst.get("rumor_id")),
        )
        entry = pick_encounter_enemy(
            loc,
            eff,
            turn,
            bestiary_knowledge=(state or {}).get("bestiary_knowledge"),
            projection=(state or {}).get("world_projection"),
            rng=rng,
        )
    if not entry:
        return None
    name = str(entry.get("name") or entry.get("id") or "")
    return {
        "hint": name,
        "flavor": f"O que diziam era verdade: {name} rondava justamente por aqui.",
        "reason": "rumor",
        "enemy_id": str(entry.get("id") or ""),
        "eff_danger": int(eff),
        "rumor_id": str(inst.get("rumor_id") or ""),
        "always_combat": kind == "criatura_avistada",
    }


def commit(sim: dict, rumor_id: str, day: int, materialization: dict) -> dict:
    """Marca a materializacao (writer unico: `rumors.mark_materialized`)."""
    from services import rumors

    out = rumors.mark_materialized(sim, rumor_id, day, materialization)
    if out is not sim:
        log_event(
            "rumor_adopt", "materialized", level="info", kind=str(materialization.get("kind") or "")
        )
    return out


# --- resolucao (R22) --------------------------------------------------------------------


def resolve_outcome(inst: dict) -> str:
    """confirmado|desmentido|inconclusivo. Adotada: falsa = desmentido; verdadeira so confirma se
    materializou. Nao adotada (312/semente): a verdade decide."""
    truth = bool(inst.get("truth"))
    if not inst.get("adopted"):
        return "confirmado" if truth else "desmentido"
    if not truth:
        return "desmentido"
    return "confirmado" if inst.get("materialized_day") else "inconclusivo"
