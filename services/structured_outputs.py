"""
structured_outputs.py — Schemas Pydantic de PROPOSTA de mudança no mundo (Fase 2.6).

Princípio: *LLM propõe, motor aplica.* O agente devolve um `ProposedWorldEvent`
(ou uma lista deles); nada disso altera o mundo até passar por
`services.world_validators.validate_proposal` e `services.event_processor`.

Spec: specs/SPEC-003-fase-2.6-structured-events.md §3.
"""

from __future__ import annotations

from typing import Dict, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "npc_killed",
    "secret_revealed",
    "location_control_changed",
    "quest_completed",
    "faction_relation_changed",
    "reputation_changed",
    # SPEC-298 R11: feito do jogador a favor/contra uma fação. SÓ o storyteller (Python,
    # source="storyteller") enfileira; o validador exige a fação em cena.
    "faction_deed",
    # Fase 4.1: gerado 100% em Python (progression.grant_xp). O LLM não consegue
    # propor: validate_proposal exige source="progression", e o schema de proposta
    # do LLM não tem campo source (model_dump nunca o carrega).
    "level_up",
    "subclass_chosen",
    "class_apex_unlocked",
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
    # SPEC-302: SO o motor de mundo emite (source="engine" no validator).
    "location_state_changed",
    "world_crisis_warning",
    # SPEC-300: partida/traição/destino off-screen de companheiro — SÓ o motor emite
    # (source="engine" no validator); o LLM nunca decide quem sai do grupo.
    "companion_left",
    "companion_betrayed",
    "companion_fate",
    # SPEC-299: lei e crime. SÓ o motor emite (source="law" exigido no validator).
    "crime_witnessed",
    "law_resolved",
    # SPEC-301: vínculo do jogador com fação (join/promote/leave/betray/dissolve).
    # SÓ o motor emite (source="engine" exigido no validator).
    "faction_membership_changed",
    # SPEC-305 R15: falha de quest por prazo — SO o motor (source engine/system).
    "quest_failed",
    # SPEC-305 R13: alívio de quest de mundo concluída — SO derivado (event_processor).
    "world_quest_relief",
    # SPEC-304: NPCs off-screen — SO o motor emite (source="engine" no validator).
    "npc_peril_warning",
    "npc_offscreen_fate",
    "npc_defected",
    "npc_fate_learned",
]


class ProposedWorldEvent(BaseModel):
    type: EventType
    actor_id: str = Field(default="player", description="Quem causou. 'player' ou id canônico.")
    target_id: str = Field(description="Entidade afetada — id EXATO de entities.json.")
    detail: str = Field(default="", description="1 frase objetiva do que aconteceu.")
    payload: dict = Field(
        default_factory=dict, description="Dados extras por tipo (ex.: new_controller_id)."
    )


class ProposedQuest(BaseModel):
    """Proposta de SIDE QUEST nova (Fase 3.3) — criação, não conclusão.

    Conclusão de quest reusa `ProposedWorldEvent(type="quest_completed",
    target_id=<quest_id>, payload={"quest_id": ...})`, não este schema.
    """

    title: str
    description: str = ""
    origin_name: str = Field(
        default="", description="Quem/o que originou a missão (nome exibível)."
    )
    origin_entity_id: str = Field(
        default="", description="Id canônico EXATO de entities.json, ou vazio."
    )
    location_id: str = Field(
        default="", description="Id de local EXATO de world_map.json, ou vazio."
    )
    reward_hint: str = ""


class CrimeClaim(BaseModel):
    """SPEC-299 R4(a): crime que a AÇÃO do jogador cometeu neste turno. O motor valida
    (catálogo fechado, vítima em cena, suporte lexical na ação) antes de aceitar."""

    crime_type: Literal["furto", "agressao", "homicidio", "dano_propriedade", "magia_ilegal"]
    victim: str = Field(
        default="",
        description="Nome EXATO de quem está na cena, 'local' para propriedade, ou vazio.",
    )
    covert: bool = Field(default=False, description="True só se a ação foi às escondidas.")


CRIME_CLAIM_TYPES = ("furto", "agressao", "homicidio", "dano_propriedade", "magia_ilegal")


def coerce_crime_claims(raw: object) -> list:
    """SPEC-299 R7: item com ``crime_type`` fora do catálogo é DESCARTADO, nunca derruba a
    resposta inteira (padrão SPEC-045)."""
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if isinstance(item, CrimeClaim):
            out.append(item)
        elif isinstance(item, dict) and item.get("crime_type") in CRIME_CLAIM_TYPES:
            out.append(item)
    return out
