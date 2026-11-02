"""SPEC-362 §6 item 3: run_round real com cada Carta alterada; o log e o texto trazem o numero novo."""

from __future__ import annotations

import os
import random
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "cards"))

import sim  # noqa: E402

from services import card_effects as fx  # noqa: E402
from services import card_piles, cards  # noqa: E402
from services import conflict_orchestrator as orch  # noqa: E402
from services import conflict_scene as cs  # noqa: E402
from services import conflict_turn as ct  # noqa: E402

# id -> (nivel do heroi, numero novo que deve aparecer no texto)
ALTERADAS = {"arc1_imp_truque": (5, "3", "player"), "arc1_cal_pulso_medido": (3, "4", "enemy")}


def _round(cid: str, level: int, alvo: str) -> tuple[dict, dict]:
    player = sim.A.hero("Arcanista Cinzento", level)
    deck = sim.full_deck("Arcanista Cinzento", level, "") + [cid]
    player["deck"] = sorted(deck)
    player["prepared_cards"] = list(
        dict.fromkeys(player["deck"] + (player.get("prepared_cards") or []))
    )
    bid = sim.A.creatures_by_category()["padrao"][0]
    enemies = sim.A._instances(sim.A.template_by_id(bid, encounter_level=4), 1)
    actors = {"player": player, **{e["id"]: e for e in enemies}}
    sides = {"hero": ["player"], "ally": [], "enemy": [e["id"] for e in enemies]}
    scene = cs.new_scene()
    for aid in actors:
        cs.place(scene, aid)
    cs.freeze(scene)
    piles = card_piles.start_piles(player, 1)
    piles["mao"] = [cid]
    state = {"player": player, "_piles": piles, "_deck_mode": "on"}
    decl = ct.TurnDeclaration(
        actor_id="player",
        jogadas=[
            ct.TurnStep(
                kind="card",
                card_id=cid,
                target_id="player" if alvo == "player" else enemies[0]["id"],
            )
        ],
    )
    with sim.deck_env():
        out = orch.run_round(
            scene, actors, sides, state, declarations={"player": decl}, rng=random.Random(1)
        )
    return out, piles


@pytest.mark.parametrize("cid", sorted(ALTERADAS))
def test_carta_alterada_joga_pelo_caminho_real(cid):
    level, numero, alvo = ALTERADAS[cid]
    out, piles = _round(cid, level, alvo)
    texto = fx.render_card_text(cards.get_card(cid))
    assert numero in texto, (cid, texto)
    # a Carta foi jogada pelo caminho real: saiu da mao e foi para o descarte (ou exaurida)
    assert cid not in piles["mao"], out.get("logs")
    assert cid in piles["descarte"] + piles["exaurida"], (piles, out.get("logs"))
    assert out["logs"]
