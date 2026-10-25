"""SPEC-303/307: calendario do mundo — meses de Valoria, estacoes canonicas, passos e festas.

Funcoes PURAS sobre os parametros congelados em `world_sim.calendar` (R2/R4/R7): nenhuma le
nivel, ficha, inventario, ouro ou party (R26/R23); toda aleatoriedade vem de `day_rng`
(`world_engine`) so na CRIACAO do calendario. Ano de Valoria (SPEC-307) = 7 meses de 20 dias
(4 semanas de 5 dias); cada mes carrega clima e uma estacao CANONICA (`primavera/verao/
outono/inverno`), chave interna das tabelas de modulacao. Sem lua nem mecanica por dia da
semana. O relogio absoluto (`world_clock.day`) segue sendo a unica fonte de tempo: a data e
sempre DERIVADA.

O calendario roda como hook `pre` do tick diario da SPEC-302 (`calendar_day_hook`): atualiza
`world["season"]`/`world["date"]`, devolve os deslocamentos de baseline de pressao do dia,
abre/cancela/encerra festas por eventos `location_state_changed` (`source="engine"`,
`cause="calendario"`) e gera digest. A estacao MODULA sistemas existentes (clima, viagem,
encontros, pressao); nao cria mecanica paralela. `RPG_CALENDAR=off|shadow|on` (ver `mode`).
"""

from __future__ import annotations

import hashlib
import os
from typing import Any, Literal

from services import world_director as wd
from services import world_pressures as wp

SEASONS: tuple[str, ...] = ("primavera", "verao", "outono", "inverno")
MODES = ("off", "shadow", "on")
CAL_VERSION = 2
V1_VERSION = 1  # SPEC-303 (4 estacoes x SEASON_DAYS); so lido por `migrate_calendar`
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


# --- calendario puro (R1-R7, R12-R14) ------------------------------------------------


def months() -> list[dict]:
    """R2: meses do ano na ordem do JSON (`id/name/of/climate/season/lore_ref`)."""
    return list(_cfg()["months"])


def weekdays() -> list[dict]:
    """R3: dias da semana (Os Cinco Sinos) `{id, name, short, lore_ref}`."""
    return list(_cfg()["weekdays"])


def _season_span(ms: list[dict], i: int) -> tuple[int, int]:
    """(meses ate o inicio do bloco contiguo da mesma estacao, tamanho do bloco em meses)."""
    n = len(ms)
    sid = ms[i]["season"]
    back = 0
    while back < n - 1 and ms[(i - back - 1) % n]["season"] == sid:
        back += 1
    fwd = 0
    while back + fwd < n - 1 and ms[(i + fwd + 1) % n]["season"] == sid:
        fwd += 1
    return back, back + fwd + 1


def create_calendar(game_id: str, anchor_day: int) -> dict:
    """R6: estacao inicial semeada + primeira virada de mes/estacao em `anchor_day + k`."""
    from services.world_engine import day_rng

    c = constants()
    ms = months()
    md, n = int(c["MONTH_DAYS"]), len(ms)
    year_days = n * md
    closers = [m for m in range(n) if ms[m]["season"] != ms[(m + 1) % n]["season"]]
    rng = day_rng(game_id, anchor_day, "calendar")
    m = closers[rng.randrange(len(closers))]
    k = rng.randint(int(c["FIRST_TURN_MIN"]), int(c["FIRST_TURN_MAX"]))
    k = max(1, min(k, md - 1))
    doy_anchor = (m + 1) * md - k
    return {
        "version": CAL_VERSION,
        "month_days": md,
        "months": n,
        "week_days": int(c["WEEK_DAYS"]),
        "epoch_offset": (doy_anchor - (int(anchor_day) - 1)) % year_days,
        "year_offset": 0,
        "anchor_day": int(anchor_day),
        "first_turn_day": int(anchor_day) + k,
    }


def date_at(cal: dict, day: int) -> dict:
    """R4: data de Valoria so dos parametros congelados e de `world_clock.day`."""
    ms, wds = months(), weekdays()
    md, n, wk = int(cal["month_days"]), int(cal["months"]), int(cal["week_days"])
    year_days = n * md
    t = int(day) - 1 + int(cal["epoch_offset"])
    doy = t % year_days
    mi = doy // md
    dom = doy % md + 1
    wi = (dom - 1) % wk
    back, span = _season_span(ms, mi)
    base = int(constants().get("YEAR_BASE", 1))
    internal_year = t // year_days + 1 + int(cal.get("year_offset", 0))
    return {
        "year": internal_year + base - 1,
        "month_index": mi,
        "month_id": ms[mi]["id"],
        "day_of_month": dom,
        "weekday_index": wi,
        "weekday_id": wds[wi]["id"],
        "season": ms[mi]["season"],
        "climate": ms[mi]["climate"],
        "day_of_year": doy,
        "day_in_season": back * md + dom,
        "season_len": span * md,
    }


def _v1_season_at(cal: dict, day: int) -> dict:
    """SPEC-303 (legado): `{season, day_in_season, year, day_of_year}` de um calendario v1."""
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


def season_at(cal: dict, day: int) -> dict:
    """R4: `{season, day_in_season, year, day_of_year}` (forma da SPEC-303). `year` aqui e o
    ano INTERNO (sem `YEAR_BASE`), base de `festa_id` — igual ao v1 apos a migracao."""
    if "month_days" not in cal and "season_days" in cal:
        return _v1_season_at(cal, day)
    d = date_at(cal, day)
    base = int(constants().get("YEAR_BASE", 1))
    return {
        "season": d["season"],
        "day_in_season": d["day_in_season"],
        "year": d["year"] - (base - 1),
        "day_of_year": d["day_of_year"],
    }


def _date_text(d: dict) -> str:
    c = constants()
    ms = {m["id"]: m for m in months()}
    wds = {w["id"]: w for w in weekdays()}
    year = f"Ano {d['year']}"
    if c.get("ERA"):
        year += f" da Era {c['ERA']}"
    return (
        f"{d['day_of_month']}º dia {ms[d['month_id']]['of']}, "
        f"{wds[d['weekday_id']]['name']} — {year}"
    )


def date_label(cal: dict, day: int) -> str:
    """R12: `3º dia de Vorrnak, Sino de Cobre — Ano 112 da Era 7`."""
    return _date_text(date_at(cal, day))


def date_view(cal: dict, day: int) -> dict:
    """R15/R16: vista da data (sem `day_of_year`/`epoch_offset`)."""
    d = date_at(cal, day)
    month = next(m for m in months() if m["id"] == d["month_id"])
    wd = next(w for w in weekdays() if w["id"] == d["weekday_id"])
    return {
        "day": int(day),
        "label": _date_text(d),
        "day_of_month": d["day_of_month"],
        "month": month["name"],
        "month_id": d["month_id"],
        "weekday": wd["name"],
        "weekday_short": wd.get("short", wd["name"]),
        "year": d["year"],
        "climate": d["climate"],
    }


def migrate_calendar(cal_v1: dict, game_id: str, day: int) -> dict:
    """R19: v1 -> v2 sem mudar a estacao nem o ano (interno) em `day` (o dia sendo virado).
    Pura; `game_id` so por simetria com `create_calendar`."""
    ms = months()
    c = constants()
    md, n = int(c["MONTH_DAYS"]), len(ms)
    year_days = n * md
    sd1 = int(cal_v1["season_days"])
    old = _v1_season_at(cal_v1, day)
    first_m = next(i for i, m in enumerate(ms) if m["season"] == old["season"])
    length = sum(md for m in ms if m["season"] == old["season"])
    doy_new = first_m * md + ((old["day_in_season"] - 1) * length) // sd1
    epoch = (doy_new - (int(day) - 1)) % year_days
    raw_year = (int(day) - 1 + epoch) // year_days + 1
    out = {
        "version": CAL_VERSION,
        "month_days": md,
        "months": n,
        "week_days": int(c["WEEK_DAYS"]),
        "epoch_offset": epoch,
        "year_offset": int(old["year"]) - raw_year,
        "anchor_day": int(cal_v1.get("anchor_day", day)),
        "migrated_from": V1_VERSION,
    }
    if "first_turn_day" in cal_v1:
        out["first_turn_day"] = int(cal_v1["first_turn_day"])
    return out


def calendar_for_read(sim: dict | None, day: int) -> dict | None:
    """R16: calendario v2 de `sim` (v1 convertido EM MEMORIA, sem gravar); `None` se ausente
    ou de versao desconhecida."""
    cal = (sim or {}).get("calendar")
    if not isinstance(cal, dict):
        return None
    if cal.get("version") == CAL_VERSION and "month_days" in cal and "epoch_offset" in cal:
        return cal
    if cal.get("version") == V1_VERSION and "season_days" in cal and "epoch_offset" in cal:
        return migrate_calendar(cal, "", day)
    return None


def clock_date_label(world: dict | None, calendar: dict | None = None) -> str:
    """R13: rotulo de data para `clock_label`; `""` => o chamador usa o texto legado."""
    if mode() != "on":
        return ""
    world = world or {}
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    if isinstance(calendar, dict):
        cal = calendar_for_read({"calendar": calendar}, day)
        if cal:
            return date_label(cal, day)
    view = world.get("date")
    if isinstance(view, dict) and view.get("day") == day and view.get("label"):
        return str(view["label"])
    return ""


def label_for(season: str, region_id: str) -> str:
    """R6: rotulo regional da estacao canonica (default quando a regiao nao define)."""
    labels = _cfg()["labels"]
    return str(
        (labels.get(region_id) or {}).get(season)
        or labels["default"].get(season)
        or str(season).capitalize()
    )


def has_regional_label(season: str, region_id: str) -> bool:
    """D8: a regiao define rotulo proprio para a estacao (Skallgard, Zhur)."""
    return season in (_cfg()["labels"].get(region_id) or {})


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
    """Registros planejados do ano (`year` = ano interno de `season_at`): `start_day` e
    `end_day` (dia em que a festa acaba). Posicao por mes + dia do mes (R11)."""
    md, n = int(cal["month_days"]), int(cal["months"])
    index = {m["id"]: i for i, m in enumerate(months())}
    out: list[dict] = []
    for f in festivals_catalog():
        doy = index[f["month"]] * md + int(f["day_of_month"]) - 1
        start = (int(year) - 1 - int(cal.get("year_offset", 0))) * n * md + doy
        start += 1 - int(cal["epoch_offset"])
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
                        event_ids=[ev["event_id"]],
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
    migrated = False
    if not isinstance(cal, dict):
        cal = create_calendar(ctx.game_id, day - 1)  # R5: liga no proximo dia virado
        sim[key] = cal
    elif cal.get("version") == V1_VERSION and "season_days" in cal:
        cal = migrate_calendar(cal, ctx.game_id, day)  # R19: sem salto de estacao
        sim[key] = cal
        migrated = True
        # R20: anunciadas v1 sao descartadas (o agendamento v2 recalcula); ativas seguem.
        sim["festivals"] = [
            r
            for r in sim.get("festivals", [])
            if isinstance(r, dict) and r.get("status") != "anunciada"
        ]
    elif cal.get("version") != CAL_VERSION:
        # R7: versao desconhecida e neutra (sem data/modulacao) e NUNCA recriada.
        log_event("world", "calendar", level="warning", day=day, mode=m, neutral=True)
        return res
    d = date_at(cal, day)
    info, prev = season_at(cal, day), season_at(cal, day - 1)
    changed = info["season"] != prev["season"]
    passes_closed = 0
    events: list[dict] = []
    digest: list[dict] = []
    counts = {"started": 0, "cancelled": 0}
    if m == "on":
        cur = str((ctx.world or {}).get("current_location_id") or "")
        ctx.world["season"] = season_view(cal, day, wp.region_of(cur))
        ctx.world["date"] = date_view(cal, day)  # R15
        res.baseline_offsets = baseline_offsets(info["season"])
        if changed:
            digest.append(
                wd.digest_item(
                    ctx.game_id,
                    day,
                    "estacao",
                    "",
                    "",
                    f"estacao.inicio.{info['season']}",
                    {"mes": next(x["name"] for x in months() if x["id"] == d["month_id"])},
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
        month_id=d["month_id"],
        day_of_month=d["day_of_month"],
        weekday_id=d["weekday_id"],
        year=d["year"],
        migrated=migrated,
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
    world["date"] = date_view(sim["calendar"], day)  # R15
    state["world"] = world
    return state
