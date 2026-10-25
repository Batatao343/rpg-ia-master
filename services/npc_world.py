"""SPEC-304: NPCs off-screen — agenda, viagem, troca de lado e morte telegrafada.

OWNER CANONICO de `npc_sim` (verdade: posição, perigos, destinos) e `npc_beliefs` (o que o
JOGADOR sabe). Roda como hook `post` do tick diário da SPEC-302 (`world_engine`), em Python
puro e seeded por `(game_id, dia, npc, propósito)`. A LLM não decide nada aqui: o digest que
este módulo produz é narrado pela chamada diária da SPEC-302 (`narrate_day`), sem chamada nova.

Regra de ouro (não-onisciência): API, dossiê, crônica e contexto do narrador leem a CRENÇA
(`belief_view`/`event_hidden_from_player`), nunca a verdade de `npc_sim`.

Modos `RPG_NPC_WORLD=off|shadow|on` (exige `RPG_WORLD_ENGINE=on`):
  off     no-op byte a byte;
  shadow  simula e grava em `npc_sim_shadow`, sem eventos, sem digest, sem efeito em cena/API;
  on      tudo ligado.
O hook nunca lê nível, ficha, inventário nem ouro do herói; a posição dele só entra na
intervenção (R16), na percepção e para NUNCA expor/matar NPC no local dele.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import unicodedata
from functools import lru_cache
from typing import Any

from services import npc_perils as perils
from services import world_director as wd
from services import world_pressures as wp

MODES = ("off", "shadow", "on")
DEFAULT_MODE = "off"
SIM_VERSION = 1
OFFSCREEN_TYPES = frozenset({"npc_peril_warning", "npc_offscreen_fate", "npc_defected"})
NPC_KINDS = ("npc_perigo", "npc_destino", "npc_ausente", "npc_resgate", "npc_lado")
_STATUS_BY_FATE = {"morto": "morto", "capturado": "capturado", "ferido": "ferido", "escapou": ""}


# --------------------------------------------------------------------------- #
# Modo e dados
# --------------------------------------------------------------------------- #
def mode() -> str:
    """`RPG_NPC_WORLD` efetivo: com o motor de mundo != on, a spec fica `off` (R29)."""
    raw = os.getenv("RPG_NPC_WORLD", "").strip().lower()
    m = raw if raw in MODES else DEFAULT_MODE
    if m == "off":
        return "off"
    from services import world_engine

    return m if world_engine.mode() == "on" else "off"


def sim_key(m: str | None = None) -> str:
    return "npc_sim" if (m or mode()) == "on" else "npc_sim_shadow"


def _const(name: str) -> Any:
    return perils.const(name)


def _cfg() -> dict:
    return perils.cfg()


def _agendas() -> dict:
    return wp._load_json("npc_agendas.json")


def _templates() -> dict:
    return wp._load_json("npc_templates.json")["templates"]


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(ch)
    ).strip()


def _day_of(world: dict | None) -> int:
    return int((((world or {}).get("world_clock")) or {}).get("day", 1) or 1)


def _rng(game_id: str, day: int, ref: str, purpose: str):
    from services.world_engine import day_rng

    return day_rng(game_id, day, f"npc:{ref}:{purpose}")


# --------------------------------------------------------------------------- #
# Identidade, grafo e lugares
# --------------------------------------------------------------------------- #
def npc_ref(key: str, row: dict | None) -> str:
    return str((row or {}).get("id") or key)


@lru_cache(maxsize=1)
def leaders() -> dict[str, str]:
    """npc_id -> faction_id (arestas `leads`, 21 líderes)."""
    from services import graph_resolver as gr

    return {
        str(e.get("source")): str(e.get("target"))
        for e in gr.resolve_edges({}, edge_type="leads", include_hidden=True)
    }


def is_leader(ref: str) -> bool:
    return ref in leaders()


def graph_entity(ref: str) -> dict | None:
    from services import graph_resolver as gr

    ent = gr.get_entity(ref)
    return ent if isinstance(ent, dict) and ent.get("type") == "npc" else None


@lru_cache(maxsize=1)
def _loc_name_index() -> dict[str, str]:
    out: dict[str, str] = {}
    for lid, loc in wp._map_index()[0].items():
        out.setdefault(_fold(loc.get("name", "")), lid)
        out.setdefault(_fold(lid), lid)
    return out


def resolve_location_ref(ref: str) -> str:
    """P6: `waiting_at` guarda o NOME de exibição; devolve o `location_id` (ou "")."""
    text = str(ref or "").strip()
    if not text:
        return ""
    locs = wp._map_index()[0]
    if text in locs:
        return text
    return _loc_name_index().get(_fold(text), "")


def _row_for(state: dict, ref_or_key: str) -> tuple[str, dict]:
    npcs = (state or {}).get("npcs") or {}
    if ref_or_key in npcs and isinstance(npcs[ref_or_key], dict):
        return str(ref_or_key), npcs[ref_or_key]
    for key, row in npcs.items():
        if isinstance(row, dict) and npc_ref(str(key), row) == ref_or_key:
            return str(key), row
    return "", {}


def _party(state: dict) -> list[dict]:
    return [c for c in (state or {}).get("party") or [] if isinstance(c, dict)]


def _party_id(comp: dict) -> str:
    from services.companion_soul import comp_id

    return comp_id(comp) or str(comp.get("name") or "")


def _party_by_id(state: dict) -> dict[str, dict]:
    return {_party_id(c): c for c in _party(state)}


def home_of(state: dict, ref: str) -> str:
    """Casa (location_id): ficha runtime -> componente do grafo -> região da facção do líder."""
    _key, row = _row_for(state, ref)
    for cand in (
        row.get("home_location_id"),
        ((graph_entity(ref) or {}).get("components") or {}).get("home_location_id"),
    ):
        loc = resolve_location_ref(str(cand or ""))
        if loc:
            return loc
    fid = leaders().get(ref)
    if fid:
        import gamedata
        from services.world_engine import faction_region_id

        region = faction_region_id(gamedata.FACTIONS.get(fid) or {})
        return wp.region_primary_location(region) if region else ""
    return ""


def _is_faction(fid: str) -> bool:
    import gamedata
    from services import graph_resolver as gr

    if not fid:
        return False
    if fid in gamedata.FACTIONS:
        return True
    ent = gr.get_entity(fid)
    return bool(ent and ent.get("type") == "faction")


def npc_faction(state: dict, ref: str) -> str:
    """R10: override da projection -> ficha -> componente do grafo -> `leads`/`member_of`."""
    from services import graph_resolver as gr

    proj = (state or {}).get("world_projection") or {}
    aff = (proj.get("npc_affiliations") or {}).get(ref)
    if aff:
        return str(aff)
    _key, row = _row_for(state, ref)
    cand = str(row.get("faction") or "")
    if _is_faction(cand):
        return cand
    comp = str((((graph_entity(ref) or {}).get("components")) or {}).get("faction") or "")
    if _is_faction(comp):
        return comp
    if ref in leaders():
        return leaders()[ref]
    for e in gr.resolve_edges(proj, entity_id=ref, edge_type="member_of", include_hidden=True):
        if e.get("source") == ref:
            return str(e.get("target"))
    return ""


def archetype_for(state: dict, ref: str) -> str:
    c = _cfg()
    agendas = _agendas()
    if ref in c.get("agenda_by_npc", {}):
        return c["agenda_by_npc"][ref]
    _key, row = _row_for(state, ref)
    role = _fold(row.get("role") or ((graph_entity(ref) or {}).get("components") or {}).get("role"))
    for radical, arch in agendas.get("role_radicals", []):
        if radical in role:
            return arch
    return "sedentario"


# --------------------------------------------------------------------------- #
# Estado e elenco (R1/R28)
# --------------------------------------------------------------------------- #
def _new_sim(day: int) -> dict:
    return {
        "version": SIM_VERSION,
        "enabled_from_day": int(day),
        "roster": [],
        "roster_fingerprint": "",
        "npcs": {},
        "perils": [],
        "last_leader_death_day": None,
        "tick_log": [],
    }


def _sim_of(state: dict, day: int, key: str | None = None) -> dict:
    cur = (state or {}).get(key or sim_key())
    if isinstance(cur, dict) and cur.get("version") == SIM_VERSION:
        return copy.deepcopy(cur)
    return _new_sim(day)


def _is_dead(state: dict, ref: str, row: dict, sim: dict) -> bool:
    from services.npc_layers import npc_alive

    if row and not npc_alive(row):
        return True
    if (sim.get("npcs", {}).get(ref) or {}).get("dead"):
        return True
    ent = ((state.get("world_projection") or {}).get("entities") or {}).get(ref)
    return isinstance(ent, dict) and ent.get("alive") is False


def _candidates(state: dict, sim: dict) -> list[str]:
    """Candidatos em ordem de prioridade, SEM teto (R1). Morto não entra."""
    from services.reputation import npc_tier

    rows = {
        npc_ref(str(k), r): r for k, r in (state.get("npcs") or {}).items() if isinstance(r, dict)
    }
    out: list[str] = []

    def add(ref: str) -> None:
        if ref and ref not in out and not _is_dead(state, ref, rows.get(ref, {}), sim):
            out.append(ref)

    for comp in _party(state):
        add(_party_id(comp))
    loved = sorted(
        r
        for r, row in rows.items()
        if row.get("known_by_player", True)
        and npc_tier(row.get("relationship", 5)) in ("amistoso", "leal")
    )
    for r in loved:
        add(r)
    for r in sorted(leaders()):
        add(r)
    rest = sorted(
        (r for r, row in rows.items() if row.get("known_by_player", True)),
        key=lambda r: (-int(rows[r].get("last_seen_turn", 0) or 0), r),
    )
    for r in rest:
        add(r)
    for r in _cfg().get("key_npcs", []):
        add(r)
    return out


def roster(state: dict) -> list[str]:
    """R1: até `ROSTER_CAP` ids — party > queridos > líderes > conhecidos > chave."""
    sim = (state.get(sim_key()) if isinstance(state.get(sim_key()), dict) else None) or {}
    return _candidates(state, sim)[: int(_const("ROSTER_CAP"))]


def _refresh_roster(state: dict, sim: dict, day: int) -> list[str]:
    cands = _candidates(state, sim)
    fp = hashlib.sha256(json.dumps(cands, sort_keys=False).encode()).hexdigest()[:16]
    if fp != sim.get("roster_fingerprint"):
        new = cands[: int(_const("ROSTER_CAP"))]
        old = set(sim.get("roster") or [])
        for ref in old - set(new):  # saiu do elenco: congela (R1)
            if ref in sim["npcs"]:
                sim["npcs"][ref]["frozen"] = True
        sim["roster"], sim["roster_fingerprint"] = new, fp
    for ref in sim["roster"]:
        entry = sim["npcs"].get(ref)
        if entry is None:
            home = home_of(state, ref)
            entry = sim["npcs"][ref] = {
                "archetype": archetype_for(state, ref),
                "home": home,
                "pos": {"location_id": home, "since_day": int(day), "arrive_day": None},
                "status": "",
                "frozen": False,
            }
        else:
            entry["frozen"] = False
    return list(sim["roster"])


# --------------------------------------------------------------------------- #
# Posição (R7)
# --------------------------------------------------------------------------- #
def presence(state: dict, npc_key: str) -> tuple[str, bool]:
    """(location_id, em_viagem). Com o modo != on devolve a casa (legado)."""
    key, row = _row_for(state, npc_key)
    ref = npc_ref(key, row) if row else npc_key
    legacy = str((row or {}).get("home_location_id") or "")
    if mode() != "on":
        return legacy, False
    entry = ((state.get("npc_sim") or {}).get("npcs") or {}).get(ref)
    if entry is None or not entry.get("pos"):
        return legacy, False
    esc = entry.get("escort")
    if esc:  # SPEC-313 R22: escoltado viaja com o jogador (ou fica onde a escolta pausou)
        return str(esc.get("paused_at") or _player_loc(state) or esc.get("at") or ""), False
    pos = entry["pos"]
    loc = str(pos.get("location_id") or "")
    return loc, (not loc and pos.get("arrive_day") is not None)


def location_of(state: dict, npc_key: str) -> str:
    """Local simulado do NPC ("" = em viagem); fora do elenco/modo off, `home_location_id`."""
    return presence(state, npc_key)[0]


def reintroduction_block(state: dict, key: str, here: str) -> str:
    """R8: motivo pelo qual o narrador NÃO pode trazer o NPC conhecido para a cena ("" = livre).
    Membro ativo da party sempre pode (ele viaja com o herói)."""
    from services.npc_layers import npc_alive

    if mode() != "on":
        return ""
    _k, row = _row_for(state, key)
    if not row:
        return ""
    ref = npc_ref(key, row)
    comp = _party_by_id(state).get(ref)
    if comp is not None and comp.get("active"):
        return ""
    entry = ((state.get("npc_sim") or {}).get("npcs") or {}).get(ref) or {}
    if not npc_alive(row) or entry.get("dead"):
        return "dead"
    if str(row.get("status") or "") == "capturado" or entry.get("status") == "capturado":
        return "captured"
    if entry:
        where, travelling = presence(state, key)
        if travelling or (here and where and where != here):
            return "away"
    return ""


def log_reintroduction_blocked(reason: str) -> None:
    from observability.telemetry import log_event

    log_event("npc", "reintroduction_blocked", level="info", reason=reason)


def dead_graph_npc(state: dict, ref_row: dict) -> bool:
    """P3: NPC de grafo já morto na projection (mesmo fora de `state.npcs`) nunca volta vivo."""
    from services.entity_identity import resolve_npc_entity_id

    if mode() != "on":
        return False
    eid = resolve_npc_entity_id(ref_row, str(ref_row.get("name") or ""))
    if not eid:
        return False
    ent = ((state.get("world_projection") or {}).get("entities") or {}).get(eid)
    return isinstance(ent, dict) and ent.get("alive") is False


def present_here(state: dict, npc_key: str, loc: str) -> bool:
    """O NPC pode estar na cena do local `loc`? (legado: sem casa = qualquer lugar)."""
    where, travelling = presence(state, npc_key)
    if mode() != "on":
        return not where or not loc or where == loc
    if travelling:
        return False
    key, row = _row_for(state, npc_key)
    if not where:
        return not str((row or {}).get("home_location_id") or "") or not loc
    return not loc or where == loc


# --------------------------------------------------------------------------- #
# Hook diário
# --------------------------------------------------------------------------- #
def _work_state(ctx: Any) -> dict:
    st = dict(ctx.state or {})
    st["world"] = {**(st.get("world") or {}), **(ctx.world or {})}
    st["world_projection"] = ctx.projection
    st["world_sim"] = ctx.sim
    st["factions"] = ctx.factions or st.get("factions") or []
    return st


def _item(
    game_id: str, day: int, kind: str, region: str, loc: str, tpl: str, params: dict, sid: str
) -> dict:
    item = wd.digest_item(
        game_id,
        day,
        kind,
        region,
        loc,
        tpl,
        params,
        subject_id=sid,
        event_ids=[sid] if sid else None,  # SPEC-308 R1
    )
    item["item_id"] = wd._h(game_id, day, kind, params.get("npc_id", ""), tpl, sid, n=12)
    return item


def _travel(src: str, dst: str, day: int) -> tuple[int | None, bool]:
    """(dia de chegada, ok). `travel_periods` None = inalcançável."""
    from services import world_distance

    periods = world_distance.travel_periods(src, dst)
    if periods is None:
        return None, False
    return int(day) + math.ceil(periods / perils.PERIODS_PER_DAY), True


def _start_trip(entry: dict, dst: str, day: int, rng: Any, *, stay: list[int]) -> bool:
    pos = entry["pos"]
    src = str(pos.get("location_id") or "")
    arrive, ok = _travel(src, dst, day)
    if not ok:
        return False
    stay_days = rng.randint(int(stay[0]), int(stay[1]))
    if arrive <= day:
        entry["pos"] = {
            "location_id": dst,
            "since_day": int(day),
            "arrive_day": None,
            "return_day": int(day) + stay_days,
        }
    else:
        entry["pos"] = {
            "location_id": "",
            "travel_from": src,
            "travel_to": dst,
            "arrive_day": int(arrive),
            "since_day": int(day),
            "return_day": int(arrive) + stay_days,
        }
    return True


def _route_candidates(state: dict, entry: dict, ref: str, arch: dict, proj: dict) -> list[str]:
    locs = wp._map_index()[0]
    home = str(entry.get("home") or "")
    home_region = wp.region_of(home)
    regions = [home_region]
    route = arch.get("route")
    if route == "adjacent_regions":
        regions += wp.region_adjacency().get(home_region, [])
    elif route == "faction_locations":
        import gamedata
        from services.world_engine import faction_region_id

        fregion = faction_region_id(gamedata.FACTIONS.get(npc_faction(state, ref)) or {})
        regions += [fregion] if fregion else []
        regions += wp.region_adjacency().get(home_region, [])[:1]
    cands: set[str] = set()
    if route in ("adjacent_regions", "faction_locations"):
        cands |= {wp.region_primary_location(r) for r in regions if r}
    cands |= (
        {
            lid
            for lid, loc in locs.items()
            if loc.get("region_id") == home_region and loc.get("kind") != "interior"
        }
        if route == "home_region"
        else set()
    )
    avoid = set(arch.get("avoid_states") or [])
    rows = proj.get("location_states") or {}
    blocked = {frozenset((r.get("a"), r.get("b"))) for r in proj.get("blocked_routes") or []}
    cur = str(entry["pos"].get("location_id") or "")
    from services import location_states as ls

    out = []
    for lid in sorted(cands):
        if not lid or lid == cur or lid not in locs:
            continue
        if str((rows.get(ls._resolve_id(lid)) or {}).get("state") or "") in avoid:
            continue
        if frozenset((cur, lid)) in blocked:
            continue
        out.append(lid)
    return out


def _nearest_safe(state: dict, home: str, proj: dict) -> str:
    from services import location_states as ls
    from services import world_distance

    locs = wp._map_index()[0]
    home_region = wp.region_of(home)
    rows = proj.get("location_states") or {}
    best: tuple[int, str] | None = None
    for lid, loc in sorted(locs.items()):
        if loc.get("kind") == "interior" or loc.get("region_id") == home_region:
            continue
        if str((rows.get(ls._resolve_id(lid)) or {}).get("state") or "") in perils.CRISIS_STATES:
            continue
        d = world_distance.travel_periods(home, lid)
        if d is not None and (best is None or (d, lid) < best):
            best = (d, lid)
    return best[1] if best else ""


def _step_position(
    state: dict, ref: str, entry: dict, d: int, game_id: str, proj: dict, player_loc: str
) -> None:
    """R5/R6: agenda, viagem, fuga de crise. Nada vira GameEvent."""
    agendas = _agendas()["archetypes"]
    arch = agendas.get(entry.get("archetype") or "sedentario") or agendas["sedentario"]
    pos = entry["pos"]
    rng = _rng(game_id, d, ref, "agenda")
    r_leave, r_pick, r_flee = rng.random(), rng.random(), rng.random()
    home = str(entry.get("home") or "")
    if not home:
        return
    # em viagem: só chega
    if pos.get("arrive_day") is not None:
        if d >= int(pos["arrive_day"]):
            entry["pos"] = {
                "location_id": str(pos.get("travel_to") or ""),
                "since_day": int(d),
                "arrive_day": None,
                "return_day": pos.get("return_day"),
                **({"refugee_from": pos["refugee_from"]} if pos.get("refugee_from") else {}),
            }
        return
    cur = str(pos.get("location_id") or "")
    from services import location_states as ls

    home_state = str(
        ((proj.get("location_states") or {}).get(ls._resolve_id(home)) or {}).get("state") or ""
    )
    in_crisis = home_state in perils.CRISIS_STATES
    entry["calm_days"] = 0 if in_crisis else int(entry.get("calm_days", 0)) + 1
    if perils.at_player(player_loc, cur):
        return  # quem está na cena do herói não some no meio dela
    if pos.get("refugee_from"):
        if entry["calm_days"] >= int(_const("RETURN_AFTER_CALM_DAYS")):
            if _start_trip(entry, home, d, rng, stay=[1, 1]):
                entry["pos"].pop("refugee_from", None)
                entry["pos"]["return_day"] = None
        return
    if in_crisis and entry.get("archetype") != "lider_residente" and cur == home:
        if r_flee < float(_const("P_FLEE")):
            dst = _nearest_safe(state, home, proj)
            if dst and _start_trip(entry, dst, d, rng, stay=[1, 1]):
                entry["pos"]["refugee_from"] = home
        return
    if float(arch.get("p_leave", 0)) <= 0 and cur == home:
        return
    if cur == home:
        if r_leave < float(arch.get("p_leave", 0)):
            cands = _route_candidates(state, entry, ref, arch, proj)
            if cands:
                dst = cands[int(r_pick * len(cands)) % len(cands)]
                _start_trip(entry, dst, d, rng, stay=list(arch.get("stay_days") or [2, 4]))
        return
    ret = pos.get("return_day")
    if ret is None or d >= int(ret):
        _start_trip(entry, home, d, rng, stay=[1, 1])
        entry["pos"]["return_day"] = None


def _sync_waiting(state: dict, sim: dict, d: int) -> set[str]:
    """Companheiro em espera: sedentário no `waiting_at` resolvido para location_id (P6)."""
    waiting: set[str] = set()
    for comp in _party(state):
        ref = _party_id(comp)
        entry = sim["npcs"].get(ref)
        if entry is None:
            continue
        if comp.get("active") or not comp.get("waiting_at"):
            continue
        waiting.add(ref)
        loc = resolve_location_ref(str(comp["waiting_at"]))
        entry["archetype"] = "sedentario"
        if entry["pos"].get("location_id") != loc:
            entry["pos"] = {"location_id": loc, "since_day": int(d), "arrive_day": None}
        entry["home"] = loc or entry.get("home", "")
    return waiting


def _captor(state: dict, loc: str) -> str:
    return wd.controller_of(state.get("world_projection") or {}, loc)


def _major(state: dict, ref: str, row: dict) -> bool:
    from services.reputation import npc_tier

    if is_leader(ref) or ref in _party_by_id(state):
        return True
    return bool(row) and npc_tier(row.get("relationship", 5)) in ("amistoso", "leal")


def day_hook(ctx: Any) -> Any:
    """Hook `post` do tick diário (R26). Ordem (§3.4): elenco, percepção, intervenção, destino,
    agenda/fuga, deserção, exposição -> abertura com telegrama, itens do digest."""
    from services.world_engine import DayHookResult

    res = DayHookResult()
    m = mode()
    if m == "off" or ctx.state is None:
        return res
    emit = m == "on"
    key = sim_key(m)
    d = int(ctx.day)
    st = _work_state(ctx)
    sim = _sim_of(st, d, key)
    if int(sim.get("last_day", -1)) >= d:
        return res
    game_id = str(st.get("game_id", ""))
    proj = ctx.projection
    player_loc = str((st.get("world") or {}).get("current_location_id") or "")
    dsim = ctx.sim if emit else None
    events: list[dict] = []
    digest: list[dict] = []
    out_patch: dict = {}

    def merge_patch(patch: dict) -> None:
        for k, v in patch.items():
            st[k] = v
            out_patch[k] = v

    roster_ids = _refresh_roster(st, sim, d)
    waiting = _sync_waiting(st, sim, d)

    # status vencidos
    for entry in sim["npcs"].values():
        if entry.get("status") == "ferido" and int(entry.get("status_until_day") or 0) <= d:
            entry["status"], entry["status_until_day"] = "", None

    # percepção do telegrama (ledger da SPEC-305/302)
    seen = set((ctx.sim or {}).get("perceived_ids") or [])
    for p in sim["perils"]:
        if not p.get("resolution") and p.get("perceived_day") is None:
            if p.get("warning_event_id") in seen:
                p["perceived_day"] = d

    resolved_today = {"morto": 0, "ferido": 0, "capturado": 0, "escapou": 0, "intervencao": 0}

    # intervenção (R16)
    for p in sim["perils"]:
        if p.get("resolution"):
            continue
        entry = sim["npcs"].get(p["npc_id"]) or {}
        if perils.check_intervention(st, p, d, player_loc):
            arrival = perils.at_player(player_loc, str(p["location_id"]))
            p["resolution"], p["resolved_day"] = "intervencao", d
            entry["last_peril_end_day"] = d
            perils.end_slot(dsim, p, d, "intervencao")
            resolved_today["intervencao"] += 1
            if arrival and entry:
                entry["pos"] = {"location_id": p["location_id"], "since_day": d, "arrive_day": None}
                if emit:
                    digest.append(
                        _item(
                            game_id,
                            d,
                            "npc_resgate",
                            p["region_id"],
                            p["location_id"],
                            "npc_resgate.chegada",
                            {"npc_id": p["npc_id"]},
                            p["warning_event_id"],
                        )
                    )
                    key_n, row = _row_for(st, p["npc_id"])
                    if row:
                        from services import reputation

                        new_row, _notice = reputation.apply_npc_delta(
                            st, key_n, 1, reason="resgate", source="engine"
                        )
                        if new_row:
                            merge_patch({"npcs": {**(st.get("npcs") or {}), key_n: new_row}})

    # destino (R17/R18)
    for p in sim["perils"]:
        if p.get("resolution") or d < int(p["deadline_day"]):
            continue
        ref = p["npc_id"]
        entry = sim["npcs"].get(ref)
        if entry is None:
            p["resolution"], p["resolved_day"] = "escapou", d
            continue
        if (
            p.get("major")
            and (not perils.perceived(p, d) or not perils.try_slot(dsim, p, d))
            and int(p.get("extensions", 0)) < int(_const("MAX_EXTENSION_DAYS"))
        ):
            p["extensions"] = int(p.get("extensions", 0)) + 1
            p["deadline_day"] = int(p["deadline_day"]) + 1
            continue
        comp = ref in waiting
        _key_n, row = _row_for(st, ref)
        graph = graph_entity(ref) is not None
        ghost = dict(_party_by_id(st).get(ref) or {}) if comp else {}
        active_q = {q.get("id") for q in st.get("quests") or [] if q.get("status") == "active"}
        peril, evs, cpatch = perils.resolve(
            st,
            p,
            d,
            _rng(game_id, d, ref, "fate"),
            sim=sim,
            dsim=dsim,
            graph_npc=graph,
            companion=comp and emit,
            captor=_captor(st, p["location_id"]),
        )
        fate = peril["resolution"]
        entry["last_peril_end_day"] = d
        if fate == "intervencao":
            resolved_today["intervencao"] += 1
            continue
        resolved_today[fate] += 1
        entry["fate"], entry["fate_event_id"] = fate, (evs[0]["event_id"] if evs else "")
        if fate == "morto":
            entry["dead"] = True
            if is_leader(ref):
                sim["last_leader_death_day"] = d
        elif fate == "ferido":
            entry["status"], entry["status_until_day"] = "ferido", d + int(_const("WOUND_DAYS"))
        elif fate == "capturado":
            entry["status"], entry["archetype"] = "capturado", "sedentario"
            entry["pos"] = {"location_id": p["location_id"], "since_day": d, "arrive_day": None}
        elif fate == "escapou":
            dst = _nearest_safe(st, str(p["location_id"]), proj)
            entry["pos"] = {
                "location_id": str(p["location_id"]),
                "since_day": d,
                "arrive_day": None,
            }
            if dst:
                _start_trip(entry, dst, d, _rng(game_id, d, ref, "escape"), stay=[1, 1])
                entry["pos"]["refugee_from"] = str(entry.get("home") or p["location_id"])
        if cpatch:
            if ghost:  # P1-2: o que o jogador viu por ultimo (a API le isto ate a percepcao)
                entry["ghost"] = ghost
                entry["ghost_quests"] = sorted(
                    q["id"]
                    for q in cpatch.get("quests") or []
                    if q.get("id") in active_q and q.get("status") == "failed"
                )
            merge_patch(cpatch)
        if emit:
            events += evs
            digest.append(
                _item(
                    game_id,
                    d,
                    "npc_destino",
                    p["region_id"],
                    p["location_id"],
                    f"npc_destino.{fate}",
                    {"npc_id": ref},
                    entry["fate_event_id"],
                )
            )

    # agenda/fuga (R5/R6)
    for ref in sorted(roster_ids):
        entry = sim["npcs"].get(ref)
        if (
            entry is None
            or entry.get("dead")
            or entry.get("frozen")
            or entry.get("status") == "capturado"
            or entry.get("escort")  # SPEC-313 R22: o escoltado nao segue a agenda
            or ref in waiting
            or (ref in _party_by_id(st) and _party_by_id(st)[ref].get("active"))
        ):
            continue
        _step_position(st, ref, entry, d, game_id, proj, player_loc)

    # deserção (R10/R11)
    defect_ev, defect_dg = _defections(st, sim, ctx, d, game_id, roster_ids)
    if emit:
        events += defect_ev
        digest += defect_dg

    # exposição -> abertura com telegrama (R12-R15)
    from services import companion_soul as cs

    opened = 0
    for ref in sorted(roster_ids):
        entry = sim["npcs"].get(ref)
        if (
            entry is None
            or entry.get("dead")
            or entry.get("frozen")
            or entry.get("status") == "capturado"
            or entry.get("escort")  # SPEC-313 R22: sem perigo off-screen enquanto escoltado
            or (ref in _party_by_id(st) and _party_by_id(st)[ref].get("active"))
        ):
            continue
        _k, row = _row_for(st, ref)
        peril, evs = perils.maybe_open(
            st,
            sim,
            ref,
            d,
            _rng(game_id, d, ref, "peril"),
            entry=entry,
            major=_major(st, ref, row),
            leader=is_leader(ref),
            dsim=dsim,
            shadow=not emit,
            player_loc=player_loc,
            force=ref in (sim.get("forced") or []),
            protected=(
                ref not in waiting
                and bool(entry.get("home"))
                and (entry.get("pos") or {}).get("location_id") == entry.get("home")
            ),
        )
        if not peril:
            continue
        sim["forced"] = [f for f in sim.get("forced") or [] if f != ref]
        opened += 1
        if not emit:
            sim["perils"].remove(peril)  # sombra: só conta, não deixa perigo "vivo"
            continue
        events += evs
        params = {"npc_id": ref}
        tpl = "npc_perigo.rumor"
        if peril["channel"] == "pedido_de_ajuda":
            tpl = "npc_perigo.pedido_de_ajuda"
            params["delivery_day"] = perils.delivery_day(peril, player_loc)
        digest.append(
            _item(
                game_id,
                d,
                "npc_perigo",
                peril["region_id"],
                peril["location_id"],
                tpl,
                params,
                peril["warning_event_id"],
            )
        )
        if ref in waiting:
            try:
                merge_patch(cs.telegraph_companion_danger(st, ref, peril["channel"], d))
            except KeyError as exc:
                from observability.telemetry import log_fallback

                log_fallback("npc_world", "companion_soul_missing", exc)

    # ausência perceptível (R9)
    if emit:
        digest += _absence_items(st, sim, d, game_id, player_loc)

    sim["last_day"] = d
    sim["perils"] = _prune_perils(sim["perils"])
    entry_log = {
        "day": d,
        "roster": len(roster_ids),
        "travelling": sum(
            1 for e in sim["npcs"].values() if (e.get("pos") or {}).get("arrive_day") is not None
        ),
        "perils_open": perils.active_count(sim),
        "opened": opened,
        "resolved": dict(resolved_today),
        "defections": sum(1 for e in (defect_ev if emit else []) if e["type"] == "npc_defected"),
    }
    sim["tick_log"] = (sim.get("tick_log", []) + [entry_log])[-30:]
    from observability.telemetry import log_event

    log_event(
        "npc_world",
        "tick",
        level="info",
        mode=m,
        day=d,
        roster=entry_log["roster"],
        moved=entry_log["travelling"],
        travelling=entry_log["travelling"],
        perils_open=entry_log["perils_open"],
        perils_resolved=entry_log["resolved"],
        defections=entry_log["defections"],
    )
    out_patch[key] = sim
    res.events = events if emit else []
    res.digest = digest if emit else []
    res.state_patch = out_patch
    return res


def _prune_perils(plist: list[dict]) -> list[dict]:
    active = [p for p in plist if not p.get("resolution")]
    done = [p for p in plist if p.get("resolution")][-30:]
    return [p for p in plist if p in active or p in done]


# --------------------------------------------------------------------------- #
# Deserção (R10/R11)
# --------------------------------------------------------------------------- #
def _trait_mult(row: dict) -> float:
    table = _cfg()["defection_trait_mult"]
    mult = 1.0
    for tid in list(row.get("hidden_traits") or []) + list(row.get("revealed_traits") or []):
        if tid in table:
            f = float(table[tid])
            if f == 0:
                return 0.0
            mult *= f
    return mult


def _defections(
    st: dict, sim: dict, ctx: Any, d: int, game_id: str, roster_ids: list[str]
) -> tuple[list[dict], list[dict]]:
    import gamedata
    from services import faction_relations as fr
    from services.world_engine import faction_region_id

    factions = {f.get("id"): f for f in (ctx.factions or []) if isinstance(f, dict)}
    causes = {c.get("on_event") or c.get("per_day"): c for c in _cfg()["defection_causes"]}
    bands = (ctx.sim or {}).get("relation_bands") or {}
    party_ids = set(_party_by_id(st))
    ctrl = [
        e
        for e in (ctx.events or [])
        if isinstance(e, dict) and e.get("type") == "location_control_changed"
    ]
    cands: list[tuple[str, str, str]] = []  # (npc, to_faction, cause)
    for ref in sorted(roster_ids):
        entry = sim["npcs"].get(ref) or {}
        if entry.get("dead") or entry.get("frozen") or is_leader(ref) or ref in party_ids:
            continue
        cur = npc_faction(st, ref)
        if not cur or cur not in gamedata.FACTIONS:
            continue
        loc = str((entry.get("pos") or {}).get("location_id") or entry.get("home") or "")
        for e in ctrl:
            new = str((e.get("payload") or {}).get("new_controller_id") or "")
            if (
                new
                and new != cur
                and new in gamedata.FACTIONS
                and e.get("target_id") in (entry.get("home"), loc)
            ):
                cands.append((ref, new, "location_control_changed"))
        f = factions.get(cur) or {}
        if f.get("defeated") or f.get("completed"):
            rival = next(
                (
                    g
                    for g in sorted(factions)
                    if g != cur
                    and not factions[g].get("defeated")
                    and bands.get(fr.pair_key(cur, g)) == "guerra"
                ),
                "",
            )
            if rival:
                cands.append((ref, rival, "faction_defeated"))
        region = wp.region_of(loc)
        for key_pair, band in bands.items():
            if band != "guerra":
                continue
            a, b = fr.split_key(key_pair)
            if cur not in (a, b):
                continue
            other = b if cur == a else a
            if other in factions and faction_region_id(factions[other]) == region and region:
                cands.append((ref, other, "faction_war_occupied_region"))
    ev: list[dict] = []
    dg: list[dict] = []
    for ref, to, cause in cands:
        _k, row = _row_for(st, ref)
        c = causes.get(cause) or {}
        p = float(c.get("p", 0)) * _trait_mult(row)
        roll = _rng(game_id, d, ref, f"defect:{cause}").random()
        if len(ev) >= int(_const("MAX_DEFECTIONS_PER_DAY")) or roll >= p:
            continue
        loc = str(
            (sim["npcs"][ref].get("pos") or {}).get("location_id")
            or sim["npcs"][ref].get("home")
            or ""
        )
        e = perils.engine_event(
            game_id,
            d,
            "npc_defected",
            ref,
            {
                "from_faction_id": npc_faction(st, ref),
                "to_faction_id": to,
                "location_id": loc,
                "cause": cause,
            },
        )
        ev.append(e)
        dg.append(
            _item(
                game_id,
                d,
                "npc_lado",
                wp.region_of(loc),
                loc,
                "npc_lado.mudou",
                {"npc_id": ref, "faccao": to},
                e["event_id"],
            )
        )
    return ev, dg


# --------------------------------------------------------------------------- #
# Digest: ausência (R9)
# --------------------------------------------------------------------------- #
def _absence_items(st: dict, sim: dict, d: int, game_id: str, player_loc: str) -> list[dict]:
    out: list[dict] = []
    for ref in sorted(sim["npcs"]):
        entry = sim["npcs"][ref]
        _k, row = _row_for(st, ref)
        if not row or not row.get("known_by_player", True) or entry.get("dead"):
            continue
        home = str(entry.get("home") or "")
        pos = entry.get("pos") or {}
        away = str(pos.get("location_id") or "") != home
        if not home or not away or not perils.at_player(player_loc, home):
            continue
        since = int(pos.get("since_day", 0))
        if entry.get("absence_noted_since") == since:
            continue
        entry["absence_noted_since"] = since
        dest = str(pos.get("travel_to") or pos.get("location_id") or "")
        told = (
            entry.get("archetype") != "mensageiro"
            and bool(dest)
            and dest != home  # quem esta VOLTANDO nao "partiu" para casa
            and not pos.get("refugee_from")
            and entry.get("status") != "capturado"
        )
        tpl = "npc_ausente.sabido" if told else "npc_ausente.ignorado"
        params = {"npc_id": ref, "destino": dest} if told else {"npc_id": ref}
        out.append(_item(game_id, d, "npc_ausente", wp.region_of(home), home, tpl, params, ""))
    return out


# --------------------------------------------------------------------------- #
# Percepção e crença (R20-R23)
# --------------------------------------------------------------------------- #
def npc_label(state: dict, ref: str) -> str:
    """R20: o nome só aparece se o NPC é conhecido do jogador; senão um rótulo."""
    key, row = _row_for(state, ref)
    if row and row.get("known_by_player", True):
        return str(row.get("name") or key)
    fid = leaders().get(ref)
    if fid:
        from services import world_perception as wperc

        return f"o líder de {wperc._faction_label(state, fid)}"
    return "alguém"


def _belief_from_item(item: dict, day: int) -> tuple[str, dict] | None:
    params = item.get("params") or {}
    ref = str(params.get("npc_id") or "")
    kind = item.get("kind")
    if not ref or kind not in NPC_KINDS:
        return None
    tpl = str(item.get("template_id") or "")
    status, loc, faction, channel = "", str(item.get("location_id") or ""), "", "rumor"
    if kind == "npc_perigo":
        status = "em_perigo"
        channel = "mensageiro" if tpl.endswith("pedido_de_ajuda") else "rumor"
    elif kind == "npc_destino":
        status = _STATUS_BY_FATE.get(tpl.rsplit(".", 1)[-1], "")
    elif kind == "npc_ausente":
        status, channel = "ausente", "testemunho"
        loc = str(params.get("destino") or "")
    elif kind == "npc_resgate":
        status, channel = "ferido", "testemunho"
    elif kind == "npc_lado":
        faction = str(params.get("faccao") or "")
    belief = {
        "status_known": status,
        "location_known": loc,
        "faction_known": faction,
        "as_of_day": int(day),
        "channel": channel,
        "source_event_id": str(item.get("subject_id") or ""),
    }
    return ref, belief


def record_beliefs(state: dict, perceived: list[dict]) -> dict:
    """R22: ÚNICO writer de `npc_beliefs`. Itens percebidos + encontro em pessoa."""
    return on_perceived(state, perceived)[0]


KNOWN_EVENTS_CAP = 20


def _knows(belief: dict, event_id: str) -> bool:
    """P2-6: a crenca lembra os eventos que o jogador ja percebeu (nao so o ultimo)."""
    return bool(event_id) and (
        belief.get("source_event_id") == event_id or event_id in (belief.get("known_events") or [])
    )


def _merge_known(old: dict, new_src: str) -> list[str]:
    ids = [*(old.get("known_events") or []), str(old.get("source_event_id") or ""), new_src]
    return list(dict.fromkeys(i for i in ids if i))[-KNOWN_EVENTS_CAP:]


def on_perceived(state: dict, perceived: list[dict]) -> tuple[dict, list[dict]]:
    """(crenças novas, eventos `npc_fate_learned`). Só no modo `on`."""
    beliefs = copy.deepcopy((state or {}).get("npc_beliefs") or {})
    events: list[dict] = []
    if mode() != "on":
        return beliefs, events
    from services import rumors

    perceived = [i for i in perceived or [] if not rumors.is_rumor_item(i)]  # SPEC-312 R11
    day = _day_of((state or {}).get("world"))
    game_id = str((state or {}).get("game_id", ""))
    sim = (state or {}).get("npc_sim") or {}

    def learn(ref: str, belief: dict, fate: str, loc: str) -> None:
        old = beliefs.get(ref) or {}
        beliefs[ref] = {**old, **{k: v for k, v in belief.items() if v or k == "status_known"}}
        src = str(belief.get("source_event_id") or "")
        beliefs[ref]["known_events"] = _merge_known(old, src)
        if fate in ("morto", "capturado") and src and not _knows(old, src):
            events.append(
                perils.engine_event(
                    game_id,
                    day,
                    "npc_fate_learned",
                    ref,
                    {
                        "fate": fate,
                        "location_id": loc,
                        "source_event_id": src,
                        "name": npc_label(state, ref),
                        "day": day,
                    },
                    extra=src,
                )
            )

    for item in perceived or []:
        got = _belief_from_item(item, day)
        if not got:
            continue
        ref, belief = got
        fate = ""
        if item.get("kind") == "npc_destino":
            fate = str(item.get("template_id", "")).rsplit(".", 1)[-1]
        learn(ref, belief, fate, str(item.get("location_id") or ""))

    here = str(((state or {}).get("world") or {}).get("current_location_id") or "")
    # chegada ao local do destino: os moradores contam (testemunho)
    for p in sim.get("perils") or []:
        fate = str(p.get("resolution") or "")
        entry = (sim.get("npcs") or {}).get(p.get("npc_id")) or {}
        if fate in ("morto", "capturado", "ferido") and perils.at_player(
            here, str(p.get("location_id") or "")
        ):
            fid = str(entry.get("fate_event_id") or "")
            if fid and not _knows(beliefs.get(p["npc_id"]) or {}, fid):
                learn(
                    p["npc_id"],
                    {
                        "status_known": _STATUS_BY_FATE.get(fate, ""),
                        "location_known": str(p["location_id"]),
                        "as_of_day": day,
                        "channel": "testemunho",
                        "source_event_id": fid,
                    },
                    fate,
                    str(p["location_id"]),
                )
    # encontro em pessoa: o NPC que está na cena é visto como está
    from services.npc_layers import is_in_scene

    for key, row in ((state or {}).get("npcs") or {}).items():
        if not isinstance(row, dict) or not row.get("in_scene") or not is_in_scene(row):
            continue
        ref = npc_ref(str(key), row)
        entry = (sim.get("npcs") or {}).get(ref) or {}
        if not entry or str((entry.get("pos") or {}).get("location_id") or "") != here:
            continue  # so quem esta MESMO aqui (a cena do local anterior ainda nao foi zerada)
        src = str(entry.get("fate_event_id") or "")
        beliefs[ref] = {
            "status_known": "",
            "location_known": here,
            "faction_known": (beliefs.get(ref) or {}).get("faction_known", ""),
            "as_of_day": day,
            "channel": "testemunho",
            "source_event_id": src,
            "known_events": _merge_known(beliefs.get(ref) or {}, src),
        }
    return beliefs, events


def belief_view(state: dict, npc_key: str) -> dict | None:
    """Override de status/local para API/dossiê. `None` = sem verdade escondida (usar o visível).

    Só há override quando existe um destino fora de cena que o jogador AINDA não percebeu."""
    if mode() != "on":
        return None
    key, row = _row_for(state, npc_key)
    ref = npc_ref(key, row) if row else npc_key
    entry = ((state.get("npc_sim") or {}).get("npcs") or {}).get(ref) or {}
    fate_id = str(entry.get("fate_event_id") or "")
    if not entry.get("fate") or not fate_id:
        return None
    belief = (state.get("npc_beliefs") or {}).get(ref) or {}
    if _knows(belief, fate_id):
        return None
    return {
        "status": str(belief.get("status_known") or ""),
        "location": str(belief.get("location_known") or (row or {}).get("location") or ""),
    }


def _known_sources(state: dict) -> set[str]:
    out: set[str] = set()
    for b in (state.get("npc_beliefs") or {}).values():
        if isinstance(b, dict):
            out.add(str(b.get("source_event_id") or ""))
            out.update(str(i) for i in b.get("known_events") or [])
    return out


def fate_hidden(state: dict, ref: str) -> bool:
    """Existe um destino fora de cena de `ref` que o jogador ainda NAO percebeu."""
    if mode() != "on":
        return False
    entry = ((state.get("npc_sim") or {}).get("npcs") or {}).get(ref) or {}
    fid = str(entry.get("fate_event_id") or "")
    belief = (state.get("npc_beliefs") or {}).get(ref) or {}
    return bool(entry.get("fate") and fid and not _knows(belief, fid))


def public_party(state: dict) -> list[dict]:
    """P1-2: a party que o JOGADOR ve. Companheiro com destino nao percebido aparece como o
    jogador o viu por ultimo (linha fantasma): sem status literal, vitalidade real nem sumico."""
    party = [c for c in (state.get("party") or []) if isinstance(c, dict)]
    if mode() != "on":
        return party
    from services.companion_soul import comp_id

    out = list(party)
    for ref, entry in ((state.get("npc_sim") or {}).get("npcs") or {}).items():
        ghost = entry.get("ghost")
        if not ghost or not fate_hidden(state, ref):
            continue
        idx = next((i for i, c in enumerate(out) if comp_id(c) == ref), None)
        if idx is None:
            out.append(dict(ghost))
        else:
            out[idx] = dict(ghost)
    return out


def public_quests(state: dict) -> list[dict]:
    """P1-1/P1-2: missao `failed` por destino nao percebido continua ativa para o jogador."""
    quests = list(state.get("quests") or [])
    if mode() != "on":
        return quests
    hidden = {
        qid
        for ref, entry in ((state.get("npc_sim") or {}).get("npcs") or {}).items()
        if fate_hidden(state, ref)
        for qid in entry.get("ghost_quests") or []
    }
    if not hidden:
        return quests
    return [
        {**q, "status": "active"} if q.get("id") in hidden and q.get("status") == "failed" else q
        for q in quests
    ]


def event_hidden_from_player(state: dict, ev: dict) -> bool:
    """R23: evento off-screen que o jogador ainda não percebeu NÃO vai ao contexto/dossiê."""
    if mode() != "on" or not isinstance(ev, dict):
        return False
    payload = ev.get("payload") or {}
    if ev.get("type") == "quest_failed" and payload.get("personal_of"):
        return fate_hidden(state, str(payload["personal_of"]))  # missao pessoal de quem "sumiu"
    from services.event_processor import is_offscreen_event

    if ev.get("type") not in OFFSCREEN_TYPES and not is_offscreen_event(ev):
        return False
    key = str(payload.get("cause_event_id") or ev.get("event_id") or "")
    return key not in _known_sources(state)


def entity_death_hidden(state: dict, entity_id: str) -> bool:
    """R23: a projection diz `alive=False`, mas o jogador ainda NAO percebeu essa morte."""
    if mode() != "on":
        return False
    entry = ((state.get("npc_sim") or {}).get("npcs") or {}).get(entity_id) or {}
    fate_id = str(entry.get("fate_event_id") or "")
    return bool(entry.get("fate") == "morto" and fate_id and fate_id not in _known_sources(state))


def visible_status(state: dict, key: str, row: dict) -> str:
    """Status exibido: crença quando há verdade escondida; senão o visível (ferimento expira)."""
    from services.npc_layers import npc_alive

    ov = belief_view(state, key)
    if ov is not None:
        return ov["status"]
    if not npc_alive(row):
        return "morto"
    status = str(row.get("status") or "")
    until = row.get("wounded_until_day")
    if status == "ferido" and until is not None and _day_of(state.get("world")) >= int(until):
        return ""
    return status


# --------------------------------------------------------------------------- #
# Contrato com a SPEC-305
# --------------------------------------------------------------------------- #
def active_perils(state: dict) -> list[dict]:
    """Perigos vivos + últimos resolvidos, SEM a verdade do destino (só `intervencao`)."""
    if mode() != "on":
        return []
    out = []
    for p in ((state.get("npc_sim") or {}).get("perils")) or []:
        res = str(p.get("resolution") or "")
        out.append(
            {
                "peril_id": p["peril_id"],
                "npc_id": p["npc_id"],
                "region_id": p.get("region_id", ""),
                "location_id": p.get("location_id", ""),
                "deadline_day": p.get("deadline_day"),
                "event_id": p.get("warning_event_id", ""),
                "resolution": ""
                if not res
                else ("intervencao" if res == "intervencao" else "encerrado"),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# Escolta (SPEC-313 R22): o NPC viaja com o jogador, sem virar companheiro
# --------------------------------------------------------------------------- #
def _player_loc(state: dict) -> str:
    return str(((state or {}).get("world") or {}).get("current_location_id") or "")


def _sim_entry(state: dict, ref: str) -> dict:
    return (((state or {}).get(sim_key()) or {}).get("npcs") or {}).get(ref) or {}


def escort_destinations(state: dict, ref: str) -> list[str]:
    """Destinos da rota do arquetipo do NPC (sem bloqueados), do mais perto ao mais longe."""
    from services import world_distance

    entry = _sim_entry(state, ref)
    if not entry or not entry.get("pos"):
        return []
    agendas = _agendas()["archetypes"]
    arch = agendas.get(entry.get("archetype") or "sedentario") or agendas["sedentario"]
    here = str((entry["pos"] or {}).get("location_id") or "")
    cands = _route_candidates(state, entry, ref, arch, (state or {}).get("world_projection") or {})
    scored = []
    for lid in cands:
        d = world_distance.travel_periods(here, lid)
        if d is not None and d >= 1 and lid != here:
            scored.append((d, lid))
    return [lid for _d, lid in sorted(scored)]


def escort_start(state: dict, ref: str, quest_id: str, to: str, day: int) -> dict:
    """`npc_sim` novo com a escolta ligada (pura). Sem entrada simulada => `npc_sim` igual."""
    sim = copy.deepcopy((state or {}).get(sim_key()) or {})
    entry = (sim.get("npcs") or {}).get(ref)
    if not entry or entry.get("escort"):
        return sim
    here = _player_loc(state)
    entry["escort"] = {
        "quest_id": str(quest_id),
        "to": str(to),
        "since_day": int(day),
        "at": here,
        "paused_at": "",
    }
    entry["pos"] = {"location_id": here, "since_day": int(day), "arrive_day": None}
    return sim


def escort_stop(state: dict, ref: str, day: int) -> dict:
    """`npc_sim` novo sem a escolta; o NPC fica onde esta (`escort.at`) e a simulacao da 304
    segue dali (pura)."""
    sim = copy.deepcopy((state or {}).get(sim_key()) or {})
    entry = (sim.get("npcs") or {}).get(ref)
    if entry and entry.get("escort"):
        esc = entry.pop("escort")
        at = str(esc.get("paused_at") or esc.get("at") or "")
        entry["pos"] = {"location_id": at, "since_day": int(day), "arrive_day": None}
    return sim


def escort_eval(state: dict, esc: dict) -> dict:
    """Nova `escort` dado onde o jogador esta agora (pura). Segue se o local novo ENCURTA a
    distancia ao destino; senao pausa onde o NPC estava; volta a seguir quando o jogador
    retorna ao local da pausa."""
    from services import world_distance

    cur, to = _player_loc(state), str(esc.get("to") or "")
    at, paused = str(esc.get("at") or ""), str(esc.get("paused_at") or "")
    if paused:
        return {**esc, "at": cur, "paused_at": ""} if cur == paused else dict(esc)
    if not cur or cur == at:
        return dict(esc)
    d_old, d_new = world_distance.travel_periods(at, to), world_distance.travel_periods(cur, to)
    if cur == to or (d_old is not None and d_new is not None and d_new < d_old):
        return {**esc, "at": cur, "paused_at": ""}
    return {**esc, "paused_at": at}


def escort_arrived(state: dict, quest: dict) -> bool:
    """O jogador chegou ao destino COM a escolta ativa e nao pausada (pura)."""
    ref = str((quest.get("lore_anchor") or {}).get("id") or "")
    esc = _sim_entry(state, ref).get("escort")
    if not esc or esc.get("quest_id") != quest.get("id"):
        return False
    new = escort_eval(state, esc)
    return not new.get("paused_at") and _player_loc(state) == str(esc.get("to"))


def escort_sync(state: dict) -> dict:
    """Fim de turno: acompanha o jogador, e solta a escolta cuja quest nao esta mais ativa.
    Devolve `{sim_key: npc_sim}` ou `{}` se nada mudou."""
    key = sim_key()
    sim = (state or {}).get(key)
    if mode() == "off" or not isinstance(sim, dict):
        return {}
    active = {q.get("id") for q in (state.get("quests") or []) if q.get("status") == "active"}
    day = _day_of((state or {}).get("world"))
    new = copy.deepcopy(sim)
    changed = False
    for entry in (new.get("npcs") or {}).values():
        esc = entry.get("escort")
        if not esc:
            continue
        if esc.get("quest_id") not in active:
            at = str(esc.get("paused_at") or esc.get("at") or "")
            entry.pop("escort")
            entry["pos"] = {"location_id": at, "since_day": day, "arrive_day": None}
            changed = True
            continue
        nxt = escort_eval(state, esc)
        if nxt != esc:
            entry["escort"] = nxt
            changed = True
        if not nxt.get("paused_at") and entry["pos"].get("location_id") != nxt.get("at"):
            entry["pos"] = {"location_id": nxt["at"], "since_day": day, "arrive_day": None}
            changed = True
    return {key: new} if changed else {}
