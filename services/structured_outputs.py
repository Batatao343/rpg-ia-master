"""
structured_outputs.py — Schemas Pydantic de PROPOSTA de mudança no mundo (Fase 2.6).

Princípio: *LLM propõe, motor aplica.* O agente devolve um `ProposedWorldEvent`
(ou lista, via `WorldChangeProposal`); nada disso altera o mundo até passar por
`services.world_validators.validate_proposal` e `services.event_processor`.

Spec: specs/fase-2.6-structured-events.md §3.
"""

from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "npc_killed",
    "secret_revealed",
    "location_control_changed",
    "quest_completed",
    "faction_relation_changed",
    "reputation_changed",
    # Fase 4.1: gerado 100% em Python (progression.grant_xp). O LLM não consegue
    # propor: validate_proposal exige source="progression", e o schema de proposta
    # do LLM não tem campo source (model_dump nunca o carrega).
    "level_up",
    # Fase 4.6: idem — gerado só pelo combate (source="combat" exigido no validator).
    "player_died",
    # spec balanceamento-early-game (R3): "O Saque" — 1ª queda da campanha vira
    # downed em vez de morte. Só o combate emite (source="combat" no validator).
    "player_downed",
    # Fase 6.1: rotas comerciais — PROPONÍVEL pelo LLM (desabamento, bloqueio
    # militar) e gerável pelo motor/regras; validator exige conexão direta real.
    "route_blocked",
    "route_cleared",
    # Fase 6.2: itens únicos — SÓ o motor emite (source="engine" no validator);
    # o LLM nunca decide quem possui um artefato único.
    "unique_item_claimed",
    "unique_item_lost",
]


class ProposedWorldEvent(BaseModel):
    type: EventType
    actor_id: str = Field(default="player", description="Quem causou. 'player' ou id canônico.")
    target_id: str = Field(description="Entidade afetada — id EXATO de entities.json.")
    detail: str = Field(default="", description="1 frase objetiva do que aconteceu.")
    payload: Dict = Field(default_factory=dict, description="Dados extras por tipo (ex.: new_controller_id).")


class WorldChangeProposal(BaseModel):
    events: List[ProposedWorldEvent] = Field(default_factory=list)
    reason: str = Field(default="", description="Por que a narrativa implica essas mudanças.")


class ProposedQuest(BaseModel):
    """Proposta de SIDE QUEST nova (Fase 3.3) — criação, não conclusão.

    Conclusão de quest reusa `ProposedWorldEvent(type="quest_completed",
    target_id=<quest_id>, payload={"quest_id": ...})`, não este schema.
    """
    title: str
    description: str = ""
    origin_name: str = Field(default="", description="Quem/o que originou a missão (nome exibível).")
    origin_entity_id: str = Field(default="", description="Id canônico EXATO de entities.json, ou vazio.")
    location_id: str = Field(default="", description="Id de local EXATO de world_map.json, ou vazio.")
    reward_hint: str = ""
