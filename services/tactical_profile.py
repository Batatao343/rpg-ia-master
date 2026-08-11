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
from copy import deepcopy
import unicodedata
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

# Tipos de comportamento (R3) e resistência a ordens (R4).
TIPOS = ("obrigatorio", "oferta", "restricao", "autonomo")
RESISTENCIAS = ("flexivel", "resistente", "absoluta", "autonoma")
TACTICAL_ACTION_KEYS = frozenset({
    "attack", "protect", "stabilize", "flank", "control", "support",
    "flee", "surrender",
})

# Condições que RETIRAM o comando do jogador sobre um personagem (R6).
LOSS_OF_COMMAND = frozenset({
    "medo", "confusao", "confusão", "controle_mental", "controle mental",
    "dominado", "enfeiticado", "separado",
})

# Arquétipos mecânicos de NPC são um catálogo fechado. Role/persona só escolhem
# uma entrada; nunca produzem diretamente uma regra de combate.
NPC_TACTICAL_FALLBACK = "equilibrado"
_NPC_TACTICAL_PROFILES: Dict[str, dict] = {
    "guardiao": {"priorities": [
        {"trigger": "aliado_em_perigo", "tipo": "obrigatorio",
         "action_key": "protect",
         "action_hint": "Protege o aliado em perigo e intercepta a ameaça.",
         "resistance": "resistente", "blocks": []},
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Mantém a posição e ataca quem ameaça seus protegidos.",
         "resistance": "resistente", "blocks": []},
    ]},
    "combatente": {"priorities": [
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Engaja o alvo mais próximo e sustenta a pressão.",
         "resistance": "flexivel", "blocks": []},
    ]},
    "batedor": {"priorities": [
        {"trigger": "sem_flanco", "tipo": "obrigatorio",
         "action_key": "flank",
         "action_hint": "Busca uma posição de flanco antes de atacar.",
         "resistance": "flexivel", "blocks": []},
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Ataca o alvo exposto a partir do flanco.",
         "resistance": "flexivel", "blocks": []},
    ]},
    "mistico": {"priorities": [
        {"trigger": "controle_disponivel", "tipo": "obrigatorio",
         "action_key": "control",
         "action_hint": "Impõe controle místico sobre a ameaça prioritária.",
         "resistance": "resistente", "blocks": []},
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Ataca à distância enquanto recompõe seu controle.",
         "resistance": "resistente", "blocks": []},
    ]},
    "suporte": {"priorities": [
        {"trigger": "aliado_terminal", "tipo": "obrigatorio",
         "action_key": "stabilize",
         "action_hint": "Estabiliza imediatamente o aliado em Estado Terminal.",
         "resistance": "resistente", "blocks": []},
        {"trigger": "aliado_ferido", "tipo": "obrigatorio",
         "action_key": "support",
         "action_hint": "Trata o aliado ferido e o mantém na luta.",
         "resistance": "resistente", "blocks": []},
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Ataca mantendo distância quando ninguém precisa de auxílio.",
         "resistance": "resistente", "blocks": []},
    ]},
    "estrategista": {"priorities": [
        {"trigger": "aliado_disponivel", "tipo": "obrigatorio",
         "action_key": "support",
         "action_hint": "Coordena o aliado para abrir uma vantagem tática.",
         "resistance": "resistente", "blocks": []},
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Ataca o alvo prioritário quando não há aliado para coordenar.",
         "resistance": "resistente", "blocks": []},
    ]},
    "oportunista": {"priorities": [
        {"trigger": "vitalidade_baixa", "tipo": "obrigatorio",
         "action_key": "flee",
         "action_hint": "Foge do combate quando a sobrevivência está em risco.",
         "resistance": "flexivel", "blocks": []},
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Ataca o alvo vulnerável e evita confronto desfavorável.",
         "resistance": "flexivel", "blocks": []},
    ]},
    NPC_TACTICAL_FALLBACK: {"priorities": [
        {"trigger": "sempre", "tipo": "obrigatorio",
         "action_key": "attack",
         "action_hint": "Ataca a ameaça principal sem abandonar uma posição segura.",
         "resistance": "flexivel", "blocks": []},
    ]},
}
NPC_TACTICAL_ARCHETYPES = frozenset(_NPC_TACTICAL_PROFILES)

_ENEMY_ARCHETYPE_ACTIONS: Dict[str, Dict[str, str]] = {
    # Conceitos materializados pelo gerador categórico.
    "equilibrado": {"sempre": "attack"},
    "bruto": {"muito_ferido": "flee", "sempre": "attack"},
    "agil": {"sempre": "flank"},
    "astuto": {"sempre": "support"},
    "mistico": {"sempre": "control"},
    # Arquétipos curados de data/bestiary.json.
    "conjurador": {
        "cercado": "flee", "muito_ferido": "flee", "sempre": "control",
    },
    "covarde_oportunista": {
        "sozinho": "surrender", "muito_ferido": "flee",
        "alvo_vulneravel": "flank", "sempre": "flank",
    },
    "emboscador": {
        "descoberto": "flank", "muito_ferido": "flee", "sempre": "attack",
    },
    "guardiao": {"muito_ferido": "protect", "sempre": "attack"},
    "lider_matilha": {
        "matilha_quebrada": "flee", "alvo_vulneravel": "support",
        "sempre": "support",
    },
    "morto_vivo_implacavel": {"sempre": "attack"},
    "predador": {
        "muito_ferido": "flee", "alvo_vulneravel": "attack",
        "sempre": "attack",
    },
    "predador_apice": {
        "plano_falhou": "flee", "alvo_vulneravel": "attack",
        "sempre": "attack",
    },
    "tatico": {
        "cercado": "flee", "muito_ferido": "flee",
        "alvo_vulneravel": "attack", "sempre": "attack",
    },
}
ENEMY_TACTICAL_ARCHETYPES = frozenset(_ENEMY_ARCHETYPE_ACTIONS)
PURSUIT_POLICIES = frozenset({"persegue", "nao_persegue"})
_PURSUIT_BY_ARCHETYPE = {
    archetype: (
        "persegue" if archetype in {
            "predador", "predador_apice", "lider_matilha",
            "morto_vivo_implacavel", "emboscador", "agil", "bruto",
        } else "nao_persegue"
    )
    for archetype in ENEMY_TACTICAL_ARCHETYPES
}

_NPC_ARCHETYPE_RULES = (
    ("guardiao", (
        "guarda", "guardiao", "sentinela", "protetor", "escolta",
        "defensor", "paladino", "vigia",
    )),
    ("suporte", (
        "curandeir", "medic", "herbal", "enfermeir", "clerig", "apoio",
    )),
    ("mistico", (
        "mago", "maga", "feiticeir", "brux", "ocult", "xama", "oracul",
        "alquim", "ritual",
    )),
    ("batedor", (
        "batedor", "explorador", "patrulheir", "arqueir", "cacador",
        "ladin", "assassin", "espiao", "furtiv", "agil",
    )),
    ("estrategista", (
        "capitao", "comandante", "estrateg", "conselheir", "diplomat",
        "lider", "lideranca", "tatic",
    )),
    ("oportunista", (
        "mercador", "comerciante", "contraband", "trapaceir", "vigar",
        "covard", "sobreviv",
    )),
    ("combatente", (
        "guerreir", "soldad", "mercen", "gladiador", "lutador", "barbar",
    )),
)


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
                "action_key": (
                    pr.get("action_key")
                    if pr.get("action_key") in TACTICAL_ACTION_KEYS
                    else None
                ),
                "action_hint": pr.get("action_hint", ""),
                "tipo": tipo,
                "resistance": pr.get("resistance", "flexivel"),
                "trigger": pr.get("trigger"),
                "requires_player_choice": tipo == "oferta",
                "autonomous": tipo == "autonomo",
                "matched": True,
            }
    return {"action_key": None, "action_hint": "", "tipo": None, "matched": False,
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
    action_key: Literal[
        "attack", "protect", "stabilize", "flank", "control", "support",
        "flee", "surrender",
    ] = "attack"
    action_hint: str = ""
    resistance: Literal["flexivel", "resistente", "absoluta", "autonoma"] = "flexivel"
    blocks: List[str] = Field(default_factory=list)


class TacticalProfileModel(BaseModel):
    priorities: List[PriorityModel] = Field(default_factory=list)


def _default_profile() -> dict:
    return {"priorities": [{"trigger": "sempre", "tipo": "obrigatorio",
                            "action_key": "attack",
                            "action_hint": "Ataca o alvo mais próximo e mais ameaçador.",
                            "resistance": "flexivel", "blocks": []}]}


def _normalize_archetype(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode().lower().strip()
    return ascii_value.replace("-", "_").replace(" ", "_")


def infer_npc_tactical_archetype(npc: dict) -> str:
    """Escolhe um arquétipo fechado; campo explícito válido tem precedência.

    Um valor explícito desconhecido cai diretamente no fallback seguro em vez
    de permitir que texto arbitrário crie um comportamento mecânico.
    """
    explicit = npc.get("tactical_archetype")
    if explicit is not None and str(explicit).strip():
        candidate = _normalize_archetype(explicit)
        return (candidate if candidate in NPC_TACTICAL_ARCHETYPES
                else NPC_TACTICAL_FALLBACK)

    text = _normalize_archetype(
        f"{npc.get('role', '')} {npc.get('persona', '')}")
    for archetype, keywords in _NPC_ARCHETYPE_RULES:
        if any(keyword in text for keyword in keywords):
            return archetype
    return NPC_TACTICAL_FALLBACK


def npc_profile_for_archetype(archetype: object) -> dict:
    """Materializa uma cópia do perfil fechado; nunca compartilha estado mutável."""
    key = _normalize_archetype(archetype)
    if key not in NPC_TACTICAL_ARCHETYPES:
        key = NPC_TACTICAL_FALLBACK
    return deepcopy(_NPC_TACTICAL_PROFILES[key])


def normalize_runtime_profile(actor: dict, profile: Optional[dict] = None) -> dict:
    """Preenche ``action_key`` dos perfis curados sem interpretar sua prosa.

    Só arquétipos e gatilhos presentes na tabela fechada são materializados.
    Perfil legado sem arquétipo reconhecido permanece sem chave e passa pelo
    fallback textual mínimo de fuga/rendição.
    """
    normalized = deepcopy(profile or actor.get("tactical_profile") or _default_profile())
    archetype = _normalize_archetype(actor.get("arquetipo"))
    actions = _ENEMY_ARCHETYPE_ACTIONS.get(archetype)
    if not actions:
        return normalized
    normalized["pursuit_policy"] = _PURSUIT_BY_ARCHETYPE.get(
        archetype, "nao_persegue"
    )
    fallback = actions.get("sempre", "attack")
    for priority in normalized.get("priorities", []) or []:
        if not isinstance(priority, dict):
            continue
        if priority.get("action_key") in TACTICAL_ACTION_KEYS:
            continue
        trigger = _normalize_archetype(priority.get("trigger") or "sempre")
        priority["action_key"] = actions.get(trigger, fallback)
    return normalized


def legacy_action_key(action_hint: object) -> str:
    """Compatibilidade fechada para perfis antigos sem ``action_key``.

    Só fuga/rendição têm vocabulário permitido; qualquer outra prosa vira ataque
    normal. Nenhuma mecânica nova é inferida do texto de apresentação.
    """
    tokens = {
        token for token in _normalize_archetype(action_hint).split("_") if token
    }
    if tokens & {"rende", "rendicao", "implora"}:
        return "surrender"
    if tokens & {"foge", "fugir", "recua", "escapa"}:
        return "flee"
    return "attack"


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
