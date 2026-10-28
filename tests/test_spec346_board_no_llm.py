"""SPEC-346 R1-R6 + D4/D5: o tabuleiro (`RPG_CARD_DECK=on`) abre pela história e a rodada não chama LLM."""

from __future__ import annotations

import copy
import random

import pytest
from langchain_core.messages import AIMessage, HumanMessage

import agents.combat as combat
from services import conflict_orchestrator as orch
from tests.test_encounter_identity_repro import _install_llm, _scan, _start_state

BOARD_REFUSAL = combat.BOARD_FREETEXT_REFUSAL


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setenv("RPG_CARD_DECK", "on")
    random.seed(7)


def _open(monkeypatch, *, scan=None, **world_extra):
    _install_llm(monkeypatch, scan=scan or _scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["world"].update(world_extra)
    return state, combat._combat_node(state)


def _after_open(state, result):
    """Estado do turno seguinte (mescla o retorno do nó, como o reducer do grafo)."""
    nxt = {**state, **{k: v for k, v in result.items() if k != "messages"}}
    nxt["messages"] = [*state["messages"], *result["messages"]]
    return nxt


def _attack_decl(state):
    target = next(e["id"] for e in state["enemies"] if not e.get("dead"))
    return {"actor_id": "player", "acao": {"kind": "attack", "target_id": target}}


def test_opening_turn_deals_hand_without_round(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a abertura não resolve rodada")

    monkeypatch.setattr(orch, "run_round", boom)
    monkeypatch.setattr(combat, "_parse_turn_declaration", boom)
    state, res = _open(monkeypatch)
    meta = res["combat"]
    assert meta["round"] == 0 and meta["active"] is True
    assert meta["pilhas"]["mao"], "a mão precisa estar na mesa"
    assert meta["phase"] == "active"
    assert len(res["messages"]) == 1 and isinstance(res["messages"][0], AIMessage)
    assert res["enemies"] and res["archive_due"] is False


@pytest.mark.parametrize(
    ("world", "origin", "expected", "why"),
    [
        ({"encounter_surprise": "enemy"}, None, "enemy", "ambush"),
        ({"encounter_surprise": "player"}, None, "heroes", "player_ambush"),
        ({}, "player_provoked", "heroes", "player_attack"),
        ({}, "regional_danger", None, "neutral"),
    ],
)
def test_opening_initiative_comes_from_the_scene(monkeypatch, world, origin, expected, why):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["world"].update(world)
    if origin:
        state["combat_origin_hint"] = origin
    res = combat._combat_node(state)
    assert res["combat"]["initiator"] == expected
    assert res["combat"]["initiator_reason"] == why


@pytest.mark.parametrize(
    ("world", "origin", "level", "expected"),
    [
        (
            {"encounter_surprise": "enemy"},
            None,
            1,
            "enemy",
        ),  # emboscada vence a proteção de nível 1
        ({}, "player_provoked", 3, "heroes"),
        ({}, "regional_danger", 3, None),  # neutro: regra de iniciativa atual (dados)
        ({}, "regional_danger", 1, "heroes"),  # neutro + herói novo: proteção atual do motor
    ],
)
def test_round_one_honors_the_scene_initiator(monkeypatch, world, origin, level, expected):
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)))
    state = _start_state(hint="Goblin")
    state["player"]["level"] = level
    state["world"].update(world)
    if origin:
        state["combat_origin_hint"] = origin
    res = combat._combat_node(state)
    state2 = _after_open(state, res)
    state2["messages"] = [*state["messages"], HumanMessage(content="Jogo as cartas")]
    state2["combat_declaration"] = _attack_decl(state2)
    seen = {}
    real = orch.run_round

    def spy(*a, **k):
        seen["initiator"] = k.get("initiator")
        return real(*a, **k)

    monkeypatch.setattr(orch, "run_round", spy)
    combat._combat_node(state2)
    assert seen["initiator"] == expected


def test_free_text_during_board_is_refused(monkeypatch):
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    before = copy.deepcopy(nxt["combat"])
    calls = []
    monkeypatch.setattr(orch, "run_round", lambda *a, **k: calls.append(1))
    for text in ("ataco o goblin", "fujo para a saída", "viajo para a cidade", "o que vejo?"):
        nxt["messages"] = [*nxt["messages"], HumanMessage(content=text)]
        out = combat._combat_node(nxt)
        assert out["messages"][0].content == BOARD_REFUSAL
        assert out["combat"]["round"] == before["round"] == 0
        assert out["combat"].get("pressagios") == before.get("pressagios")
        assert out["combat"]["idle_turns"] == 0  # recusa não deixa o combate expirar
        assert not out.get("combat_flee_attempt")
        nxt = {**nxt, "combat": out["combat"]}
    assert not calls


def test_free_text_refusal_ignores_router_travel_flee_flag(monkeypatch):
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="vou para Skallgard")]
    nxt["combat_flee_attempt"] = True
    nxt["combat_flee_destination"] = "skallgard"
    out = combat._combat_node(nxt)
    assert out["messages"][0].content == BOARD_REFUSAL
    assert out["combat_flee_attempt"] is False


def _flee_outcomes(monkeypatch, seed):
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Fugir")]
    nxt["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "flee"}}
    random.seed(seed)
    out = combat._combat_node(nxt)
    return out["combat"].get("chase", {}).get("trilha"), out["combat"]["active"], out


def test_flee_button_is_deterministic_by_seed(monkeypatch):
    seen = {}
    for seed in range(12):
        a = _flee_outcomes(monkeypatch, seed)
        b = _flee_outcomes(monkeypatch, seed)
        assert a[:2] == b[:2], seed
        seen[(a[0], a[1])] = seed
    # o dado importa: ao longo de 12 sementes aparecem desfechos diferentes (avança/perde/escapa)
    assert len({k[0] for k in seen}) >= 2, seen
    # e a fuga consome a Ação: o combate registrou 1 rodada
    _t, _active, out = _flee_outcomes(monkeypatch, 0)
    assert out["combat"]["round"] == 1


def test_flee_button_can_escape_and_ends_with_outcome(monkeypatch):
    escaped = None
    for seed in range(30):
        state, res = _open(monkeypatch)
        cur = _after_open(state, res)
        random.seed(seed)
        for _press in range(6):  # a fuga é uma trilha: pode levar mais de uma rodada
            cur["messages"] = [*cur["messages"], HumanMessage(content="Fugir")]
            cur["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "flee"}}
            out = combat._combat_node(cur)
            if not out["combat"]["active"]:
                escaped = out
                break
            cur = {**cur, **{k: v for k, v in out.items() if k != "messages"}}
        if escaped is not None and escaped["combat"].get("outcome") == "fled":
            break
        escaped = None
    assert escaped is not None, "nenhuma semente escapou em 6 apertos"
    assert escaped["combat"]["outcome"] == "fled"
    assert escaped["messages"][0].content.strip()


def test_round_message_is_registry(monkeypatch):
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    hand = nxt["combat"]["pilhas"]["mao"]
    from services import cards

    attack_card = next(c for c in hand if (cards.get_card(c) or {}).get("efeito"))
    eid = nxt["enemies"][0]["id"]
    nxt["combat_declaration"] = {
        "actor_id": "player",
        "acao": {"kind": "card", "card_id": attack_card, "target_id": eid},
        "jogadas": [{"kind": "card", "card_id": attack_card, "target_id": eid}],
    }
    out = combat._combat_node(nxt)
    text = out["messages"][0].content
    card = cards.get_card(attack_card)
    assert card["name"] in text
    assert "×" not in text and "->" not in text and "⚔️" not in text
    import re

    assert not re.search(r"Vitalidade \d", text)
    assert "vs Esquiva" not in text and "total " not in text.lower().replace("totalmente", "")


def test_status_lines_go_to_registry_not_appended(monkeypatch):
    from services import round_log

    out = {
        "attacks": [],
        "logs": [],
        "cards_used": [],
        "deaths": [],
        "terminal": [],
    }
    lines = round_log.round_registry(out, {"player": {"name": "Ysolde"}}, ["Dor Surda no Baralho."])
    assert lines == ["Dor Surda no Baralho."]
    text = "\n".join(lines)
    assert not text.endswith(" ".join(["Dor Surda no Baralho.", "x"]))  # sem a antiga concatenação


def _no_llm(monkeypatch):
    import importlib

    names = (  # todo módulo que importa `get_llm`: o grafo inteiro, não só o combate
        "agents.combat",
        "agents.router",
        "agents.loot",
        "agents.campaign_manager",
        "agents.archivist",
        "agents.bestiary",
        "agents.librarian",
        "agents.npc",
        "agents.storyteller",
        "agents.world_simulator",
        "services.chronicle_compression",
        "services.shared_pool",
        "services.encounter_preparation",
        "services.death_flow",
    )

    def boom(*a, **k):
        raise AssertionError("a rodada `on` não pode chamar LLM")

    for name in names:
        mod = importlib.import_module(name)
        if hasattr(mod, "get_llm"):
            monkeypatch.setattr(mod, "get_llm", boom)
    import llm_setup

    monkeypatch.setattr(llm_setup, "get_llm", boom)


def test_round_with_jogadas_makes_zero_llm_calls_in_the_whole_graph(monkeypatch):
    import main

    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo a carta")]
    nxt["combat_declaration"] = _attack_decl(nxt)
    nxt["campaign_plan"] = {"beats": [], "current_step": 0, "last_planned_turn": 99}
    _no_llm(monkeypatch)
    final = main.app.invoke(nxt)
    assert final["combat"]["round"] == 1
    assert isinstance(final["messages"][-1], AIMessage)


def test_scar_is_deterministic_on(monkeypatch):
    from services import death_flow

    seen = {}

    def spy(participant, llm, **k):
        seen["llm"] = llm
        return {}

    monkeypatch.setattr(death_flow, "generate_scar", spy)
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    nxt["player"]["scar_pending"] = True
    nxt["combat_declaration"] = _attack_decl(nxt)
    real = orch.run_round

    def rr(*a, **k):
        out = real(*a, **k)
        out["scars_pending"] = ["player"]
        return out

    monkeypatch.setattr(orch, "run_round", rr)
    monkeypatch.setattr(death_flow, "check_scar_required", lambda p: True)
    _no_llm(monkeypatch)
    combat._combat_node(nxt)
    assert seen["llm"] is None


@pytest.mark.parametrize("mode", ["off", "shadow"])
def test_shadow_and_off_keep_narrated_rounds(monkeypatch, mode):
    monkeypatch.setenv("RPG_CARD_DECK", mode)
    _install_llm(monkeypatch, scan=_scan(("Goblin", 1)), narration="Narração por LLM.")
    state = _start_state(hint="Goblin")
    state["combat_declaration"] = {"actor_id": "player", "acao": {"kind": "pass"}}
    narrated = []
    real = combat._narrate

    def spy(*a, **k):
        narrated.append(1)
        return real(*a, **k)

    monkeypatch.setattr(combat, "_narrate", spy)
    out = combat._combat_node(state)
    assert narrated, "off/shadow seguem narrando a rodada"
    assert out["combat"]["round"] == 1  # e a abertura resolve a 1ª rodada, como antes


def test_api_flee_button_builds_structured_flee_declaration(monkeypatch):
    """Contrato da API (D5): `action_kind="flee"` vira `combat_declaration.acao.kind == "flee"`."""
    import api
    from tests.test_api_jogadas import _req, _state

    state = _state(monkeypatch)
    api._apply_action_options(state, _req(action_kind="flee"))
    assert state["combat_declaration"]["acao"]["kind"] == "flee"


def test_refused_play_shows_the_reason_in_the_registry(monkeypatch):
    """Carta fora da mão: nada é gasto e a mensagem diz por quê (não 'O combate segue')."""
    state, res = _open(monkeypatch)
    nxt = _after_open(state, res)
    eid = nxt["enemies"][0]["id"]
    nxt["messages"] = [*nxt["messages"], HumanMessage(content="Jogo")]
    nxt["combat_declaration"] = {
        "actor_id": "player",
        "acao": {"kind": "card", "card_id": "carta_que_nao_existe", "target_id": eid},
        "jogadas": [{"kind": "card", "card_id": "carta_que_nao_existe", "target_id": eid}],
    }
    before = copy.deepcopy(nxt["combat"]["pilhas"])
    out = combat._combat_node(nxt)
    assert out["combat"]["round"] == 0
    assert out["combat"]["pilhas"] == before
    assert "O combate segue" not in out["messages"][0].content
    assert out["messages"][0].content.strip()
