"""SPEC-377 item 3 — quem e alvo de Carta ("vivo"/"lado") em card_effects x conflict_turn."""

from __future__ import annotations

from services import card_effects as fx
from services import conflict_orchestrator as orch
from services import conflict_turn as ct


def _ctx(**over):
    actors = {
        "h1": {"id": "h1", "name": "Heroi", "is_player": True},
        "e1": {"id": "e1", "name": "Rendido", "surrendered": True, "status": "rendido"},
        "e2": {"id": "e2", "name": "Lutador"},
    }
    for k, v in over.items():
        actors[k].update(v)
    sides = {"hero": ["h1"], "enemy": ["e1", "e2"]}
    return fx.Ctx(scene={}, actors_by_id=actors, sides=sides)


def _targets(ctx, eff, actor="h1", target=None):
    return fx._targets_for(eff, ctx, actor, target)


def test_rendido_nao_e_alvo_de_carta_em_area():
    assert _targets(_ctx(), {"kind": "dano", "alvo": "inimigos"}) == ["e2"]


def test_rendido_nao_vira_fallback_opp_primeiro():
    # id do rendido ordena antes do lutador: o fallback `opp[:1]` nao pode escolhe-lo
    assert _targets(_ctx(), {"kind": "dano"}) == ["e2"]


def test_rendido_nao_recebe_cura_do_baralho_inimigo():
    ctx = _ctx()
    assert "e1" not in _targets(ctx, {"kind": "cura", "alvo": "aliados"}, actor="e2")


def test_rendido_persistido_na_rodada_seguinte():
    """A marca `surrendered` e a unica persistida entre rodadas (sem `status`)."""
    ctx = _ctx(e1={"status": "ativo"})
    assert _targets(ctx, {"kind": "dano", "alvo": "inimigos"}) == ["e2"]


def test_terminal_fotografado():
    """R16 (D3b): terminal fora da Carta, dentro do ataque declarado, sem turno proprio."""
    terminal = {"id": "t", "estado_terminal": True}
    assert fx._alive(terminal) is False
    assert ct._targetable(terminal) is True
    assert orch._can_act(terminal) is False


def test_lado_coerente_por_modulo():
    sides = {"hero": ["h"], "ally": ["a"], "enemy": ["e"]}
    assert fx._card_side("h", sides) == fx._card_side("a", sides) == "heroes"
    assert fx._card_side("e", sides) == "enemy"
    assert ct._turn_side("h", sides) == ct._turn_side("a", sides) == "hero"
    assert ct._turn_side("e", sides) == "enemy"
