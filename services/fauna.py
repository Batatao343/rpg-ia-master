"""services/fauna.py — fauna viva: ecologia deterministica, presenca e sinais (SPEC-360).

Writer unico de `world_sim.fauna` (`{"v": 1, "presencas": [...], "carcacas": [...]}`): toda
funcao que muda o estado devolve um `world_sim` NOVO (nunca muta o recebido), exceto o hook
diario, que muta `ctx.sim` como os outros hooks do motor de mundo.

Mecanica e Python: peso, presenca, sinal, caca e carcaca sao funcoes puras de estado mais
`world_engine.day_rng`. A LLM so recebe a pista pronta (`<SINAIS_NA_CENA>`, 0 token sem sinal).
Flags (SPEC-340): `RPG_FAUNA` = off|shadow|on (pesos, R8-R12) e `RPG_FAUNA_SINAIS` = off|on
(presenca, sinais, aproximacao, caca e rumor, R13-R23; exige `RPG_FAUNA != off`).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

MODES = ("off", "shadow", "on")  # RPG_FAUNA
SINAIS_MODES = ("off", "on")  # RPG_FAUNA_SINAIS
FAUNA_JSON = Path(__file__).resolve().parent.parent / "data" / "world" / "fauna.json"
CONFIG_JSON = Path(__file__).resolve().parent.parent / "data" / "world" / "fauna_config.json"
SIM_VERSION = 1
FIRST_SIGNS = ("marca", "rastro", "resto")  # vestigio antes (R14)
LATER_SIGNS = ("som", "cheiro")  # so depois de >= 1 sinal mostrado
SIGN_TYPES = (*FIRST_SIGNS, *LATER_SIGNS)
SCENE_RULE = "Narre como detalhe do ambiente; não nomeie nem descreva a criatura."
_STATUS = ("ativa", "encontrada", "dispersa", "cacada")
_ORIGENS = ("dia", "conversao", "rastro")


class Presenca(TypedDict):
    pid: str
    creature_id: str
    region_id: str
    locais: list[str]
    born_day: int
    expires_day: int
    sinais_mostrados: list[str]
    origem: Literal["dia", "conversao", "rastro"]
    status: Literal["ativa", "encontrada", "dispersa", "cacada"]


class FaunaSim(TypedDict):
    v: int
    presencas: list[Presenca]
    carcacas: list[dict]


# --------------------------------------------------------------------------- flags e dados

_warned_sinais = False


def mode() -> str:
    raw = os.getenv("RPG_FAUNA", "").strip().lower()
    return raw if raw in MODES else "off"


def sinais_mode() -> str:
    """`RPG_FAUNA_SINAIS`; exige `RPG_FAUNA != off` (senao vale `off`, com 1 log)."""
    global _warned_sinais
    raw = os.getenv("RPG_FAUNA_SINAIS", "").strip().lower()
    val = raw if raw in SINAIS_MODES else "off"
    if val == "on" and mode() == "off":
        if not _warned_sinais:
            _warned_sinais = True
            _log("sinais_sem_motor")
        return "off"
    return val


@lru_cache(maxsize=1)
def _config() -> dict:
    return dict(json.loads(CONFIG_JSON.read_text(encoding="utf-8")).get("constants") or {})


def const(name: str) -> Any:
    return _config()[name]


@lru_cache(maxsize=1)
def load() -> dict[str, dict]:
    """`{creature_id: entrada}` do `fauna.json` (cada entrada ganha `id`). Sem arquivo: vazio."""
    if not FAUNA_JSON.exists():
        return {}
    doc = json.loads(FAUNA_JSON.read_text(encoding="utf-8"))
    return {cid: {**e, "id": cid} for cid, e in (doc.get("criaturas") or {}).items()}


def entry(creature_id: str) -> dict | None:
    return load().get(str(creature_id or ""))


def effective_territory(creature_id: str) -> list[str]:
    return list(((entry(creature_id) or {}).get("ecologia") or {}).get("territorio") or [])


def approach_line(creature_id: str) -> str:
    """R17: frase de aproximacao da criatura ("" sem fauna)."""
    return str(((entry(creature_id) or {}).get("sinais") or {}).get("aproximacao") or "")


def _log(name: str, **fields: Any) -> None:
    try:
        from observability.telemetry import log_event

        log_event("fauna", name, level="info", **fields)
    except Exception:  # silent-ok: telemetria nunca derruba o jogo
        pass


def _sha(*parts: Any) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _bestiary(creature_id: str) -> dict:
    import gamedata

    return (gamedata.BESTIARY or {}).get(creature_id) or {}


def _in_region(creature_id: str, region_id: str) -> bool:
    return region_id in (_bestiary(creature_id).get("regions") or [])


# --------------------------------------------------------------------------- estado


def _empty() -> FaunaSim:
    return {"v": SIM_VERSION, "presencas": [], "carcacas": []}


def _cap_presences(rows: list[dict]) -> list[dict]:
    cap = int(const("MAX_PRESENCAS"))
    if len(rows) <= cap:
        return rows
    active = [r for r in rows if r.get("status") == "ativa"]
    rest = sorted(
        (r for r in rows if r.get("status") != "ativa"),
        key=lambda r: (-int(r.get("born_day", 0)), str(r.get("pid"))),
    )
    keep = {id(r) for r in (active + rest)[:cap]}
    return [r for r in rows if id(r) in keep]


def normalize_fauna_sim(raw: Any) -> FaunaSim:
    """R24: save antigo (sem a chave) vira vazio; presenca de criatura que sumiu do
    `fauna.json` e descartada (com `log_fallback`); caps respeitados."""
    if not isinstance(raw, dict):
        return _empty()
    crit = load()
    pres: list[dict] = []
    for p in raw.get("presencas") or []:
        if not isinstance(p, dict) or not p.get("pid"):
            continue
        if p.get("creature_id") not in crit:
            try:
                from observability.telemetry import log_fallback

                log_fallback(
                    "fauna",
                    "presenca_sem_criatura",
                    ValueError(str(p.get("creature_id"))),
                )
            except Exception:  # silent-ok
                pass
            continue
        row = {
            "pid": str(p["pid"]),
            "creature_id": str(p["creature_id"]),
            "region_id": str(p.get("region_id") or ""),
            "locais": [str(x) for x in p.get("locais") or []][: int(const("MAX_LOCAIS"))],
            "born_day": int(p.get("born_day", 0) or 0),
            "expires_day": int(p.get("expires_day", 0) or 0),
            "sinais_mostrados": [
                str(s) for s in p.get("sinais_mostrados") or [] if s in SIGN_TYPES
            ],
            "origem": p.get("origem") if p.get("origem") in _ORIGENS else "dia",
            "status": p.get("status") if p.get("status") in _STATUS else "ativa",
        }
        pres.append(row)
    carc = [
        {"loc": str(c["loc"]), "day": int(c["day"]), "creature_id": str(c["creature_id"])}
        for c in raw.get("carcacas") or []
        if isinstance(c, dict) and c.get("loc") and c.get("creature_id") and "day" in c
    ][-int(const("MAX_CARCACAS")) :]
    return {"v": SIM_VERSION, "presencas": _cap_presences(pres), "carcacas": carc}


def _fauna_of(sim: dict | None) -> FaunaSim:
    return normalize_fauna_sim((sim or {}).get("fauna"))


def _with_fauna(sim: dict | None, fauna: FaunaSim) -> dict:
    out = dict(sim or {})
    out["fauna"] = fauna
    return out


def _day(world: dict | None) -> int:
    return int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)


def _active(p: dict, day: int) -> bool:
    return p.get("status") == "ativa" and int(p.get("expires_day", 0)) >= int(day)


def presences_at(sim: dict | None, location_id: str, day: int) -> list[Presenca]:
    """Presencas ativas no local: primeiro a que o jogador ja vem lendo (com sinal mostrado),
    depois a mais recente; empate por pid."""
    rows = [
        p
        for p in ((sim or {}).get("fauna") or {}).get("presencas") or []
        if isinstance(p, dict) and _active(p, day) and location_id in (p.get("locais") or [])
    ]
    rows.sort(
        key=lambda p: (
            0 if p.get("sinais_mostrados") else 1,
            -int(p.get("born_day", 0)),
            str(p.get("pid")),
        )
    )
    return rows  # type: ignore[return-value]


def presence_at(sim: dict | None, location_id: str, day: int) -> Presenca | None:
    """A presenca do local que o encontro usa (R15): a ja anunciada vem antes da nova."""
    rows = presences_at(sim, location_id, day)
    return rows[0] if rows else None


def presence_by_id(sim: dict | None, pid: str) -> dict | None:
    for p in ((sim or {}).get("fauna") or {}).get("presencas") or []:
        if isinstance(p, dict) and p.get("pid") == pid:
            return p
    return None


def _carcasses_at(fauna: dict, location_id: str, day: int) -> list[str]:
    ttl = int(const("CARCACA_DIAS"))
    return [
        str(c["creature_id"])
        for c in fauna.get("carcacas") or []
        if c.get("loc") == location_id and 0 <= int(day) - int(c.get("day", 0)) <= ttl
    ]


# --------------------------------------------------------------------------- ecologia (R8-R10)


@dataclass(frozen=True)
class EcoCtx:
    location_id: str
    region_id: str
    period: str | None
    season: str | None
    bestiary_knowledge: dict = field(default_factory=dict)
    turn: int = 0
    pressure_bands: dict = field(default_factory=dict)
    weather_state: str | None = None
    carcacas_aqui: list = field(default_factory=list)
    presencas_aqui: list = field(default_factory=list)


def eco_ctx(
    world: dict | None,
    world_sim: dict | None,
    *,
    location_id: str,
    region_id: str,
    bestiary_knowledge: dict | None,
    turn: int,
    season: str | None,
) -> EcoCtx:
    world = world or {}
    sim = world_sim or {}
    day = _day(world)
    fauna = (sim.get("fauna") or {}) if isinstance(sim.get("fauna"), dict) else {}
    pres = [
        str(p.get("creature_id"))
        for p in fauna.get("presencas") or []
        if isinstance(p, dict) and _active(p, day) and location_id in (p.get("locais") or [])
    ]
    return EcoCtx(
        location_id=location_id,
        region_id=region_id,
        period=((world.get("world_clock") or {}).get("period") or world.get("time_of_day")),
        season=season,
        bestiary_knowledge=dict(bestiary_knowledge or {}),
        turn=int(turn or 0),
        pressure_bands=dict((sim.get("bands") or {}).get(region_id) or {}),
        weather_state=world.get("weather_state"),
        carcacas_aqui=_carcasses_at(fauna, location_id, day) if location_id else [],
        presencas_aqui=pres,
    )


def _suppressed(creature_id: str, ctx: EcoCtx) -> bool:
    from services.ecology import hunt_pressure

    return hunt_pressure(creature_id, ctx.bestiary_knowledge, ctx.turn) <= float(
        const("PRESSAO_SUPRIMIDA")
    )


def _condition(cond: str, ctx: EcoCtx) -> bool:
    if cond == "carcaca_recente":
        return bool(ctx.carcacas_aqui)
    kind, _, val = cond.partition(":")
    if kind == "clima":
        return bool(val) and ctx.weather_state == val
    if kind == "pressao":
        return ctx.pressure_bands.get(val) in ("sinal", "crise")
    return False


def eco_multiplier(entry: dict, ctx: EcoCtx) -> tuple[float, list[str]]:
    """R8: fator ecologico da criatura no contexto e as razoes (ids curtos, nunca texto)."""
    eco = (entry or {}).get("ecologia") or {}
    f, why = 1.0, []
    hor = eco.get("horario") or []
    if ctx.period and hor and ctx.period not in hor:
        f *= float(const("HORARIO_FORA"))
        why.append("horario")
    if ctx.season:
        m = float((eco.get("estacoes") or {}).get(ctx.season, 1.0))
        if m != 1.0:
            f *= m
            why.append(f"estacao:{ctx.season}")
    terr = eco.get("territorio") or []
    if ctx.location_id and terr and ctx.location_id not in terr:
        f *= float(const("TERRITORIO_FORA"))
        why.append("territorio")
    preds = [p for p in entry.get("predadores") or [] if _in_region(p, ctx.region_id)]
    if any(_suppressed(p, ctx) for p in preds):
        f *= float(const("PRESA_LIBERADA"))
        why.append("presa_liberada")
    preys = [q for q in eco.get("presas") or [] if _in_region(q, ctx.region_id)]
    if preys and all(_suppressed(q, ctx) for q in preys):
        f *= float(const("PREDADOR_FAMINTO"))
        why.append("predador_faminto")
    if set(eco.get("foge_de") or []) & set(ctx.presencas_aqui):
        f *= float(const("FOGE_DE"))
        why.append("foge_de")
    for r in eco.get("reage") or []:
        if _condition(str(r.get("quando") or ""), ctx):
            eff = r.get("efeito")
            f *= {"mais": float(const("REAGE_MAIS")), "menos": float(const("REAGE_MENOS"))}.get(
                eff, 0.0
            )
            why.append(f"reage:{r.get('quando')}:{eff}")
    return f, why


# --------------------------------------------------------------------------- presenca (R13, R19)


def _make_presence(
    game_id: str,
    creature_id: str,
    region_id: str,
    locais: list[str],
    day: int,
    origem: str,
    ttl: int,
) -> Presenca:
    return {
        "pid": _sha(game_id, creature_id, day, origem)[:12],
        "creature_id": creature_id,
        "region_id": region_id,
        "locais": list(dict.fromkeys(locais))[: int(const("MAX_LOCAIS"))],
        "born_day": int(day),
        "expires_day": int(day) + max(0, int(ttl) - 1),
        "sinais_mostrados": [],
        "origem": origem,  # type: ignore[typeddict-item]
        "status": "ativa",
    }


def _ttl(e: dict, game_id: str, day: int, salt: str) -> int:
    lo, hi = (list((e.get("ecologia") or {}).get("permanencia") or [3, 6]) + [3, 6])[:2]
    lo, hi = int(lo), int(max(lo, hi))
    return lo + int(_sha(game_id, day, salt)[:6], 16) % (hi - lo + 1)


def _expire(fauna: FaunaSim, day: int) -> FaunaSim:
    for p in fauna["presencas"]:
        if p["status"] == "ativa" and int(p["expires_day"]) < int(day):
            p["status"] = "dispersa"
            _log("presenca_expira", creature=p["creature_id"], sinais=len(p["sinais_mostrados"]))
    ttl = int(const("CARCACA_DIAS"))
    fauna["carcacas"] = [c for c in fauna["carcacas"] if int(day) - int(c["day"]) <= ttl]
    return fauna


def _region_danger(region_id: str, world: dict | None) -> int:
    import gamedata
    from world_utils import _effective_danger

    vals = [
        _effective_danger(world or {}, loc["id"])
        for loc in gamedata.WORLD_MAP.get("locations", [])
        if loc.get("region_id") == region_id and not loc.get("parent_id")
    ]
    return max(vals) if vals else 1


def _fits_danger(creature_id: str, danger: int) -> bool:
    elite = "elite" in str(_bestiary(creature_id).get("type", "")).lower()
    if danger <= 2:
        return not elite
    if danger >= 4:
        return elite
    return True


def _region_candidates(region_id: str, danger: int) -> list[dict]:
    from encounter_budget import is_boss

    return [
        e
        for cid, e in sorted(load().items())
        if e.get("regiao") == region_id
        and _bestiary(cid)
        and not is_boss(_bestiary(cid))
        and _fits_danger(cid, danger)
    ]


def day_hook(ctx: Any):
    """R13: hook diario `post` order 15 (antes dos rumores). Muta `ctx.sim["fauna"]`."""
    from services import world_engine
    from services import world_pressures as wp

    result = world_engine.DayHookResult()
    if sinais_mode() != "on" or world_engine.mode() != "on":
        return result
    sim, day = ctx.sim, int(ctx.day)
    fauna = _expire(_fauna_of(sim), day)
    regions: set[str] = set()
    try:
        from services import rumors

        regions.update(rumors.frequented_regions(sim, day))
    except Exception:  # silent-ok: sem rumores, so a regiao atual
        pass
    here = wp.region_of(str(((ctx.world or {}).get("current_location_id")) or ""))
    if here:
        regions.add(here)
    state = ctx.state or {}
    world = ctx.world or {}
    from services import world_calendar

    season = world_calendar.active_season(world)
    rng = world_engine.day_rng(ctx.game_id, day, "fauna")
    for region in sorted(regions):
        roll, pick = rng.random(), rng.random()  # sempre 2 sorteios por regiao
        active = [p for p in fauna["presencas"] if p["region_id"] == region and _active(p, day)]
        if len(active) >= int(const("MAX_PRESENCAS_REGIAO")) or roll >= float(const("P_PRESENCA")):
            continue
        taken = {p["creature_id"] for p in active}
        ectx = EcoCtx(
            location_id="",
            region_id=region,
            period=None,
            season=season,
            bestiary_knowledge=dict(state.get("bestiary_knowledge") or {}),
            turn=int(world.get("turn_count", 0) or 0),
            pressure_bands=dict((sim.get("bands") or {}).get(region) or {}),
            weather_state=world.get("weather_state"),
        )
        cands = [
            e
            for e in _region_candidates(region, _region_danger(region, world))
            if e["id"] not in taken
        ]
        # territorio ja ocupado por outra presenca pesa menos (as criaturas se espalham)
        covered = {n for p in active for n in p["locais"]}
        weights = [
            eco_multiplier(e, ectx)[0]
            * (
                1.0
                if set(effective_territory(e["id"])) - covered
                else float(const("TERRITORIO_OCUPADO"))
            )
            for e in cands
        ]
        total = sum(weights)
        if total <= 0:
            continue
        acc, chosen = 0.0, cands[-1]
        for e, w in zip(cands, weights):
            acc += w
            if pick * total < acc:
                chosen = e
                break
        locais = [n for n in effective_territory(chosen["id"]) if wp.region_of(n) == region]
        if not locais:
            continue
        pres = _make_presence(
            ctx.game_id,
            chosen["id"],
            region,
            locais,
            day,
            "dia",
            _ttl(chosen, ctx.game_id, day, chosen["id"]),
        )
        fauna["presencas"].append(pres)
        _log("presenca_nasce", creature=chosen["id"], region=region, origem="dia")
    fauna["presencas"] = _cap_presences(fauna["presencas"])
    sim["fauna"] = fauna
    return result


# --------------------------------------------------------------------------- sinais (R14-R16, R22)


def _next_sign(e: dict, shown: list[str], pid: str) -> str | None:
    sinais = (e or {}).get("sinais") or {}
    first = [t for t in FIRST_SIGNS if sinais.get(t) and t not in shown]
    later = [t for t in LATER_SIGNS if sinais.get(t) and t not in shown]
    if not shown:
        opts = first or later
    else:
        opts = first + later
    if not opts:
        return None
    return opts[int(_sha(pid, len(shown))[:6], 16) % len(opts)]


def render_block(text: str) -> str:
    return f"<SINAIS_NA_CENA>\n- {text}\n{SCENE_RULE}\n</SINAIS_NA_CENA>"


def scene_block(state: dict) -> tuple[str, dict]:
    """R14: no maximo 1 sinal novo por cena, da presenca ativa no local. Sem sinal novo o
    bloco nao existe (`("", {})`, zero token)."""
    if sinais_mode() != "on":
        return "", {}
    world = state.get("world") or {}
    sim = state.get("world_sim") or {}
    day, loc = _day(world), str(world.get("current_location_id") or "")
    pres, e, kind = None, None, None
    for cand in presences_at(sim, loc, day):  # a anunciada continua; esgotada, passa a vez
        e = entry(cand["creature_id"])
        kind = _next_sign(e or {}, list(cand.get("sinais_mostrados") or []), cand["pid"])
        if kind:
            pres = cand
            break
    if not pres or not e or not kind:
        return "", {}
    fauna = _fauna_of(sim)
    for p in fauna["presencas"]:
        if p["pid"] == pres["pid"]:
            p["sinais_mostrados"] = [*p["sinais_mostrados"], kind]
    _log("sinal", creature=pres["creature_id"], tipo=kind, origem="cena")
    return render_block(str(e["sinais"][kind])), {"world_sim": _with_fauna(sim, fauna)}


def _add_presence(
    state: dict, e: dict, location_id: str, day: int, origem: str, first: str | None
) -> tuple[dict, dict]:
    import gamedata

    sim = state.get("world_sim") or {}
    fauna = _fauna_of(sim)
    region = str((gamedata.get_location(location_id) or {}).get("region_id") or e.get("regiao"))
    gid = str(state.get("game_id") or "")
    locais = [location_id, *[n for n in effective_territory(e["id"]) if n != location_id]]
    pres = _make_presence(
        gid, e["id"], region, locais, day, origem, _ttl(e, gid, day, f"{origem}:{e['id']}")
    )
    if first:
        pres["sinais_mostrados"] = [first]
    fauna["presencas"] = _cap_presences([*fauna["presencas"], pres])
    _log("presenca_nasce", creature=e["id"], region=region, origem=origem)
    return _with_fauna(sim, fauna), pres


def convert_to_signal(state: dict, entry: dict, location_id: str, day: int) -> tuple[str, dict]:
    """R16: gatilho de fauna sem presenca (ou com presenca ainda sem sinal, §9) + criatura
    `cedo` vira sinal (sem combate). A presenca que ja esta no local mostra o 1o sinal."""
    sim0 = state.get("world_sim") or {}
    pres = presence_at(sim0, location_id, day)
    if pres and pres["creature_id"] == entry.get("id") and not pres.get("sinais_mostrados"):
        kind = _next_sign(entry, [], pres["pid"])
        if not kind:
            return "", {}
        fauna = _fauna_of(sim0)
        for p in fauna["presencas"]:
            if p["pid"] == pres["pid"]:
                p["sinais_mostrados"] = [kind]
        _log("conversao", creature=entry.get("id"), tipo=kind)
        return str(entry["sinais"][kind]), {"world_sim": _with_fauna(sim0, fauna)}
    kind = _next_sign(entry, [], _sha(state.get("game_id"), entry.get("id"), day))
    if not kind:
        return "", {}
    sim, _pres = _add_presence(state, entry, location_id, day, "conversao", kind)
    _log("conversao", creature=entry.get("id"), tipo=kind)
    return str(entry["sinais"][kind]), {"world_sim": sim}


def track_signal(state: dict, entry: dict, location_id: str, day: int) -> tuple[str, dict]:
    """R22: o rastro sorteado mostra o `sinais.rastro` (sem nome) e cria ou reforca a presenca."""
    if sinais_mode() != "on":
        return "", {}
    text = str(((entry or {}).get("sinais") or {}).get("rastro") or "")
    if not text:
        return "", {}
    sim = state.get("world_sim") or {}
    fauna = _fauna_of(sim)
    for p in fauna["presencas"]:
        if p["creature_id"] == entry["id"] and _active(p, day):
            if location_id not in p["locais"] and len(p["locais"]) < int(const("MAX_LOCAIS")):
                p["locais"] = [*p["locais"], location_id]
            if "rastro" not in p["sinais_mostrados"]:
                p["sinais_mostrados"] = [*p["sinais_mostrados"], "rastro"]
            p["expires_day"] = max(int(p["expires_day"]), int(day) + 1)
            _log("sinal", creature=entry["id"], tipo="rastro", origem="rastro")
            return text, {"world_sim": _with_fauna(sim, fauna)}
    new_sim, _pres = _add_presence(state, entry, location_id, day, "rastro", "rastro")
    _log("sinal", creature=entry["id"], tipo="rastro", origem="rastro")
    return text, {"world_sim": new_sim}


# --------------------------------------------------------------------------- encontro e caca


def detection_bonus(sim: dict | None, presence_id: str) -> int:
    """R18: quem leu >= 2 sinais da presenca percebe melhor o encontro dela."""
    p = presence_by_id(sim, presence_id) if presence_id else None
    if p and len(p.get("sinais_mostrados") or []) >= int(const("SINAIS_PARA_BONUS")):
        return int(const("PRESENCA_BONUS_DETECCAO"))
    return 0


def mark_encountered(
    sim: dict | None, presence_id: str, day: int, *, status: str = "encontrada"
) -> tuple[dict, list[str]]:
    """Fecha a presenca no encontro; devolve os tipos de sinal mostrados (R23)."""
    fauna = _fauna_of(sim)
    shown: list[str] = []
    for p in fauna["presencas"]:
        if p["pid"] == presence_id:
            shown = list(p["sinais_mostrados"])
            p["status"] = status if status in _STATUS else "encontrada"
            _log(
                "encontro",
                creature=p["creature_id"],
                precedido=bool(shown),
                sinais=len(shown),
                caca=status == "cacada",
            )
    return _with_fauna(sim, fauna), shown


def record_kill(sim: dict | None, creature_id: str, location_id: str, day: int) -> dict:
    """R11: morte de criatura de fauna deixa carcaca no local (cap 20, expira em 2 dias)."""
    if mode() == "off" or not entry(creature_id) or not location_id:
        return dict(sim or {})
    fauna = _expire(_fauna_of(sim), day)
    fauna["carcacas"] = [
        *fauna["carcacas"],
        {"loc": str(location_id), "day": int(day), "creature_id": str(creature_id)},
    ][-int(const("MAX_CARCACAS")) :]
    return _with_fauna(sim, fauna)


_HUNT_RE = re.compile(
    r"\b(?:sig[oa]|seguir|segue|sigamos|vou seguir)\s+(?:o|os|a|as|esse|esses|aquele)?\s*"
    r"(?:rastros?|pegadas?|cheiro|som|trilha|marcas?)\b"
    r"|\brastre(?:ar|io|amos|ia|ando)\b"
    r"|\bcac(?:ar|amos|ando)\b"
    r"|\bir atras do que deixou\b"
    r"|\bvou atras do que deixou\b",
)


def _fold(text: str) -> str:
    import unicodedata

    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(ch)
    )


def hunt_intent(text: str) -> bool:
    """R20: intencao de cacar o que deixou os sinais (regex fechada, sem LLM)."""
    return bool(_HUNT_RE.search(_fold(text)))


def hunt_hint(state: dict, world: dict, player_level: int, text: str = "") -> dict | None:
    """R20: com intencao de caca, >= 1 sinal mostrado e presenca ativa no local, um encontro
    no lugar, com a surpresa do jogador. Forma do `law_hint`. Sem LLM."""
    if sinais_mode() != "on" or not hunt_intent(text):
        return None
    sim = state.get("world_sim") or {}
    loc_id = str((world or {}).get("current_location_id") or "")
    pres = presence_at(sim, loc_id, _day(world))
    if not pres or not pres.get("sinais_mostrados"):
        return None
    import gamedata
    from world_utils import _effective_danger, forced_encounter_danger

    cid = pres["creature_id"]
    loc = gamedata.get_location(loc_id) or {}
    eff = forced_encounter_danger(loc, _effective_danger(world or {}, loc_id), player_level)
    _log("caca", creature=cid, sinais=len(pres["sinais_mostrados"]))
    return {
        "hint": str(_bestiary(cid).get("name") or cid),
        "enemy_id": cid,
        "flavor": approach_line(cid),
        "aproximacao": approach_line(cid),
        "reason": "caca",
        "presence_id": pres["pid"],
        "always_combat": True,
        "eff_danger": eff,
    }


# --------------------------------------------------------------------------- telemetria (R29)


def summary(sim: dict | None) -> dict:
    """Contagens do playtest derivadas do estado (sem texto nem nome): sinais mostrados,
    encontros (precedidos ou nao) e cacadas."""
    rows = [
        p for p in ((sim or {}).get("fauna") or {}).get("presencas") or [] if isinstance(p, dict)
    ]
    met = [p for p in rows if p.get("status") in ("encontrada", "cacada")]
    return {
        "sinal": sum(len(p.get("sinais_mostrados") or []) for p in rows),
        "encontro": len(met),
        "encontro_precedido": sum(1 for p in met if p.get("sinais_mostrados")),
        "caca": sum(1 for p in rows if p.get("status") == "cacada"),
        "presencas": len(rows),
    }
