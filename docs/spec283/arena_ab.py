"""SPEC-283 arena A/B (reproduce: bash scripts/dev/py.sh docs/spec283/arena_ab.py 30): player death rate
with the SPEC-283 selector OFF (before) vs ON (after). Pure engine, offline, seeded."""

import json
import os
import random
import sys

os.environ["RPG_FORCE_MOCK"] = "1"
sys.path.insert(0, os.getcwd())

from agents import combat as cbt  # noqa: E402
from agents.bestiary import load_bestiary, template_by_id  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import conflict_turn as ct  # noqa: E402

SUPPORT = {
    "bst_furia_final",
    "bst_postura_muralha",
    "bst_noite_skallgard",
    "bst_osso_costa",
    "bst_poeira_pradaria",
    "bst_coro_colmeia",
    "bst_carregar_ruina",
    "bst_roubar_calor",
}
SEEDS = range(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
MAX_ROUNDS = 20


def creatures():
    out = []
    for bid, entry in load_bestiary().items():
        cards = {c.get("id") if isinstance(c, dict) else c for c in entry.get("cartas") or []}
        if cards & SUPPORT:
            out.append(bid)
    return sorted(out)


def fight(bid, seed):
    player = orch.ensure_combat_sheet(
        {
            "id": "player",
            "name": "Ilsa",
            "is_player": True,
            "class_name": "Devoto do Abismo",
            "level": 3,
            "virtudes": {"forca": 4, "agilidade": 3, "corpo": 4, "mente": 1, "carisma": 1},
            "entropy": 10,
            "max_entropy": 10,
            "abyss_charge": 0,
        },
        is_player=True,
    )
    nxt = {}
    enemies = cbt._instances(template_by_id(bid), 2, nxt)  # par: permite suporte a aliado
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    rng = random.Random(seed)
    support_uses = 0
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [e for e in enemies if orch._can_act(e)]
        if not alive:
            return "win", rnd, support_uses
        decl = ct.TurnDeclaration(
            actor_id="player", acao=ct.TurnStep(kind="attack", target_id=alive[0]["id"])
        )
        out = orch.run_round(
            scene, actors, sides, {"player": player}, declarations={"player": decl}, rng=rng
        )
        support_uses += len(out.get("enemy_support_cards") or [])
        if (
            player.get("dead")
            or player.get("estado_terminal")
            or out.get("player_dead")
            or (int(player.get("vitalidade", 0) or 0) <= 0)
        ):
            return "death", rnd, support_uses
        if out.get("ended"):
            return "win", rnd, support_uses
    return "timeout", MAX_ROUNDS, support_uses


def run(mode):
    original = orch._enemy_support_card
    if mode == "before":
        orch._enemy_support_card = lambda *a, **k: None
    try:
        res = {"death": 0, "win": 0, "timeout": 0, "rounds": 0, "support_uses": 0, "fights": 0}
        for bid in creatures():
            for seed in SEEDS:
                outcome, rounds, uses = fight(bid, seed)
                res[outcome] += 1
                res["rounds"] += rounds
                res["support_uses"] += uses
                res["fights"] += 1
    finally:
        orch._enemy_support_card = original
    res["death_rate"] = round(res["death"] / res["fights"], 3)
    res["avg_rounds"] = round(res["rounds"] / res["fights"], 2)
    return res


if __name__ == "__main__":
    print(
        json.dumps({"creatures": len(creatures()), "before": run("before"), "after": run("after")})
    )
