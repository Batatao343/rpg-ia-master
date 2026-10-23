"""SPEC-302 R6-R10: modelo PURO de pressoes regionais (sem estado global, sem LLM).

Quatro pressoes inteiras [0,100] por regiao (`guerra`, `fome`, `praga`, `abismo`) que
sobem por causas, derivam para a baseline, ruido seeded e contagio de praga. Bandas com
histerese (`normal` -> `sinal` -> `crise`) e escolha de sinais pequenos. Toda
aleatoriedade vem do `rng` recebido (ver `world_engine.day_rng`); nada aqui le o heroi.
"""

from __future__ import annotations

import json
import math
import os
from functools import cache, lru_cache
from typing import Any

KINDS: tuple[str, ...] = ("guerra", "fome", "praga", "abismo")
BANDS = ("normal", "sinal", "crise")
_DATA_DIR = os.path.join("data", "world")


@cache
def _load_json(name: str) -> dict:
    path = os.path.join(_DATA_DIR, name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def get_config() -> dict:
    """Config cacheada de `data/world/pressures.json` (nao mutar o retorno)."""
    return _load_json("pressures.json")


def constants(cfg: dict | None = None) -> dict:
    return (cfg or get_config())["constants"]


def director_constants(cfg: dict | None = None) -> dict:
    return (cfg or get_config())["director"]


# --- geografia derivada do mapa (R6/R8) ------------------------------------------


@lru_cache(maxsize=1)
def _map_index() -> tuple[dict, dict, dict]:
    """(location_by_id, region_of, region_links) a partir de `gamedata.WORLD_MAP`."""
    import gamedata

    locs = {loc["id"]: loc for loc in gamedata.WORLD_MAP.get("locations", [])}
    region_of = {lid: str(loc.get("region_id") or "") for lid, loc in locs.items()}
    links: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for lid, loc in locs.items():
        for other in loc.get("connections") or []:
            ra, rb = region_of.get(lid, ""), region_of.get(other, "")
            if not ra or not rb or ra == rb:
                continue
            for key, pair in (((ra, rb), (lid, other)), ((rb, ra), (other, lid))):
                lst = links.setdefault(key, [])
                if pair not in lst and (pair[1], pair[0]) not in lst:
                    lst.append(pair)
    return locs, region_of, links


def region_ids() -> list[str]:
    """As regioes do mapa, ordenadas (estavel)."""
    return sorted({r for r in _map_index()[1].values() if r})


def region_of(location_id: str) -> str:
    return _map_index()[1].get(str(location_id or ""), "")


def region_adjacency() -> dict[str, list[str]]:
    """Adjacencia simetrica derivada das `connections` entre `region_id` diferentes."""
    adj: dict[str, set[str]] = {r: set() for r in region_ids()}
    for ra, rb in _map_index()[2]:
        adj.setdefault(ra, set()).add(rb)
    return {r: sorted(v) for r, v in adj.items()}


def region_link_pairs(ra: str, rb: str) -> list[tuple[str, str]]:
    return list(_map_index()[2].get((ra, rb), []))


def region_primary_location(region_id: str) -> str:
    """Local-ancora da regiao: o de mesmo id; senao o primeiro nao-interior (ordenado)."""
    locs = _map_index()[0]
    if region_id in locs and locs[region_id].get("region_id") == region_id:
        return region_id
    cands = sorted(
        lid
        for lid, loc in locs.items()
        if loc.get("region_id") == region_id and loc.get("kind") != "interior"
    )
    return cands[0] if cands else ""


def region_label(region_id: str) -> str:
    """Nome de exibicao da regiao (campo `region` dos locais)."""
    for loc in _map_index()[0].values():
        if loc.get("region_id") == region_id and loc.get("region"):
            return str(loc["region"])
    return region_id


# --- estado inicial / bandas (R6, R9) ---------------------------------------------


def baseline(cfg: dict | None = None) -> dict[str, dict[str, int]]:
    """Baseline por regiao do mapa (regiao sem entrada = 10 em tudo)."""
    table = (cfg or get_config())["regions"]
    return {r: {k: int(table.get(r, {}).get(k, 10)) for k in KINDS} for r in region_ids()}


def next_band(old: str, value: int, cfg: dict | None = None) -> str:
    """Histerese: sobe em SINAL/CRISE; so desce abaixo de RECUPERA (sinal) / CRISE-HYST."""
    c = constants(cfg)
    sinal, crise, rec, hyst = c["SINAL"], c["CRISE"], c["RECUPERA"], c.get("CRISE_HYST", 5)
    if old == "crise":
        if value >= crise - hyst:
            return "crise"
        return "sinal" if value >= rec else "normal"
    if value >= crise:
        return "crise"
    if old == "sinal":
        return "sinal" if value >= rec else "normal"
    return "sinal" if value >= sinal else "normal"


def initial_bands(pressures: dict, cfg: dict | None = None) -> dict[str, dict[str, str]]:
    return {
        r: {k: next_band("normal", int(v), cfg) for k, v in row.items()}
        for r, row in pressures.items()
    }


def update_bands(
    bands: dict, pressures: dict, cfg: dict | None = None
) -> tuple[dict, list[tuple[str, str, str, str]]]:
    """Novas bandas + transicoes de SUBIDA `(regiao, tipo, antiga, nova)` (R9)."""
    new: dict[str, dict[str, str]] = {}
    ups: list[tuple[str, str, str, str]] = []
    for r in sorted(pressures):
        new[r] = {}
        for k in KINDS:
            old = (bands.get(r) or {}).get(k, "normal")
            nb = next_band(old, int(pressures[r].get(k, 0)), cfg)
            new[r][k] = nb
            if BANDS.index(nb) > BANDS.index(old):
                ups.append((r, k, old, nb))
    return new, ups


# --- dinamica diaria (R7, R8) -----------------------------------------------------


def _clamp(v: int) -> int:
    return max(0, min(100, int(v)))


def step_pressures(
    pressures: dict,
    *,
    rng: Any,
    cfg: dict | None = None,
    deltas: dict | None = None,
    relief: dict | None = None,
    blocked_pairs: set | None = None,
) -> dict[str, dict[str, int]]:
    """Um dia de dinamica. Ordem: (a)+(b) `deltas`/`relief`/surtos, (c) deriva,
    (d) ruido, (e) contagio de praga, (f) clamp. Puro: devolve nova tabela."""
    c = constants(cfg)
    base = baseline(cfg)
    weights = (cfg or get_config()).get("surge_weight", {})
    deltas = deltas or {}
    relief = relief or {}
    blocked_pairs = blocked_pairs or set()
    out = {
        r: {k: int(pressures.get(r, {}).get(k, base[r][k])) for k in KINDS} for r in sorted(base)
    }

    for r in sorted(out):
        for k in KINDS:
            v = out[r][k] + int((deltas.get(r) or {}).get(k, 0))
            # surto seeded (causa de estado do mundo): sempre sorteia p/ manter o fluxo estavel
            roll = rng.random()
            amount = rng.randint(int(c["surge_min"]), int(c["surge_max"]))
            if roll < float(c["surge_p"]) * float(weights.get(r, 1.0)):
                v += amount
            if (relief.get(r) or {}).get(k):
                v -= int(c["crisis_relief_per_day"])
            # (c) deriva rumo a baseline
            b = base[r][k]
            step = int(c["drift_per_day"])
            if v > b:
                v = max(b, v - step)
            elif v < b:
                v = min(b, v + step)
            # (d) ruido
            v += rng.randint(-int(c["noise"]), int(c["noise"]))
            out[r][k] = v

    # (e) contagio de praga (usa a praga pos-ruido, aplica em delta separado)
    adj = region_adjacency()
    gain: dict[str, int] = {}
    for r in sorted(out):
        praga = out[r]["praga"]
        if praga < int(c["spread_threshold"]):
            continue
        for nb in adj.get(r, []):
            roll = rng.random()
            pairs = region_link_pairs(r, nb)
            open_link = any(
                (a, b) not in blocked_pairs and (b, a) not in blocked_pairs for a, b in pairs
            )
            if open_link and roll < float(c["spread_p"]):
                gain[nb] = gain.get(nb, 0) + math.floor(praga * float(c["spread_factor"]))
    for r, g in gain.items():
        out[r]["praga"] += g

    return {r: {k: _clamp(v) for k, v in row.items()} for r, row in out.items()}


# --- causas por tabela (R7a/b) ----------------------------------------------------


def event_deltas(
    events: list[dict],
    *,
    cfg: dict | None = None,
    factions: list | None = None,
    leader_faction: Any = None,
    faction_region: Any = None,
) -> dict[str, dict[str, int]]:
    """Causas `on_event` aplicadas UMA vez por evento do event_log. Tabela de dados."""
    out: dict[str, dict[str, int]] = {}
    by_id = {f.get("id"): f for f in (factions or []) if isinstance(f, dict)}

    def add(region: str, kind: str, delta: int) -> None:
        if region:
            row = out.setdefault(region, {})
            row[kind] = row.get(kind, 0) + delta

    for ev in events:
        if not isinstance(ev, dict):
            continue
        etype = ev.get("type")
        payload = ev.get("payload") or {}
        target = str(ev.get("target_id") or "")
        for cause in (cfg or get_config()).get("causes", []):
            if cause.get("on_event") != etype:
                continue
            cond = cause.get("if")
            fid = ""
            if cond == "new_controller_hostile":
                fid = str(payload.get("new_controller_id") or "")
                if (by_id.get(fid) or {}).get("disposition") != "hostil":
                    continue
            elif cond == "target_leads_faction":
                fid = str(leader_faction(target) if leader_faction else "")
                if not fid:
                    continue
            scope = cause.get("scope")
            regions: list[str] = []
            if scope == "endpoint_regions":
                regions = [
                    region_of(target),
                    region_of(str(payload.get("other_location_id") or "")),
                ]
            elif scope == "target_region":
                regions = [region_of(target)]
            elif scope == "faction_region":
                regions = [faction_region(by_id.get(fid) or {}) if faction_region else ""]
            for region in dict.fromkeys(r for r in regions if r):
                add(region, str(cause["pressure"]), int(cause["delta"]))
    return out


# --- sinais pequenos (R10) --------------------------------------------------------


def signal_templates(kind: str, cfg_signals: dict) -> list[str]:
    prefix = f"{kind}.sinal."
    return sorted(t for t in cfg_signals.get("templates", {}) if t.startswith(prefix))


def pick_signals(
    prev: dict,
    cur: dict,
    bands: dict,
    *,
    day: int,
    rng: Any,
    cfg: dict | None = None,
    signals_cfg: dict | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Ate 1 sinal/regiao/dia, teto global `MAX_SIGNALS_PER_DAY`. Regiao em banda `sinal`
    ou com alta diaria >= `signal_delta` pode emitir. Sorteia sempre (fluxo estavel)."""
    c = constants(cfg)
    cap = int(limit if limit is not None else director_constants(cfg)["MAX_SIGNALS_PER_DAY"])
    sig_cfg = signals_cfg or _load_json("signals.json")
    cands: list[tuple[int, str, str]] = []
    for r in sorted(cur):
        best: tuple[int, str] | None = None
        for k in KINDS:
            v = int(cur[r].get(k, 0))
            rise = v - int(prev.get(r, {}).get(k, v))
            if (bands.get(r) or {}).get(k) == "sinal" or rise >= int(c["signal_delta"]):
                score = v + rise
                if best is None or score > best[0]:
                    best = (score, k)
        if best:
            cands.append((-best[0], r, best[1]))
    cands.sort()
    out: list[dict] = []
    for _, r, k in cands:
        pool = signal_templates(k, sig_cfg)
        roll = rng.random()
        if not pool or len(out) >= cap:
            continue
        tid = pool[int(roll * len(pool)) % len(pool)]
        tpl = sig_cfg["templates"][tid]
        out.append(
            {
                "day": int(day),
                "region_id": r,
                "location_id": region_primary_location(r),
                "pressure": k,
                "template_id": tid,
                "visibility": "local" if tpl.get("visibility") == "local" else "regional",
            }
        )
    return out
