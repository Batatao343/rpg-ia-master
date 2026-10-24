"""SPEC-303: calendario do mundo — estacoes, passos sazonais e festas da lore.

Funcoes PURAS sobre os parametros congelados em `world_sim.calendar` (R2/R4): nenhuma le
nivel, ficha, inventario, ouro ou party (R26); toda aleatoriedade vem de `day_rng`
(`world_engine`) so na CRIACAO do calendario. Sem lua, semana nem dia de mercado: so
ano -> 4 estacoes de `SEASON_DAYS` dias.

O calendario roda como hook `pre` do tick diario da SPEC-302 (`calendar_day_hook`): atualiza
`world["season"]`, devolve os deslocamentos de baseline de pressao do dia, abre/cancela/
encerra festas por eventos `location_state_changed` (`source="engine"`, `cause="calendario"`)
e gera digest. A estacao MODULA sistemas existentes (clima, viagem, encontros, pressao); nao
cria mecanica paralela. `RPG_CALENDAR=off|shadow|on` (ver `mode`).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Literal

from services import world_director as wd
from services import world_pressures as wp

SEASONS: tuple[str, ...] = ("primavera", "verao", "outono", "inverno")
MODES = ("off", "shadow", "on")
CAL_VERSION = 1
FESTIVAL_RING = 20  # festas encerradas/canceladas mantidas no sim
# R11: fato determinístico entregue ao narrador na travessia de passo fechado
CROSSING_NOTE = "O passo está fechado pela neve; a travessia leva o dia inteiro."


def mode() -> Literal["off", "shadow", "on"]:
    """R25: `off` se motor ou calendario `off`; `shadow` se qualquer um `shadow`; senao `on`."""
    from services import world_engine

    raw = os.getenv("RPG_CALENDAR", "").strip().lower()
    cal = raw if raw in MODES else "on"
    eng = world_engine.mode()
    if "off" in (eng, cal):
        return "off"
    if "shadow" in (eng, cal):
        return "shadow"
    return "on"


def _cfg() -> dict:
    return wp._load_json("calendar.json")


def constants() -> dict:
    return _cfg()["constants"]


def festivals_catalog() -> list[dict]:
    return list(wp._load_json("festivals.json").get("festivals", []))


def _festival(festival_id: str) -> dict | None:
    return next((f for f in festivals_catalog() if f.get("id") == festival_id), None)


# --- calendario puro (R1-R6) ---------------------------------------------------------


def create_calendar(game_id: str, anchor_day: int) -> dict:
    """R3: estacao inicial semeada + primeira virada em `anchor_day + k`, k em 4..8."""
    from services.world_engine import day_rng

    c = constants()
    sd = int(c["SEASON_DAYS"])
    year = 4 * sd
    rng = day_rng(game_id, anchor_day, "calendar")
    s0 = rng.randrange(4)
    k = rng.randint(int(c["FIRST_TURN_MIN"]), int(c["FIRST_TURN_MAX"]))
    k = max(1, min(k, sd - 1))
    doy_anchor = s0 * sd + (sd - k)
    return {
        "version": CAL_VERSION,
        "season_days": sd,
        "epoch_offset": (doy_anchor - (int(anchor_day) - 1)) % year,
        "anchor_day": int(anchor_day),
        "first_turn_day": int(anchor_day) + k,
    }


def season_at(cal: dict, day: int) -> dict:
    """R2: `{season, day_in_season, year, day_of_year}` — so dos parametros e do dia."""
    sd = int(cal["season_days"])
    year_days = 4 * sd
    t = int(day) - 1 + int(cal["epoch_offset"])
    doy = t % year_days
    return {
        "season": SEASONS[doy // sd],
        "day_in_season": doy % sd + 1,
        "year": t // year_days + 1,
        "day_of_year": doy,
    }


def label_for(season: str, region_id: str) -> str:
    """R6: rotulo regional da estacao canonica (default quando a regiao nao define)."""
    labels = _cfg()["labels"]
    return str(
        (labels.get(region_id) or {}).get(season)
        or labels["default"].get(season)
        or str(season).capitalize()
    )


def season_label(cal: dict, day: int, region_id: str) -> str:
    return label_for(season_at(cal, day)["season"], region_id)


def season_view(cal: dict, day: int, region_id: str) -> dict:
    info = season_at(cal, day)
    return {
        "id": info["season"],
        "label": label_for(info["season"], region_id),
        "day_in_season": info["day_in_season"],
    }


# --- leituras para os sistemas modulados (R8, R10-R12, R14b) ---------------------------


def active_season(world: dict | None) -> str | None:
    """Estacao vigente para os consumidores; `None` (modulacao neutra) sem calendario/`off`."""
    sid = ((world or {}).get("season") or {}).get("id")
    if sid not in SEASONS or mode() != "on":
        return None
    return str(sid)


def baseline_offsets(season: str | None) -> dict[str, dict[str, int]]:
    """R12: deslocamento de baseline `{regiao: {pressao: int}}` da estacao."""
    if season not in SEASONS:
        return {}
    return {
        r: {k: int(v) for k, v in row.items()}
        for r, row in (_cfg()["pressure_offsets"].get(season) or {}).items()
    }


def _region_table(table: dict, region_id: str) -> dict:
    return table.get(region_id) or table.get("default") or {}


def weather_multipliers(region_id: str, season: str | None) -> dict[str, float]:
    """R8: multiplicador por estado de clima de destino (default 1,0)."""
    if season not in SEASONS:
        return {}
    return dict(_region_table(_cfg()["weather_mult"], region_id).get(season) or {})


def encounter_multipliers(region_id: str, season: str | None) -> dict[str, float]:
    """R14b: multiplicador de peso por `enemy_id` (so dentro do mesmo porte)."""
    if season not in SEASONS:
        return {}
    return dict((_cfg()["encounter_mult"].get(region_id) or {}).get(season) or {})


def pass_between(a: str, b: str) -> dict | None:
    pair = {a, b}
    for p in _cfg().get("passes", []):
        if {p["a"], p["b"]} == pair:
            return dict(p)
    return None


def pass_closed(world: dict | None, a: str, b: str) -> bool:
    """R10: o passo `a<->b` esta fechado pela estacao (derivado, nunca gravado)."""
    season = active_season(world)
    p = pass_between(str(a or ""), str(b or "")) if season else None
    return bool(p and season in (p.get("closed_in") or []))


def seasonal_closed_pairs(world: dict | None) -> set[frozenset[str]]:
    """R10/R11b: pares fechados pela estacao (le `world["season"]`; nunca o heroi)."""
    season = active_season(world)
    if not season:
        return set()
    return {
        frozenset((p["a"], p["b"]))
        for p in _cfg().get("passes", [])
        if season in (p.get("closed_in") or [])
    }


def pass_extra_periods() -> int:
    return int(constants()["PASS_EXTRA_PERIODS"])


# --- festas (R15-R19) ----------------------------------------------------------------


def festa_id(game_id: str, festival_id: str, year: int) -> str:
    return hashlib.sha256(f"{game_id}|{festival_id}|{year}".encode()).hexdigest()[:16]


def festival_schedule(cal: dict, game_id: str, year: int) -> list[dict]:
    """Registros planejados do ano: `start_day` e `end_day` (dia em que a festa acaba)."""
    sd = int(cal["season_days"])
    out: list[dict] = []
    for f in festivals_catalog():
        doy = SEASONS.index(f["season"]) * sd + int(f["day_in_season"]) - 1
        start = (int(year) - 1) * 4 * sd + doy - int(cal["epoch_offset"]) + 1
        out.append(
            {
                "festa_id": festa_id(game_id, f["id"], year),
                "festival_id": f["id"],
                "year": int(year),
                "start_day": start,
                "end_day": start + int(f.get("duration_days", 1)),
            }
        )
    return out


def festival_effects(festival_id: str) -> dict:
    """R18: override de efeito do festival (`price_mult`, `restock_mult`, `merchant_closed`)."""
    return dict((_festival(festival_id) or {}).get("effects") or {})


def festival_label(festival_id: str) -> str:
    return str((_festival(festival_id) or {}).get("label") or "")


def valid_festival_event(payload: dict) -> bool:
    """Validator: `cause="calendario"` so com state in {festa, ""} e festival existente."""
    return (
        payload.get("state", "") in ("festa", "")
        and _festival(str(payload.get("festival_id") or "")) is not None
    )


def _region_crisis(sim: dict, region_id: str) -> bool:
    return any(
        c.get("region_id") == region_id for c in (*wd.active_crises(sim), *wd.announced_crises(sim))
    )


def _state_event(game_id: str, day: int, lid: str, new: str, rec: dict) -> dict:
    return wd._ev(
        game_id,
        day,
        "location_state_changed",
        lid,
        {
            "state": new,
            "previous": "" if new else "festa",
            "severity": 1 if new else 0,
            "crisis_id": rec["festa_id"],
            "cause": "calendario",
            "festival_id": rec["festival_id"],
            "day": int(day),
        },
        f"festa_{'ini' if new else 'fim'}_{rec['festa_id']}",
    )


def _festival_step(ctx: Any, cal: dict) -> tuple[list[dict], list[dict], dict]:
    """Anuncia (R19), abre/cancela (R16/R17) e encerra festas. Muta `ctx.sim['festivals']`."""
    sim, day, gid = ctx.sim, int(ctx.day), ctx.game_id
    herald = int(constants()["FESTIVAL_HERALD_DAYS"])
    rows = (ctx.projection or {}).get("location_states") or {}
    events: list[dict] = []
    digest: list[dict] = []
    counts = {"started": 0, "cancelled": 0}
    recs: list[dict] = [dict(r) for r in sim.get("festivals", []) if isinstance(r, dict)]
    known = {r["festa_id"] for r in recs}
    year = season_at(cal, day)["year"]
    anchor = int(cal["anchor_day"])
    for y in (year, year + 1):
        for plan in festival_schedule(cal, gid, y):
            if plan["festa_id"] in known or plan["start_day"] <= anchor:
                continue
            if plan["start_day"] - herald <= day < plan["end_day"]:
                recs.append({**plan, "status": "anunciada", "location_ids": []})
                known.add(plan["festa_id"])
                fest = _festival(plan["festival_id"]) or {}
                if day < plan["start_day"]:
                    seen_regions: set[str] = set()
                    for lid in fest.get("location_ids", []):
                        reg = wp.region_of(lid)
                        if reg in seen_regions:
                            continue
                        seen_regions.add(reg)
                        digest.append(
                            wd.digest_item(
                                gid,
                                day,
                                "festa_proxima",
                                reg,
                                lid,
                                "festa.proxima",
                                {"local": lid, "festa": fest.get("name", "")},
                            )
                        )
    for rec in sorted(recs, key=lambda r: (r["start_day"], r["festa_id"])):
        fest = _festival(rec["festival_id"]) or {}
        if rec["status"] == "anunciada" and day >= rec["start_day"]:
            if day >= rec["end_day"]:
                rec["status"] = "cancelada"  # tick pulado (teto de dias): sem digest
                continue
            started: list[str] = []
            for lid in fest.get("location_ids", []):
                reg = wp.region_of(lid)
                if (rows.get(lid) or {}).get("state") or _region_crisis(sim, reg):
                    counts["cancelled"] += 1
                    digest.append(
                        wd.digest_item(
                            gid,
                            day,
                            "festa_cancelada",
                            reg,
                            lid,
                            "festa.cancelada",
                            {"local": lid, "festa": fest.get("name", "")},
                        )
                    )
                    continue
                ev = _state_event(gid, day, lid, "festa", rec)
                events.append(ev)
                started.append(lid)
                counts["started"] += 1
                digest.append(
                    wd.digest_item(
                        gid,
                        day,
                        "festa",
                        reg,
                        lid,
                        "festa.inicio",
                        {
                            "local": lid,
                            "festa": fest.get("name", ""),
                            "rotulo": fest.get("label", ""),
                        },
                        subject_id=ev["event_id"],
                    )
                )
            rec["location_ids"] = started
            rec["status"] = "ativa" if started else "cancelada"
        elif rec["status"] == "ativa" and day >= rec["end_day"]:
            for lid in rec.get("location_ids", []):
                row = rows.get(lid) or {}
                if row.get("state") == "festa" and row.get("crisis_id") == rec["festa_id"]:
                    events.append(_state_event(gid, day, lid, "", rec))
            rec["status"] = "encerrada"
    live = [r for r in recs if r["status"] in ("anunciada", "ativa")]
    done = [r for r in recs if r["status"] not in ("anunciada", "ativa")]
    sim["festivals"] = sorted(live + done[-FESTIVAL_RING:], key=lambda r: r["start_day"])
    return events, digest, counts


# --- hook diario (R7) ----------------------------------------------------------------


def calendar_day_hook(ctx: Any) -> Any:
    """Hook `pre` (order 10): estacao, offsets de baseline, passos e festas do dia `ctx.day`."""
    from observability.telemetry import log_event
    from services.world_engine import DayHookResult

    res = DayHookResult()
    m = mode()
    if m == "off":
        return res
    sim, day = ctx.sim, int(ctx.day)
    key = "calendar" if m == "on" else "calendar_shadow"
    cal = sim.get(key)
    if not isinstance(cal, dict) or cal.get("version") != CAL_VERSION:
        cal = create_calendar(ctx.game_id, day - 1)  # R5: liga no proximo dia virado
        sim[key] = cal
    info, prev = season_at(cal, day), season_at(cal, day - 1)
    changed = info["season"] != prev["season"]
    passes_closed = 0
    events: list[dict] = []
    digest: list[dict] = []
    counts = {"started": 0, "cancelled": 0}
    if m == "on":
        cur = str((ctx.world or {}).get("current_location_id") or "")
        ctx.world["season"] = season_view(cal, day, wp.region_of(cur))
        res.baseline_offsets = baseline_offsets(info["season"])
        if changed:
            digest.append(
                wd.digest_item(
                    ctx.game_id, day, "estacao", "", "", f"estacao.inicio.{info['season']}"
                )
            )
        for p in _cfg().get("passes", []):
            closed = info["season"] in p["closed_in"]
            passes_closed += int(closed)
            if closed != (prev["season"] in p["closed_in"]):
                tpl = "passo.fechou" if closed else "passo.abriu"
                for here, other in ((p["a"], p["b"]), (p["b"], p["a"])):
                    digest.append(
                        wd.digest_item(
                            ctx.game_id,
                            day,
                            "passo",
                            wp.region_of(here),
                            here,
                            tpl,
                            {"local": other},
                        )
                    )
        events, fdigest, counts = _festival_step(ctx, cal)
        digest += fdigest
        res.events, res.digest = events, digest
    log_event(
        "world",
        "calendar",
        level="info",
        day=day,
        season=info["season"],
        changed=changed,
        festas_started=counts["started"],
        festas_cancelled=counts["cancelled"],
        passes_closed=passes_closed,
        mode=m,
    )
    return res


def init_new_game(state: dict) -> dict:
    """R5: jogo novo — cria `world_sim` com calendario ancorado no dia 1 e `world["season"]`.
    Muta e devolve `state`. Sem efeito fora do modo `on`."""
    if mode() != "on":
        return state
    from services import world_engine

    world = state.get("world") or {}
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    sim = world_engine.ensure_world_sim(state, day, state.get("factions") or [])
    sim.setdefault("calendar", create_calendar(str(state.get("game_id", "")), day))
    state["world_sim"] = sim
    cur = str(world.get("current_location_id") or "")
    world["season"] = season_view(sim["calendar"], day, wp.region_of(cur))
    state["world"] = world
    return state
