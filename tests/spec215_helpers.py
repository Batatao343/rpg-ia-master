"""SPEC-215 — fixtures compartilhadas (estado determinístico p/ conhecimento de NPC)."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

KILL_EVENT = {
    "event_id": "ev_kill_valerius",
    "turn": 4,
    "type": "npc_killed",
    "actor_id": "player",
    "target_id": "npc_valerius",
    "payload": {},
    "source": "combat",
}


def pack_state(**over) -> dict:
    """Estado com um NPC morto em outra cidade + memória/resumo do jogador."""
    base = {
        "game_id": "spec215-game",
        "world": {
            "turn_count": 5,
            "current_location": "Nova Arcádia",
            "current_location_id": "nova_arcadia",
            "world_clock": {"day": 2, "period": "Tarde"},
        },
        "world_projection": {"entities": {"npc_valerius": {"alive": False}}},
        "event_log": [dict(KILL_EVENT)],
        "pending_world_events": [],
        "narrative_summary": "O herói matou Valerius no porto e fugiu ferido.",
        "memory_facts": [
            {
                "memory_id": "mem_player_1",
                "text": "O herói viu Valerius cair.",
                "provenance": "player_observation",
                "confidence": "confirmed",
                "source_id": "turn:4",
                "source_turn": 4,
                "canonical_entity_ids": ["npc_valerius"],
            }
        ],
        "npcs": {
            "Guarda": {
                "name": "Guarda",
                "id": "npc_guarda",
                "role": "guarda",
                "persona": "rude",
                "location": "nova_arcadia",
                "home_location_id": "nova_arcadia",
                "in_scene": True,
                "memory": [],
                "relationship": 5,
            }
        },
        "party": [],
        "messages": [HumanMessage(content="quem manda aqui?")],
    }
    base.update(over)
    return base


def stub_rag(monkeypatch):
    """Leitores RAG determinísticos (sem embeddings/rede)."""
    from services import context_builder as cb

    monkeypatch.setattr(cb, "RAG_AVAILABLE", True)
    monkeypatch.setattr(cb, "query_rag", lambda *a, **k: "Lore público de Nova Arcádia.")
    monkeypatch.setattr(
        cb,
        "query_session_memory",
        lambda *a, **k: "[CONFIRMADO | player_observation] sessão do jogador",
    )
    monkeypatch.setattr(
        cb, "query_npc_memory", lambda *a, **k: "[RELATADO | npc_claim] memória do guarda"
    )


def pack_text(pack) -> str:
    return "\n----\n".join([pack.world_state_block, pack.lore_block, pack.memory_block])
