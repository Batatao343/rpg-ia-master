"""services/tactical_profile.py — perfil tático persistido (spec conflito-08).

UMA estrutura de dados, DOIS consumidores (risco §7 da spec): decidir a IA de um
inimigo (`pick_action`) e validar as ordens do jogador sobre companheiros
(`validate_companion_order`). O perfil é gerado 1× por uma LLM robusta na CRIAÇÃO
(`generate_tactical_profile`, com guard) e persiste na ficha — NUNCA se roda LLM em
tempo real de combate.

ADITIVO (como 03-07): módulo novo + testes. A remoção de `get_behavior`/perfis
fixos de `combat_mechanics.py` e a fiação em `agents/bestiary.py` vão no cutover
(conflito-13); aqui o motor puro convive com o antigo.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Tipos de comportamento (R3) e resistência a ordens (R4).
TIPOS = ("obrigatorio", "oferta", "restricao", "autonomo")
RESISTENCIAS = ("flexivel", "resistente", "absoluta", "autonoma")

# Condições que RETIRAM o comando do jogador sobre um personagem (R6).
LOSS_OF_COMMAND = frozenset({
    "medo", "confusao", "confusão", "controle_mental", "controle mental",
    "dominado", "enfeiticado", "separado",
})


# ==========================================================================
# Etapa 1 — pick_action (IA de inimigo por prioridade ordenada)
# ==========================================================================
def _trigger_valid(trigger: str, scene_state: dict) -> bool:
    """Um gatilho é válido quando 'sempre' ou quando `scene_state[trigger]` é
    verdadeiro. Gatilhos computados ficam a cargo do chamador (que preenche o
    scene_state) — o motor não interpreta texto livre (mecânica é Python)."""
    t = str(trigger or "").strip().lower()
    if t in ("sempre", "always", ""):
        return True
    return bool((scene_state or {}).get(t))


def pick_action(profile: dict, scene_state: Optional[dict] = None) -> dict:
    """R1/R2: devolve a decisão da PRIMEIRA prioridade cujo gatilho é válido —
    ordem = precedência. Cobre ação/alvo/recurso/reação/fuga/rendição via
    `action_hint`. 'oferta' pede escolha ao jogador; 'obrigatorio' executa sem
    escolha. Sem prioridade válida → decisão nula (o chamador aplica o default)."""
    scene = scene_state or {}
    for pr in profile.get("priorities", []) or []:
        if _trigger_valid(pr.get("trigger"), scene):
            tipo = pr.get("tipo", "obrigatorio")
            return {
                "action_hint": pr.get("action_hint", ""),
                "tipo": tipo,
                "resistance": pr.get("resistance", "flexivel"),
                "trigger": pr.get("trigger"),
                "requires_player_choice": tipo == "oferta",
                "autonomous": tipo == "autonomo",
                "matched": True,
            }
    return {"action_hint": "", "tipo": None, "matched": False,
            "requires_player_choice": False, "autonomous": False}


# ==========================================================================
# Etapa 2 — validação de ordem de companheiro
# ==========================================================================
def validate_companion_order(companion: dict, order: dict) -> dict:
    """R3/R4/R6: valida uma ordem do jogador contra o perfil do companheiro. Uma
    Restrição cujos `blocks` batem com as `tags` da ordem só é vencida conforme a
    resistência — Flexível cede sempre; Resistente cede só com `leverage` (lealdade/
    efeito apropriado); Absoluta/Autônoma nunca. Recusa NUNCA crasha: devolve a
    escolha ao jogador."""
    profile = companion.get("tactical_profile") or {}
    order_tags = set(order.get("tags") or [])
    for pr in profile.get("priorities", []) or []:
        if pr.get("tipo") != "restricao":
            continue
        if not (set(pr.get("blocks") or []) & order_tags):
            continue
        resist = str(pr.get("resistance", "flexivel")).lower()
        if resist == "flexivel":
            continue                                   # contrariável normalmente
        if resist == "resistente" and order.get("leverage"):
            continue                                   # lealdade/efeito apropriado
        return {"accepted": False, "return_choice_to_player": True,
                "resistance": resist,
                "reason": pr.get("action_hint") or "O companheiro recusa a ordem."}
    return {"accepted": True, "return_choice_to_player": False, "reason": ""}


# ==========================================================================
# Etapa 3 — controle de party / perda de controle (R6)
# ==========================================================================
def loses_command(member: dict) -> bool:
    """R6: True se o personagem saiu de controle por condição EXPLÍCITA
    (medo/confusão/controle mental/inconsciência/separação não acompanhada)."""
    if not member.get("conscious", True) or member.get("incapacitated"):
        return True
    for c in member.get("active_conditions", []) or []:
        name = str(c.get("name", "")).strip().lower()
        if name in LOSS_OF_COMMAND or c.get("removes_command"):
            return True
    return False


def player_controls_member(member: dict) -> bool:
    """R6: o jogador comanda o membro enquanto nenhuma condição explícita o tirar."""
    return not loses_command(member)


def profile_takes_over(member: dict) -> bool:
    """R3/R6: o perfil (Autônomo) assume o turno SÓ quando o comando é retirado."""
    return loses_command(member)


def player_retains_party_control(party: List[dict]) -> bool:
    """R6: o jogador mantém o controle da party enquanto QUALQUER membro consciente
    e comandável estiver no conflito — mesmo com o protagonista fora."""
    return any(player_controls_member(m) for m in (party or []))


# ==========================================================================
# Etapa 4 — geração do perfil (LLM robusta, 1×, persistida) — guard obrigatório
# ==========================================================================
class PriorityModel(BaseModel):
    trigger: str
    tipo: Literal["obrigatorio", "oferta", "restricao", "autonomo"] = "obrigatorio"
    action_hint: str = ""
    resistance: Literal["flexivel", "resistente", "absoluta", "autonoma"] = "flexivel"
    blocks: List[str] = Field(default_factory=list)


class TacticalProfileModel(BaseModel):
    priorities: List[PriorityModel] = Field(default_factory=list)


def _default_profile() -> dict:
    return {"priorities": [{"trigger": "sempre", "tipo": "obrigatorio",
                            "action_hint": "Ataca o alvo mais próximo e mais ameaçador.",
                            "resistance": "flexivel", "blocks": []}]}


def generate_tactical_profile(archetype: str, llm, *, context: Optional[dict] = None) -> dict:
    """R5: gera o perfil tático via LLM robusta (tier SMART), com o GUARD de
    resiliência obrigatório — `FallbackLLM`/erro cai num perfil default
    determinístico. Chamado UMA vez na criação, nunca em combate."""
    prompt = (
        "Gere um perfil tático de combate para o arquétipo de Valoria a seguir, como "
        "uma lista ORDENADA de prioridades (a primeira cujo gatilho vale prevalece). "
        "Cada prioridade: trigger, tipo (obrigatorio|oferta|restricao|autonomo), "
        "action_hint, resistance (flexivel|resistente|absoluta|autonoma), blocks "
        "(tags de ordem que uma Restrição impede).\n"
        f"Arquétipo: {archetype}. Contexto: {context or {}}."
    )
    try:
        result = llm.with_structured_output(TacticalProfileModel).invoke(prompt)
        if isinstance(result, TacticalProfileModel) and result.priorities:
            return result.model_dump()
    except Exception:
        pass
    return _default_profile()


def get_or_generate_profile(entry: dict, archetype: str, llm, *,
                            context: Optional[dict] = None) -> dict:
    """Cacheia agressivamente (risco §7): se a ficha JÁ tem `tactical_profile`,
    reusa sem tocar no LLM; senão gera 1× e grava na ficha."""
    existing = entry.get("tactical_profile")
    if existing:
        return existing
    profile = generate_tactical_profile(archetype, llm, context=context)
    entry["tactical_profile"] = profile
    return profile
