"""SPEC-369 Fase A - regua das metas do epico de Cartas (offline, MockLLM, seeded, sem LLM).

    bash scripts/dev/py.sh docs/spec369/metricas_369.py <cmd> --seeds 0-19 --out docs/spec369/base-0-19.json

Subcomandos (R6): base, uso, duracao, pressagio, posturas, emboscada, familias. Cada um grava a
SUA chave no JSON de ``--out`` (o arquivo e mesclado, nao sobrescrito). So IMPORTA `sim`,
`metricas_epico`, `arena_spec341`, `arena_spec355` e `arena_familias`; todo monkeypatch volta no
``finally``. Nenhum avaliador, orcamento, golden ou arena antiga e editado (R2).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import random
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in ("docs/spec369", "docs/spec341", "docs/spec335", "docs/spec355", "scripts/cards", ""):
    sys.path.insert(0, os.path.join(ROOT, _p))

import bot_pressagio as BP  # noqa: E402

ME, sim, A = BP.ME, BP.sim, BP.A
import arena_spec341 as B  # noqa: E402
import arena_spec355 as E  # noqa: E402

from services import card_effects as fx  # noqa: E402
from services import (  # noqa: E402
    card_piles,
    cards,
    enemy_intent,
)
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402


def _load_path(name: str, rel: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


F = _load_path("arena_familias_369", "docs/spec332/arena_familias.py")
_T355 = _load_path("test_spec355_arena_369", "tests/test_spec355_arena.py")

REF_368 = os.path.join(ROOT, "docs", "spec368", "metricas-0-19.json")
PARAMS_368 = {"levels": [1, 3, 5], "categories": ["padrao", "elite"], "per_cat": 3}
# Cartas que entraram no catalogo DEPOIS do JSON da 368 (03/11): reacoes iniciais da SPEC-371
# (992810fa, 82ea73dd). Sem elas a base reproduz `metricas-0-19.json` byte a byte (Etapa 0).
CARTAS_POS_368 = ("arc1_ini_cinza_nos_olhos", "dev1_ini_dor_devolvida", "med1_ini_pinca_no_tendao")
TETO_INFO = 12  # braco informativo "teto 12" (Relogio do produto), nao e criterio
BRACOS = ("off", "on-cego", "on-368", "on-faixa")
FAIXA = (0.45, 0.85)
TETO_PADRAO = 0.75
DELTA_FAMILIA_PP = 10.0
EXCECOES_TETO = {k for v in _T355.EXCECOES_TETO.values() for k in v}


def parse_seeds(raw: str) -> list[int]:
    return ME._parse_seeds(raw)


def write_section(path: str, key: str, data: dict) -> None:
    """Mescla ``{key: data}`` no JSON de ``path`` (cria se nao existir)."""
    cur: dict = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            cur = json.load(fh)
    cur[key] = data
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(cur, ensure_ascii=False, indent=1) + "\n")


# --------------------------------------------------------------------------
# base / duracao / uso: a luta da 368, so observada
# --------------------------------------------------------------------------
@contextlib.contextmanager
def capturar():
    """Observa ``ME.fight`` sem mudar nada: registra cada luta (+ rodadas com cura) e o
    ``seen`` de cada Postura. Restaura os dois atributos no ``finally``."""
    log: list[dict] = []
    seen_by_class: dict[str, dict] = {}
    ctx = {"heals": 0}
    orig_fight, orig_decl = ME.fight, ME.sim.full_deck_decl

    def decl_obs(player, piles, target_id, seen=None):
        decl = orig_decl(player, piles, target_id, seen)
        if any(s.kind == "card" and sim._kind(s.card_id or "") == "cura" for s in decl.jogadas):
            ctx["heals"] += 1
        return decl

    def fight_obs(bid, n, class_name, level, seed, deck, tag, *, omen, seen):
        ctx["heals"] = 0
        res = orig_fight(bid, n, class_name, level, seed, deck, tag, omen=omen, seen=seen)
        if not omen:
            seen_by_class[class_name] = seen
        log.append(
            {
                "cls": class_name,
                "level": level,
                "bid": bid,
                "seed": seed,
                "omen": omen,
                "rounds": res["rounds"],
                "outcome": res["outcome"],
                "damage": res["damage"],
                "heal_rounds": ctx["heals"],
                "n_rounds": len(res["per_round"]),
            }
        )
        return res

    ME.fight, ME.sim.full_deck_decl = fight_obs, decl_obs
    try:
        yield log, seen_by_class
    finally:
        ME.fight, ME.sim.full_deck_decl = orig_fight, orig_decl


def run_base(seeds, *, r10: bool = True, classes=None, **params) -> tuple[dict, list, dict]:
    """``metricas_epico.run`` com os parametros da 368 (sobrescreviveis so para teste)."""
    p = {**PARAMS_368, **params}
    with capturar() as (log, seen_by_class):
        result = ME.run(seeds, p["levels"], p["categories"], p["per_cat"], r10=r10, classes=classes)
    return result, log, seen_by_class


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1)


@contextlib.contextmanager
def sem_cartas(ids: tuple[str, ...]):
    """Tira ``ids`` do catalogo em memoria (nada em disco) e devolve no ``finally``.
    O cache de herois da arena 285 tambem e zerado: a ficha inicial (SPEC-371) ja nasce com a
    reacao inicial preparada, e o heroi em cache guardaria a Carta tirada."""
    cat = cards._load_cards()
    saved = {i: cat.pop(i) for i in ids if i in cat}
    heroes = dict(A._HEROES)
    A._HEROES.clear()
    try:
        yield
    finally:
        cat.update(saved)
        A._HEROES.clear()
        A._HEROES.update(heroes)


def cmd_base(seeds: list[int]) -> dict:
    """R9a: reproduz a 368; com as sementes 0-19, compara byte a byte com o JSON commitado.
    Divergiu (catalogo mudou depois de 03/11): mede tambem sem as Cartas posteriores
    (``CARTAS_POS_368``), o que isola a causa; a base nova (catalogo atual) e a que vale."""
    result, _, _ = run_base(seeds)
    out = {"r9": result["r9"], "r10": result["r10"]}
    if seeds == list(range(20)):
        with open(REF_368, encoding="utf-8") as fh:
            ref = json.load(fh)
        out["equivalencia_368"] = {k: _canon(result[k]) == _canon(ref[k]) for k in ("r9", "r10")}
        with sem_cartas(CARTAS_POS_368):
            antigo, _, _ = run_base(seeds)
        out["equivalencia_368_sem_cartas_pos_368"] = {
            k: _canon(antigo[k]) == _canon(ref[k]) for k in ("r9", "r10")
        }
        out["cartas_pos_368"] = list(CARTAS_POS_368)
    return out


def _hist(values: list[int]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in sorted(values):
        out[str(v)] = out.get(str(v), 0) + 1
    return out


def _duracao_de(fights: list[dict]) -> dict:
    rounds = [f["rounds"] for f in fights]
    capped = [min(r, TETO_INFO) for r in rounds]
    n = max(1, len(fights))
    total_rounds = max(1, sum(f["n_rounds"] for f in fights))
    wins_cap = sum(f["outcome"] == "win" and f["rounds"] <= TETO_INFO for f in fights)
    return {
        "conflitos": len(fights),
        "histograma_rodadas": _hist(rounds),
        "p95_rodadas": ME.p95(rounds),
        "timeout_pct": round(100 * sum(f["outcome"] == "timeout" for f in fights) / n, 1),
        "pct_rodadas_com_cura": round(
            100 * sum(f["heal_rounds"] for f in fights) / total_rounds, 1
        ),
        "teto12_informativo": {
            "pct_conflitos_cortados": round(100 * sum(r > TETO_INFO for r in rounds) / n, 1),
            "p95_rodadas": ME.p95(capped),
            "vitoria_pct": round(100 * wins_cap / n, 1),
        },
    }


def cmd_duracao(seeds: list[int]) -> dict:
    """R6 duracao: histograma, timeouts e % de rodadas com cura, por Postura e total."""
    _, log, _ = run_base(seeds, r10=False)
    out = {"por_postura": {}, "total": _duracao_de(log)}
    for cls in dict.fromkeys(f["cls"] for f in log):
        out["por_postura"][cls] = _duracao_de([f for f in log if f["cls"] == cls])
    return out


def categoria(cid: str) -> str:
    """``sangromante`` (trava do dono, inclui `bas_san_*`) > ``basica`` > ``onda`` > ``legada``."""
    card = cards.get_card(cid) or {}
    if card.get("classe") == "Sangromante":
        return "sangromante"
    if card.get("basica"):
        return "basica"
    if str(card.get("origem") or "").startswith("onda"):
        return "onda"
    return "legada"


def delta_v2(card: dict, seeds: list[int]) -> dict:
    """``lote-v2`` (SPEC-358) da propria Carta do catalogo. Com as sementes 0-19 e
    exatamente ``sim.simulate_protocolo_lote([card], protocolo="v2")`` (lote de 1)."""
    level = max(int(card.get("level_req", 1) or 1), 1)
    rep = sim.simulate_batch(
        [card],
        [level],
        sim.PROTOCOLO_LOTE["categories"],
        sim.PROTOCOLO_LOTE["per_cat"],
        list(seeds),
        protocolo="v2",
    )
    return rep[card["id"]]


def _uso_resumo(rows: dict) -> dict:
    out: dict = {}
    for cid, r in rows.items():
        cat = out.setdefault(r["categoria"], {"uso_acima_60": [], "dominante_delta": []})
        if r["uso"] > ME.USO_ALTO:
            cat["uso_acima_60"].append(cid)
        if "dominante" in r["bandeiras_v2"]:
            cat["dominante_delta"].append(cid)
    return dict(sorted(out.items()))


def cmd_uso(seeds: list[int], *, ids: list[str] | None = None) -> dict:
    """R6 uso: por Carta com n >= 5 na mao (bot da 368), categoria, uso, versao e Delta v2."""
    _, _, seen_by_class = run_base(seeds, r10=False)
    seen: dict = {}
    for s in seen_by_class.values():
        ME._merge(seen, s)
    rows: dict = {}
    for cid, (na_mao, jogada) in sorted(seen.items()):
        if na_mao < ME.AMOSTRA_USO or (ids and cid not in ids):
            continue
        card = dict(cards.get_card(cid) or {"id": cid})
        rep = delta_v2(card, seeds)
        rows[cid] = {
            "categoria": categoria(cid),
            "classe": card.get("classe"),
            "versao": fx.versao(card),
            "custo_folego": fx.custo_folego(card),  # snapshot (Astra P3-8, isencao D-369-10)
            "na_mao": na_mao,
            "uso": round(jogada / na_mao, 3),
            "delta_pp_v2": rep["delta_pp"],
            "delta_base": rep["delta_base"],
            "taxa_uso_lote": rep["taxa_uso"],
            "lutas_por_braco": rep["lutas_por_braco"],
            "bandeiras_v2": rep["bandeiras"],
            "avisos_v2": rep["avisos"],
        }
        print(
            f"[uso] {cid}: uso {rows[cid]['uso']} d {rep['delta_pp']} {rep['bandeiras']}",
            flush=True,
        )
    return {"cartas": rows, "por_categoria": _uso_resumo(rows)}


# --------------------------------------------------------------------------
# pressagio (R7/R8): 4 bracos x conhecimento x baralho de inimigo
# --------------------------------------------------------------------------
def decisor(braco: str):
    """``(player, piles, actors, sides, scene, forecast, seen, target) -> TurnDeclaration``."""

    def cego(player, piles, actors, sides, scene, forecast, seen, target):
        return sim.full_deck_decl(player, piles, target, seen)

    def b368(player, piles, actors, sides, scene, forecast, seen, target):
        decl = sim.full_deck_decl(player, piles, target, seen)
        return ME._heed_omen(player, piles, decl, forecast, seen)

    def faixa(player, piles, actors, sides, scene, forecast, seen, target):
        return BP.leitor_faixa_decl(player, piles, actors, sides, scene, forecast, seen)

    return {"off": cego, "on-cego": cego, "on-368": b368, "on-faixa": faixa}[braco]


def _arena(bid, n, class_name, level, deck, known: bool):
    player = A.hero(class_name, level)
    player["deck"] = sorted(deck)
    player["prepared_cards"] = list(
        dict.fromkeys(list(player["deck"]) + (player.get("prepared_cards") or []))
    )
    enemies = A._instances(
        A.template_by_id(bid, encounter_level=A.DANGER_BY_LEVEL.get(level, 4)), n
    )
    if known:
        for e in enemies:
            e["known"] = True  # jogador que ja viu a familia (`knowledge_level` -> conhecida)
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    return player, enemies, actors, sides, scene


def _morreu(player: dict, out: dict) -> bool:
    return bool(
        player.get("dead")
        or player.get("estado_terminal")
        or out.get("player_dead")
        or int(player.get("vitalidade", 0) or 0) <= 0
    )


def fight_braco(bid, n, class_name, level, seed, deck, braco: str, *, known: bool) -> dict:
    """A luta de ``metricas_epico.fight`` (mesma tag, rngs e parada), com o bot do braco."""
    random.seed(f"m368|{level}|{class_name}|{bid}|{n}|{seed}")
    player, enemies, actors, sides, scene = _arena(bid, n, class_name, level, deck, known)
    rng, omen_rng = random.Random(seed), random.Random(f"omen:{seed}")
    piles = card_piles.start_piles(player, seed)
    state = {"player": player, "_piles": piles, "_deck_mode": "on"}
    decide, omen = decisor(braco), braco != "off"
    res = {"outcome": "timeout", "rounds": ME.MAX_ROUNDS, "damage": 0}
    for rnd in range(1, ME.MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            return {**res, "outcome": "win", "rounds": rnd}
        full = player["vitalidade"] >= player["max_vitalidade"]
        initiator = "heroes" if rnd == 1 and level <= 2 and full else None
        kwargs: dict = {}
        forecast: dict = {}
        if omen:
            forecast = enemy_intent.forecast_round(scene, actors, sides, omen_rng)
            kwargs["pressagios"] = forecast
        decl = decide(player, piles, actors, sides, scene, forecast, {}, alive[0]["id"])
        vit_before = int(player.get("vitalidade", 0) or 0)
        out = orch.run_round(
            scene, actors, sides, state, declarations={"player": decl},
            initiator=initiator, rng=rng, **kwargs,
        )  # fmt: skip
        res["damage"] += max(0, vit_before - max(0, int(player.get("vitalidade", 0) or 0)))
        if _morreu(player, out):
            return {**res, "outcome": "death", "rounds": rnd}
        if out.get("ended"):
            return {**res, "outcome": "win", "rounds": rnd}
        card_piles.begin_round(piles)
    return res


def _resumo(rows: list[tuple]) -> dict:
    dmg = [f["damage"] for *_, f in rows]
    return {
        "conflitos": len(rows),
        "dano_medio": round(statistics.fmean(dmg), 2) if dmg else 0.0,
        "vitoria_pct": round(
            100 * sum(f["outcome"] == "win" for *_, f in rows) / max(1, len(rows)), 1
        ),
        "rodadas_media": round(statistics.fmean(f["rounds"] for *_, f in rows), 2) if rows else 0.0,
    }


def _pareado(arm: list[tuple], ref: list[tuple]) -> dict:
    """Delta por semente (mesmas lutas, pareadas pela ordem): media por semente e quantas caem."""
    by_seed: dict[int, list[float]] = {}
    for (_, seed, fa), (_, seed_r, fr) in zip(arm, ref, strict=True):
        assert seed == seed_r
        by_seed.setdefault(seed, []).append(fa["damage"] - fr["damage"])
    per = {s: statistics.fmean(v) for s, v in sorted(by_seed.items())}
    mean_ref = statistics.fmean(f["damage"] for *_, f in ref) if ref else 0.0
    mean_arm = statistics.fmean(f["damage"] for *_, f in arm) if arm else 0.0
    return {
        "delta_pct": round(100 * (mean_arm - mean_ref) / mean_ref, 1) if mean_ref else 0.0,
        "razao": round(mean_arm / mean_ref, 4) if mean_ref else 0.0,
        "sementes_abaixo": sum(v < 0 for v in per.values()),
        "sementes": len(per),
    }


def run_bracos(seeds, *, known: bool, decks: str, classes=None, **params) -> dict[str, list]:
    p = {**PARAMS_368, **params}
    encs = sim.encounters(p["levels"], p["categories"], p["per_cat"])
    rows: dict[str, list] = {}
    for braco in BRACOS:
        intent = "off" if braco == "off" else "on"
        rows[braco] = []
        with sim.deck_env(), ME._env(RPG_ENEMY_DECKS=decks, RPG_ENEMY_INTENT=intent):
            for cls in classes or A.CLASSES:
                for bid, n, level in encs:
                    deck = sim.full_deck(cls, level)
                    for seed in seeds:
                        f = fight_braco(bid, n, cls, level, seed, deck, braco, known=known)
                        rows[braco].append((cls, seed, f))
        print(
            f"[pressagio] known={known} decks={decks} {braco}: {_resumo(rows[braco])}", flush=True
        )
    return rows


def _bloco_pressagio(rows: dict[str, list]) -> dict:
    out: dict = {b: _resumo(rows[b]) for b in BRACOS}
    for b in BRACOS[1:]:
        out[b]["vs_off"] = _pareado(rows[b], rows["off"])
        if b != "on-cego":
            out[b]["vs_cego"] = _pareado(rows[b], rows["on-cego"])
        out[b]["por_postura"] = {
            cls: _resumo([r for r in rows[b] if r[0] == cls])
            for cls in dict.fromkeys(r[0] for r in rows[b])
        }
    out["delta_faixa_vs_cego_pct"] = out["on-faixa"]["vs_cego"]["delta_pct"]
    out["delta_faixa_vs_off_pct"] = out["on-faixa"]["vs_off"]["delta_pct"]
    out["razao_faixa_cego"] = out["on-faixa"]["vs_cego"]["razao"]
    return out


def cmd_pressagio(
    seeds, *, conhecimentos=("desconhecida", "conhecida"), decks=("off", "on")
) -> dict:
    """R8: 4 bracos x conhecimento x baralho de inimigo; Delta pareado contra off e on-cego."""
    out: dict = {}
    for k in conhecimentos:
        for d in decks:
            rows = run_bracos(seeds, known=(k == "conhecida"), decks=d)
            out.setdefault(k, {})[f"decks_{d}"] = _bloco_pressagio(rows)
    return out


# --------------------------------------------------------------------------
# posturas / emboscada / familias (avaliadores antigos, so importados)
# --------------------------------------------------------------------------
def _seed_range(seeds: list[int]) -> range:
    if seeds != list(range(seeds[0], seeds[-1] + 1)):
        raise ValueError("posturas/emboscada usam faixa contigua de sementes")
    return range(seeds[0], seeds[-1] + 1)


def guarda_r19(posturas: dict) -> dict:
    """R19(a) na leitura absoluta; (b)/(d) ficam com os totais de referencia desta medida."""
    fora, teto = [], []
    for cls, subs in posturas.items():
        total = subs["todas"]["total"]
        if not FAIXA[0] <= total <= FAIXA[1]:
            fora.append(f"{cls}: {total}")
        for sub, v in subs.items():
            if v["padrao"] > TETO_PADRAO and (cls, sub) not in EXCECOES_TETO:
                teto.append(f"{cls}/{sub}: {v['padrao']}")
    arc = posturas.get("Arcanista Cinzento", {}).get("todas", {}).get("total")
    return {
        "totais": {cls: subs["todas"]["total"] for cls, subs in posturas.items()},
        "postura_fora_45_85": fora,
        "padrao_acima_75": teto,
        "arcanista_todas_ge_45": arc is not None and arc >= FAIXA[0],
        "excecoes_teto": sorted(f"{c}/{s}" for c, s in EXCECOES_TETO),
        "ok": not fora and not teto and arc is not None and arc >= FAIXA[0],
    }


def cmd_posturas(seeds: list[int], classes: list[str] | None = None) -> dict:
    """``classes`` (so para teste): recorte de Posturas no formato de ``arena_spec341 --classes``."""
    res = B.posturas(_seed_range(seeds), B._classes_arg(classes))
    return {"posturas": res, "guarda_r19": guarda_r19(res)}


def tem_iniciativa(cls: str, level: int, sub: str) -> bool:
    """D-369-6: o credito da 355 (Carta no ``full_deck``) OU uma ``passiva`` ``buff_iniciativa``
    da propria Postura com ``level_req <= nivel`` (o produto a honra nas preparadas,
    `agents/combat.py:1933`)."""
    if _orig_has_initiative(cls, level, sub):
        return True
    for c in cards.cards_for_class(cls, sub):
        if c.get("classe") != cls or c.get("tipo") != "passiva" or c.get("apex"):
            continue
        if int(c.get("level_req", 1) or 1) > level:
            continue
        if any(e.get("kind") == "buff_iniciativa" for e in fx.normalize(c)):
            return True
    return False


_orig_has_initiative = E.has_initiative_card


def cmd_emboscada(
    seeds: list[int], base_posturas: dict | None = None, classes_sel: list[str] | None = None
) -> dict:
    """R6 emboscada: o fluxo de ``arena_spec355 emboscada`` + a mistura com o credito D-369-6.
    ``base_total`` = a arena SEM emboscada (igual ao ``posturas``); ``emboscada_total`` = o braco
    com ``initiator="enemy"`` na 1a rodada, outro protocolo (os prints ``[posturas]`` deste
    subcomando sao desse braco)."""
    rng = _seed_range(seeds)
    classes = B._classes_arg(classes_sel)
    base = base_posturas or B.posturas(rng, classes)
    orig_run_round = orch.run_round
    orch.run_round = E._ambush_round
    try:
        amb = B.posturas(rng, classes)
    finally:
        orch.run_round = orig_run_round
    mix_355 = E.mix(base, amb)
    E.has_initiative_card = tem_iniciativa
    try:
        mix_369 = E.mix(base, amb)
    finally:
        E.has_initiative_card = _orig_has_initiative
    out: dict = {}
    for cls, subs in mix_355.items():
        out[cls] = {}
        for sub, v in subs.items():
            out[cls][sub] = {**v, "realista_369": mix_369[cls][sub]["realista_com_contrapartida"]}
    return {
        "cenario": "emboscada realista (f_viagem = 1), credito de passiva D-369-6",
        "posturas": out,
    }


def _celula(fam, ids, level, seeds, per_family, cat_of) -> dict:
    row: dict = {}
    for mode in ("off", "on"):
        c = {"fights": 0, "win": 0, "death": 0, "timeout": 0, "rounds": 0}
        for bid in F.pick(ids, per_family):
            n = A.group_size(cat_of[bid] if cat_of[bid] in A.CATEGORIES else "padrao", level)
            for cls in A.CLASSES:
                for seed in seeds:
                    with ME._env(RPG_ENEMY_DECKS=mode):
                        outcome, rounds = F.fight(bid, n, cls, level, seed, mode)
                    c["fights"] += 1
                    c[outcome] += 1
                    c["rounds"] += rounds
        row[mode] = {
            "win": round(c["win"] / c["fights"], 3),
            "death": round(c["death"] / c["fights"], 3),
            "avg_rounds": round(c["rounds"] / c["fights"], 2),
            "fights": c["fights"],
        }
    row["delta_pp"] = round((row["on"]["win"] - row["off"]["win"]) * 100, 1)
    return row


def classifica_familia(row: dict) -> str:
    """D-369-7: ``alvo`` = `off` em 45-85 % e (`on` fora OU |Delta| > 10 pp); ``fora_de_escopo`` =
    `off` ja fora da faixa; senao ``ok``."""
    off, on = row["off"]["win"], row["on"]["win"]
    if not FAIXA[0] <= off <= FAIXA[1]:
        return "fora_de_escopo"
    if not FAIXA[0] <= on <= FAIXA[1] or abs(row["delta_pp"]) > DELTA_FAMILIA_PP:
        return "alvo"
    return "ok"


def cmd_familias(seeds: list[int], *, per_family: int = 5, levels=(3, 5), only=None) -> dict:
    fams = F.families()
    cat_of = {b: F.normalize_categoria(e) for b, e in F.load_bestiary().items()}
    cells: dict = {}
    for fam, ids in fams.items():
        if not ids or (only and fam not in only):
            continue
        for level in levels:
            row = _celula(fam, ids, level, seeds, per_family, cat_of)
            row["classe_d369_7"] = classifica_familia(row)
            cells[f"{fam}|L{level}"] = row
            print(f"[familias] {fam}|L{level}: {row}", flush=True)
    return {
        "per_family": per_family,
        "cells": cells,
        "celulas_alvo": sorted(k for k, v in cells.items() if v["classe_d369_7"] == "alvo"),
    }


# --------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for name in ("base", "uso", "duracao", "pressagio", "posturas", "emboscada", "familias"):
        p = sp.add_parser(name)
        p.add_argument("--seeds", default="0-19")
        p.add_argument("--out", default="")
        if name == "uso":
            p.add_argument("--ids", nargs="*", default=None)
        if name == "pressagio":
            p.add_argument("--conhecimento", default="desconhecida,conhecida")
            p.add_argument("--decks", default="off,on")
        if name == "emboscada":
            p.add_argument("--base", default="", help="JSON com a chave `posturas` ja medida")
        if name == "familias":
            p.add_argument("--only", default="")
            p.add_argument("--levels", default="3,5")
    return ap


def _dispatch(args, seeds: list[int]) -> dict:
    if args.cmd == "base":
        return cmd_base(seeds)
    if args.cmd == "uso":
        return cmd_uso(seeds, ids=args.ids)
    if args.cmd == "duracao":
        return cmd_duracao(seeds)
    if args.cmd == "pressagio":
        return cmd_pressagio(
            seeds, conhecimentos=args.conhecimento.split(","), decks=args.decks.split(",")
        )
    if args.cmd == "posturas":
        return cmd_posturas(seeds)
    if args.cmd == "emboscada":
        base = None
        if args.base:
            with open(args.base, encoding="utf-8") as fh:
                base = json.load(fh)["posturas"]["posturas"]
        return cmd_emboscada(seeds, base)
    return cmd_familias(
        seeds,
        only=[f for f in args.only.split(",") if f] or None,
        levels=tuple(int(x) for x in args.levels.split(",")),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    seeds = parse_seeds(args.seeds)
    t0 = time.time()
    data = _dispatch(args, seeds)
    data["meta"] = {
        "spec": "SPEC-369",
        "seeds": [seeds[0], seeds[-1]],
        "elapsed_s": round(time.time() - t0, 1),
    }
    if args.out:
        write_section(args.out, args.cmd, data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
