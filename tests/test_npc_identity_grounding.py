"""Regressões da matriz B para identidade canônica de NPC."""
from __future__ import annotations

from types import SimpleNamespace

from langchain_core.messages import HumanMessage

from agents import archivist, npc, storyteller
from agents.archivist import MemoryUpdate
from playtest.invariants import check_entities, check_memory_provenance
from services.context_builder import build_context_pack
from services.entity_identity import coalesce_runtime_npcs, find_runtime_npc_key
from services.memory_provenance import (
    make_memory_fact,
    npc_identity_contradiction,
    validate_memory_fact,
)
import persistence


def _skriit(*, in_scene: bool = False, last_seen: int = 27) -> dict:
    return {
        "id": "npc_skriit_mil-olhos",
        "name": "Skriit Mil-olhos",
        "role": "Líder goblin fugitivo",
        "appearance": (
            "Goblin pequeno e encolhido, de pele verde-acinzentada, "
            "orelha rasgada e venda no olho esquerdo."
        ),
        "persona": "Astuto e desconfiado.",
        "home_location_id": "sk_salao_do_jarl",
        "in_scene": in_scene,
        "last_seen_turn": last_seen,
        "relationship": 6,
    }


def _state() -> dict:
    return {
        "game_id": "npc-identity",
        "world": {
            "turn_count": 32,
            "current_location_id": "sk_salao_do_jarl",
            "current_location": "Salão do Jarl",
        },
        "npcs": {"Skriit Mil-olhos": _skriit(in_scene=True)},
        "memory_facts": [],
        "narrative_summary": "Skriit aguarda no Salão do Jarl.",
    }


def test_reintroducao_por_id_reusa_chave_e_ficha_canonica(monkeypatch) -> None:
    monkeypatch.setattr(
        storyteller, "generate_new_npc", lambda *_a, **_k: _skriit(in_scene=False),
    )
    original = {"Skriit Mil-olhos": _skriit(in_scene=False)}
    out = storyteller._with_new_npc(
        original,
        "npc_skriit_mil_olhos",
        "Salão do Jarl",
        "Skriit reaparece.",
        game_id="g",
        home_id="sk_salao_do_jarl",
        turn=51,
    )
    assert list(out) == ["Skriit Mil-olhos"]
    assert out["Skriit Mil-olhos"]["in_scene"] is True
    assert out["Skriit Mil-olhos"]["last_seen_turn"] == 51
    assert out["Skriit Mil-olhos"]["appearance"].startswith("Goblin pequeno")


def test_npc_actor_resolve_id_sem_criar_segunda_chave(monkeypatch) -> None:
    class _Structured:
        def invoke(self, _messages):
            return npc.NPCResponse(
                dialogue="Continuo sendo eu.",
                action_description="ajeita a venda do olho",
                memory_update="",
            )

    class _LLM:
        def with_structured_output(self, _schema):
            return _Structured()

    monkeypatch.setattr(npc, "get_llm", lambda **_kwargs: _LLM())
    monkeypatch.setattr(
        npc,
        "build_context_pack",
        lambda *_args, **_kwargs: SimpleNamespace(
            memory_block="", lore_block="", world_state_block=""),
    )
    monkeypatch.setattr(npc, "add_npc_memory", lambda *_args, **_kwargs: True)
    state = {
        **_state(),
        "active_npc_name": "npc_skriit_mil_olhos",
        "messages": [HumanMessage(content="Skriit, fale comigo.")],
        "party": [],
        "factions": [],
        "faction_intel": {},
        "quests": [],
    }

    out = npc.npc_actor_node(state)

    assert list(out["npcs"]) == ["Skriit Mil-olhos"]
    assert out["npcs"]["Skriit Mil-olhos"]["appearance"].startswith("Goblin pequeno")
    assert "Continuo sendo eu" in out["messages"][0].content


def test_coalescencia_legada_por_id_preserva_identidade_e_estado_recente() -> None:
    duplicate = {
        **_skriit(in_scene=True, last_seen=51),
        "appearance": "Homem alto de cabelo grisalho.",
        "relationship": 2,
    }
    npcs = {
        "Skriit Mil-olhos": _skriit(in_scene=False, last_seen=27),
        "npc_skriit_mil_olhos": duplicate,
    }
    assert find_runtime_npc_key(npcs, "npc_skriit_mil_olhos") == "Skriit Mil-olhos"
    merged = coalesce_runtime_npcs(npcs)
    assert list(merged) == ["Skriit Mil-olhos"]
    assert merged["Skriit Mil-olhos"]["appearance"].startswith("Goblin pequeno")
    assert merged["Skriit Mil-olhos"]["in_scene"] is True
    assert merged["Skriit Mil-olhos"]["last_seen_turn"] == 51

    raw = persistence._state_to_save_data(
        {"game_id": "npc-identity", "player": {}, "npcs": npcs}, "npc-identity",
    )
    assert list(raw["npcs"]) == ["Skriit Mil-olhos"]
    assert list(persistence._raw_to_state(raw)["npcs"]) == ["Skriit Mil-olhos"]


def test_memoria_recusa_especie_e_porte_contraditorios_da_matriz_b() -> None:
    state = _state()
    bad = (
        "Skriit Mil-olhos (homem alto, cabelo grisalho, olho direito coberto "
        "por tira de couro) reconheceu o jogador."
    )
    contradiction = npc_identity_contradiction(bad, state)
    assert contradiction == {
        "npc_key": "Skriit Mil-olhos",
        "npc_name": "Skriit Mil-olhos",
        "field": "species",
        "expected": "goblin",
        "claimed": "humano",
    }
    accepted, reason = validate_memory_fact(
        make_memory_fact(
            bad, provenance="inference", source_id="archivist:32", source_turn=32,
        ),
        state,
    )
    assert accepted is None
    assert reason == "npc_identity_contradiction:Skriit Mil-olhos:species"
    assert npc_identity_contradiction(
        "Skriit Mil-olhos, goblin pequeno e ferido, aguarda no salão.", state,
    ) is None


def test_coalescencia_prefere_identidade_original_mesmo_em_ordem_inversa() -> None:
    original = {**_skriit(last_seen=27), "created_turn": 2}
    duplicate = {
        **_skriit(in_scene=True, last_seen=51), "created_turn": 50,
        "appearance": "Homem alto.", "relationship": 2,
    }
    merged = coalesce_runtime_npcs({
        "npc_skriit_mil_olhos": duplicate, "Skriit Mil-olhos": original,
    })
    assert len(merged) == 1
    row = next(iter(merged.values()))
    assert row["appearance"].startswith("Goblin pequeno")
    assert row["created_turn"] == 2
    assert row["last_seen_turn"] == 51
    assert row["relationship"] == 2


def test_contexto_e_invariantes_quarentenam_identidade_antiga(monkeypatch) -> None:
    from services import context_builder

    bad_text = "Skriit Mil-olhos é um homem alto de cabelo grisalho."
    bad = make_memory_fact(
        bad_text, provenance="inference", source_id="archivist:32", source_turn=32,
    )
    state = {**_state(), "memory_facts": [bad], "narrative_summary": bad_text}
    monkeypatch.setattr(context_builder, "query_rag", lambda *_a, **_k: "")
    monkeypatch.setattr(
        context_builder, "query_session_memory", lambda *_a, **_k: bad_text,
    )
    pack = build_context_pack(state, "Skriit", "story", game_id="g")
    assert "homem alto" not in pack.memory_block

    memory_violations = check_memory_provenance(
        state, {"memory_facts": []}, 32,
    )
    assert [row.check_id for row in memory_violations] == [
        "memory.npc_identity_grounding"
    ]

    duplicate_state = {
        **state,
        "npcs": {
            "Skriit Mil-olhos": _skriit(),
            "npc_skriit_mil_olhos": _skriit(in_scene=True, last_seen=51),
        },
        "event_log": [],
    }
    assert [row.check_id for row in check_entities(duplicate_state, None, 51)] == [
        "entity.npc_duplicate_identity"
    ]

    same_name_distinct_ids = {
        **state,
        "npcs": {
            "Skriit Mil-olhos": _skriit(),
            "skriit_alias": {
                **_skriit(in_scene=True, last_seen=51),
                "id": "npc_runtime_aleatorio",
            },
        },
        "event_log": [],
    }
    assert [
        row.check_id for row in check_entities(same_name_distinct_ids, None, 51)
    ] == ["entity.npc_duplicate_identity"]


def test_archivist_recusa_fato_e_resumo_com_identidade_trocada(monkeypatch) -> None:
    bad = "Skriit Mil-olhos é um homem alto de cabelo grisalho."

    class _Structured:
        def invoke(self, _messages):
            return MemoryUpdate(
                new_summary=bad, important_facts=[bad], chronicle_entry="",
            )

    class _LLM:
        def with_structured_output(self, _schema):
            return _Structured()

    writes: list[list[str]] = []
    monkeypatch.setattr(archivist, "get_llm", lambda **_kw: _LLM())
    monkeypatch.setattr(
        archivist,
        "add_memory_to_session",
        lambda _game_id, facts, **_kwargs: writes.append(list(facts)) or True,
    )
    out = archivist.archive_node({**_state(), "archive_due": True, "messages": []})
    assert writes == []
    assert out["memory_facts"] == []
    assert out["narrative_summary"] == "Skriit aguarda no Salão do Jarl."
    assert {row["reason"] for row in out["memory_rejections"]} == {
        "npc_identity_contradiction:Skriit Mil-olhos:species",
        "npc_identity_contradiction",
    }
