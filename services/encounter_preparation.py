"""services/encounter_preparation.py — preparação de encontro pela LLM (spec conflito-11).

Move a montagem do encontro pra ANTES do conflito: a LLM transforma a cena
narrativa em cena JOGÁVEL (zonas, objetos, inimigos regionais, NPCs, reforços,
eventos do Abismo possíveis) usando SÓ o catálogo fechado (conflito-03) e
categorias de potência — nunca números livres. Depois a cena congela (conflito-03
R8) e o combate roda 100% sem LLM.

O que é 100% Python (determinístico, testado aqui): Nível do Encontro (R6),
validação de catálogo/base narrativa/região (R4/R7/R8), tabela de potência (R5) e
a cena simplificada de segurança (R9). A GERAÇÃO pela LLM usa o guard obrigatório.

ADITIVO: a mudança de GRAFO (mover `_spawn_enemies_integrated` pra fora do
`combat_node`, NPC nascer com ficha completa em `agents/npc.py`) é o cutover
(conflito-13). Aqui: motor puro + o builder de ficha de combate + testes.
"""
import json
import os
from copy import deepcopy
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

import gamedata
from services import conflict_scene as cs
from services import abyss_events

# R6: teto do Nível do Encontro (perigo ABSOLUTO — nunca depende da party).
ENCOUNTER_LEVEL_MAX = 10
_EVENT_TYPE_BONUS = {"comum": 0, "emboscada": 1, "cacada": 1, "ritual": 2,
                     "invasao": 2, "apex": 3, "chefe": 3}
_IMPORTANCE_BONUS = {"trivial": -1, "comum": 0, "importante": 1, "climax": 2}

_POTENCY: Optional[dict] = None


# ==========================================================================
# Etapa 1 — Nível do Encontro (Python puro, R6)
# ==========================================================================
def compute_encounter_level(*, location_danger: int = 1, region_danger: int = 1,
                            event_type: str = "comum", importance: str = "comum",
                            unique_threats: int = 0) -> int:
    """R6: Nível do Encontro = perigo ABSOLUTO do local/região/evento/importância/
    ameaças únicas. NÃO recebe nem considera o nível/força da party (decisão fechada
    do épico). O jogador nunca vê este número."""
    base = max(int(location_danger or 1), int(region_danger or 1))
    level = (base
             + _EVENT_TYPE_BONUS.get(str(event_type).lower(), 0)
             + _IMPORTANCE_BONUS.get(str(importance).lower(), 0)
             + int(unique_threats or 0))
    return max(1, min(ENCOUNTER_LEVEL_MAX, level))


# ==========================================================================
# Etapa 4 — Potência por categoria (R5)
# ==========================================================================
def _load_potency() -> dict:
    global _POTENCY
    if _POTENCY is None:
        path = os.path.join(gamedata.DATA_DIR, "potency_by_level.json")
        with open(path, encoding="utf-8") as f:
            _POTENCY = json.load(f)
    return _POTENCY


def potency_value(categoria: str, encounter_level: int, dimension: str = "dano") -> int:
    """R5: categoria (fraco/moderado/forte/devastador) + Nível do Encontro → valor
    real determinístico. valor = base + incremento*(nível-1)."""
    table = _load_potency().get("dimensoes", {}).get(dimension, {})
    pair = table.get(str(categoria).lower())
    if not pair:
        return 0
    base, slope = int(pair[0]), int(pair[1])
    return base + slope * max(0, int(encounter_level) - 1)


_NUMERIC_EFFECT_PARAMS = frozenset({
    "amount", "damage", "duration", "duracao", "dc", "difficulty",
    "count", "quantity", "cost", "custo",
})
_TARGETED_EFFECTS = frozenset({"damage", "apply_condition", "reposition"})
_POTENCY_DIMENSION = {
    "damage": ("amount", "dano"),
    "apply_condition": ("duration", "duracao"),
    "spawn_reinforcement": ("count", "reforcos"),
}


def materialize_effect(effect: dict, encounter_level: int, *,
                       valid_targets: Optional[set[str]] = None) -> Optional[dict]:
    """Materializa um EffectSpec categórico. Números recebidos são sempre
    descartados e recalculados; assim nem um dict aberto vindo de provider
    consegue dirigir a mecânica."""
    if not cs.validate_effect_kind(effect):
        return None
    kind = str(effect.get("kind"))
    raw_params = effect.get("params") if isinstance(effect.get("params"), dict) else {}
    category = str(
        effect.get("potency")
        or raw_params.get("potency")
        or raw_params.get("potencia")
        or "moderado"
    ).strip().lower()
    categories = set(_load_potency().get("categorias") or [])
    if category not in categories:
        return None

    params = {
        str(key): value for key, value in raw_params.items()
        if str(key) not in _NUMERIC_EFFECT_PARAMS
        and str(key) not in {"potency", "potencia"}
    }
    target = params.get("target")
    if kind in _TARGETED_EFFECTS:
        if not isinstance(target, str) or not target.strip():
            return None
        if valid_targets is not None and target not in valid_targets:
            return None

    numeric = _POTENCY_DIMENSION.get(kind)
    if numeric:
        field, dimension = numeric
        params[field] = potency_value(category, encounter_level, dimension)

    return {
        "kind": kind,
        "potency": category,
        "params": params,
        "_mechanical_origin": "potency_by_level",
    }


def _scene_target_ids(scene: dict) -> set[str]:
    """IDs mecânicos de entidades declaradas, nunca da geometria proposta.

    ``positions`` pertence à saída livre da LLM e, portanto, não prova que um
    participante existe. Identidade canônica vem apenas das coleções de atores
    que atravessaram a borda de preparação.
    """
    ids = {"player"}
    for collection in ("enemies", "npcs"):
        for actor in scene.get(collection) or []:
            if isinstance(actor, dict) and (actor.get("id") or actor.get("name")):
                ids.add(str(actor.get("id") or actor.get("name")))
    return ids


def normalize_prepared_scene(scene: dict, encounter_level: int) -> dict:
    """Normaliza toda saída da LLM antes da validação/congelamento.

    Efeitos inválidos tornam a cena inválida (fallback seguro) em vez de serem
    aplicados parcialmente. Custos/quantidades livres de evento e objeto também
    são substituídos por valores derivados/constantes do contrato.
    """
    out = deepcopy(scene or {})
    errors: List[str] = []
    targets = _scene_target_ids(out)

    def normalize_holder(holder: dict, label: str) -> None:
        effect = holder.get("effect")
        if not isinstance(effect, dict):
            return
        normalized = materialize_effect(effect, encounter_level, valid_targets=targets)
        if normalized is None:
            errors.append(f"Efeito inválido em {label}.")
        else:
            holder["effect"] = normalized

    for obj in out.get("objects") or []:
        if not isinstance(obj, dict):
            errors.append("Objeto preparado não é um objeto JSON.")
            continue
        # Objetos preparados são consumíveis por contrato. A ausência da chave
        # significava uso infinito em conflict_scene.apply_object_interaction.
        obj["uses_remaining"] = 1
        for interaction in obj.get("interactions") or []:
            if isinstance(interaction, dict):
                normalize_holder(interaction, f"objeto {obj.get('id', '?')}")
            else:
                errors.append(f"Interação inválida em objeto {obj.get('id', '?')}.")

    potency_rank = {"fraco": 0, "moderado": 1, "forte": 2, "devastador": 3}
    for index, event in enumerate(out.get("abyss_events") or []):
        if not isinstance(event, dict):
            errors.append("Evento do Abismo preparado não é um objeto JSON.")
            continue
        normalize_holder(event, f"evento {event.get('id', index)}")
        effect = event.get("effect") if isinstance(event.get("effect"), dict) else {}
        category = str(effect.get("potency") or "moderado")
        event["prioridade"] = max(1, len(out.get("abyss_events") or []) - index)
        event["cargas_necessarias"] = potency_rank.get(category, 1)
        event["usos_permitidos"] = 1

    for index, trigger in enumerate(out.get("reinforcement_triggers") or []):
        if isinstance(trigger, dict):
            trigger["order"] = index
            normalize_holder(trigger, f"reforço {trigger.get('id', index)}")
        else:
            errors.append("Gatilho de reforço preparado não é um objeto JSON.")

    out["_normalization_errors"] = errors
    out["encounter_level"] = max(1, min(ENCOUNTER_LEVEL_MAX, int(encounter_level or 1)))
    return out


# ==========================================================================
# Etapa 3 — seleção de criatura por região (R7)
# ==========================================================================
def validate_creature_selection(creature: dict, region: str, *,
                                event_justification: bool = False,
                                authorized_variant: bool = False,
                                canonical_introduction: bool = False) -> bool:
    """R7: criatura respeita a região — associada à região, justificada pelo evento,
    variante autorizada, ou introduzida por acontecimento canônico. Fora de região
    sem razão de mundo = rejeitada (nunca por conveniência de balanceamento)."""
    regions = {str(r).lower() for r in (creature.get("regions") or creature.get("regioes") or [])}
    if str(region).lower() in regions:
        return True
    return bool(event_justification or authorized_variant or canonical_introduction)


# ==========================================================================
# Etapa 2 — validação da cena preparada (R4/R8) + eventos do Abismo (R10/§10)
# ==========================================================================
def validate_preparation(scene: dict) -> dict:
    """R4/R8: efeitos só do catálogo fechado; objeto interativo só com base
    narrativa; evento do Abismo só com base na cena. Retorna {ok, errors}."""
    errors: List[str] = list(scene.get("_normalization_errors") or [])
    objetos = scene.get("objects") or []
    obj_tokens = objetos  # abyss valida contra os próprios objetos da cena

    for o in objetos:
        if not str(o.get("base_narrativa") or "").strip():
            errors.append(f"Objeto '{o.get('id', o.get('name'))}' sem base narrativa (R8).")
        for it in (o.get("interactions") or []):
            effect = it.get("effect") or {}
            if not cs.validate_effect_kind(effect):
                errors.append(f"Efeito fora do catálogo em '{o.get('id')}' (R4).")
            elif (str(effect.get("kind")) in _POTENCY_DIMENSION
                  and effect.get("_mechanical_origin") != "potency_by_level"):
                errors.append(f"Efeito numérico não materializado em '{o.get('id')}'.")
            elif effect.get("_mechanical_origin") == "potency_by_level":
                expected = materialize_effect(
                    effect,
                    int(scene.get("encounter_level", 1) or 1),
                    valid_targets=_scene_target_ids(scene),
                )
                if expected != effect:
                    errors.append(f"Efeito mecânico inconsistente em '{o.get('id')}'.")

    for ev in (scene.get("abyss_events") or []):
        if not abyss_events.validate_event_has_scene_basis(ev, obj_tokens):
            errors.append(f"Evento do Abismo '{ev.get('id')}' sem base na cena (R5).")
        effect = ev.get("effect") or {}
        if effect and not cs.validate_effect_kind(effect):
            errors.append(f"Evento do Abismo '{ev.get('id')}' tem efeito fora do catálogo.")
        elif (str(effect.get("kind")) in _POTENCY_DIMENSION
              and effect.get("_mechanical_origin") != "potency_by_level"):
            errors.append(f"Evento do Abismo '{ev.get('id')}' não foi materializado.")

    return {"ok": not errors, "errors": errors}


# ==========================================================================
# Etapa 5 — geração pela LLM (guard) + cena simplificada de segurança (R9)
# ==========================================================================
class PreparedScene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: List[Dict] = Field(default_factory=list)
    positions: Dict[str, Dict] = Field(default_factory=dict)
    enemies: List[Dict] = Field(default_factory=list)
    npcs: List[Dict] = Field(default_factory=list)
    objects: List[Dict] = Field(default_factory=list)
    reinforcement_triggers: List[Dict] = Field(default_factory=list)
    objectives: List[str] = Field(default_factory=list)
    ending_conditions: List[str] = Field(default_factory=list)
    abyss_events: List[Dict] = Field(default_factory=list)


def fallback_safe_scene(context: Optional[dict] = None) -> dict:
    """R9: cena simplificada DETERMINÍSTICA quando toda a cadeia de providers falha
    — sem zonas/objetos elaborados, sem inventar nada. O conflito nunca trava sem
    começar. Inimigos vêm do contexto (já nomeados na narrativa)."""
    ctx = context or {}
    enemies = list(ctx.get("enemies") or [])
    scene = cs.new_scene([{"id": "z0", "name": ctx.get("location", "Campo"), "connections": []}])
    scene["objects"] = []
    scene["enemies"] = enemies
    scene["npcs"] = list(ctx.get("npcs") or [])
    scene["objectives"] = []
    scene["ending_conditions"] = []
    scene["abyss_events"] = []
    scene["encounter_level"] = int(ctx.get("encounter_level", 1) or 1)
    scene["safe_fallback"] = True
    return scene


def prepare_encounter(narrative_context: dict, llm) -> dict:
    """R1/R2/R9: pede à LLM a cena jogável (structured output) e VALIDA (R4/R7/R8);
    resultado inválido, `FallbackLLM` ou erro → cena simplificada de segurança
    (R9). GUARD obrigatório. O fallback ENTRE providers é do `RoutedLLM`/`ROUTES`
    (llm_setup) — aqui só se garante que, esgotada a cadeia, nada trava."""
    try:
        result = llm.with_structured_output(PreparedScene).invoke(_prep_prompt(narrative_context))
        if isinstance(result, PreparedScene):
            scene = result.model_dump()
            # IDs mecânicos já conhecidos entram no conjunto de alvos válidos.
            scene["enemies"] = list(narrative_context.get("enemies") or scene.get("enemies") or [])
            scene["npcs"] = list(narrative_context.get("npcs") or scene.get("npcs") or [])
            scene = normalize_prepared_scene(
                scene, int(narrative_context.get("encounter_level", 1) or 1))
            if validate_preparation(scene)["ok"]:
                scene.pop("_normalization_errors", None)
                return scene
    except Exception:
        pass
    return fallback_safe_scene(narrative_context)


def _prep_prompt(ctx: dict) -> str:
    return (
        "Transforme a cena narrativa a seguir numa cena de conflito JOGÁVEL de "
        "Valoria: zonas + ligações, posições iniciais, Engajamentos, inimigos do "
        "bestiário regional, NPCs, objetos interativos (só coerentes com a cena já "
        "narrada) e efeitos SÓ do catálogo fechado. Use categorias de potência "
        "(fraco/moderado/forte/devastador), nunca números.\n"
        f"Contexto: {ctx}."
    )


# ==========================================================================
# Etapa 6 — NPC nasce com ficha de combate completa (R10)
# ==========================================================================
def build_npc_combat_sheet(npc: dict) -> dict:
    """R10: dá a um NPC gerado no roleplay a ficha de combate COMPLETA desde a
    criação (não o `combat_stats` rudimentar) — Virtudes, Vitalidade/espaços de
    Ferimento (conflito-01), Esquiva, categoria e perfil específico materializado
    por um arquétipo tático fechado."""
    from services.conflict_resolution import compute_esquiva
    from services.tactical_profile import (
        infer_npc_tactical_archetype,
        npc_profile_for_archetype,
    )

    virtudes = dict(npc.get("virtudes") or {"forca": 1, "agilidade": 1, "corpo": 1,
                                            "mente": 1, "carisma": 1})
    corpo = int(virtudes.get("corpo", 1) or 1)
    tactical_archetype = infer_npc_tactical_archetype(npc)
    sheet = {
        "id": npc.get("id") or gamedata_slug(npc.get("name", "npc")),
        "name": npc.get("name", "NPC"),
        "virtudes": virtudes,
        "vitalidade": gamedata.vitalidade_para_corpo(corpo),
        "max_vitalidade": gamedata.vitalidade_para_corpo(corpo),
        "ferimento_espacos": gamedata.espacos_ferimento_para_corpo(corpo),
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "esquiva": compute_esquiva({"virtudes": virtudes}),
        "categoria": npc.get("categoria", "padrao"),
        "active_conditions": [],
        "tactical_archetype": tactical_archetype,
        "tactical_profile": npc_profile_for_archetype(tactical_archetype),
        "status": "ativo",
    }
    return sheet


def gamedata_slug(name: str) -> str:
    return "npc_" + "".join(c if c.isalnum() else "_" for c in str(name).lower()).strip("_")
