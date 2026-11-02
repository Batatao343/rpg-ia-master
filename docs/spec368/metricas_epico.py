"""SPEC-368 R9/R10 - metricas de aceite do epico de Cartas (offline, MockLLM, seeded, sem LLM).

Reproduzir:
    bash scripts/dev/py.sh docs/spec368/metricas_epico.py [--seeds 0-19] [--levels 1,3,5] \
        [--categories padrao,elite] [--per-cat 3] [--skip-r10] [--out docs/spec368/metricas-0-19.json]

Ferramenta NOVA sobre a arena existente: importa `scripts/cards/sim.py` (baralho completo, bot e
`deck_env`) sem altera-lo; nao toca avaliadores, orcamento, golden nem arenas antigas.

R9 (cartas `on`, mesmo bot e mesmos baralhos do `sim.py`; por Postura e total):
  - Cartas jogadas por rodada (media e p50) - rodadas em que o jogador agiu;
  - % de rodadas com >= 3 escolhas validas (Cartas distintas na mao jogaveis AGORA, sem Pacto);
    `pct_rodadas_ge3_com_basico` soma o ataque basico (sempre valido) como mais uma escolha;
  - % de Cartas da mao usadas (jogadas / oportunidades) e as Cartas com uso > 60 % (n >= 5);
  - p95 de rodadas por conflito (nearest-rank; timeout conta MAX_ROUNDS).
R10 (SPEC-329, `RPG_ENEMY_INTENT` off x on, mesmas sementes, baralhos de inimigo off): dano
  recebido pelo heroi por conflito. No braco `on` o bot le o Pressagio publico e, se algum
  inimigo vai atacar o heroi, abre a rodada com uma Carta de defesa (quando cabe no Folego).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import math
import os
import random
import statistics
import sys
import time

os.environ.setdefault("RPG_FORCE_MOCK", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    "cards_sim_368", os.path.join(ROOT, "scripts", "cards", "sim.py")
)
sim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sim)  # type: ignore[union-attr]

A = sim.A
from services import card_piles, cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import conflict_turn as ct  # noqa: E402
from services import enemy_intent  # noqa: E402

MAX_ROUNDS = sim.MAX_ROUNDS
USO_ALTO = 0.60
AMOSTRA_USO = 5
_NOT_PLAYABLE = ("reacao", "passiva", "virtude")


@contextlib.contextmanager
def _env(**values: str):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return float(ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)])


def _usable(player: dict, cid: str) -> bool:
    card = cards.get_card(cid) or {}
    if card.get("tipo") in _NOT_PLAYABLE or card.get("injogavel"):
        return False
    freq = str(card.get("frequencia", "livre"))
    counter = cards.FREQ_COUNTER.get(freq)
    if freq == "turno" or not counter:
        return True
    used = int(((player.get("card_usage") or {}).get(cid) or {}).get(counter, 0) or 0)
    return used < 1


def valid_choices(player: dict, piles: dict, target_id: str) -> int:
    """Cartas DISTINTAS da mao jogaveis agora (paga so com Folego proprio)."""
    n = 0
    for cid in dict.fromkeys(piles["mao"]):
        if not _usable(player, cid):
            continue
        tgt = "player" if sim._kind(cid) in sim._DEFENSE_KINDS else target_id
        plan = card_piles.plan_plays(
            piles, player, [ct.TurnStep(kind="card", card_id=cid, target_id=tgt)]
        )
        if plan["ok"] and plan["emprestado"] == 0:
            n += 1
    return n


def _heed_omen(player: dict, piles: dict, decl: ct.TurnDeclaration, forecast: dict, seen: dict):
    """R10: ha ataque previsto contra o heroi -> abre com uma Carta de defesa que caiba."""
    threatened = any(
        str(i.get("tipo", "")).startswith("ataque") and i.get("alvo_id") == "player"
        for intents in forecast.values()
        for i in intents
    )
    played = {s.card_id for s in decl.jogadas if s.kind == "card"}
    if not threatened or any(sim._kind(c) in sim._DEFENSE_KINDS for c in played):
        return decl
    for cid in piles["mao"]:
        if cid in played or not _usable(player, cid) or sim._kind(cid) not in sim._DEFENSE_KINDS:
            continue
        step = ct.TurnStep(kind="card", card_id=cid, target_id="player")
        plan = card_piles.plan_plays(piles, player, [step, *decl.jogadas])
        if plan["ok"] and plan["emprestado"] == 0:
            seen.setdefault(cid, [0, 0])[1] += 1
            return ct.TurnDeclaration(actor_id="player", jogadas=[step, *decl.jogadas])
    return decl


def fight(bid, n, class_name, level, seed, deck, tag, *, omen: bool, seen: dict) -> dict:
    """Uma luta de arena; devolve rodadas, desfecho, dano recebido e metricas por rodada."""
    random.seed(f"{tag}|{level}|{class_name}|{bid}|{n}|{seed}")
    player = A.hero(class_name, level)
    player["deck"] = sorted(deck)
    player["prepared_cards"] = list(
        dict.fromkeys(list(player["deck"]) + (player.get("prepared_cards") or []))
    )
    enemies = A._instances(
        A.template_by_id(bid, encounter_level=A.DANGER_BY_LEVEL.get(level, 4)), n
    )
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    rng = random.Random(seed)
    piles = card_piles.start_piles(player, seed)
    state = {"player": player, "_piles": piles, "_deck_mode": "on"}
    res = {"outcome": "timeout", "rounds": MAX_ROUNDS, "damage": 0, "per_round": []}
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            res.update(outcome="win", rounds=rnd)
            return res
        initiator = (
            "heroes"
            if rnd == 1 and level <= 2 and player["vitalidade"] >= player["max_vitalidade"]
            else None
        )
        target = alive[0]["id"]
        choices = valid_choices(player, piles, target)
        decl = sim.full_deck_decl(player, piles, target, seen)
        kwargs = {}
        if omen:
            forecast = enemy_intent.forecast_round(scene, actors, sides, rng)
            decl = _heed_omen(player, piles, decl, forecast, seen)
            kwargs["pressagios"] = forecast
        played = sum(1 for s in decl.jogadas if s.kind == "card")
        vit_before = int(player.get("vitalidade", 0) or 0)
        out = orch.run_round(
            scene,
            actors,
            sides,
            state,
            declarations={"player": decl},
            initiator=initiator,
            rng=rng,
            **kwargs,
        )
        res["per_round"].append((played, choices))
        res["damage"] += max(0, vit_before - max(0, int(player.get("vitalidade", 0) or 0)))
        if (
            player.get("dead")
            or player.get("estado_terminal")
            or out.get("player_dead")
            or int(player.get("vitalidade", 0) or 0) <= 0
        ):
            res.update(outcome="death", rounds=rnd)
            return res
        if out.get("ended"):
            res.update(outcome="win", rounds=rnd)
            return res
        card_piles.begin_round(piles)
    return res


def _agg_r9(fights: list[dict], seen: dict) -> dict:
    rounds = [f["rounds"] for f in fights]
    per_round = [pr for f in fights for pr in f["per_round"]]
    played = [p for p, _ in per_round]
    ge3 = sum(1 for _, c in per_round if c >= 3)
    ge3_basic = sum(1 for _, c in per_round if c + 1 >= 3)
    hand_total = sum(v[0] for v in seen.values())
    played_total = sum(v[1] for v in seen.values())
    high = {
        cid: round(v[1] / v[0], 3)
        for cid, v in sorted(seen.items())
        if v[0] >= AMOSTRA_USO and v[1] / v[0] > USO_ALTO
    }
    n = max(1, len(per_round))
    wins = sum(f["outcome"] == "win" for f in fights)
    timeouts = sum(f["outcome"] == "timeout" for f in fights)
    return {
        "conflitos": len(fights),
        "rodadas": len(per_round),
        "cartas_por_rodada_media": round(statistics.fmean(played), 3) if played else 0.0,
        "cartas_por_rodada_p50": float(statistics.median(played)) if played else 0.0,
        "pct_rodadas_ge3_escolhas": round(100 * ge3 / n, 1),
        "pct_rodadas_ge3_com_basico": round(100 * ge3_basic / n, 1),
        "uso_cartas_da_mao_pct": round(100 * played_total / max(1, hand_total), 1),
        "cartas_com_uso_acima_60": high,
        "p95_rodadas_conflito": p95(rounds),
        "vitoria_pct": round(100 * wins / max(1, len(fights)), 1),
        "timeout_pct": round(100 * timeouts / max(1, len(fights)), 1),
    }


def _merge(a: dict, b: dict) -> dict:
    for cid, (h, p) in b.items():
        cur = a.setdefault(cid, [0, 0])
        cur[0] += h
        cur[1] += p
    return a


def _parse_seeds(raw: str) -> list[int]:
    if "-" in raw:
        lo, hi = raw.split("-", 1)
        return list(range(int(lo), int(hi) + 1))
    return [int(x) for x in raw.split(",")]


def _agg_r10(rows: dict) -> dict:
    def summarize(items: list[tuple[str, dict]]) -> dict:
        dmg = [f["damage"] for _, f in items]
        wins = sum(f["outcome"] == "win" for _, f in items)
        return {
            "conflitos": len(items),
            "dano_medio": round(statistics.fmean(dmg), 2) if dmg else 0.0,
            "vitoria_pct": round(100 * wins / max(1, len(items)), 1),
        }

    out: dict = {"total": {}, "por_postura": {}}
    for arm in ("off", "on"):
        out["total"][arm] = summarize(rows[arm])
        for cls in sorted({c for c, _ in rows[arm]}):
            out["por_postura"].setdefault(cls, {})[arm] = summarize(
                [r for r in rows[arm] if r[0] == cls]
            )
    off, on = out["total"]["off"]["dano_medio"], out["total"]["on"]["dano_medio"]
    out["total"]["delta_dano"] = round(on - off, 2)
    out["total"]["delta_dano_pct"] = round(100 * (on - off) / off, 1) if off else 0.0
    out["total"]["dano_cai"] = on < off
    return out


def run(seeds, levels, categories, per_cat, *, r10: bool, classes=None) -> dict:
    classes = list(classes or A.CLASSES)
    encs = sim.encounters(levels, categories, per_cat)
    r9_by_class: dict[str, dict] = {}
    all_fights: list[dict] = []
    all_seen: dict = {}
    r10_rows: dict[str, list] = {"off": [], "on": []}
    with sim.deck_env(), _env(RPG_ENEMY_DECKS="off", RPG_ENEMY_INTENT="off"):
        for cls in classes:
            fights: list[dict] = []
            seen: dict = {}
            for bid, n, level in encs:
                deck = sim.full_deck(cls, level)
                for seed in seeds:
                    fights.append(
                        fight(bid, n, cls, level, seed, deck, "m368", omen=False, seen=seen)
                    )
            r9_by_class[cls] = _agg_r9(fights, seen)
            all_fights += fights
            _merge(all_seen, seen)
            r10_rows["off"] += [(cls, f) for f in fights]
    result: dict = {"r9": {"por_postura": r9_by_class, "total": _agg_r9(all_fights, all_seen)}}
    if r10:
        with sim.deck_env(), _env(RPG_ENEMY_DECKS="off", RPG_ENEMY_INTENT="on"):
            for cls in classes:
                for bid, n, level in encs:
                    deck = sim.full_deck(cls, level)
                    for seed in seeds:
                        f = fight(bid, n, cls, level, seed, deck, "m368", omen=True, seen={})
                        r10_rows["on"].append((cls, f))
        result["r10"] = _agg_r10(r10_rows)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-19")
    ap.add_argument("--levels", default="1,3,5")
    ap.add_argument("--categories", default="padrao,elite")
    ap.add_argument("--per-cat", type=int, default=3)
    ap.add_argument("--classes", default="")
    ap.add_argument("--skip-r10", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)
    seeds = _parse_seeds(args.seeds)
    t0 = time.time()
    result = run(
        seeds,
        [int(x) for x in args.levels.split(",")],
        args.categories.split(","),
        args.per_cat,
        r10=not args.skip_r10,
        classes=[c for c in args.classes.split(",") if c] or None,
    )
    result["meta"] = {
        "spec": "SPEC-368",
        "seeds": [seeds[0], seeds[-1]],
        "levels": args.levels,
        "categories": args.categories,
        "per_cat": args.per_cat,
        "bot": "scripts/cards/sim.py full_deck_decl (+ leitura do Pressagio no braco R10 on)",
        "elapsed_s": round(time.time() - t0, 1),
    }
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
