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


# ------------------------------------------------------------------ revisão Sol (P1-1, P1-3, P2-1, P2-4)
def _schema_probe(monkeypatch, player, enemies, scene, piles):
    seen = []

    class _Probe:
        def with_structured_output(self, model):
            seen.append(model)
            return self

        def invoke(self, _messages):
            return AIMessage(content="erro")

    monkeypatch.setattr(combat_agent, "get_llm", lambda *a, **k: _Probe())
    combat_agent._parse_turn_declaration(player, enemies, "faço algo estranho", scene, piles=piles)
    return seen[0]


def test_schema_classify_so_tem_extra_card_ids_com_baralho(monkeypatch):
    player, enemies, scene, piles = _parser_state(monkeypatch)
    assert (
        "extra_card_ids" in _schema_probe(monkeypatch, player, enemies, scene, piles).model_fields
    )
    assert (
        "extra_card_ids"
        not in _schema_probe(monkeypatch, player, enemies, scene, None).model_fields
    )


def test_nome_mais_longo_vence_sem_duplicar(monkeypatch):
    from services import cards

    player, enemies, scene, piles = _parser_state(monkeypatch)
    base = deepcopy(cards.get_card(GOLPE))
    curta = {**base, "id": "x_vazao", "name": "Vazão"}
    longa = {**base, "id": "x_vazao_c", "name": "Vazão Controlada"}
    monkeypatch.setitem(cards.all_cards(), "x_vazao", curta)
    monkeypatch.setitem(cards.all_cards(), "x_vazao_c", longa)
    piles["mao"] += ["x_vazao", "x_vazao_c"]
    decl = combat_agent._parse_turn_declaration(
        player, enemies, "uso Vazão Controlada", scene, piles=piles
    )
    assert [s.card_id for s in decl.plays()] == ["x_vazao_c"]


def _start_state(monkeypatch, mode):
    from langchain_core.messages import SystemMessage

    monkeypatch.setenv("RPG_CARD_DECK", mode)
    state = api._build_combat_simulator_state(_request(quantity=1))
    state["combat"] = {}
    state["messages"] = [SystemMessage(content="COMBAT START")]
    return state


def test_no_cria_pilhas_no_inicio_com_semente_derivada(monkeypatch):
    import zlib

    state = _start_state(monkeypatch, "on")
    out = combat_agent._combat_node(state)
    meta = out["combat"]
    expected = zlib.crc32(meta["instance_id"].encode("utf-8"))
    assert meta["pilhas"]["seed"] == expected
    assert "prepared_cards_pre_deck" in out["player"] and out["player"]["deck"]


def test_shadow_nao_muda_a_ficha_e_off_restaura_a_preparacao(monkeypatch):
    state = _start_state(monkeypatch, "shadow")
    before = deepcopy(state["player"]["prepared_cards"])
    out = combat_agent._combat_node(state)
    assert out["player"]["prepared_cards"] == before and "deck" not in out["player"]
    assert "pilhas" in out["combat"]
    # on -> off: rollback da Preparação
    state = _start_state(monkeypatch, "on")
    before = deepcopy(state["player"]["prepared_cards"])
    on = combat_agent._combat_node(state)
    assert on["player"]["prepared_cards"] != before
    monkeypatch.setenv("RPG_CARD_DECK", "off")
    st2 = _start_state(monkeypatch, "off")
    st2["player"] = on["player"]
    off = combat_agent._combat_node(st2)
    assert off["player"]["prepared_cards"] == before


def test_save_load_no_meio_do_conflito_e_mais_uma_rodada(monkeypatch, tmp_path):
    import persistence

    monkeypatch.setattr(persistence, "SAVES_DIR", str(tmp_path))
    state = _start_state(monkeypatch, "on")
    state["combat_declaration"] = None
    first = combat_agent._combat_node(state)
    assert first["combat"]["active"] is True  # R-5: conflito precisa seguir ativo
    mid = {**state, **{k: v for k, v in first.items() if k != "messages"}}
    mid["messages"] = [HumanMessage(content="Encerrar turno")]
    assert persistence.save_game_state(deepcopy(mid)) is True
    loaded = persistence.load_game_state(persistence.save_path(mid["game_id"]))
    assert loaded["combat"]["pilhas"] == mid["combat"]["pilhas"]
    loaded["messages"] = [HumanMessage(content="Encerrar turno")]
    import random

    random.seed(5)
    a = combat_agent._combat_node(deepcopy(mid))
    random.seed(5)
    b = combat_agent._combat_node(loaded)
    assert a["combat"]["pilhas"] == b["combat"]["pilhas"]
    assert a["combat"]["active"] and b["combat"]["active"]
    assert a["combat"]["round"] == b["combat"]["round"] == 2
    for key in ("vitalidade", "entropy", "abyss_charge"):
        assert a["player"].get(key) == b["player"].get(key)
    assert [e.get("vitalidade") for e in a["enemies"]] == [
        e.get("vitalidade") for e in b["enemies"]
    ]


def test_recusa_preserva_pressagios(monkeypatch):
    monkeypatch.setenv("RPG_ENEMY_INTENT", "on")
    state = _state(monkeypatch)
    state["combat_simulation"] = {"enabled": False}
    state["combat"]["pressagios"] = {"r": [1]}
    state["combat"]["pressagios_publicos"] = [{"x": 1}]

    class _Pack:
        world_state_block = ""

    monkeypatch.setattr(combat_agent, "_narrate", lambda *a, **k: "n")
    monkeypatch.setattr(combat_agent, "build_context_pack", lambda *a, **k: _Pack())
    api._apply_action_options(state, _req(jogadas=_plays(state, "san_sil_exato")))
    out = combat_agent._combat_node(state)
    assert out["combat"]["pressagios"] == {"r": [1]}
    assert out["combat"]["pressagios_publicos"] == [{"x": 1}]


def test_api_action_com_jogadas_e_pilhas_na_resposta(monkeypatch):
    from fastapi.testclient import TestClient

    saved = {}

    def save(state):
        saved[state["game_id"]] = deepcopy(state)
        return True

    def load(path=None):
        if not path:
            return None
        gid = path.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".json")
        return deepcopy(saved.get(gid))

    monkeypatch.setattr(api, "save_game_state", save)
    monkeypatch.setattr(api, "load_game_state", load)
    monkeypatch.setattr("services.checkpoints.maybe_write", lambda *a, **k: None)
    state = _state(monkeypatch)
    state["game_id"] = "0d8f5b1e-4c3a-4f6e-9b7a-2e1d3c4b5a69"
    state["combat_simulation"] = {"enabled": True, "enemy_id": "x", "quantity": 1}
    saved["0d8f5b1e-4c3a-4f6e-9b7a-2e1d3c4b5a69"] = deepcopy(state)
    eid = state["enemies"][0]["id"]
    client = TestClient(api.app)
    res = client.post(
        "/game/action",
        json={
            "game_id": "0d8f5b1e-4c3a-4f6e-9b7a-2e1d3c4b5a69",
            "input_text": "Encerrar turno",
            "jogadas": [
                {"card_id": GOLPE, "target_id": eid},
                {"card_id": GUARDA, "target_id": "player"},
            ],
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["combat"]["pilhas"]["folego"] == cp.FOLEGO_BASE
    assert len(body["combat"]["pilhas"]["mao"]) == cp.MAO_BASE
    after = saved["0d8f5b1e-4c3a-4f6e-9b7a-2e1d3c4b5a69"]["combat"]
    assert [p["card_id"] for p in after["last_player_action"]["plays"]] == [GOLPE, GUARDA]
