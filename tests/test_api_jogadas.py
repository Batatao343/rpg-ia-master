"""SPEC-328 R13-R16 - lista de jogadas na API, parser e nó de combate (1 narração/rodada)."""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat_agent
import api
from services import card_piles as cp
from tests.test_combat_simulator import _request

GOLPE, GUARDA = "bas_san_golpe", "bas_san_guarda"


def _state(monkeypatch, mode="on"):
    monkeypatch.setenv("RPG_CARD_DECK", mode)
    state = api._build_combat_simulator_state(_request(quantity=1))
    player = state["player"]
    cp.migrate_deck(player)
    state["combat"]["pilhas"] = cp.start_piles(player, 42)
    state["combat"]["pilhas"]["mao"] = [GOLPE, GUARDA, GOLPE, "san_corte_troca", "san_finta"]
    state["messages"] = [HumanMessage(content="Encerrar turno")]
    return state


def _req(**kw) -> api.ActionRequest:
    return api.ActionRequest(game_id="g", input_text="Encerrar turno", **kw)


def _plays(state, *cards):
    eid = state["enemies"][0]["id"]
    return [
        api.PlayStepRequest(card_id=c, target_id="player" if c == GUARDA else eid) for c in cards
    ]


def test_lista_inteira_vira_declaracao_em_um_request(monkeypatch):
    state = _state(monkeypatch)
    api._apply_action_options(state, _req(jogadas=_plays(state, GOLPE, GUARDA)))
    decl = state["combat_declaration"]
    assert [s["card_id"] for s in decl["jogadas"]] == [GOLPE, GUARDA]
    assert decl["acao"]["card_id"] == GOLPE


def test_lista_recusada_com_baralho_desligado(monkeypatch):
    state = _state(monkeypatch, mode="off")
    with pytest.raises(HTTPException) as exc:
        api._apply_action_options(state, _req(jogadas=_plays(state, GOLPE)))
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "deck_off"


def test_teto_de_jogadas_no_schema():
    with pytest.raises(ValueError):
        _req(jogadas=[api.PlayStepRequest(card_id=GOLPE)] * 9)


def test_no_resolve_a_lista_e_compra_a_proxima_mao(monkeypatch):
    state = _state(monkeypatch)
    api._apply_action_options(state, _req(jogadas=_plays(state, GOLPE, GUARDA)))
    out = combat_agent._combat_node(state)
    meta = out["combat"]
    assert meta["round"] == 1
    piles = meta["pilhas"]
    assert len(piles["mao"]) == cp.MAO_BASE and piles["folego"] == cp.FOLEGO_BASE
    assert GOLPE in piles["descarte"] and GUARDA in piles["descarte"]
    assert len(piles["descarte"]) == 5  # 2 jogadas + 3 da mão não usada, descartadas
    assert state["combat"]["pilhas"]["mao"][0] == GOLPE  # entrada intocada (sem mutar o state)


def test_carta_fora_da_mao_rejeitada_com_motivo_e_sem_gastar(monkeypatch):
    state = _state(monkeypatch)
    before = deepcopy(state["combat"]["pilhas"])
    entropy = state["player"]["entropy"]
    api._apply_action_options(state, _req(jogadas=_plays(state, "san_sil_exato")))
    out = combat_agent._combat_node(state)
    assert "não está na sua mão" in out["messages"][0].content
    assert out["combat"]["round"] == 0  # a rodada nao foi consumida
    assert out["combat"]["pilhas"] == before
    assert out["player"]["entropy"] == entropy


def test_uma_narracao_por_rodada_com_varias_jogadas(monkeypatch):
    state = _state(monkeypatch)
    state["combat_simulation"] = {"enabled": False}
    calls = []

    def fake_narrate(*args, **kwargs):
        calls.append(1)
        return "narração"

    def forbidden(*_a, **_k):
        raise AssertionError("nenhuma chamada LLM extra por carta")

    class _Pack:
        world_state_block = ""

    monkeypatch.setattr(combat_agent, "_narrate", fake_narrate)
    monkeypatch.setattr(combat_agent, "get_llm", forbidden)
    monkeypatch.setattr(combat_agent, "build_context_pack", lambda *a, **k: _Pack())
    api._apply_action_options(state, _req(jogadas=_plays(state, GOLPE, GUARDA, GOLPE)))
    combat_agent._combat_node(state)
    assert len(calls) == 1


# ------------------------------------------------------------------ parser (R15)
def _parser_state(monkeypatch):
    state = _state(monkeypatch)
    return state["player"], state["enemies"], state["combat"]["scene"], state["combat"]["pilhas"]


def test_texto_livre_vira_lista_de_cartas_na_ordem_do_texto(monkeypatch):
    player, enemies, scene, piles = _parser_state(monkeypatch)
    decl = combat_agent._parse_turn_declaration(
        player,
        enemies,
        "primeiro Couro Encharcado e depois Talho de Sangue Ralo",
        scene,
        piles=piles,
    )
    assert [s.card_id for s in decl.plays()] == [GUARDA, GOLPE]
    assert decl.acao.card_id == GUARDA


def test_parser_sem_baralho_segue_uma_acao(monkeypatch):
    player, enemies, scene, _ = _parser_state(monkeypatch)
    decl = combat_agent._parse_turn_declaration(player, enemies, "Talho de Sangue Ralo", scene)
    assert decl.jogadas == [] and decl.acao.card_id == GOLPE


def test_parser_guard_do_fallback_llm(monkeypatch):
    player, enemies, scene, piles = _parser_state(monkeypatch)

    class _Fallback:
        def with_structured_output(self, _model):
            return self

        def invoke(self, _messages):
            return AIMessage(content="erro de provider")  # FallbackLLM: nao e instancia do schema

    monkeypatch.setattr(combat_agent, "get_llm", lambda *a, **k: _Fallback())
    decl = combat_agent._parse_turn_declaration(
        player, enemies, "faço algo estranho", scene, piles=piles
    )
    assert decl.acao.kind == "attack" and decl.acao.target_id == enemies[0]["id"]


def test_catalogo_do_prompt_e_a_mao_com_folego(monkeypatch):
    player, _enemies, _scene, piles = _parser_state(monkeypatch)
    text = combat_agent._prepared_cards_catalog(player, piles)
    assert "Fôlego disponível: 3" in text and GOLPE in text
    assert "san_sil_exato" not in text  # fora da mao


def test_visao_publica_do_combate_expoe_mao_e_contagens(monkeypatch):
    state = _state(monkeypatch)
    view = api._combat_block(state)
    assert view["pilhas"]["folego"] == 3 and len(view["pilhas"]["mao"]) == 5
    assert isinstance(view["pilhas"]["compra"], int) and "ordem" not in view["pilhas"]
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    assert "pilhas" not in api._combat_block(state)


def test_combate_antigo_sem_pilhas_segue_no_modo_atual(monkeypatch):
    state = _state(monkeypatch)
    state["combat"].pop("pilhas")
    out = combat_agent._combat_node(state)
    assert "pilhas" not in out["combat"] and out["combat"]["round"] == 1


def test_flag_off_ignora_pilhas_salvas(monkeypatch):
    state = _state(monkeypatch, mode="off")
    saved = deepcopy(state["combat"]["pilhas"])
    out = combat_agent._combat_node(state)
    assert out["combat"]["pilhas"] == saved and out["combat"]["round"] == 1
