"""SPEC-372 R15: avaliador deterministico das criaturas de trama (T1-T8), congelado na Etapa 1.

Quem otimiza o produto NAO altera este arquivo nem `tests/test_spec372_eval.py` (D10:
ambos em `evals/protected-paths.txt`). Mudanca de limiar, cenario ou medida so pelo
coordenador, com registro na spec. Se T2 ou T4 falharem, ajusta-se `TRAMA_MULT` ou o
conteudo (`desde`, quais criaturas), nunca este arquivo (SPEC-372 Etapa 6).

O estagio de trama e LITERAL aqui: o avaliador monta os estados e diz qual estagio cada
trama tem (`STAGE_CASES`, `max_stages`), sem perguntar ao `plot_stage` do produto. T8
confere o `plot_stage`/`plot_stages` do produto contra esses literais; T1-T6 entregam o
mapa literal ao motor pelo contrato abaixo.

Contrato que o produto precisa expor (SPEC-372 §3.3; documentado no parecer
`handoffs/SPEC-372-eval-authoring.md`):

- `services.plot_threads.plot_stage(state, thread_id)` e `plot_stages(state, region_id)`;
- `world_utils.encounter_distribution(..., trama_stages=Mapping[str, str] | None)` e
  `world_utils.check_encounter(..., trama_stages=Mapping[str, str] | None)`, kwargs que
  chegam a `EcoCtx.trama_stages` (o chamador de jogo passa `plot_stages(state, regiao)`);
- `services.fauna.day_hook(ctx)` deriva o estagio de `ctx.state` (R3) e grava `trama_id`
  na presenca nascida nos locais da trama (R10);
- flag `RPG_FAUNA_TRAMAS` (`off`|`on`), efetiva so com `RPG_FAUNA=on` e
  `RPG_PLOT_THREADS=on` (R12); com `off`, `trama_stages` e ignorado.

Partes:

1. **Distribuicao exata** (T1, T2): `encounter_distribution` em contexto neutro, por local
   x periodo, com mapas de estagio literais.
2. **Simulacao** (T1, T3, T4, T5): o perfil de viagem da SPEC-360 (`scripts/fauna/eval.py`,
   helpers reaproveitados) em tres modos: `off` (flag desligada), `dormente` (flag ligada,
   estado sem sinal de trama) e `maximo` (flag ligada, estado com todo sinal de trama).
3. **T6** determinismo, **T7** relatorio da 360 com a flag `off` igual ao baseline
   versionado (`docs/spec360/eval-nova_arcadia.md`), **T8** estagio literal.

Uso: `bash scripts/dev/py.sh scripts/fauna/eval_tramas.py [--seeds 20] [--days 30] [--out PATH]`.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import functools
import importlib.util
import inspect
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REGION = "nova_arcadia"
DEFAULT_SEEDS = 20
DEFAULT_DAYS = 30
REPORT = ROOT / "docs" / "spec372" / "eval-tramas-nova_arcadia.md"
BASELINE_360 = ROOT / "docs" / "spec360" / "eval-nova_arcadia.md"
FLAG = "RPG_FAUNA_TRAMAS"

STAGES = ("dormente", "tocada", "investigada", "revelada")
DESDE = ("tocada", "investigada", "revelada")

# Limiares congelados (R15). Nao editar no mesmo trabalho que mexe no produto.
T1_MAX_SHARE = 0.0
T1_MAX_PRESENCAS = 0
T1_MAX_TRACK = 0
T2_MIN_RATIO = 1.5
T3_MIN_LOCAIS = 1.0
T4_MIN_DELTA = -0.10
T4_MAX_DELTA = 0.05
T5_MAX_VAZAMENTOS = 0
T8_MIN_CASES = 10
MODES = ("off", "dormente", "maximo")


# --------------------------------------------------------------------------- utilidades


@functools.lru_cache(maxsize=1)
def _ev360():
    spec = importlib.util.spec_from_file_location(
        "spec360_eval_for_372", ROOT / "scripts" / "fauna" / "eval.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@contextlib.contextmanager
def _env(**values: str | None):
    old = {k: os.environ.get(k) for k in values}
    for k, v in values.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _flags(tramas: str):
    """Fauna, sinais e tramas ligados nos tres modos; so a flag da SPEC-372 varia."""
    return _env(
        RPG_FAUNA="on",
        RPG_FAUNA_SINAIS="on",
        RPG_PLOT_THREADS="on",
        RPG_WORLD_ENGINE="on",
        RPG_FAUNA_TRAMAS=tramas,
    )


def require_contract(*, motor: bool = True) -> list[str]:
    """Lista o que falta do contrato do produto (vazio = ok). Nao chama o produto."""
    import world_utils as wu
    from services import plot_threads

    missing = []
    for fn in ("plot_stage", "plot_stages"):
        if not callable(getattr(plot_threads, fn, None)):
            missing.append(f"services.plot_threads.{fn}")
    for fn in ("encounter_distribution", "check_encounter") if motor else ():
        if "trama_stages" not in inspect.signature(getattr(wu, fn)).parameters:
            missing.append(f"world_utils.{fn}(trama_stages=...)")
    return missing


def _assert_contract(*, motor: bool = True) -> None:
    missing = require_contract(motor=motor)
    if missing:
        raise RuntimeError("contrato SPEC-372 ausente no produto: " + ", ".join(missing))


def _catalog() -> dict:
    return json.loads((ROOT / "data" / "world" / "plot_threads.json").read_text(encoding="utf-8"))


def region_threads() -> dict[str, dict]:
    return {t["id"]: t for t in _catalog().get("threads") or [] if t.get("region_id") == REGION}


def _norm_tramas(raw) -> list[dict]:
    """Normalizacao propria do avaliador (D1/D2): string solta vale `desde: tocada`."""
    out = []
    for item in raw or []:
        if isinstance(item, str):
            out.append({"id": item, "desde": "tocada"})
        elif isinstance(item, dict) and item.get("id"):
            out.append({"id": str(item["id"]), "desde": str(item.get("desde") or "tocada")})
    return out


def linked_creatures() -> dict[str, list[dict]]:
    """`{creature_id: [{id, desde}]}` das criaturas de NA com `tramas` em `fauna.json`."""
    doc = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    out = {}
    for cid, e in sorted((doc.get("criaturas") or {}).items()):
        if e.get("regiao") != REGION:
            continue
        links = _norm_tramas(e.get("tramas"))
        if links:
            out[cid] = links
    return out


def _rank(stage: str) -> int:
    return STAGES.index(stage) if stage in STAGES else 0


def _reached(links: list[dict], stages: dict[str, str]) -> list[str]:
    return [
        lk["id"] for lk in links if _rank(stages.get(lk["id"], "dormente")) >= _rank(lk["desde"])
    ]


def _below(desde: str) -> str:
    return STAGES[max(0, _rank(desde) - 1)]


def _locations() -> list[str]:
    import gamedata

    return sorted(
        loc["id"]
        for loc in gamedata.WORLD_MAP.get("locations", [])
        if loc.get("region_id") == REGION
    )


def _fold_tokens(text: str) -> set[str]:
    return _ev360()._tokens(text)


def forbidden_by_thread() -> dict[str, set[str]]:
    """Tokens (>= 4 letras, sem acento) das assinaturas dos `secret_ids` e dos nomes do `core`
    de cada trama. Fonte: dados (catalogo, grafo, assinaturas), nunca o lint do produto."""
    from services.secret_signatures import SECRET_SIGNATURES

    ents = json.loads((ROOT / "data" / "graph" / "entities.json").read_text(encoding="utf-8"))
    sigs = {k.casefold(): v for k, v in SECRET_SIGNATURES.items()}
    ev = _ev360()
    out: dict[str, set[str]] = {}
    for tid, t in region_threads().items():
        toks: set[str] = set()
        for sid in t.get("secret_ids") or []:
            for phrase in sigs.get(str(sid).casefold(), []):
                toks |= ev._tokens(phrase)
        for npc in t.get("core") or []:
            ent = ents.get(npc) or {}
            for name in [ent.get("name") or "", *(ent.get("aliases") or [])]:
                toks |= ev._tokens(str(name))
        out[tid] = toks
    return out


# --------------------------------------------------------------------------- estados literais


def _rumor_row(rid: str, seed_id: str, loc: str, *, perceived: int, resolution: str = "") -> dict:
    row = {
        "rumor_id": rid,
        "seed_id": seed_id,
        "family": "lore",
        "location_id": loc,
        "truth": True,
        "born_day": 1,
        "born_turn": 1,
        "expires_day": 999,
        "perceived_day": perceived,
    }
    if resolution:
        row["resolution"] = resolution
        row["resolved_day"] = 2
    return row


def _quest(qid: str, rid: str, status: str) -> dict:
    return {
        "id": qid,
        "world_kind": "investigar_rumor",
        "status": status,
        "lore_anchor": {"type": "rumor", "id": rid},
        "region_id": REGION,
        "created_day": 1,
    }


def _base(**extra) -> dict:
    st = {
        "game_id": "spec372-t8",
        "world": {
            "current_location_id": "na_anel_lama",
            "world_clock": {"day": 3, "period": "Tarde"},
        },
        "world_sim": {"rumors": []},
        "npcs": {},
        "quests": [],
        "event_log": [],
        "campaign_plan": {},
    }
    for k, v in extra.items():
        st[k] = v
    return st


_CORPOS = "tr_na_corpos_marcados"
_LORDE = "tr_na_o_que_o_lorde_trocou"
_SEED_CORPOS = "rumor_a_praga_de_ferro_nao_veio_das_minas"
_SEED_LORDE = "rumor_as_leis_de_valerius_foram_escritas_em_uma_noite"
_NPC_CORPOS = "npc_tr_pio_ferrugem"  # ancora so da porta p1 de corpos marcados
_NPC_LORDE = "npc_tr_rute_corvo_veterana"  # ancora so da porta p1 de o que o lorde trocou


def _npc(npc_id: str, **fields) -> dict:
    return {npc_id: {"id": npc_id, "name": npc_id, **fields}}


def stage_cases() -> list[tuple[str, dict, dict[str, str]]]:
    """T8: (nome, estado, estagios esperados das tramas citadas; as demais de NA = dormente).
    Um caso por regra da R1, combinacoes, negativos e o caso da R2."""
    return [
        ("vazio", _base(), {}),
        (
            "tocada_npc_known_by_player",
            _base(npcs=_npc(_NPC_CORPOS, known_by_player=True, knowledge_source="met")),
            {_CORPOS: "tocada"},
        ),
        (
            "tocada_npc_knowledge_met",
            _base(npcs=_npc(_NPC_LORDE, knowledge_source="met")),
            {_LORDE: "tocada"},
        ),
        (
            "dormente_npc_so_mencionado",
            _base(npcs=_npc(_NPC_CORPOS, known_by_player=False, knowledge_source="mentioned")),
            {},
        ),
        (
            "tocada_rumor_percebido",
            _base(
                world_sim={"rumors": [_rumor_row("r1", _SEED_CORPOS, "na_anel_lama", perceived=2)]}
            ),
            {_CORPOS: "tocada"},
        ),
        (
            "dormente_rumor_nao_percebido",
            _base(
                world_sim={"rumors": [_rumor_row("r1", _SEED_CORPOS, "na_anel_lama", perceived=0)]}
            ),
            {},
        ),
        (
            "tocada_fio_de_abertura_porta",
            _base(
                campaign_plan={
                    "opening_thread": {
                        "thread_refs": [f"{_LORDE}__p2"],
                        "region_id": REGION,
                        "arcs_left": 2,
                    }
                }
            ),
            {_LORDE: "tocada"},
        ),
        (
            "investigada_quest_ativa",
            _base(
                world_sim={"rumors": [_rumor_row("r1", _SEED_CORPOS, "na_anel_lama", perceived=2)]},
                quests=[_quest("q1", "r1", "active")],
            ),
            {_CORPOS: "investigada"},
        ),
        (
            "investigada_quest_concluida",
            _base(
                world_sim={"rumors": [_rumor_row("r2", _SEED_LORDE, "na_anel_ferro", perceived=2)]},
                quests=[_quest("q2", "r2", "completed")],
            ),
            {_LORDE: "investigada"},
        ),
        (
            "investigada_rumor_confirmado",
            _base(
                world_sim={
                    "rumors": [
                        _rumor_row(
                            "r1", _SEED_CORPOS, "na_anel_lama", perceived=2, resolution="confirmado"
                        )
                    ]
                }
            ),
            {_CORPOS: "investigada"},
        ),
        (
            "revelada_segredo_por_id",
            _base(event_log=[{"type": "secret_revealed", "target_id": "corpos"}]),
            {_CORPOS: "revelada"},
        ),
        (
            "revelada_segredo_por_entidade",
            _base(event_log=[{"type": "secret_revealed", "target_id": "npc_valerius"}]),
            {_LORDE: "revelada"},
        ),
        (
            "maior_estagio_vence",
            _base(
                npcs=_npc(_NPC_CORPOS, known_by_player=True, knowledge_source="met"),
                world_sim={"rumors": [_rumor_row("r1", _SEED_CORPOS, "na_anel_lama", perceived=2)]},
                quests=[_quest("q1", "r1", "active")],
                event_log=[{"type": "secret_revealed", "target_id": "praga"}],
            ),
            {_CORPOS: "revelada"},
        ),
        (
            "r2_quest_falhou_volta_a_tocada",
            _base(
                world_sim={"rumors": [_rumor_row("r1", _SEED_CORPOS, "na_anel_lama", perceived=2)]},
                quests=[_quest("q1", "r1", "failed")],
            ),
            {_CORPOS: "tocada"},
        ),
        (
            "segredo_nao_aceito_nao_revela",
            _base(event_log=[{"type": "secret_hinted", "target_id": "corpos"}]),
            {},
        ),
        ("maximo", max_state("spec372-t8"), max_stages()),
    ]


def max_stages() -> dict[str, str]:
    """Estagio literal do estado `maximo`: `revelada` se a trama tem `secret_ids`, senao
    `investigada` (sem segredo nao ha como revelar; R1)."""
    return {
        tid: ("revelada" if t.get("secret_ids") else "investigada")
        for tid, t in region_threads().items()
    }


def max_state_fields() -> dict:
    """Campos do estado `maximo`: cada trama com rumor percebido + quest de investigacao
    ativa sobre ele + todos os seus `secret_ids` aceitos (event_log)."""
    rumors, quests, events = [], [], []
    for tid, t in sorted(region_threads().items()):
        seeds = list(t.get("rumor_ids") or [])
        for i, seed in enumerate(seeds):
            rid = f"ev372-{tid}-{i}"
            rumors.append(_rumor_row(rid, seed, (t.get("locations") or [""])[0], perceived=1))
            if i == 0:
                quests.append(_quest(f"q372-{tid}", rid, "active"))
        for sid in t.get("secret_ids") or []:
            events.append({"type": "secret_revealed", "target_id": sid})
    return {"rumors": rumors, "quests": quests, "event_log": events}


def max_state(game_id: str) -> dict:
    f = max_state_fields()
    return _base(
        game_id=game_id,
        world_sim={"rumors": copy.deepcopy(f["rumors"])},
        quests=copy.deepcopy(f["quests"]),
        event_log=copy.deepcopy(f["event_log"]),
    )


def stage_metrics() -> dict:
    """T8: estagio do produto x literal, por caso e por trama de NA; e o produto nao muta."""
    _assert_contract(motor=False)
    from services import plot_threads

    threads = sorted(region_threads())
    cases, wrong, mutated = [], [], []
    with _flags("on"):
        for name, state, expected in stage_cases():
            want = {tid: expected.get(tid, "dormente") for tid in threads}
            before = json.dumps(state, sort_keys=True, ensure_ascii=False)
            got_one = {tid: str(plot_threads.plot_stage(state, tid)) for tid in threads}
            got_all = {k: str(v) for k, v in dict(plot_threads.plot_stages(state, REGION)).items()}
            if json.dumps(state, sort_keys=True, ensure_ascii=False) != before:
                mutated.append(name)
            ghost = str(plot_threads.plot_stage(state, "tr_na_nao_existe"))
            ok = (
                got_one == want
                and {t: got_all.get(t) for t in threads} == want
                and ghost == "dormente"
            )
            cases.append(name)
            if not ok:
                wrong.append(
                    {
                        "case": name,
                        "want": {t: s for t, s in want.items() if s != "dormente"},
                        "plot_stage": {t: s for t, s in got_one.items() if s != "dormente"},
                        "plot_stages": {t: s for t, s in got_all.items() if s != "dormente"},
                        "inexistente": ghost,
                    }
                )
    return {"cases": cases, "wrong": wrong, "mutated": mutated}


# --------------------------------------------------------------------------- distribuicao


def _distribution(loc: str, period: str, stages: dict[str, str]) -> dict[str, float]:
    import gamedata
    import world_utils as wu

    rows = wu.encounter_distribution(
        gamedata.get_location(loc) or {},
        _ev360().PLAYER_LEVEL,
        100,
        bestiary_knowledge={},
        projection={},
        world=_ev360()._neutral_world(loc, period),
        world_sim={},
        trama_stages=dict(stages),
    )
    total = sum(w for _e, w in rows) or 1.0
    out: dict[str, float] = {}
    for e, w in rows:
        out[str(e.get("id"))] = out.get(str(e.get("id")), 0.0) + w / total
    return out


def distribution_metrics() -> dict:
    """T1 (fatia 0 antes do estagio) e T2 (puxao nos locais da trama depois do estagio)."""
    from world_utils import PERIODS

    linked = linked_creatures()
    threads = region_threads()
    locs = _locations()
    dormant = {tid: "dormente" for tid in threads}
    top = max_stages()
    t1: dict[str, dict] = {}
    with _flags("on"):
        for cid, links in linked.items():
            below = {**dormant, **{lk["id"]: _below(lk["desde"]) for lk in links}}
            worst = 0.0
            for stages in (dormant, below):
                for loc in locs:
                    for p in PERIODS:
                        worst = max(worst, _distribution(loc, p, stages).get(cid, 0.0))
            t1[cid] = {"max_share": round(worst, 6)}
        on = {(loc, p): _distribution(loc, p, top) for loc in locs for p in PERIODS}
    with _flags("off"):
        off = {(loc, p): _distribution(loc, p, top) for loc in locs for p in PERIODS}
    t2: dict[str, dict] = {}
    unreachable = []
    for cid, links in linked.items():
        hit = _reached(links, top)
        if not hit:
            unreachable.append(cid)
            continue
        where = sorted(
            {loc for tid in hit for loc in (threads.get(tid) or {}).get("locations") or []}
        )
        ctxs = [(loc, p) for loc in where for p in PERIODS]
        s_off = sum(off[c].get(cid, 0.0) for c in ctxs if c in off)
        s_on = sum(on[c].get(cid, 0.0) for c in ctxs if c in on)
        t2[cid] = {
            "threads": hit,
            "share_off": round(s_off / max(1, len(ctxs)), 6),
            "share_on": round(s_on / max(1, len(ctxs)), 6),
            "ratio": round(s_on / s_off, 4) if s_off > 0 else None,
        }
    return {"t1": t1, "t2": t2, "unreachable": unreachable}


# --------------------------------------------------------------------------- simulacao


def _scenario_state(ev, seed: int, mode: str) -> dict:
    st = ev._new_state(seed)
    st["game_id"] = f"spec372-eval-{seed}"
    if mode in ("off", "maximo"):
        f = max_state_fields()
        st["world_sim"]["rumors"] = copy.deepcopy(f["rumors"])
        st["quests"] = copy.deepcopy(f["quests"])
        st["event_log"] = copy.deepcopy(f["event_log"])
    else:
        st["world_sim"]["rumors"] = []
        st["quests"] = []
        st["event_log"] = []
    st["npcs"] = {}
    st["campaign_plan"] = {}
    return st


def _scenario_stages(mode: str) -> dict[str, str]:
    if mode == "dormente":
        return {tid: "dormente" for tid in region_threads()}
    return max_stages()


def _collect_presences(sim: dict, seen: dict[str, dict]) -> None:
    for p in ((sim or {}).get("fauna") or {}).get("presencas") or []:
        if isinstance(p, dict) and p.get("pid") and p["pid"] not in seen:
            seen[p["pid"]] = copy.deepcopy(p)


def _simulate(seed: int, days: int, mode: str, ev, forbidden: dict[str, set[str]]) -> dict:
    import world_utils as wu
    from services import discovery as disc
    from services import fauna
    from world_utils import PERIODS

    linked = linked_creatures()
    stages = _scenario_stages(mode)
    state = _scenario_state(ev, seed, mode)
    world, nodes = state["world"], ev._region_nodes()
    out = {
        "actions": 0,
        "triggers": 0,
        "fauna_combats": 0,
        "conversions": 0,
        "texts": 0,
        "linked_picks": {},
        "leaks": [],
    }
    seen: dict[str, dict] = {}

    def owner_leaks(owner: str, text: str) -> None:
        out["texts"] += 1
        for lk in linked.get(owner, []):
            out["leaks"] += [
                (owner, lk["id"], t)
                for t in sorted(_fold_tokens(text) & forbidden.get(lk["id"], set()))
            ]

    seasons = ("primavera", "verao", "outono", "inverno")
    turn = 0
    for day in range(1, days + 1):
        drng = random.Random(ev._seed_int(seed, day, "day"))
        world["weather_state"] = drng.choice(ev.WEATHERS)
        world["season"] = {"id": seasons[((day - 1) // 15) % 4]}
        world["world_clock"] = {"day": day, "period": world["world_clock"]["period"]}
        ev._run_day_hooks(state, day)
        _collect_presences(state["world_sim"], seen)
        for i in range(ev.ARRIVALS_PER_DAY + 1):
            turn += 1
            out["actions"] += 1
            rest = i == ev.ARRIVALS_PER_DAY
            arng = random.Random(ev._seed_int(seed, turn, "act"))
            period = PERIODS[(day + i) % len(PERIODS)]
            world["world_clock"] = {"day": day, "period": period}
            world["time_of_day"] = period
            world["turn_count"] = turn
            if not rest:
                here = world["current_location_id"]
                dest = arng.choice([n for n in nodes if n != here])
                world["current_location_id"] = dest
                world["current_location"] = dest
            random.seed(ev._seed_int(seed, turn, "pick"))
            kind_rng = random.Random(ev._seed_int(seed, turn, "kind"))
            enc = wu.check_encounter(
                world,
                [],
                {},
                turn,
                bestiary_knowledge=state["bestiary_knowledge"],
                projection={},
                player_level=ev.PLAYER_LEVEL,
                world_sim=state["world_sim"],
                trama_stages=dict(stages),
            )
            kind = wu.roll_encounter_type(ev.FORCED_DANGER, rng=kind_rng)
            loc = world["current_location_id"]
            sign_this_turn = False
            if enc and enc.get("reason") in ev.FAUNA_REASONS:
                out["triggers"] += 1
                world["last_encounter_turn"] = turn
                cid = str(enc.get("enemy_id") or "")
                entry = fauna.entry(cid)
                if cid in linked:
                    key = f"{cid}|{'convert' if enc.get('fauna_convert') else kind}"
                    out["linked_picks"][key] = out["linked_picks"].get(key, 0) + 1
                if enc.get("fauna_convert") and entry:
                    before = ev._shown_counts(state["world_sim"])
                    note, upd = fauna.convert_to_signal(state, entry, loc, day)
                    state["world_sim"] = upd.get("world_sim", state["world_sim"])
                    out["conversions"] += 1
                    sign_this_turn = True
                    owner_leaks(ev._new_sign_owner(before, state["world_sim"]) or cid, note)
                elif kind == "combat":
                    out["fauna_combats"] += 1
                    owner_leaks(cid, str(enc.get("flavor") or ""))
                    if entry:
                        pres = ev._presence(state["world_sim"], str(enc.get("presence_id") or ""))
                        if pres:
                            state["world_sim"], _ = fauna.mark_encountered(
                                state["world_sim"], pres["pid"], day
                            )
                        state["world_sim"] = fauna.record_kill(state["world_sim"], cid, loc, day)
                    state["bestiary_knowledge"] = disc.record_kills(
                        state["bestiary_knowledge"], [{"id": cid}], turn
                    )
                    _collect_presences(state["world_sim"], seen)
                    continue
                elif kind == "track" and entry:
                    before = ev._shown_counts(state["world_sim"])
                    note, upd = fauna.track_signal(state, entry, loc, day)
                    state["world_sim"] = upd.get("world_sim", state["world_sim"])
                    if note:
                        sign_this_turn = True
                        owner_leaks(ev._new_sign_owner(before, state["world_sim"]) or cid, note)
            if not sign_this_turn:
                before = ev._shown_counts(state["world_sim"])
                block, upd = fauna.scene_block(state)
                if block:
                    state["world_sim"] = upd.get("world_sim", state["world_sim"])
                    owner_leaks(ev._new_sign_owner(before, state["world_sim"]), block)
            _collect_presences(state["world_sim"], seen)
    threads = region_threads()
    pres = list(seen.values())
    out["presences"] = len(pres)
    out["presences_trama_id"] = sum(1 for p in pres if "trama_id" in p)
    out["linked_presences"] = sum(1 for p in pres if p.get("creature_id") in linked)
    t3_n = t3_ok = 0
    t3_bad = []
    for p in pres:
        cid = str(p.get("creature_id") or "")
        if cid not in linked or p.get("origem") != "dia":
            continue
        hit = _reached(linked[cid], stages)
        if not hit:
            continue
        t3_n += 1
        allowed = {loc for tid in hit for loc in (threads.get(tid) or {}).get("locations") or []}
        good = (
            set(p.get("locais") or []) <= allowed
            and bool(p.get("locais"))
            and p.get("trama_id") in hit
        )
        if good:
            t3_ok += 1
        else:
            t3_bad.append((cid, tuple(p.get("locais") or []), str(p.get("trama_id"))))
    out["t3_n"], out["t3_ok"], out["t3_bad"] = t3_n, t3_ok, t3_bad
    return out


def _aggregate(rows: list[dict]) -> dict:
    agg: dict = {}
    for r in rows:
        for k, v in r.items():
            if isinstance(v, dict):
                d = agg.setdefault(k, {})
                for kk, vv in v.items():
                    d[kk] = d.get(kk, 0) + vv
            elif isinstance(v, list):
                agg.setdefault(k, []).extend(v)
            else:
                agg[k] = agg.get(k, 0) + v
    return agg


def simulation(seeds: int, days: int) -> dict:
    _assert_contract()
    ev = _ev360()
    forbidden = forbidden_by_thread()
    res = {}
    for mode in MODES:
        with _flags("off" if mode == "off" else "on"):
            res[mode] = _aggregate([_simulate(s, days, mode, ev, forbidden) for s in range(seeds)])
    return res


def _static_leaks(forbidden: dict[str, set[str]]) -> list[tuple]:
    """T5 estatico: todo texto de sinal/aproximacao de criatura ligada em `fauna.json`."""
    doc = json.loads((ROOT / "data" / "world" / "fauna.json").read_text(encoding="utf-8"))
    out = []
    for cid, links in linked_creatures().items():
        sinais = ((doc.get("criaturas") or {}).get(cid) or {}).get("sinais") or {}
        for k, txt in sorted(sinais.items()):
            for lk in links:
                out += [
                    (cid, lk["id"], k, t)
                    for t in sorted(_fold_tokens(str(txt)) & forbidden.get(lk["id"], set()))
                ]
    return out


# --------------------------------------------------------------------------- T7


def baseline_360_identical() -> dict:
    """T7: com a flag `off` (tramas do mundo ligadas), o relatorio da 360 e o baseline."""
    ev = _ev360()
    with _env(RPG_FAUNA_TRAMAS="off", RPG_PLOT_THREADS="on"):
        text = ev.render(ev.run(ev.DEFAULT_SEEDS, ev.DEFAULT_DAYS))
    base = BASELINE_360.read_text(encoding="utf-8")
    return {"identical": text == base, "chars": len(text), "baseline_chars": len(base)}


# --------------------------------------------------------------------------- relatorio


def run(seeds: int = DEFAULT_SEEDS, days: int = DEFAULT_DAYS, *, with_t7: bool = True) -> dict:
    _assert_contract()
    linked = linked_creatures()
    forbidden = forbidden_by_thread()
    dist = distribution_metrics()
    sim = simulation(seeds, days)
    stage = stage_metrics()
    static = _static_leaks(forbidden)
    off, dorm, top = sim["off"], sim["dormente"], sim["maximo"]

    def rate(r):
        return 100.0 * r["fauna_combats"] / max(1, r["actions"])

    def delta(r):
        return round((rate(r) - rate(off)) / rate(off), 4) if rate(off) else None

    dorm_picks = dorm.get("linked_picks") or {}
    t1_share = max([v["max_share"] for v in dist["t1"].values()] or [0.0])
    t1_track = sum(v for k, v in dorm_picks.items() if k.endswith("|track"))
    ratios = [v["ratio"] for v in dist["t2"].values()]
    t3_frac = round(top["t3_ok"] / top["t3_n"], 4) if top["t3_n"] else None
    leaks = len(static) + len(dorm["leaks"]) + len(top["leaks"])
    m = {
        "linked": len(linked),
        "threads_covered": len({lk["id"] for links in linked.values() for lk in links}),
        "T1_max_share": t1_share,
        "T1_presencas": dorm["linked_presences"],
        "T1_track": t1_track,
        "T1_picks": sum(dorm_picks.values()),
        "T2_min_ratio": min(ratios) if ratios and None not in ratios else None,
        "T2_unreachable": len(dist["unreachable"]),
        "T3_locais": t3_frac,
        "T3_n": top["t3_n"],
        "T3_off_trama_id": off["presences_trama_id"],
        "T4_triggers": {k: sim[k]["triggers"] for k in MODES},
        "T4_delta_dormente": delta(dorm),
        "T4_delta_maximo": delta(top),
        "T5_vazamentos": leaks,
        "T8_cases": len(stage["cases"]),
        "T8_wrong": len(stage["wrong"]),
        "T8_mutated": len(stage["mutated"]),
    }
    passed = {
        "T1": bool(linked)
        and t1_share <= T1_MAX_SHARE
        and m["T1_presencas"] <= T1_MAX_PRESENCAS
        and t1_track <= T1_MAX_TRACK
        and m["T1_picks"] == 0,
        "T2": bool(linked)
        and m["T2_unreachable"] == 0
        and m["T2_min_ratio"] is not None
        and m["T2_min_ratio"] >= T2_MIN_RATIO,
        "T3": bool(linked)
        and t3_frac is not None
        and t3_frac >= T3_MIN_LOCAIS
        and m["T3_off_trama_id"] == 0,
        "T4": len(set(m["T4_triggers"].values())) == 1
        and off["fauna_combats"] > 0
        and all(
            d is not None and T4_MIN_DELTA <= d <= T4_MAX_DELTA
            for d in (m["T4_delta_dormente"], m["T4_delta_maximo"])
        ),
        "T5": leaks <= T5_MAX_VAZAMENTOS and (dorm["texts"] + top["texts"]) > 0,
        "T8": m["T8_cases"] >= T8_MIN_CASES and m["T8_wrong"] == 0 and m["T8_mutated"] == 0,
    }
    res = {
        "config": {"seeds": seeds, "days": days, "region": REGION},
        "links": {cid: links for cid, links in linked.items()},
        "dist": dist,
        "sim": {
            k: {kk: vv for kk, vv in v.items() if kk not in ("leaks", "t3_bad")}
            for k, v in sim.items()
        },
        "rates": {k: round(rate(sim[k]), 3) for k in MODES},
        "t3_bad": sorted(set(top["t3_bad"]))[:10],
        "leak_samples": sorted(set(static))[:10] + sorted(set(dorm["leaks"] + top["leaks"]))[:10],
        "stage": stage,
        "metrics": m,
        "passed": passed,
    }
    if with_t7:
        t7 = baseline_360_identical()
        res["t7"] = t7
        passed["T7"] = t7["identical"]
    return res


def _ok(flag: bool) -> str:
    return "ok" if flag else "FALHOU"


def render(res: dict) -> str:
    m, p, cfg = res["metrics"], res["passed"], res["config"]
    lines = [
        "# SPEC-372 — eval das criaturas de trama: Nova Arcádia",
        "",
        "Gerado por `scripts/fauna/eval_tramas.py` (avaliador congelado na Etapa 1; não editar à mão).",
        "",
        f"- Região: `{cfg['region']}` · seeds: {cfg['seeds']} · dias por seed: {cfg['days']}",
        f"- Criaturas ligadas: {m['linked']} · tramas com criatura: {m['threads_covered']}",
        "- Modos: `off` (flag desligada), `dormente` (flag ligada, nenhum sinal de trama),"
        " `maximo` (flag ligada, todo sinal de trama; estágio literal por trama abaixo).",
        "",
        "| Teste | Valor | Limiar | Resultado |",
        "|---|---|---|---|",
        f"| T1 portão: maior fatia antes do estágio | {m['T1_max_share']} | ≤ {T1_MAX_SHARE} | {_ok(p['T1'])} |",
        f"| T1 presenças de ligada (dormente) | {m['T1_presencas']} | ≤ {T1_MAX_PRESENCAS} | {_ok(p['T1'])} |",
        f"| T1 escolhas no `track` (dormente) | {m['T1_track']} | ≤ {T1_MAX_TRACK} | {_ok(p['T1'])} |",
        f"| T2 puxão: menor razão on/off nos locais | {m['T2_min_ratio']} | ≥ {T2_MIN_RATIO} | {_ok(p['T2'])} |",
        f"| T2 ligadas inalcançáveis | {m['T2_unreachable']} | = 0 | {_ok(p['T2'])} |",
        f"| T3 presenças nos locais da trama (n={m['T3_n']}) | {m['T3_locais']} | ≥ {T3_MIN_LOCAIS} | {_ok(p['T3'])} |",
        f"| T3 `trama_id` com a flag off | {m['T3_off_trama_id']} | = 0 | {_ok(p['T3'])} |",
        f"| T4 gatilhos off/dormente/maximo | {m['T4_triggers']} | iguais | {_ok(p['T4'])} |",
        f"| T4 Δ combates (dormente) | {m['T4_delta_dormente']} | {T4_MIN_DELTA} a +{T4_MAX_DELTA} | {_ok(p['T4'])} |",
        f"| T4 Δ combates (maximo) | {m['T4_delta_maximo']} | {T4_MIN_DELTA} a +{T4_MAX_DELTA} | {_ok(p['T4'])} |",
        f"| T5 vazamento (segredo/núcleo) | {m['T5_vazamentos']} | ≤ {T5_MAX_VAZAMENTOS} | {_ok(p['T5'])} |",
        f"| T8 estágio literal ({m['T8_cases']} casos) | {m['T8_wrong']} errados, {m['T8_mutated']} mutados | 0 | {_ok(p['T8'])} |",
    ]
    if "t7" in res:
        lines.append(
            f"| T7 relatório da 360 com a flag off | {res['t7']['identical']} | idêntico | {_ok(p['T7'])} |"
        )
    lines += [
        "",
        "## Estágio do modo `maximo` (literal)",
        "",
        f"`{json.dumps(max_stages(), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Ligações",
        "",
        f"`{json.dumps(res['links'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Contagens",
        "",
        "| Modo | Ações | Gatilhos | Combates de fauna | Conversões | Presenças | Presenças de ligada | Combates/100 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for k in MODES:
        r = res["sim"][k]
        lines.append(
            f"| {k} | {r['actions']} | {r['triggers']} | {r['fauna_combats']} | {r['conversions']} |"
            f" {r['presences']} | {r['linked_presences']} | {res['rates'][k]} |"
        )
    lines += [
        "",
        "## Distribuição (contexto neutro, exata)",
        "",
        f"- T1 por criatura: {json.dumps(res['dist']['t1'], ensure_ascii=False, sort_keys=True)}",
        f"- T2 por criatura: {json.dumps(res['dist']['t2'], ensure_ascii=False, sort_keys=True)}",
        f"- Inalcançáveis: {json.dumps(res['dist']['unreachable'], ensure_ascii=False)}",
        "",
    ]
    if res["stage"]["wrong"] or res["stage"]["mutated"]:
        lines += ["## T8 divergências", ""]
        lines += [
            f"- {json.dumps(w, ensure_ascii=False, sort_keys=True)}" for w in res["stage"]["wrong"]
        ]
        lines += [f"- mutou o estado: {n}" for n in res["stage"]["mutated"]] + [""]
    if res["t3_bad"]:
        lines += ["## T3 presenças fora (amostra)", ""] + [f"- {x}" for x in res["t3_bad"]] + [""]
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
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render(res))
    print(json.dumps({"metrics": res["metrics"], "passed": res["passed"]}, ensure_ascii=False))
    return 0 if all(res["passed"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
