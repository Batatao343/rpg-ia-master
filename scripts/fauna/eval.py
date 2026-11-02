"""SPEC-360 R28: avaliador deterministico da fauna viva (M1-M7), congelado na Etapa 1.

Quem otimiza o produto NAO altera este arquivo nem `tests/test_spec360_eval.py` (D6:
ambos em `evals/protected-paths.txt`). Mudanca de limiar ou de medida so pelo coordenador,
com registro na spec.

Duas partes:

1. **Simulacao** (M1, M5, M6, M7): perfil sintetico de viagem em Nova Arcadia. Por dia de
   jogo, 3 chegadas entre os nos da regiao e 1 descanso (4 acoes; o periodo gira com o dia).
   O fluxo de cada acao segue a SPEC-360 §3.5 (hooks do dia -> `check_encounter` -> combate,
   conversao em sinal, rastro ou cena com `<SINAIS_NA_CENA>`). A mesma semente roda com as
   flags `off` (baseline) e `on`; a aleatoriedade de cada acao e semeada por (seed, turno),
   igual nos dois modos.
2. **Distribuicao exata** (M2, M3, M4): pesos do sorteio ponderado
   (`world_utils.encounter_distribution`) em contexto neutro (sem clima, estacao, carcaca
   nem presenca), por local x periodo, com `RPG_FAUNA=on`. Sem amostragem: sem ruido.

Uso: `bash scripts/dev/py.sh scripts/fauna/eval.py [--seeds 20] [--days 60] [--out PATH]`.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import random
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGION = "nova_arcadia"
DEFAULT_SEEDS = 20
DEFAULT_DAYS = 60
ARRIVALS_PER_DAY = 3
PLAYER_LEVEL = 3  # perigo forcado 4 -> forca 3 (porte cheio, sem BOSS)
FORCED_DANGER = 4
REPORT = ROOT / "docs" / "spec360" / "eval-nova_arcadia.md"

# Limiares congelados (D4). Nao editar no mesmo trabalho que mexe no produto.
M1_MIN_PRECEDIDO = 0.70
M1_MIN_APROXIMACAO = 1.00
M2_MAX_RATIO_FORA = 0.35
M3_MIN_PRESA_SOBE = 1.5
M3_MAX_PREDADOR_CAI = 0.6
M4_MIN_TERRITORIO = 0.80
M5_MIN_DELTA = -0.20
M5_MAX_DELTA = 0.05
M6_MAX_VAZAMENTOS = 0
M3_DEFEATED = 6
SIGN_TYPES = ("rastro", "resto", "som", "cheiro", "marca", "aproximacao", "rumor")
FAUNA_REASONS = ("looming_threat", "high_danger")
WEATHERS = ("limpo", "nublado", "chuva")


# --------------------------------------------------------------------------- utilidades


def _fold(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", str(text or "").lower())
        if not unicodedata.combining(ch)
    )


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", _fold(text)) if len(t) >= 4}


def _seed_int(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16], 16)


@contextlib.contextmanager
def _flags(fauna: str, sinais: str):
    old = {k: os.environ.get(k) for k in ("RPG_FAUNA", "RPG_FAUNA_SINAIS")}
    os.environ["RPG_FAUNA"] = fauna
    os.environ["RPG_FAUNA_SINAIS"] = sinais
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _region_nodes() -> list[str]:
    import gamedata

    return sorted(
        loc["id"]
        for loc in gamedata.WORLD_MAP.get("locations", [])
        if loc.get("region_id") == REGION and not loc.get("parent_id")
    )


def _forbidden_tokens() -> dict[str, set[str]]:
    """Tokens (>= 4 letras, sem acento) do nome, do id e da familia em jogo de cada criatura
    com fauna: independente do lint (o avaliador nao confia no produto)."""
    import yaml

    import gamedata

    fauna = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    fichas: dict[str, dict] = {}
    familias: dict[str, str] = {}
    for path in sorted((ROOT / "data" / "bestiario" / "fichas").glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        familias.update(doc.get("familias_em_jogo") or {})
        for c in doc.get("criaturas") or []:
            fichas.setdefault(str(c.get("id")), c)
    out: dict[str, set[str]] = {}
    for cid in fauna.get("criaturas") or {}:
        ficha = fichas.get(cid) or {}
        name = str(ficha.get("nome") or (gamedata.BESTIARY.get(cid) or {}).get("name") or "")
        fam = str(familias.get(str(ficha.get("familia") or ""), ""))
        out[cid] = _tokens(name) | _tokens(cid.replace("_", " ")) | _tokens(fam)
    return out


def _leaks(text: str, forbidden: set[str]) -> list[str]:
    return sorted(_tokens(text) & forbidden)


# --------------------------------------------------------------------------- simulacao


def _new_state(seed: int) -> dict:
    gid = f"spec360-eval-{seed}"
    nodes = _region_nodes()
    world = {
        "current_location_id": nodes[0],
        "current_location": nodes[0],
        "world_clock": {"day": 1, "period": "Amanhecer"},
        "time_of_day": "Amanhecer",
        "turn_count": 0,
        "danger_overrides": {n: FORCED_DANGER for n in nodes},
        "weather_state": "limpo",
        "season": {"id": "primavera"},
    }
    sim = {"region_presence": {REGION: 1}}
    return {
        "game_id": gid,
        "world": world,
        "world_sim": sim,
        "bestiary_knowledge": {},
        "player": {"level": PLAYER_LEVEL, "name": "Avaliador"},
        "messages": [],
    }


def _run_day_hooks(state: dict, day: int) -> None:
    from services import fauna, world_engine

    sim = state["world_sim"]
    sim.setdefault("region_presence", {})[REGION] = day
    ctx = world_engine.DayContext(
        game_id=state["game_id"],
        day=day,
        sim=sim,
        projection={},
        world=state["world"],
        factions=[],
        rng=world_engine.day_rng(state["game_id"], day, "eval"),
        state=state,
    )
    res = fauna.day_hook(ctx)
    patch = getattr(res, "state_patch", None) or {}
    if patch.get("world_sim"):
        state["world_sim"] = patch["world_sim"]


def _presence(sim: dict, pid: str) -> dict | None:
    for p in ((sim or {}).get("fauna") or {}).get("presencas") or []:
        if p.get("pid") == pid:
            return p
    return None


def _shown_counts(sim: dict) -> dict[str, int]:
    return {
        p["pid"]: len(p.get("sinais_mostrados") or [])
        for p in ((sim or {}).get("fauna") or {}).get("presencas") or []
    }


def _new_sign_owner(before: dict[str, int], sim: dict) -> str:
    for p in ((sim or {}).get("fauna") or {}).get("presencas") or []:
        if len(p.get("sinais_mostrados") or []) > before.get(p["pid"], 0):
            return str(p.get("creature_id") or "")
    return ""


def _simulate(seed: int, days: int, *, on: bool, forbidden: dict[str, set[str]]) -> dict:
    import world_utils as wu
    from services import discovery as disc
    from services import fauna

    state = _new_state(seed)
    world, nodes = state["world"], _region_nodes()
    from world_utils import PERIODS

    out = {
        "arrivals": 0,
        "rests": 0,
        "triggers": 0,
        "conversions": 0,
        "fauna_combats": 0,
        "combats_with_entry": 0,
        "precedido": 0,
        "aproximacao": 0,
        "signs_shown": 0,
        "leaks": [],
        "texts": 0,
    }
    seasons = ("primavera", "verao", "outono", "inverno")
    turn = 0
    for day in range(1, days + 1):
        drng = random.Random(_seed_int(seed, day, "day"))
        world["weather_state"] = drng.choice(WEATHERS)
        world["season"] = {"id": seasons[((day - 1) // 15) % 4]}
        world["world_clock"] = {"day": day, "period": world["world_clock"]["period"]}
        if on:
            _run_day_hooks(state, day)
        for i in range(ARRIVALS_PER_DAY + 1):
            turn += 1
            rest = i == ARRIVALS_PER_DAY
            arng = random.Random(_seed_int(seed, turn, "act"))
            period = PERIODS[(day + i) % len(PERIODS)]
            world["world_clock"] = {"day": day, "period": period}
            world["time_of_day"] = period
            world["turn_count"] = turn
            if rest:
                out["rests"] += 1
            else:
                here = world["current_location_id"]
                dest = arng.choice([n for n in nodes if n != here])
                world["current_location_id"] = dest
                world["current_location"] = dest
                out["arrivals"] += 1
            random.seed(_seed_int(seed, turn, "pick"))
            kind_rng = random.Random(_seed_int(seed, turn, "kind"))
            enc = wu.check_encounter(
                world,
                [],
                {},
                turn,
                bestiary_knowledge=state["bestiary_knowledge"],
                projection={},
                player_level=PLAYER_LEVEL,
                world_sim=state["world_sim"],
            )
            kind = wu.roll_encounter_type(FORCED_DANGER, rng=kind_rng)
            sign_this_turn = False
            loc = world["current_location_id"]
            if enc and enc.get("reason") in FAUNA_REASONS:
                out["triggers"] += 1
                world["last_encounter_turn"] = turn
                cid = str(enc.get("enemy_id") or "")
                entry = fauna.entry(cid) if on else None
                if on and enc.get("fauna_convert") and entry:
                    before = _shown_counts(state["world_sim"])
                    note, upd = fauna.convert_to_signal(state, entry, loc, day)
                    state["world_sim"] = upd.get("world_sim", state["world_sim"])
                    out["conversions"] += 1
                    sign_this_turn = True
                    owner = _new_sign_owner(before, state["world_sim"]) or cid
                    out["texts"] += 1
                    out["leaks"] += [(owner, t) for t in _leaks(note, forbidden.get(owner, set()))]
                elif kind == "combat":
                    out["fauna_combats"] += 1
                    if fauna.entry(cid):
                        out["combats_with_entry"] += 1
                        pres = _presence(state["world_sim"], str(enc.get("presence_id") or ""))
                        if pres and pres.get("sinais_mostrados"):
                            out["precedido"] += 1
                        line = fauna.approach_line(cid) if on else ""
                        if on and line and line in str(enc.get("flavor") or ""):
                            out["aproximacao"] += 1
                        if on:
                            out["texts"] += 1
                            out["leaks"] += [
                                (cid, t)
                                for t in _leaks(
                                    str(enc.get("flavor") or ""), forbidden.get(cid, set())
                                )
                            ]
                        if on and pres:
                            state["world_sim"], _ = fauna.mark_encountered(
                                state["world_sim"], pres["pid"], day
                            )
                        if on:
                            state["world_sim"] = fauna.record_kill(
                                state["world_sim"], cid, loc, day
                            )
                    state["bestiary_knowledge"] = disc.record_kills(
                        state["bestiary_knowledge"], [{"id": cid}], turn
                    )
                    continue  # combate: sem cena de sinal neste turno
                elif kind == "track" and on and entry:
                    before = _shown_counts(state["world_sim"])
                    note, upd = fauna.track_signal(state, entry, loc, day)
                    state["world_sim"] = upd.get("world_sim", state["world_sim"])
                    if note:
                        sign_this_turn = True
                        owner = _new_sign_owner(before, state["world_sim"]) or cid
                        out["texts"] += 1
                        out["leaks"] += [
                            (owner, t) for t in _leaks(note, forbidden.get(owner, set()))
                        ]
            if on and not sign_this_turn:
                before = _shown_counts(state["world_sim"])
                block, upd = fauna.scene_block(state)
                if block:
                    state["world_sim"] = upd.get("world_sim", state["world_sim"])
                    owner = _new_sign_owner(before, state["world_sim"])
                    out["signs_shown"] += 1
                    out["texts"] += 1
                    out["leaks"] += [(owner, t) for t in _leaks(block, forbidden.get(owner, set()))]
    return out


# --------------------------------------------------------------------------- distribuicao


def _neutral_world(loc: str, period: str) -> dict:
    return {
        "current_location_id": loc,
        "world_clock": {"day": 10, "period": period},
        "time_of_day": period,
        "turn_count": 100,
    }


def _distribution(loc: str, period: str, bk: dict) -> dict[str, float]:
    import gamedata
    import world_utils as wu

    rows = wu.encounter_distribution(
        gamedata.get_location(loc) or {},
        PLAYER_LEVEL,
        100,
        bestiary_knowledge=bk,
        projection={},
        world=_neutral_world(loc, period),
        world_sim={},
    )
    total = sum(w for _e, w in rows) or 1.0
    out: dict[str, float] = {}
    for e, w in rows:
        out[str(e.get("id"))] = out.get(str(e.get("id")), 0.0) + w / total
    return out


def distribution_metrics() -> dict:
    from services import fauna
    from world_utils import PERIODS

    nodes = _region_nodes()
    crit = {cid: e for cid, e in fauna.load().items() if e.get("regiao") == REGION}
    terr = {cid: set(fauna.effective_territory(cid)) for cid in crit}
    hours = {cid: set((e.get("ecologia") or {}).get("horario") or []) for cid, e in crit.items()}
    base = {(loc, p): _distribution(loc, p, {}) for loc in nodes for p in PERIODS}

    # M2: por criatura, fatia media fora do horario / dentro (locais do territorio)
    m2: dict[str, float] = {}
    for cid in crit:
        ins = [
            base[(loc, p)].get(cid, 0.0)
            for loc in nodes
            if loc in terr[cid]
            for p in PERIODS
            if p in hours[cid]
        ]
        outs = [
            base[(loc, p)].get(cid, 0.0)
            for loc in nodes
            if loc in terr[cid]
            for p in PERIODS
            if p not in hours[cid]
        ]
        if ins and outs and sum(ins) > 0:
            m2[cid] = round((sum(outs) / len(outs)) / (sum(ins) / len(ins)), 4)

    # M4: fatia das escolhas em criatura do territorio, onde ha candidata territorial
    m4_vals = []
    for (loc, _p), dist in sorted(base.items()):
        territorial = [cid for cid in dist if cid in terr and loc in terr[cid]]
        if territorial:
            m4_vals.append(sum(dist[c] for c in territorial))
    m4 = round(sum(m4_vals) / len(m4_vals), 4) if m4_vals else None

    # M3: presas sobem quando o predador e cacado; predador cai sem presa
    m3_up: dict[str, float] = {}
    m3_down: dict[str, float] = {}
    for pred, e in sorted(crit.items()):
        preys = [q for q in (e.get("ecologia") or {}).get("presas") or []]
        ctxs = [(loc, p) for loc in nodes if loc in terr[pred] for p in PERIODS if p in hours[pred]]
        if not preys or not ctxs:
            continue
        ups, downs = [], []
        hunted = {pred: {"defeated": M3_DEFEATED, "last_update_turn": 100, "seen": M3_DEFEATED}}
        starved = {
            q: {"defeated": M3_DEFEATED, "last_update_turn": 100, "seen": M3_DEFEATED}
            for q in preys
        }
        for loc, p in ctxs:
            b = base[(loc, p)]
            prey_b = sum(b.get(q, 0.0) for q in preys)
            if prey_b > 0:
                h = _distribution(loc, p, hunted)
                ups.append(sum(h.get(q, 0.0) for q in preys) / prey_b)
            s = _distribution(loc, p, starved)
            pb_rest = 1.0 - prey_b
            ps_rest = 1.0 - sum(s.get(q, 0.0) for q in preys)
            if b.get(pred, 0.0) > 0 and pb_rest > 0 and ps_rest > 0:
                downs.append((s.get(pred, 0.0) / ps_rest) / (b[pred] / pb_rest))
        if ups:
            m3_up[pred] = round(sum(ups) / len(ups), 4)
        if downs:
            m3_down[pred] = round(sum(downs) / len(downs), 4)
    return {"m2": m2, "m3_up": m3_up, "m3_down": m3_down, "m4": m4, "m4_n": len(m4_vals)}


# --------------------------------------------------------------------------- relatorio


def run(seeds: int = DEFAULT_SEEDS, days: int = DEFAULT_DAYS) -> dict:
    forbidden = _forbidden_tokens()
    fauna_json = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    json_leaks = []
    for cid, e in sorted((fauna_json.get("criaturas") or {}).items()):
        for k in SIGN_TYPES:
            txt = (e.get("sinais") or {}).get(k)
            if txt:
                json_leaks += [(cid, k, t) for t in _leaks(str(txt), forbidden.get(cid, set()))]
    totals = {"off": {}, "on": {}}
    for label, on in (("off", False), ("on", True)):
        with _flags("on" if on else "off", "on" if on else "off"):
            agg: dict = {}
            for s in range(seeds):
                r = _simulate(s, days, on=on, forbidden=forbidden)
                for k, v in r.items():
                    agg[k] = (agg.get(k) or ([] if isinstance(v, list) else 0)) + v
            totals[label] = agg
    with _flags("on", "on"):
        dist = distribution_metrics()
    off, on = totals["off"], totals["on"]
    rate_off = 100.0 * off["fauna_combats"] / max(1, off["arrivals"] + off["rests"])
    rate_on = 100.0 * on["fauna_combats"] / max(1, on["arrivals"] + on["rests"])
    delta = (rate_on - rate_off) / rate_off if rate_off else 0.0
    n = max(1, on["combats_with_entry"])
    leaks = len(json_leaks) + len(on["leaks"])
    m = {
        "M1_precedido": round(on["precedido"] / n, 4),
        "M1_aproximacao": round(on["aproximacao"] / n, 4),
        "M2_pior_razao": max(dist["m2"].values()) if dist["m2"] else None,
        "M3_presa_sobe_min": min(dist["m3_up"].values()) if dist["m3_up"] else None,
        "M3_predador_cai_max": max(dist["m3_down"].values()) if dist["m3_down"] else None,
        "M4_territorio": dist["m4"],
        "M5_delta": round(delta, 4),
        "M6_vazamentos": leaks,
    }
    passed = {
        "M1": m["M1_precedido"] >= M1_MIN_PRECEDIDO and m["M1_aproximacao"] >= M1_MIN_APROXIMACAO,
        "M2": m["M2_pior_razao"] is not None and m["M2_pior_razao"] <= M2_MAX_RATIO_FORA,
        "M3": (
            m["M3_presa_sobe_min"] is not None
            and m["M3_predador_cai_max"] is not None
            and m["M3_presa_sobe_min"] >= M3_MIN_PRESA_SOBE
            and m["M3_predador_cai_max"] <= M3_MAX_PREDADOR_CAI
        ),
        "M4": m["M4_territorio"] is not None and m["M4_territorio"] >= M4_MIN_TERRITORIO,
        "M5": M5_MIN_DELTA <= m["M5_delta"] <= M5_MAX_DELTA,
        "M6": leaks <= M6_MAX_VAZAMENTOS,
    }
    return {
        "config": {"seeds": seeds, "days": days, "region": REGION},
        "off": {k: v for k, v in off.items() if k != "leaks"},
        "on": {k: v for k, v in on.items() if k != "leaks"},
        "rates": {"off": round(rate_off, 3), "on": round(rate_on, 3)},
        "dist": dist,
        "metrics": m,
        "passed": passed,
        "leak_samples": sorted(set(map(tuple, json_leaks)))[:10] + sorted(set(on["leaks"]))[:10],
    }


def render(res: dict) -> str:
    m, p = res["metrics"], res["passed"]
    cfg = res["config"]
    lines = [
        "# SPEC-360 — eval da fauna viva: Nova Arcádia",
        "",
        "Gerado por `scripts/fauna/eval.py` (avaliador congelado na Etapa 1; não editar à mão).",
        "",
        f"- Região: `{cfg['region']}` · seeds: {cfg['seeds']} · dias por seed: {cfg['days']}",
        f"- Perfil sintético: {ARRIVALS_PER_DAY} chegadas por dia entre os nós da região + 1 descanso;"
        f" perigo forçado {FORCED_DANGER}, nível {PLAYER_LEVEL}.",
        "",
        "| Métrica | Valor | Limiar | Resultado |",
        "|---|---|---|---|",
        f"| M1 sinal antes (precedidos) | {m['M1_precedido']:.4f} | ≥ {M1_MIN_PRECEDIDO} | {'ok' if p['M1'] else 'FALHOU'} |",
        f"| M1 aproximação | {m['M1_aproximacao']:.4f} | ≥ {M1_MIN_APROXIMACAO} | {'ok' if p['M1'] else 'FALHOU'} |",
        f"| M2 horário (pior razão fora/dentro) | {m['M2_pior_razao']} | ≤ {M2_MAX_RATIO_FORA} | {'ok' if p['M2'] else 'FALHOU'} |",
        f"| M3 presa sobe (mínimo) | {m['M3_presa_sobe_min']} | ≥ {M3_MIN_PRESA_SOBE} | {'ok' if p['M3'] else 'FALHOU'} |",
        f"| M3 predador cai (máximo) | {m['M3_predador_cai_max']} | ≤ {M3_MAX_PREDADOR_CAI} | {'ok' if p['M3'] else 'FALHOU'} |",
        f"| M4 território | {m['M4_territorio']} | ≥ {M4_MIN_TERRITORIO} | {'ok' if p['M4'] else 'FALHOU'} |",
        f"| M5 combates por 100 ações (Δ on vs off) | {m['M5_delta']:+.4f} | {M5_MIN_DELTA} a +{M5_MAX_DELTA} | {'ok' if p['M5'] else 'FALHOU'} |",
        f"| M6 vazamento de nome | {m['M6_vazamentos']} | ≤ {M6_MAX_VAZAMENTOS} | {'ok' if p['M6'] else 'FALHOU'} |",
        "",
        "## Contagens",
        "",
        "| Modo | Chegadas | Descansos | Gatilhos | Combates de fauna | Conversões | Sinais em cena |",
        "|---|---|---|---|---|---|---|",
    ]
    for label in ("off", "on"):
        r = res[label]
        lines.append(
            f"| {label} | {r['arrivals']} | {r['rests']} | {r['triggers']} | {r['fauna_combats']} |"
            f" {r['conversions']} | {r['signs_shown']} |"
        )
    lines += [
        "",
        f"Combates por 100 ações: off {res['rates']['off']} · on {res['rates']['on']}.",
        "",
        "## Distribuição (contexto neutro, exata)",
        "",
        f"- M2 por criatura (fora/dentro): {json.dumps(res['dist']['m2'], ensure_ascii=False, sort_keys=True)}",
        f"- M3 presa sobe por predador: {json.dumps(res['dist']['m3_up'], ensure_ascii=False, sort_keys=True)}",
        f"- M3 predador cai: {json.dumps(res['dist']['m3_down'], ensure_ascii=False, sort_keys=True)}",
        f"- M4 contextos com candidata territorial: {res['dist']['m4_n']}",
        "",
    ]
    if res["leak_samples"]:
        lines += ["## Vazamentos (amostra)", ""] + [f"- {x}" for x in res["leak_samples"]] + [""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--out", default=str(REPORT))
    args = ap.parse_args(argv)
    os.environ.setdefault("RPG_FORCE_MOCK", "1")
    res = run(args.seeds, args.days)
    text = render(res)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(json.dumps({"metrics": res["metrics"], "passed": res["passed"]}, ensure_ascii=False))
    return 0 if all(res["passed"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
