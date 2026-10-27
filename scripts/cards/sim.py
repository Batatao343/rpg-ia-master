"""SPEC-336 R4: simulação de arena de um lote de Cartas (offline, MockLLM, seeded).

    bash scripts/dev/py.sh scripts/cards/sim.py --lote data/cards/_rascunhos/<lote>.json \
        [--levels 1,3,5] [--per-cat 3] [--seeds 3] [--categories padrao,elite] [--json]

Para cada Carta do lote: monta o baralho COMPLETO da Postura (básicas + Acervo até o
nível), joga ``N`` conflitos de arena determinísticos COM e SEM a Carta (mesmas
sementes) e reporta taxa de uso quando na mão, delta de vitória (pp) e dano/proteção
por Fôlego. Marca ``em_branco`` (uso < 5 %) e ``dominante`` (uso > 60 % ou delta > +8 pp).

O bot é o de baralho completo (``full_deck_decl``): cura quando < 50 % de Vitalidade,
defesa quando < 75 %, depois os golpes de maior dano, enquanto houver Fôlego (sem
tomar emprestado no Pacto). Reaproveita a arena da SPEC-285 e a do baralho (SPEC-328).
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import logging
import os
import random
import sys

os.environ.setdefault("RPG_FORCE_MOCK", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

_spec = importlib.util.spec_from_file_location(
    "arena285", os.path.join(ROOT, "docs", "spec285", "arena_lethality.py")
)
A = importlib.util.module_from_spec(_spec)
# A arena da 285 faz `logging.disable(CRITICAL)` global ao ser importada; isso
# silenciaria o log do processo inteiro (e dos testes seguintes). Restaura.
_prev_disable = logging.root.manager.disable
_spec.loader.exec_module(A)  # type: ignore[union-attr]
logging.disable(_prev_disable)

from services import card_effects as fx  # noqa: E402
from services import card_piles, cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import conflict_turn as ct  # noqa: E402

MAX_ROUNDS = 20
LIMIAR_BRANCA = 0.05
LIMIAR_DOMINANTE_USO = 0.60
LIMIAR_DOMINANTE_DELTA_PP = 8.0
AMOSTRA_MINIMA_MAO = 5  # menos que isto: "amostra insuficiente", sem bandeira
MIN_LUTAS_DELTA = 40  # abaixo disto o delta de vitória é ruído (1 luta = 2,5 pp ou mais)
SEM_BANDEIRA = {"amostra_insuficiente", "uso_nao_medido"}

_DEFENSE_KINDS = {"protecao", "vigilia", "buff_defesa"}


# --------------------------------------------------------------------------
# Catálogo temporário (injeta o lote sem tocar em data/)
# --------------------------------------------------------------------------
@contextlib.contextmanager
def injected(batch: list[dict]):
    base = cards._load_cards()
    saved = dict(base)
    try:
        for c in batch:
            base[c["id"]] = fx.materialize(c)
        yield
    finally:
        base.clear()
        base.update(saved)


# --------------------------------------------------------------------------
# Baralho completo da Postura
# --------------------------------------------------------------------------
def full_deck(class_name: str, level: int, subclass: str = "", extra: list[str] | None = None):
    """Básicas + Cartas do Acervo da Postura (``level_req`` ≤ nível), determinístico.
    ``extra`` entra por último e garante vaga (substitui a mais fraca se cheio)."""
    basics = cards.basicas_for_class(class_name)
    deck: list[str] = []
    deck += (basics["golpe"][:1] or []) * 4
    deck += (basics["guarda"][:1] or []) * 4
    deck += basics["assinatura"][:1]
    pool = [
        c
        for c in cards.cards_for_class(class_name, subclass)
        if c.get("tipo") in cards._DECK_TIPOS
        and not c.get("apex")
        and int(c.get("level_req", 1) or 1) <= level
        and c["id"] not in (extra or [])
    ]
    pool.sort(key=lambda c: (-int(c.get("tier", 1) or 1), c["id"]))
    for c in pool:
        copies = 2 if c.get("patamar") in cards._COMMON_PATAMARES else 1
        for _ in range(copies):
            if len(deck) < cards.DECK_MAX - len(extra or []):
                deck.append(c["id"])
    for cid in extra or []:
        if len(deck) < cards.DECK_MAX:
            deck.append(cid)
        else:
            weakest = min(
                (i for i, d in enumerate(deck) if d not in basics["golpe"] + basics["guarda"]),
                key=lambda i: int((cards.get_card(deck[i]) or {}).get("tier", 1) or 1),
                default=len(deck) - 1,
            )
            deck[weakest] = cid
    while len(deck) < cards.DECK_MIN and deck:
        deck.append(deck[0])
    return deck


def _kind(cid: str) -> str:
    return A._card_kind(cid)


def full_deck_decl(player: dict, piles: dict, target_id: str, seen: dict | None = None):
    """Bot de baralho completo. ``seen`` (opcional) acumula ``{id: [na_mao, jogada]}``."""
    hand = list(piles["mao"])
    steps: list[ct.TurnStep] = []
    vit, mx = int(player.get("vitalidade", 0) or 0), int(player.get("max_vitalidade", 1) or 1)
    played_turn: set[str] = set()
    if seen is not None:
        for cid in hand:  # uma oportunidade por cópia na mão
            seen.setdefault(cid, [0, 0])[0] += 1

    def usable(cid: str) -> bool:
        card = cards.get_card(cid) or {}
        if card.get("tipo") in ("reacao", "passiva", "virtude") or card.get("injogavel"):
            return False
        freq = str(card.get("frequencia", "livre"))
        counter = cards.FREQ_COUNTER.get(freq)
        if freq == "turno":
            return cid not in played_turn
        used = int(((player.get("card_usage") or {}).get(cid) or {}).get(counter or "", 0) or 0)
        return not counter or used < 1

    def try_add(step: ct.TurnStep) -> bool:
        plan = card_piles.plan_plays(piles, player, [*steps, step])
        if plan["ok"] and plan["emprestado"] == 0:
            steps.append(step)
            return True
        return False

    def play(cid: str, target: str) -> bool:
        if (
            cid in hand
            and usable(cid)
            and try_add(ct.TurnStep(kind="card", card_id=cid, target_id=target))
        ):
            played_turn.add(cid)
            hand.remove(cid)
            if seen is not None:
                seen.setdefault(cid, [0, 0])[1] += 1
            return True
        return False

    if vit * 2 < mx:
        for cid in list(hand):
            if _kind(cid) == "cura" and play(cid, "player"):
                break
    if vit * 4 < mx * 3:
        for cid in list(hand):
            if _kind(cid) in _DEFENSE_KINDS and play(cid, "player"):
                break
    attacks = sorted(
        (c for c in hand if _kind(c) in ct._ATTACK_EFFECTS),
        key=lambda c: (-A._card_damage(c), c),
    )
    for cid in attacks:
        play(cid, target_id)
    for cid in list(hand):  # sobras de suporte/controle com Fôlego restante
        if _kind(cid) in ct._SUPPORT_EFFECTS and _kind(cid) != "cura":
            play(cid, "player")
    if not steps:
        steps.append(ct.TurnStep(kind="attack", target_id=target_id))
    return ct.TurnDeclaration(actor_id="player", jogadas=steps)


# --------------------------------------------------------------------------
# Luta
# --------------------------------------------------------------------------
@contextlib.contextmanager
def deck_env():
    """``RPG_CARD_DECK=on`` só durante a luta (não vaza para o resto do processo)."""
    old = os.environ.get("RPG_CARD_DECK")
    os.environ["RPG_CARD_DECK"] = "on"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("RPG_CARD_DECK", None)
        else:
            os.environ["RPG_CARD_DECK"] = old


def fight(bid, n, class_name, level, seed, deck, tag, seen=None):
    with deck_env():
        return _fight(bid, n, class_name, level, seed, deck, tag, seen)


def _fight(bid, n, class_name, level, seed, deck, tag, seen=None):
    """Uma luta de arena com o baralho dado. Devolve ``("win"|"death"|"timeout", rodadas)``."""
    random.seed(f"{tag}|{level}|{class_name}|{bid}|{n}|{seed}")
    player = A.hero(class_name, level)
    player["deck"] = list(deck)
    player["prepared_cards"] = list(
        dict.fromkeys(list(deck) + (player.get("prepared_cards") or []))
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
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            return "win", rnd
        initiator = (
            "heroes"
            if rnd == 1 and level <= 2 and player["vitalidade"] >= player["max_vitalidade"]
            else None
        )
        decl = full_deck_decl(player, piles, alive[0]["id"], seen)
        out = orch.run_round(
            scene, actors, sides, state, declarations={"player": decl}, initiator=initiator, rng=rng
        )
        if (
            player.get("dead")
            or player.get("estado_terminal")
            or out.get("player_dead")
            or int(player.get("vitalidade", 0) or 0) <= 0
        ):
            return "death", rnd
        if out.get("ended"):
            return "win", rnd
        card_piles.begin_round(piles)
    return "timeout", MAX_ROUNDS


def pick(ids: list[str], k: int) -> list[str]:
    if len(ids) <= k:
        return ids
    step = len(ids) / k
    return [ids[int(i * step)] for i in range(k)]


def encounters(levels, categories, per_cat) -> list[tuple]:
    pool = A.creatures_by_category()
    return [
        (bid, A.group_size(cat, level), level)
        for level in levels
        for cat in categories
        for bid in pick(pool[cat], per_cat)
    ]


def batch_fights(class_name, deck, tag, encs, seeds, seen=None):
    wins = fights = 0
    for bid, n, level in encs:
        for seed in seeds:
            outcome, _ = fight(bid, n, class_name, level, seed, deck, tag, seen)
            fights += 1
            wins += outcome == "win"
    return wins, fights


# --------------------------------------------------------------------------
# Relatório por Carta
# --------------------------------------------------------------------------
def per_folego(card: dict) -> dict:
    """Dano e proteção médios por Fôlego (estático, dos números base da Carta)."""
    folego = max(1, fx.custo_folego(card))
    dano = prot = 0.0
    for e in fx.normalize(card):
        if fx.gatilho(e) != fx.GATILHO_PADRAO:
            continue
        kind = str(e.get("kind"))
        amt = float(fx.base_value(e)) if e.get("formula") is None else fx._formula_avg(e["formula"])
        if kind in ("dano", "contra_ataque"):
            dano += amt
        elif kind == "dot":
            dano += amt * max(1, int(e.get("duracao", e.get("duration", 1)) or 1))
        elif kind == "sangria":
            dano += amt * (amt + 1) / 2
        elif kind in ("protecao", "vigilia"):
            prot += amt
    return {
        "dano_por_folego": round(dano / folego, 2),
        "protecao_por_folego": round(prot / folego, 2),
    }


def simulate_batch(batch: list[dict], levels, categories, per_cat, seeds) -> dict:
    encs = encounters(levels, categories, per_cat)
    report: dict[str, dict] = {}
    with injected(batch):
        for card in batch:
            cid = card["id"]
            cls = card.get("classe")
            level = max(int(card.get("level_req", 1) or 1), 1)
            subclass = str(card.get("subclasse") or "")
            my_levels = [lv for lv in levels if lv >= level] or [max(levels)]
            my_encs = [e for e in encs if e[2] in my_levels]
            sem = full_deck(cls, max(my_levels), subclass)
            com = full_deck(
                cls,
                max(my_levels),
                subclass,
                extra=[cid, cid][: 2 if card.get("patamar") in cards._COMMON_PATAMARES else 1],
            )
            seen: dict = {}
            w0, f0 = batch_fights(cls, sem, "sem", my_encs, seeds)
            w1, f1 = batch_fights(cls, com, "com", my_encs, seeds, seen)
            na_mao, jogada = seen.get(cid, [0, 0])
            uso = (jogada / na_mao) if na_mao else 0.0
            delta = round(((w1 / f1) - (w0 / f0)) * 100, 1) if f0 and f1 else 0.0
            flags = []
            jogavel = card.get("tipo") not in ("reacao", "passiva", "virtude") and (
                _kind(cid) in ct._ATTACK_EFFECTS or _kind(cid) in ct._SUPPORT_EFFECTS
            )
            if not jogavel:
                flags.append("uso_nao_medido")  # reação/passiva: o motor joga, o bot não declara
            elif na_mao < AMOSTRA_MINIMA_MAO:
                flags.append("amostra_insuficiente")
            else:
                if uso < LIMIAR_BRANCA:
                    flags.append("em_branco")
                if uso > LIMIAR_DOMINANTE_USO:
                    flags.append("dominante")
            if (
                f1 >= MIN_LUTAS_DELTA
                and delta > LIMIAR_DOMINANTE_DELTA_PP
                and "dominante" not in flags
            ):
                flags.append("dominante")
            report[cid] = {
                "classe": cls,
                "vezes_na_mao": na_mao,
                "vezes_jogada": jogada,
                "taxa_uso": round(uso, 3),
                "vitoria_sem": round(w0 / f0, 3) if f0 else 0.0,
                "vitoria_com": round(w1 / f1, 3) if f1 else 0.0,
                "delta_pp": delta,
                "lutas_por_braco": f1,
                **per_folego(card),
                "bandeiras": flags,
            }
    return report


# Protocolo de lote (fixado pelo coordenador/SPEC-336, igual para todos os lotes): cada Carta
# ISOLADA (as outras do lote saem do catálogo na sua rodada), ao nível de entrada
# (`level_req`), encontro padrão, 20 sementes. É só um preset dos parâmetros acima: métrica,
# limiares e fórmulas são os mesmos de `simulate_batch`.
PROTOCOLO_LOTE = {"categories": ["padrao"], "per_cat": 4, "seeds": 20}


def simulate_protocolo_lote(batch: list[dict]) -> dict:
    ids = {c["id"] for c in batch}
    report: dict[str, dict] = {}
    base = cards._load_cards()
    for card in batch:
        saved = {i: base.pop(i) for i in ids - {card["id"]} if i in base}
        try:
            level = max(int(card.get("level_req", 1) or 1), 1)
            report.update(
                simulate_batch(
                    [card],
                    [level],
                    PROTOCOLO_LOTE["categories"],
                    PROTOCOLO_LOTE["per_cat"],
                    list(range(PROTOCOLO_LOTE["seeds"])),
                )
            )
        finally:
            base.update(saved)
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lote", required=True)
    ap.add_argument(
        "--protocolo",
        choices=["lote"],
        help="preset: cada Carta isolada, ao level_req, 20 sementes, encontro padrão",
    )
    ap.add_argument("--out", help="grava o relatório JSON neste arquivo")
    ap.add_argument("--levels", default="1,3,5")
    ap.add_argument("--categories", default="padrao")
    ap.add_argument("--per-cat", type=int, default=4)
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    from services import card_lint

    batch = card_lint.load_batch(args.lote)
    if args.protocolo == "lote":
        report = simulate_protocolo_lote(batch)
    else:
        report = simulate_batch(
            batch,
            [int(x) for x in args.levels.split(",")],
            args.categories.split(","),
            args.per_cat,
            list(range(args.seeds)),
        )
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
            f.write("\n")
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        for cid, r in report.items():
            print(
                f"{cid}: uso {r['taxa_uso']:.0%} ({r['vezes_jogada']}/{r['vezes_na_mao']}) "
                f"delta {r['delta_pp']:+.1f}pp dano/F {r['dano_por_folego']} prot/F "
                f"{r['protecao_por_folego']} {','.join(r['bandeiras'])}"
            )
    return 1 if any(set(r["bandeiras"]) - SEM_BANDEIRA for r in report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
