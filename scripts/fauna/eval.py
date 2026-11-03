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

SPEC-370 (Etapa 1, autor de eval; R16-R20): o mesmo avaliador por regiao.

- `--regiao <r>`: roda na regiao `r` (nos raiz dela) e grava `docs/spec360/eval-<r>.md`. O
  relatorio comeca com o corpo da 360 (byte a byte igual ao caminho sem flag) e acrescenta a
  secao SPEC-370: M1 com oraculo proprio, M7 no tamanho do relatorio, M8 e os N/A.
- `--todas`: todas as regioes com `data/bestiario/fauna/<r>.yaml` + `docs/spec360/eval-global.md`
  com o M5 global (o que barra; por regiao o M5 e informativo, D5).
- Sem flag: comportamento da 360 (Nova Arcadia, relatorio da 360, mesmo codigo de saida).

Oraculo proprio do M1 (R18, P2-8 do Sol): o avaliador guarda cada texto de sinal devolvido por
`scene_block`, `convert_to_signal` e `track_signal`, atribui o texto a criatura comparando com
os campos de `sinais` lidos de `data/world/fauna.json` (arquivo de dados, nao o estado da
presenca) e conta o combate como precedido se um sinal daquela criatura saiu numa acao anterior,
no mesmo local ou num no do territorio dela (lido do mesmo arquivo), depois do ultimo combate
com ela e nao antes do dia de nascimento da presenca. `presence.sinais_mostrados` nao entra.

Uso: `bash scripts/dev/py.sh scripts/fauna/eval.py [--regiao R | --todas] [--seeds 20]
[--days 60] [--out PATH]`.
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
# SPEC-370 (congelados na Etapa 1; D5, D7). Nao editar no mesmo trabalho que mexe no produto.
M5_REGIAO_ALERTA_MIN = -0.30  # informativo por regiao (o global barra com M5_MIN/MAX_DELTA)
M5_REGIAO_ALERTA_MAX = 0.10
M8_MAX_DENSIDADE = 0.40  # fracao das acoes com sinal novo (cena + conversao + rastro)
M4_MIN_NOS = 2  # regiao com menos nos raiz: M4 N/A (nao ha "fora do territorio")
REGIONS = (
    "nova_arcadia",
    "pantano_melancolia",
    "brekmar",
    "skallgard",
    "pradaria_ruinas",
    "montanhas_afiadas",
    "aethelgard",
    "floresta_sussurros",
    "selva_xylos",
    "deserto_zhur",
    "costa_negra",
    "ophidia",
)
FAUNA_DIR = ROOT / "data" / "bestiario" / "fauna"
REPORT_DIR = ROOT / "docs" / "spec360"
SIGN_TEXT_TYPES = ("marca", "rastro", "resto", "som", "cheiro")  # textos que viram sinal
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


def _region_nodes(region: str = REGION) -> list[str]:
    import gamedata

    return sorted(
        loc["id"]
        for loc in gamedata.WORLD_MAP.get("locations", [])
        if loc.get("region_id") == region and not loc.get("parent_id")
    )


def regions_with_fauna() -> list[str]:
    """Regioes (na ordem de REGIONS) com bloco autorado em `data/bestiario/fauna/<r>.yaml`."""
    return [r for r in REGIONS if (FAUNA_DIR / f"{r}.yaml").exists()]


def _fauna_data() -> dict[str, dict]:
    """`data/world/fauna.json` lido pelo avaliador (dados, nao estado do produto)."""
    raw = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    return dict(raw.get("criaturas") or {})


def _sign_index(data: dict[str, dict]) -> dict[str, tuple[str, ...]]:
    """Por criatura, os textos de sinal (marca/rastro/resto/som/cheiro) do arquivo de dados."""
    out: dict[str, tuple[str, ...]] = {}
    for cid, e in sorted(data.items()):
        sinais = e.get("sinais") or {}
        texts = tuple(
            str(sinais[k]).strip() for k in SIGN_TEXT_TYPES if str(sinais.get(k) or "").strip()
        )
        if texts:
            out[cid] = texts
    return out


def _territory_index(data: dict[str, dict]) -> dict[str, frozenset[str]]:
    return {
        cid: frozenset((e.get("ecologia") or {}).get("territorio") or []) for cid, e in data.items()
    }


def attribute_sign(text: str, sign_index: dict[str, tuple[str, ...]]) -> frozenset[str]:
    """Criaturas cujo texto de sinal (do arquivo de dados) aparece no texto emitido."""
    t = str(text or "")
    if not t.strip():
        return frozenset()
    return frozenset(cid for cid, texts in sign_index.items() if any(s in t for s in texts))


def precedido_oraculo(
    emitted: list[tuple[int, str, frozenset[str]]],
    creature_id: str,
    location_id: str,
    turn: int,
    after_turn: int,
    territory: frozenset[str],
) -> bool:
    """R18: houve sinal da criatura numa acao anterior (`after_turn < t < turn`), no mesmo
    local do combate ou num no do territorio dela?"""
    for t, loc, owners in emitted:
        if after_turn < t < turn and creature_id in owners:
            if loc == location_id or loc in territory:
                return True
    return False


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


def _new_state(seed: int, region: str = REGION) -> dict:
    gid = f"spec360-eval-{seed}"
    nodes = _region_nodes(region)
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
    sim = {"region_presence": {region: 1}}
    return {
        "game_id": gid,
        "world": world,
        "world_sim": sim,
        "bestiary_knowledge": {},
        "player": {"level": PLAYER_LEVEL, "name": "Avaliador"},
        "messages": [],
    }


def _run_day_hooks(state: dict, day: int, region: str = REGION) -> None:
    from services import fauna, world_engine

    sim = state["world_sim"]
    sim.setdefault("region_presence", {})[region] = day
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


def _simulate(
    seed: int,
    days: int,
    *,
    on: bool,
    forbidden: dict[str, set[str]],
    region: str = REGION,
    sign_index: dict[str, tuple[str, ...]] | None = None,
    territory: dict[str, frozenset[str]] | None = None,
) -> dict:
    import world_utils as wu
    from services import discovery as disc
    from services import fauna

    state = _new_state(seed, region)
    world, nodes = state["world"], _region_nodes(region)
    from world_utils import PERIODS

    if sign_index is None or territory is None:
        data = _fauna_data()
        sign_index = _sign_index(data) if sign_index is None else sign_index
        territory = _territory_index(data) if territory is None else territory
    # Oraculo proprio (R18): (turno, local, criaturas atribuidas) de cada texto emitido.
    emitted: list[tuple[int, str, frozenset[str]]] = []
    last_combat: dict[str, int] = {}
    orc = {
        "precedido_oraculo": 0,
        "acoes_com_sinal": 0,
        "sinais_emitidos": 0,
        "sinais_sem_dono": 0,
        "sinais_multi_dono": 0,
        "m1_so_legado": 0,
        "m1_so_oraculo": 0,
    }

    def _emit(turn_: int, loc_: str, text: str) -> None:
        owners = attribute_sign(text, sign_index)
        orc["sinais_emitidos"] += 1
        if not owners:
            orc["sinais_sem_dono"] += 1
        elif len(owners) > 1:
            orc["sinais_multi_dono"] += 1
        emitted.append((turn_, loc_, owners))

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
            _run_day_hooks(state, day, region)
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
                # regiao de 1 no (Ophidia): a "chegada" volta ao mesmo no
                dest = arng.choice([n for n in nodes if n != here] or nodes)
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
                    if str(note or "").strip():
                        _emit(turn, loc, note)
                    owner = _new_sign_owner(before, state["world_sim"]) or cid
                    out["texts"] += 1
                    out["leaks"] += [(owner, t) for t in _leaks(note, forbidden.get(owner, set()))]
                elif kind == "combat":
                    out["fauna_combats"] += 1
                    if fauna.entry(cid):
                        out["combats_with_entry"] += 1
                        pres = _presence(state["world_sim"], str(enc.get("presence_id") or ""))
                        legado = bool(pres and pres.get("sinais_mostrados"))
                        if legado:
                            out["precedido"] += 1
                        if on:
                            # janela: depois do ultimo combate com ela e nao antes do dia em que
                            # a presenca nasceu (o estado so ESTREITA a janela, nunca a abre)
                            lo = last_combat.get(cid, 0)
                            if pres:
                                born = int(pres.get("born_day") or 1)
                                lo = max(lo, (born - 1) * (ARRIVALS_PER_DAY + 1))
                            novo = bool(pres) and precedido_oraculo(
                                emitted, cid, loc, turn, lo, territory.get(cid, frozenset())
                            )
                            orc["precedido_oraculo"] += int(novo)
                            orc["m1_so_legado"] += int(legado and not novo)
                            orc["m1_so_oraculo"] += int(novo and not legado)
                            last_combat[cid] = turn
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
                        _emit(turn, loc, note)
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
                    _emit(turn, loc, block)
                    owner = _new_sign_owner(before, state["world_sim"])
                    out["signs_shown"] += 1
                    out["texts"] += 1
                    out["leaks"] += [(owner, t) for t in _leaks(block, forbidden.get(owner, set()))]
            if emitted and emitted[-1][0] == turn:
                orc["acoes_com_sinal"] += 1  # M8: acao com >= 1 texto de sinal novo
    out.update(orc)
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


def distribution_metrics(region: str = REGION) -> dict:
    from services import fauna
    from world_utils import PERIODS

    nodes = _region_nodes(region)
    crit = {cid: e for cid, e in fauna.load().items() if e.get("regiao") == region}
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


def _core(seeds: int, days: int, region: str) -> dict:
    forbidden = _forbidden_tokens()
    data = _fauna_data()
    sign_index, territory = _sign_index(data), _territory_index(data)
    json_leaks = []
    for cid, e in sorted(data.items()):
        if e.get("regiao") != region:
            continue
        for k in SIGN_TYPES:
            txt = (e.get("sinais") or {}).get(k)
            if txt:
                json_leaks += [(cid, k, t) for t in _leaks(str(txt), forbidden.get(cid, set()))]
    totals = {"off": {}, "on": {}}
    for label, on in (("off", False), ("on", True)):
        with _flags("on" if on else "off", "on" if on else "off"):
            agg: dict = {}
            for s in range(seeds):
                r = _simulate(
                    s,
                    days,
                    on=on,
                    forbidden=forbidden,
                    region=region,
                    sign_index=sign_index,
                    territory=territory,
                )
                for k, v in r.items():
                    agg[k] = (agg.get(k) or ([] if isinstance(v, list) else 0)) + v
            totals[label] = agg
    with _flags("on", "on"):
        dist = distribution_metrics(region)
    off, on = totals["off"], totals["on"]
    actions_off = off["arrivals"] + off["rests"]
    actions_on = on["arrivals"] + on["rests"]
    rate_off = 100.0 * off["fauna_combats"] / max(1, actions_off)
    rate_on = 100.0 * on["fauna_combats"] / max(1, actions_on)
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
        "config": {"seeds": seeds, "days": days, "region": region},
        "off": {k: v for k, v in off.items() if k != "leaks"},
        "on": {k: v for k, v in on.items() if k != "leaks"},
        "rates": {"off": round(rate_off, 3), "on": round(rate_on, 3)},
        "dist": dist,
        "metrics": m,
        "passed": passed,
        "leak_samples": sorted(set(map(tuple, json_leaks)))[:10] + sorted(set(on["leaks"]))[:10],
    }


# M7: o baseline `off` escolhe a criatura com `random.Random()` sem semente
# (`services/ecology.py:59`, caminho legado), entao QUEM sai no `off` varia entre execucoes;
# QUANTOS (gatilhos, combates) nao. O hash cobre todo o resultado `on`, a distribuicao, as
# metricas e, do `off`, so as contagens que entram em metrica (M5 e R9 da 360).
M7_OFF_KEYS = ("arrivals", "rests", "triggers", "fauna_combats", "conversions", "signs_shown")


def _digest(core: dict) -> str:
    view = {k: v for k, v in core.items() if k != "off"}
    view["off"] = {k: core["off"].get(k) for k in M7_OFF_KEYS}
    blob = json.dumps(view, ensure_ascii=False, sort_keys=True, default=list)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _spec370(core: dict, region: str) -> dict:
    """Metricas e veredito da SPEC-370 (R16-R20) a partir do resultado da simulacao."""
    on, m, dist = core["on"], core["metrics"], core["dist"]
    n_nodes = len(_region_nodes(region))
    n = on["combats_with_entry"]
    actions = on["arrivals"] + on["rests"]
    mm = {
        "M1_precedido_oraculo": round(on["precedido_oraculo"] / max(1, n), 4),
        "M1_precedido_legado": m["M1_precedido"],
        "M1_aproximacao": m["M1_aproximacao"],
        "M5_regiao_delta": m["M5_delta"],
        "M8_densidade": round(on["acoes_com_sinal"] / max(1, actions), 4),
    }
    na: dict[str, str] = {}
    if n_nodes < M4_MIN_NOS:
        na["M4"] = f"{n_nodes} nó raiz na região: não há 'fora do território'"
    if not dist["m3_up"] and not dist["m3_down"]:
        na["M3"] = "nenhum par predador–presa elegível no porte forçado (perigo 4, nível 3)"
    m3 = None
    if "M3" not in na:
        up_ok = (not dist["m3_up"]) or m["M3_presa_sobe_min"] >= M3_MIN_PRESA_SOBE
        down_ok = (not dist["m3_down"]) or m["M3_predador_cai_max"] <= M3_MAX_PREDADOR_CAI
        m3 = up_ok and down_ok
    passed = {
        "M1": n > 0
        and mm["M1_precedido_oraculo"] >= M1_MIN_PRECEDIDO
        and mm["M1_aproximacao"] >= M1_MIN_APROXIMACAO,
        "M2": core["passed"]["M2"],
        "M3": m3,  # None = N/A
        "M4": None if "M4" in na else core["passed"]["M4"],
        "M6": core["passed"]["M6"] and on["texts"] > 0,
        "M8": mm["M8_densidade"] <= M8_MAX_DENSIDADE,
        "triggers_iguais": core["off"]["triggers"] == on["triggers"],
    }
    alert = not (M5_REGIAO_ALERTA_MIN <= mm["M5_regiao_delta"] <= M5_REGIAO_ALERTA_MAX)
    return {"metrics": mm, "passed": passed, "na": na, "m5_alerta": alert, "nodes": n_nodes}


def run(
    seeds: int = DEFAULT_SEEDS,
    days: int = DEFAULT_DAYS,
    region: str = REGION,
    *,
    m7: bool = False,
) -> dict:
    """Uma regiao. As chaves da 360 ficam iguais; a SPEC-370 acrescenta `spec370` e, com
    `m7=True`, roda a mesma simulacao 2x no mesmo tamanho e compara o hash (R19)."""
    res = _core(seeds, days, region)
    digest = _digest(res)
    m7_res = None
    if m7:
        again = _digest(_core(seeds, days, region))
        m7_res = {"hash_a": digest, "hash_b": again, "igual": digest == again}
    s = _spec370(res, region)
    s["passed"]["M7"] = None if m7_res is None else m7_res["igual"]
    s["m7"] = m7_res
    res["spec370"] = s
    return res


def gate_ok(res: dict) -> bool:
    """Veredito por regiao da SPEC-370: N/A (None) conta como ok; M5 por regiao nao barra."""
    return all(v is not False for v in res["spec370"]["passed"].values())


def global_m5(results: dict[str, dict]) -> dict:
    """R17: combates de fauna por 100 acoes somando as regioes, on vs off, mesmas seeds."""
    tot = {"off": [0, 0], "on": [0, 0]}
    for res in results.values():
        for label in ("off", "on"):
            r = res[label]
            tot[label][0] += r["fauna_combats"]
            tot[label][1] += r["arrivals"] + r["rests"]
    rate_off = 100.0 * tot["off"][0] / max(1, tot["off"][1])
    rate_on = 100.0 * tot["on"][0] / max(1, tot["on"][1])
    delta = (rate_on - rate_off) / rate_off if rate_off else 0.0
    return {
        "regions": sorted(results),
        "rate_off": round(rate_off, 3),
        "rate_on": round(rate_on, 3),
        "M5_global_delta": round(delta, 4),
        "passed": bool(results) and M5_MIN_DELTA <= round(delta, 4) <= M5_MAX_DELTA,
    }


def run_all(seeds: int = DEFAULT_SEEDS, days: int = DEFAULT_DAYS, *, m7: bool = False) -> dict:
    results = {r: run(seeds, days, r, m7=m7) for r in regions_with_fauna()}
    return {"regions": results, "global": global_m5(results)}


def _region_name(region: str) -> str:
    if region == "nova_arcadia":
        return "Nova Arcádia"
    import gamedata

    return str((gamedata.get_location(region) or {}).get("name") or region)


def render(res: dict) -> str:
    m, p = res["metrics"], res["passed"]
    cfg = res["config"]
    lines = [
        f"# SPEC-360 — eval da fauna viva: {_region_name(cfg['region'])}",
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


def _verdict(v: bool | None) -> str:
    return "N/A" if v is None else ("ok" if v else "FALHOU")


def render_full(res: dict) -> str:
    """Relatorio por regiao (R16): corpo da 360 (identico a `render`) + secao SPEC-370."""
    s = res["spec370"]
    mm, p, on = s["metrics"], s["passed"], res["on"]
    m7 = s["m7"]
    m7_val = "não rodado" if m7 is None else f"`{m7['hash_a'][:16]}` × `{m7['hash_b'][:16]}`"
    m3_val = s["na"].get("M3") or (
        f"sobe {res['metrics']['M3_presa_sobe_min']} · cai {res['metrics']['M3_predador_cai_max']}"
    )
    m4_val = s["na"].get("M4") or str(res["metrics"]["M4_territorio"])
    m5_flag = "ALERTA" if s["m5_alerta"] else "ok"
    lines = [
        render(res),
        "## SPEC-370 — por região, oráculo próprio do M1, M7 e M8",
        "",
        f"- Nós raiz na região: {s['nodes']}. N/A declarados no avaliador (R16).",
        "",
        "| Métrica | Valor | Limiar | Resultado |",
        "|---|---|---|---|",
        f"| M1 precedidos (oráculo próprio, R18) | {mm['M1_precedido_oraculo']:.4f} | ≥ {M1_MIN_PRECEDIDO} | {_verdict(p['M1'])} |",
        f"| M1 precedidos (oráculo antigo, `sinais_mostrados`) | {mm['M1_precedido_legado']:.4f} | informativo | — |",
        f"| M1 aproximação | {mm['M1_aproximacao']:.4f} | ≥ {M1_MIN_APROXIMACAO} | {_verdict(p['M1'])} |",
        f"| M2 horário | {res['metrics']['M2_pior_razao']} | ≤ {M2_MAX_RATIO_FORA} | {_verdict(p['M2'])} |",
        f"| M3 cadeia alimentar | {m3_val} | ≥ {M3_MIN_PRESA_SOBE} / ≤ {M3_MAX_PREDADOR_CAI} | {_verdict(p['M3'])} |",
        f"| M4 território | {m4_val} | ≥ {M4_MIN_TERRITORIO} | {_verdict(p['M4'])} |",
        f"| M5 por região (informativo, D5) | {mm['M5_regiao_delta']:+.4f} | alerta fora de {M5_REGIAO_ALERTA_MIN} a +{M5_REGIAO_ALERTA_MAX} | {m5_flag} |",
        f"| M6 vazamento de nome | {res['metrics']['M6_vazamentos']} | ≤ {M6_MAX_VAZAMENTOS} | {_verdict(p['M6'])} |",
        f"| M7 determinismo ({res['config']['seeds']} × {res['config']['days']}) | {m7_val} | hashes iguais | {_verdict(p['M7'])} |",
        f"| M8 densidade de sinal novo | {mm['M8_densidade']:.4f} | ≤ {M8_MAX_DENSIDADE} | {_verdict(p['M8'])} |",
        "",
        "### Oráculo do M1",
        "",
        f"- Combates de fauna com entrada (on): {on['combats_with_entry']} · precedidos (oráculo"
        f" próprio): {on['precedido_oraculo']} · (antigo): {on['precedido']}.",
        f"- Divergências: só o antigo conta {on['m1_so_legado']} · só o próprio conta"
        f" {on['m1_so_oraculo']}.",
        f"- Textos de sinal emitidos: {on['sinais_emitidos']} · sem dono no arquivo de dados:"
        f" {on['sinais_sem_dono']} · com mais de um dono: {on['sinais_multi_dono']}.",
        f"- Ações com sinal novo (M8): {on['acoes_com_sinal']} de {on['arrivals'] + on['rests']}.",
        f"- Gatilhos off = on (R9 da 360): {_verdict(p['triggers_iguais'])}.",
        "",
    ]
    return "\n".join(lines)


def render_global(allres: dict) -> str:
    g = allres["global"]
    lines = [
        "# SPEC-370 — eval da fauna viva: global",
        "",
        "Gerado por `scripts/fauna/eval.py --todas` (avaliador da Etapa 1; não editar à mão).",
        "",
        f"- Regiões com fauna: {len(g['regions'])} · M5 global (o que barra, R17):"
        f" {g['M5_global_delta']:+.4f} (faixa {M5_MIN_DELTA} a +{M5_MAX_DELTA}) →"
        f" {'ok' if g['passed'] else 'FALHOU'}.",
        f"- Combates por 100 ações: off {g['rate_off']} · on {g['rate_on']}.",
        "",
        "| Região | M1 próprio | M1 antigo | M2 | M3 | M4 | M5 (info) | M6 | M7 | M8 | Veredito |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r, res in allres["regions"].items():
        s = res["spec370"]
        mm, p = s["metrics"], s["passed"]
        lines.append(
            f"| `{r}` | {mm['M1_precedido_oraculo']:.4f} | {mm['M1_precedido_legado']:.4f} |"
            f" {_verdict(p['M2'])} | {_verdict(p['M3'])} | {_verdict(p['M4'])} |"
            f" {mm['M5_regiao_delta']:+.4f}{' (alerta)' if s['m5_alerta'] else ''} |"
            f" {_verdict(p['M6'])} | {_verdict(p['M7'])} | {mm['M8_densidade']:.4f} |"
            f" {'ok' if gate_ok(res) else 'FALHOU'} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    ap.add_argument("--days", type=int, default=DEFAULT_DAYS)
    ap.add_argument("--out", default=None)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--regiao", choices=REGIONS, default=None)
    grp.add_argument("--todas", action="store_true")
    args = ap.parse_args(argv)
    os.environ.setdefault("RPG_FORCE_MOCK", "1")
    if args.todas:
        allres = run_all(args.seeds, args.days, m7=True)
        for r, res in allres["regions"].items():
            _write(REPORT_DIR / f"eval-{r}.md", render_full(res))
        _write(Path(args.out) if args.out else REPORT_DIR / "eval-global.md", render_global(allres))
        summary = {
            "global": allres["global"],
            "regions": {r: res["spec370"]["passed"] for r, res in allres["regions"].items()},
        }
        print(json.dumps(summary, ensure_ascii=False))
        ok = allres["global"]["passed"] and all(map(gate_ok, allres["regions"].values()))
        return 0 if ok else 1
    if args.regiao:
        res = run(args.seeds, args.days, args.regiao, m7=True)
        _write(
            Path(args.out) if args.out else REPORT_DIR / f"eval-{args.regiao}.md", render_full(res)
        )
        s = res["spec370"]
        print(json.dumps({"metrics": s["metrics"], "passed": s["passed"]}, ensure_ascii=False))
        return 0 if gate_ok(res) else 1
    # sem flag: o caminho da 360 (Nova Arcadia, relatorio e codigo de saida da 360)
    res = run(args.seeds, args.days)
    _write(Path(args.out) if args.out else REPORT, render(res))
    print(json.dumps({"metrics": res["metrics"], "passed": res["passed"]}, ensure_ascii=False))
    return 0 if all(res["passed"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
