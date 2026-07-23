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
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

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
    errors: List[str] = []
    objetos = scene.get("objects") or []
    obj_tokens = objetos  # abyss valida contra os próprios objetos da cena

    for o in objetos:
        if not str(o.get("base_narrativa") or "").strip():
            errors.append(f"Objeto '{o.get('id', o.get('name'))}' sem base narrativa (R8).")
        for it in (o.get("interactions") or []):
            if not cs.validate_effect_kind(it.get("effect") or {}):
                errors.append(f"Efeito fora do catálogo em '{o.get('id')}' (R4).")

    for ev in (scene.get("abyss_events") or []):
        if not abyss_events.validate_event_has_scene_basis(ev, obj_tokens):
            errors.append(f"Evento do Abismo '{ev.get('id')}' sem base na cena (R5).")

    return {"ok": not errors, "errors": errors}


# ==========================================================================
# Etapa 5 — geração pela LLM (guard) + cena simplificada de segurança (R9)
# ==========================================================================
class PreparedScene(BaseModel):
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
            scene["encounter_level"] = int(narrative_context.get("encounter_level", 1) or 1)
            if validate_preparation(scene)["ok"]:
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
    Ferimento (conflito-01), Esquiva, categoria e um `tactical_profile` default
    (o real vem da conflito-08)."""
    from services.conflict_resolution import compute_esquiva
    from services.tactical_profile import _default_profile

    virtudes = dict(npc.get("virtudes") or {"forca": 1, "agilidade": 1, "corpo": 1,
                                            "mente": 1, "carisma": 1})
    corpo = int(virtudes.get("corpo", 1) or 1)
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
        "tactical_profile": npc.get("tactical_profile") or _default_profile(),
        "status": "ativo",
    }
    return sheet


def gamedata_slug(name: str) -> str:
    return "npc_" + "".join(c if c.isalnum() else "_" for c in str(name).lower()).strip("_")
