"""SPEC-215 §4 passo 7 — gate de conhecimento no contexto do `npc_actor` (R6/R11/R14)."""
from __future__ import annotations

import logging
import os

import pytest
from langchain_core.messages import HumanMessage

from services import context_builder as cb
from services import graph_resolver as gr
from services import npc_knowledge as nk
from tests.spec215_helpers import pack_state, pack_text, stub_rag

GOLDEN = os.path.join(os.path.dirname(__file__), "fixtures", "spec215_npc_pack_off.txt")
QUERY = "Guarda nova_arcadia quem manda aqui?"
DEAD = "npc_halveth_fixture"
KILL = {"event_id": "ev_halveth", "turn": 4, "type": "npc_killed", "actor_id": "player",
        "target_id": DEAD, "payload": {}, "source": "combat"}


@pytest.fixture(autouse=True)
def _rag(monkeypatch):
    gr.clear_cache()
    stub_rag(monkeypatch)
    yield
    gr.clear_cache()


def _pack(state, mode, monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", mode)
    return cb.build_context_pack(state, query=QUERY, purpose="npc",
                                 game_id="spec215-game", npc_id="npc_guarda")


def _distant_state(**over):
    return pack_state(event_log=[dict(KILL)],
                      world_projection={"entities": {DEAD: {"alive": False}}}, **over)


def _witness_link(subject="ev_halveth", clock=5):
    return {"link_id": f"w-{subject}", "holder_id": "npc:npc_guarda", "subject_kind": "event",
            "subject_id": subject, "relation": "observed_by", "source": "world",
            "channel": "witness", "hops": 0, "acquired_clock": clock, "acquired_turn": 4,
            "location_id": "nova_arcadia"}


def test_off_pack_identical_to_head_snapshot(monkeypatch):
    with open(GOLDEN, encoding="utf-8") as fh:
        golden = fh.read()
    ledger = {"knowledge_links": [_witness_link()], "knowledge_queue": [],
              "location_heard": {"nova_arcadia": ["ev_halveth"]}, "legacy_knowledge": False}
    assert pack_text(_pack(pack_state(), "off", monkeypatch)) == golden
    assert pack_text(_pack(pack_state(**ledger), "off", monkeypatch)) == golden
    monkeypatch.delenv("RPG_NPC_KNOWLEDGE")
    assert pack_text(cb.build_context_pack(pack_state(**ledger), query=QUERY, purpose="npc",
                                           game_id="spec215-game", npc_id="npc_guarda")) == golden


def test_shadow_identical_to_off_and_logs(monkeypatch, caplog):
    off = pack_text(_pack(_distant_state(), "off", monkeypatch))
    with caplog.at_level(logging.INFO, logger="rpg.npc_knowledge"):
        shadow = pack_text(_pack(_distant_state(), "shadow", monkeypatch))
    assert shadow == off
    assert any(r.name == "rpg.npc_knowledge" and "filtered" in r.getMessage()
               for r in caplog.records)


def test_on_distant_npc_does_not_know_death(monkeypatch):
    off = pack_text(_pack(_distant_state(), "off", monkeypatch))
    assert DEAD in off and "foi morto" in off  # baseline onisciente
    on = pack_text(_pack(_distant_state(), "on", monkeypatch))
    assert DEAD not in on
    assert "morto" not in on
    # D2: resumo/ledger/memória de sessão do JOGADOR fora; memória do NPC fica.
    assert "O herói matou Valerius" not in on
    assert "sessão do jogador" not in on
    assert "memória do guarda" in on


def test_on_witness_sees_viu(monkeypatch):
    on = pack_text(_pack(_distant_state(knowledge_links=[_witness_link()]), "on", monkeypatch))
    assert "[VIU]" in on and DEAD in on
    assert f"{DEAD}: morto" in on  # status morto só para quem sabe da morte


def test_on_limits_knowledge_to_eight(monkeypatch):
    events = [{**KILL, "event_id": f"ev_{i}", "target_id": f"{DEAD}_{i}"} for i in range(12)]
    links = [_witness_link(f"ev_{i}", clock=i) for i in range(12)]
    pack = _pack(pack_state(event_log=events, knowledge_links=links), "on", monkeypatch)
    text = pack_text(pack)
    assert text.count("[VIU]") == nk.NPC_KNOWLEDGE_CONTEXT_MAX
    assert pack.total_tokens_est <= int(3500 * 1.05)


def test_on_fail_closed_on_internal_error(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("ledger corrompido")
    monkeypatch.setattr(nk, "knowledge_lines", boom)
    on = pack_text(_pack(_distant_state(knowledge_links=[_witness_link()]), "on", monkeypatch))
    assert DEAD not in on and "foi morto" not in on
    assert "O herói matou Valerius" not in on
    assert "memória do guarda" in on


def test_story_purpose_unaffected_by_flag(monkeypatch):
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "off")
    off = cb.build_context_pack(_distant_state(), query=QUERY, purpose="story",
                                game_id="spec215-game")
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    on = cb.build_context_pack(_distant_state(), query=QUERY, purpose="story",
                               game_id="spec215-game")
    assert pack_text(off) == pack_text(on)


# ------------------------------------------------------------------ prompt do npc_actor
class _NPCLLM:
    def __init__(self):
        self.captured = None

    def with_structured_output(self, model, *_a, **_k):
        self._model = model
        return self

    def with_retry(self, *_a, **_k):
        return self

    def invoke(self, msgs):
        self.captured = str(msgs[0].content)
        return self._model(dialogue="oi", action_description="", memory_update="",
                           relationship_change=0, faction_reveals=[])


def _prompt(monkeypatch, state, mode):
    import agents.npc as npc
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", mode)
    llm = _NPCLLM()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    out = npc.npc_actor_node({**state, "active_npc_name": "Guarda",
                              "messages": [HumanMessage(content="quem manda aqui?")]})
    return llm.captured, out


def test_npc_prompt_off_ignores_ledger(monkeypatch):
    plain, out_plain = _prompt(monkeypatch, _distant_state(), "off")
    ledger, out_ledger = _prompt(monkeypatch, _distant_state(knowledge_links=[_witness_link()]),
                                 "off")
    assert plain == ledger
    assert "O estado atual acima é a verdade de AGORA." in plain
    assert "knowledge_links" not in out_plain and "knowledge_links" not in out_ledger
    shadow, out_shadow = _prompt(monkeypatch, _distant_state(), "shadow")
    assert shadow == plain


def test_npc_prompt_on_speaks_of_what_character_knows(monkeypatch):
    prompt, _ = _prompt(monkeypatch, _distant_state(), "on")
    assert "verdade de AGORA" not in prompt
    assert "Se não está aqui nem na sua memória, você não sabe." in prompt
    assert DEAD not in prompt


def test_npc_on_player_told_is_recorded(monkeypatch):
    chronicle = [{"chapter_id": "c", "entries": [
        {"text": "x", "turn": 4, "kind": "milestone", "event_id": "ev_halveth"}]}]
    st = _distant_state(chronicle=chronicle)
    import agents.npc as npc
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    llm = _NPCLLM()
    monkeypatch.setattr(npc, "get_llm", lambda *a, **k: llm)
    monkeypatch.setattr(npc, "RAG_AVAILABLE", False)
    out = npc.npc_actor_node({**st, "active_npc_name": "Guarda", "messages": [
        HumanMessage(content=f"Você soube que {DEAD} morreu?")]})
    links = out.get("knowledge_links") or []
    assert any(lk["relation"] == "told_to" and lk["channel"] == "player" for lk in links)
    assert "[BOATO" in llm.captured  # relação 5 < 6: ouviu, não acredita
    assert out.get("event_log") is None  # fala do jogador não vira fato


def test_directed_distant_city_before_and_after_due(monkeypatch):
    """Cenário dirigido (§6): morte em Brekmar; NPC em Ophidia (3 períodos)
    não sabe antes do due_clock e cita como notícia depois."""
    monkeypatch.setenv("RPG_NPC_KNOWLEDGE", "on")
    params = {k: (1.0, r, h) for k, (_p, r, h) in nk.SUBJECT_PARAMS.items()}
    monkeypatch.setattr(nk, "SUBJECT_PARAMS", params)
    kill = {**KILL, "turn": 7}
    st = pack_state(
        event_log=[kill], world_projection={"entities": {DEAD: {"alive": False}}},
        world={"turn_count": 7, "current_location": "Brekmar",
               "current_location_id": "brekmar", "world_clock": {"day": 2, "period": "Tarde"}},
        npcs={"Osric": {"name": "Osric", "id": "npc_osric", "home_location_id": "ophidia",
                        "in_scene": False, "relationship": 5}})
    st = {**st, **nk.turn_updates(st)}
    due = next(d["due_clock"] for d in st["knowledge_queue"] if d["to_location_id"] == "ophidia")

    def pack_at(clock):
        import world_utils
        day, idx = divmod(clock, 5)
        world = {**st["world"], "current_location_id": "ophidia", "current_location": "Ophidia",
                 "world_clock": {"day": day, "period": world_utils.PERIODS[idx]}}
        state = {**st, "world": world}
        state = {**state, **nk.deliver_due(state, clock)}
        return pack_text(cb.build_context_pack(state, query="Osric notícias", purpose="npc",
                                               game_id="spec215-game", npc_id="npc_osric"))

    before = pack_at(due - 1)
    assert DEAD not in before and "morto" not in before
    after = pack_at(due)
    assert "[OUVIU DE viajantes de Brekmar]" in after and DEAD in after


def test_on_remote_control_change_edge_needs_knowledge(monkeypatch):
    """R6/R3: a aresta dinâmica criada por `location_control_changed` remoto não
    teleporta para o NPC que não sabe do evento (com `off` segue onisciente)."""
    ev = {"event_id": "ev_ctrl_remote_1", "turn": 4, "type": "location_control_changed",
          "actor_id": "player", "target_id": "ophidia",
          "payload": {"new_controller_id": "faction_fixture_215"}}
    proj = {"dynamic_edges": [{"id": "dyn_ev_ctrl_remo", "source": "faction_fixture_215",
                               "type": "controls", "target": "ophidia",
                               "created_by_event": "ev_ctrl_remote_1"}]}
    state = pack_state(event_log=[ev], world_projection=proj)
    assert "faction_fixture_215" in pack_text(_pack(state, "off", monkeypatch))
    assert "faction_fixture_215" not in pack_text(_pack(state, "on", monkeypatch))
