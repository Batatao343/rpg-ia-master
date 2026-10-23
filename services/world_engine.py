"""SPEC-302: motor de mundo — tick diario, pressoes regionais e curva de tensao.

OWNER CANONICO de `world_sim` (e `world_sim_shadow`). `advance_days` roda 1 tick por dia
de jogo virado, em Python puro e seeded (`day_rng`), e devolve eventos `source="engine"`
para a fila `pending_world_events` (o arquivista valida e aplica na projection). A LLM so
narra o digest ja filtrado (agents/world_simulator.narrate_day); ela nunca decide.

Modos `RPG_WORLD_ENGINE=off|shadow|on`:
  off     comportamento legado (storyteller usa `simulate_world`);
  shadow  o motor roda e grava em `world_sim_shadow`; NAO emite eventos nem aplica efeitos;
  on      tudo ligado.
O motor NUNCA le nivel, ficha, inventario, ouro nem party do heroi (R5).
"""

from __future__ import annotations

import copy
import hashlib
import os
import random
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal

from services import faction_relations as fr
from services import world_director as wd
from services import world_pressures as wp

MODES = ("off", "shadow", "on")
DEFAULT_MODE = "on"
SIM_VERSION = 1


def mode() -> str:
    """`RPG_WORLD_ENGINE`; valor invalido cai no default."""
    raw = os.getenv("RPG_WORLD_ENGINE", "").strip().lower()
    return raw if raw in MODES else DEFAULT_MODE


def sim_key(m: str | None = None) -> str:
    return "world_sim" if (m or mode()) == "on" else "world_sim_shadow"


def day_rng(game_id: str, day: int, salt: str) -> random.Random:
    """R3: unica fonte de aleatoriedade do motor."""
    digest = hashlib.sha256(f"{game_id}|{day}|{salt}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(ch)
    ).strip()


@lru_cache(maxsize=1)
def _region_name_index() -> dict[str, str]:
    import gamedata

    out: dict[str, str] = {}
    for loc in gamedata.WORLD_MAP.get("locations", []):
        if loc.get("region") and loc.get("region_id"):
            out.setdefault(_fold(loc["region"]), loc["region_id"])
            out.setdefault(_fold(loc["region_id"]), loc["region_id"])
    return out


def faction_region_id(faction: dict) -> str | None:
    """P12: o `region` das faccoes e nome de exibicao; aqui vira `region_id` do mapa."""
    return _region_name_index().get(_fold((faction or {}).get("region", "")))


@lru_cache(maxsize=1)
def _leaders() -> dict[str, str]:
    from services import graph_resolver as gr

    out: dict[str, str] = {}
    for e in gr.resolve_edges({}, edge_type="leads", include_hidden=True):
        out[str(e.get("source"))] = str(e.get("target"))
    return out


# --- hooks (pontos de extensao para specs filhas) ---------------------------------


@dataclass
class DayContext:
    game_id: str
    day: int
    sim: dict
    projection: dict
    world: dict
    factions: list
    rng: random.Random


@dataclass
class DayHookResult:
    pressure_deltas: dict = field(default_factory=dict)  # region -> kind -> int
    events: list = field(default_factory=list)
    digest: list = field(default_factory=list)


DayHook = Callable[[DayContext], DayHookResult]
_HOOKS: list[tuple[str, str, int, DayHook]] = []


def register_day_hook(name: str, fn: DayHook, *, stage: Literal["pre", "post"], order: int) -> None:
    """Registra (ou substitui, pelo nome) um hook diario. `pre` roda antes das causas
    (calendario); `post` depois do diretor (NPCs)."""
    global _HOOKS
    _HOOKS = [h for h in _HOOKS if h[0] != name]
    _HOOKS.append((name, stage, int(order), fn))


def _run_hooks(stage: str, ctx: DayContext) -> DayHookResult:
    merged = DayHookResult()
    for _, _stage, _, fn in sorted(
        (h for h in _HOOKS if h[1] == stage), key=lambda h: (h[2], h[0])
    ):
        res = fn(ctx)
        for r, row in (res.pressure_deltas or {}).items():
            for k, v in row.items():
                merged.pressure_deltas.setdefault(r, {})[k] = (
                    merged.pressure_deltas.get(r, {}).get(k, 0) + v
                )
        merged.events += list(res.events or [])
        merged.digest += list(res.digest or [])
    return merged


# --- estado ------------------------------------------------------------------------


def _new_sim(game_id: str, day: int, factions: list, m: str) -> dict:
    cfg = wp.get_config()
    pressures = wp.baseline(cfg)
    seed = fr.seed_relations(factions)
    return {
        "version": SIM_VERSION,
        "mode": m,
        "enabled_from_day": int(day),
        "last_ticked_day": int(day),
        "last_event_seq": -1,  # -1 = ainda nao ancorado ao event_log (R29: sem retroativo)
        "pressures": pressures,
        "bands": wp.initial_bands(pressures, cfg),
        "phase": "calmo",
        "phase_since_day": int(day),
        "calm_until_day": int(day) + int(wp.director_constants(cfg)["INITIAL_CALM_DAYS"]),
        "recovery_until_day": 0,
        "region_last_crisis_end": {},
        "crises": [],
        "announce_block": {},
        "faction_relations": seed,
        "relation_bands": {
            k: b for k, v in seed.items() if (b := fr.next_relation_band("neutra", v)) != "neutra"
        },
        "faction_acc": {},
        "war_calm_days": {},
        "signals": [],
        "pending_digest": [],
        "tick_log": [],
    }


def ensure_world_sim(state: dict, current_day: int, factions: list | None = None) -> dict:
    """R29: `world_sim` ausente -> inicializa no dia atual (sem simulacao retroativa)."""
    m = mode()
    existing = (state or {}).get(sim_key(m))
    if isinstance(existing, dict) and existing.get("version") == SIM_VERSION:
        return copy.deepcopy(existing)
    return _new_sim(str((state or {}).get("game_id", "")), int(current_day), factions or [], m)


def region_pressure(state: dict, region_id: str, kind: str) -> int:
    """Leitura para specs consumidoras (modo `on`: `world_sim`)."""
    sim = (state or {}).get("world_sim") or {}
    return int(((sim.get("pressures") or {}).get(region_id) or {}).get(kind, 0))


@dataclass(frozen=True)
class WorldTickResult:
    world: dict
    factions: list
    world_sim: dict | None
    pending_events: list
    digest: list
    days_ticked: int
    sim_key: str = "world_sim"


def _clock_day(world: dict) -> int:
    return int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)


# --- um dia ------------------------------------------------------------------------


def _merge_deltas(into: dict, other: dict) -> None:
    for r, row in other.items():
        for k, v in row.items():
            into.setdefault(r, {})
            into[r][k] = into[r].get(k, 0) + int(v)


def _state_causes(sim: dict, projection: dict, world: dict, factions: list, cfg: dict) -> dict:
    """Causas `per_day` da tabela (R7b)."""
    out: dict = {}
    rows = (projection or {}).get("location_states") or {}
    by_id = {f.get("id"): f for f in factions if isinstance(f, dict)}
    for cause in cfg.get("causes", []):
        kind = cause.get("per_day")
        if not kind:
            continue
        pressure, delta = str(cause["pressure"]), int(cause["delta"])
        regions: list[str] = []
        if kind == "active_loc_state":
            regions = sorted(
                {
                    wp.region_of(lid)
                    for lid, row in rows.items()
                    if (row or {}).get("state") == cause.get("state")
                }
            )
        elif kind == "pressure_band":
            src, band = cause.get("pressure_src"), cause.get("band")
            regions = [r for r in sorted(sim["bands"]) if sim["bands"][r].get(src) == band]
        elif kind == "looming_threat":
            if world.get("looming_threat"):
                fid = str(world.get("looming_threat_faction") or "")
                reg = faction_region_id(by_id.get(fid) or {}) if fid else None
                regions = [reg] if reg else []
        elif kind == "faction_war_presence":
            regs = set()
            for key, band in (sim.get("relation_bands") or {}).items():
                if band != "guerra":
                    continue
                a, b = fr.split_key(key)
                ra, rb = (
                    faction_region_id(by_id.get(a) or {}),
                    faction_region_id(by_id.get(b) or {}),
                )
                if (
                    ra
                    and ra == rb
                    and not (by_id.get(a) or {}).get("defeated")
                    and not (by_id.get(b) or {}).get("defeated")
                ):
                    regs.add(ra)
            regions = sorted(regs)
        for r in regions:
            if r:
                out.setdefault(r, {})
                out[r][pressure] = out[r].get(pressure, 0) + delta
    return out


def _tick_day(
    sim: dict,
    day: int,
    *,
    game_id: str,
    new_events: list,
    projection: dict,
    world: dict,
    factions: list,
    intel: dict,
    m: str,
    cfg: dict,
) -> tuple[list, list, dict, list]:
    """Um tick. Devolve (eventos, digest, world, factions). Muta `sim` e `projection`."""
    from services.event_processor import apply_event

    dc = wp.director_constants(cfg)
    events: list[dict] = []
    digest: list[dict] = []
    emit = m == "on"

    def commit(evs: list[dict]) -> None:
        for ev in evs:
            projection.update(apply_event({**ev, "turn": day}, projection))
        events.extend(evs)

    # 1. hooks pre
    ctx = DayContext(game_id, day, sim, projection, world, factions, day_rng(game_id, day, "hooks"))
    pre = _run_hooks("pre", ctx)

    # 2-3. causas (eventos novos do event_log + estado)
    deltas = wp.event_deltas(
        new_events,
        cfg=cfg,
        factions=factions,
        leader_faction=lambda npc: _leaders().get(npc, ""),
        faction_region=faction_region_id,
    )
    _merge_deltas(deltas, _state_causes(sim, projection, world, factions, cfg))
    _merge_deltas(deltas, pre.pressure_deltas)
    relief: dict = {}
    for rec in wd.active_crises(sim):
        if rec["kind"] in wp.KINDS:
            relief.setdefault(rec["region_id"], {})[rec["kind"]] = True
    blocked = {(r.get("a"), r.get("b")) for r in (projection.get("blocked_routes") or [])}

    # 4. relacoes (R21) — antes das pressoes, o rompimento empurra `guerra` do dia
    control_events = [
        e for e in new_events if isinstance(e, dict) and e.get("type") == "location_control_changed"
    ]
    seed = fr.seed_relations(factions)
    rels = fr.step_relations(
        sim["faction_relations"],
        seed,
        factions=factions,
        rng=day_rng(game_id, day, "relations"),
        faction_region=faction_region_id,
        control_events=control_events,
        region_of=wp.region_of,
    )
    rbands, changes = fr.crossings(rels, sim.get("relation_bands") or {})
    sim["faction_relations"], sim["relation_bands"] = rels, rbands
    rel_events: list[dict] = []
    by_id = {f.get("id"): f for f in factions if isinstance(f, dict)}
    for key, _old, new in changes:
        a, b = fr.split_key(key)
        label = {"guerra": "enemy_of", "alianca": "allied_with", "neutra": "neutral"}[new]
        rel_events.append(
            wd._ev(
                game_id,
                day,
                "faction_relation_changed",
                a,
                {"other_faction_id": b, "relation": label},
                b,
            )
        )
        reg = faction_region_id(by_id.get(a) or {}) or ""
        tpl = {"guerra": "rel.guerra", "alianca": "rel.alianca", "neutra": "rel.neutra"}[new]
        digest.append(
            wd.digest_item(
                game_id,
                day,
                "relacao",
                reg,
                wp.region_primary_location(reg) if reg else "",
                tpl,
                {"faccao": a},
                subject_id=rel_events[-1]["event_id"],
            )
        )
        if new == "guerra" and reg:
            deltas.setdefault(reg, {})["guerra"] = (
                deltas.get(reg, {}).get("guerra", 0) + fr.WAR_BOOST
            )

    # 5. pressoes
    prev_pressures = copy.deepcopy(sim["pressures"])
    sim["pressures"] = wp.step_pressures(
        sim["pressures"],
        rng=day_rng(game_id, day, "pressures"),
        cfg=cfg,
        deltas=deltas,
        relief=relief,
        blocked_pairs=blocked,
    )

    # 6. progresso de faccao (so `on`; R21b)
    if emit:
        acc = sim.setdefault("faction_acc", {})
        new_factions = []
        for f in factions:
            f = dict(f)
            if not f.get("completed") and not f.get("defeated"):
                a = float(acc.get(f.get("id"), 0.0)) + float(f.get("pace", 3)) * float(
                    dc["FACTION_DAY_FACTOR"]
                )
                inc = int(a)
                acc[f.get("id")] = a - inc
                f["progress"] = min(100, int(f.get("progress", 0)) + inc)
            new_factions.append(f)
        factions = new_factions

    # 7. bandas, sinais, avisos
    sim["bands"], _ups = wp.update_bands(sim.get("bands") or {}, sim["pressures"], cfg)
    sigs = wp.pick_signals(
        prev_pressures,
        sim["pressures"],
        sim["bands"],
        day=day,
        rng=day_rng(game_id, day, "signals"),
        cfg=cfg,
    )
    for s in sigs:
        s["signal_id"] = wd._h(game_id, day, s["region_id"], s["template_id"], n=12)
        digest.append(
            wd.digest_item(
                game_id,
                day,
                "sinal",
                s["region_id"],
                s["location_id"],
                s["template_id"],
                {"local": s["location_id"]},
            )
        )
    sim["signals"] = (sim.get("signals", []) + sigs)[-60:]

    # 8. diretor (crises de pressao)
    drng = day_rng(game_id, day, "director")
    if rel_events:
        commit(rel_events)
    _, dev, ddg = wd.step_crises(
        sim,
        day,
        projection,
        drng,
        game_id=game_id,
        factions=factions,
        faction_region=faction_region_id,
        cfg=cfg,
    )
    commit(dev)
    digest += ddg

    # 8b. ascensoes (R21b): competem por vaga DEPOIS das crises de pressao
    if emit:
        world, factions, aev, adg = _ascension_step(
            sim, day, game_id, world, factions, intel, cfg, drng
        )
        commit(aev)
        digest += adg

    # 9. recuperacao de ruina/ocupado (R20)
    rev, rdg = wd.recovery_step(
        sim,
        day,
        projection,
        day_rng(game_id, day, "recovery"),
        game_id=game_id,
        factions=factions,
        cfg=cfg,
    )
    commit(rev)
    digest += rdg

    # 10. hooks post, fase
    ctx = DayContext(
        game_id, day, sim, projection, world, factions, day_rng(game_id, day, "hooks_post")
    )
    post = _run_hooks("post", ctx)
    commit(list(post.events))
    digest += list(post.digest)
    wd.update_phase(sim, day)
    return events, digest, world, factions


def _ascension_step(
    sim: dict, day: int, game_id: str, world: dict, factions: list, intel: dict, cfg: dict, rng: Any
) -> tuple[dict, list, list, list]:
    from world_utils import resolve_faction_completions

    dc = wp.director_constants(cfg)
    events: list[dict] = []
    digest: list[dict] = []
    factions = [dict(f) for f in factions]
    for f in factions:
        fid = f.get("id")
        region = faction_region_id(f) or ""
        if not region or f.get("completed") or f.get("defeated"):
            continue
        prog = int(f.get("progress", 0))
        if prog >= int(dc["ASCENSION_WARN_PROGRESS"]) and not wd._has_record(
            sim, region, "ascensao", str(fid)
        ):
            rec = wd.announce(
                sim, day, region, "ascensao", rng, game_id=game_id, faction_id=str(fid), cfg=cfg
            )
            if rec:
                loc = wp.region_primary_location(region)
                ev = wd._ev(
                    game_id,
                    day,
                    "world_crisis_warning",
                    loc,
                    {
                        "kind": "ascensao",
                        "region_id": region,
                        "crisis_id": rec["crisis_id"],
                        "earliest_day": day + int(dc["MIN_WARNING_DAYS"]),
                        "faction_id": str(fid),
                    },
                    str(fid),
                )
                events.append(ev)
                digest.append(
                    wd.digest_item(
                        game_id,
                        day,
                        "aviso",
                        region,
                        loc,
                        "ascensao.aviso",
                        {"faccao": str(fid), "local": loc},
                        subject_id=ev["event_id"],
                    )
                )
        if prog >= 100:
            rec = wd._find_announced(sim, region, "ascensao", str(fid))
            if rec and wd._try_open(sim, rec, day, cfg):
                f["completed"] = True
                ev_in = {
                    "id": fid,
                    "name": f.get("name"),
                    "goal": f.get("goal", ""),
                    "disposition": f.get("disposition", "neutro"),
                }
                factions, world, _note = resolve_faction_completions(
                    factions, world, [ev_in], intel
                )
                digest.append(
                    wd.digest_item(
                        game_id,
                        day,
                        "ascensao",
                        region,
                        wp.region_primary_location(region),
                        "ascensao.crise.inicio",
                        {"faccao": str(fid)},
                    )
                )
                break  # no maximo uma ascensao por dia
    return world, factions, events, digest


# --- API publica -------------------------------------------------------------------


def advance_days(
    state: dict, world_before: dict, world_after: dict, factions: list, intel: dict
) -> WorldTickResult:
    """R1-R4: 1 tick por dia virado entre `last_ticked_day` e o dia de `world_after`."""
    m = mode()
    key = sim_key(m)
    factions = list(factions or [])
    if m == "off":
        return WorldTickResult(world_after, factions, None, [], [], 0, key)

    from observability.telemetry import log_event

    cfg = wp.get_config()
    dc = wp.director_constants(cfg)
    game_id = str(state.get("game_id", ""))
    day_before, day_after = _clock_day(world_before), _clock_day(world_after)
    sim = ensure_world_sim(state, day_before, factions)
    if day_before - int(sim.get("last_ticked_day", day_before)) > int(dc["MAX_DAYS_PER_ACTION"]):
        # on->off->on: sim velho (motor desligado por muito tempo) nao vira catch-up (R29)
        sim = _new_sim(game_id, day_before, factions, m)
    sim["mode"] = m
    last = int(sim.get("last_ticked_day", day_before))
    if day_after <= last:
        return WorldTickResult(world_after, factions, sim, [], [], 0, key)

    days = list(range(last + 1, day_after + 1))
    capped = len(days) > int(dc["MAX_DAYS_PER_ACTION"])
    if capped:
        days = days[-int(dc["MAX_DAYS_PER_ACTION"]) :]
        log_event("world", "tick_capped", level="warning", skipped=day_after - last - len(days))
    elog = list(state.get("event_log") or [])
    projection = copy.deepcopy(state.get("world_projection") or {})
    if m == "shadow":  # o sombra mantem a PROPRIA projecao de estados/rotas (nao toca a real)
        projection["location_states"] = copy.deepcopy(sim.get("shadow_location_states") or {})
        projection["blocked_routes"] = copy.deepcopy(sim.get("shadow_blocked_routes") or [])
    seq = int(sim.get("last_event_seq", -1))
    new_events = [] if seq < 0 else elog[seq:]
    sim["last_event_seq"] = len(elog)

    world = copy.deepcopy(world_after)
    all_events: list[dict] = []
    all_digest: list[dict] = []
    for d in days:
        n_before = len(all_events)
        evs, dg, world, new_factions = _tick_day(
            sim,
            d,
            game_id=game_id,
            new_events=new_events,
            projection=projection,
            world=world,
            factions=factions,
            intel=intel or {},
            m=m,
            cfg=cfg,
        )
        if m == "on":
            factions = new_factions
        new_events = []  # causas do log so entram no primeiro dia simulado
        all_events += evs
        all_digest += dg
        entry = {
            "day": d,
            "phase": sim.get("phase"),
            "active": len(wd.active_crises(sim)),
            "started": sum(
                1
                for e in evs
                if e["type"] == "location_state_changed"
                and e["payload"].get("previous") == ""
                and e["payload"].get("state")
            ),
            "ended": sum(
                1
                for e in evs
                if e["type"] == "location_state_changed" and not e["payload"].get("state")
            ),
            "signals": sum(1 for x in dg if x["kind"] == "sinal"),
        }
        sim["tick_log"] = (sim.get("tick_log", []) + [entry])[-30:]
        log_event(
            "world",
            "tick",
            level="info",
            mode=m,
            perceived=0,
            events=len(all_events) - n_before,
            **entry,
        )
    sim["last_ticked_day"] = int(day_after)
    if capped:
        sim["tick_log"].append({"day": day_after, "capped": True})
        sim["tick_log"] = sim["tick_log"][-30:]
    if m == "shadow":
        sim["shadow_location_states"] = projection.get("location_states") or {}
        sim["shadow_blocked_routes"] = projection.get("blocked_routes") or []
    if m == "on":
        from services import location_states as _ls

        world["location_danger_delta"] = {
            lid: d
            for lid, row in (projection.get("location_states") or {}).items()
            if (d := _ls.danger_delta(row, lid))
        }
        cur = world.get("current_location_id")
        if cur:
            from world_utils import _effective_danger

            world["danger_level"] = _effective_danger(world, cur)
        sim["pending_digest"] = (sim.get("pending_digest", []) + all_digest)[-20:]
    return WorldTickResult(
        world if m == "on" else world_after,
        factions if m == "on" else list(factions),
        sim,
        all_events if m == "on" else [],
        all_digest,
        len(days),
        key,
    )
