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
from observability.telemetry import log_event as _log_event
from services import abyss_events
from services import conflict_scene as cs

# R6: teto do Nível do Encontro (perigo ABSOLUTO — nunca depende da party).
ENCOUNTER_LEVEL_MAX = 10
_EVENT_TYPE_BONUS = {
    "comum": 0,
    "emboscada": 1,
    "cacada": 1,
    "ritual": 2,
    "invasao": 2,
    "apex": 3,
    "chefe": 3,
}
_IMPORTANCE_BONUS = {"trivial": -1, "comum": 0, "importante": 1, "climax": 2}

_POTENCY: dict | None = None


# ==========================================================================
# Etapa 1 — Nível do Encontro (Python puro, R6)
# ==========================================================================
def compute_encounter_level(
    *,
    location_danger: int = 1,
    region_danger: int = 1,
    event_type: str = "comum",
    importance: str = "comum",
    unique_threats: int = 0,
) -> int:
    """R6: Nível do Encontro = perigo ABSOLUTO do local/região/evento/importância/
    ameaças únicas. NÃO recebe nem considera o nível/força da party (decisão fechada
    do épico). O jogador nunca vê este número."""
    base = max(int(location_danger or 1), int(region_danger or 1))
    level = (
        base
        + _EVENT_TYPE_BONUS.get(str(event_type).lower(), 0)
        + _IMPORTANCE_BONUS.get(str(importance).lower(), 0)
        + int(unique_threats or 0)
    )
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


_NUMERIC_EFFECT_PARAMS = frozenset(
    {
        "amount",
        "damage",
        "duration",
        "duracao",
        "dc",
        "difficulty",
        "count",
        "quantity",
        "cost",
        "custo",
    }
)
_TARGETED_EFFECTS = frozenset({"damage", "apply_condition", "reposition"})
_POTENCY_DIMENSION = {
    "damage": ("amount", "dano"),
    "apply_condition": ("duration", "duracao"),
    "spawn_reinforcement": ("count", "reforcos"),
}


def materialize_effect(
    effect: dict, encounter_level: int, *, valid_targets: set[str] | None = None
) -> dict | None:
    """Materializa um EffectSpec categórico. Números recebidos são sempre
    descartados e recalculados; assim nem um dict aberto vindo de provider
    consegue dirigir a mecânica."""
    if not cs.validate_effect_kind(effect):
        return None
    kind = str(effect.get("kind"))
    raw_params = effect.get("params") if isinstance(effect.get("params"), dict) else {}
    category = (
        str(
            effect.get("potency")
            or raw_params.get("potency")
            or raw_params.get("potencia")
            or "moderado"
        )
        .strip()
        .lower()
    )
    categories = set(_load_potency().get("categorias") or [])
    if category not in categories:
        return None

    params = {
        str(key): value
        for key, value in raw_params.items()
        if str(key) not in _NUMERIC_EFFECT_PARAMS and str(key) not in {"potency", "potencia"}
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
    errors: list[str] = []
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
def validate_creature_selection(
    creature: dict,
    region: str,
    *,
    event_justification: bool = False,
    authorized_variant: bool = False,
    canonical_introduction: bool = False,
) -> bool:
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
    errors: list[str] = list(scene.get("_normalization_errors") or [])
    objetos = scene.get("objects") or []
    obj_tokens = objetos  # abyss valida contra os próprios objetos da cena

    for o in objetos:
        if not str(o.get("base_narrativa") or "").strip():
            errors.append(f"Objeto '{o.get('id', o.get('name'))}' sem base narrativa (R8).")
        for it in o.get("interactions") or []:
            effect = it.get("effect") or {}
            if not cs.validate_effect_kind(effect):
                errors.append(f"Efeito fora do catálogo em '{o.get('id')}' (R4).")
            elif (
                str(effect.get("kind")) in _POTENCY_DIMENSION
                and effect.get("_mechanical_origin") != "potency_by_level"
            ):
                errors.append(f"Efeito numérico não materializado em '{o.get('id')}'.")
            elif effect.get("_mechanical_origin") == "potency_by_level":
                expected = materialize_effect(
                    effect,
                    int(scene.get("encounter_level", 1) or 1),
                    valid_targets=_scene_target_ids(scene),
                )
                if expected != effect:
                    errors.append(f"Efeito mecânico inconsistente em '{o.get('id')}'.")

    for ev in scene.get("abyss_events") or []:
        if not abyss_events.validate_event_has_scene_basis(ev, obj_tokens):
            errors.append(f"Evento do Abismo '{ev.get('id')}' sem base na cena (R5).")
        effect = ev.get("effect") or {}
        if effect and not cs.validate_effect_kind(effect):
            errors.append(f"Evento do Abismo '{ev.get('id')}' tem efeito fora do catálogo.")
        elif (
            str(effect.get("kind")) in _POTENCY_DIMENSION
            and effect.get("_mechanical_origin") != "potency_by_level"
        ):
            errors.append(f"Evento do Abismo '{ev.get('id')}' não foi materializado.")

    return {"ok": not errors, "errors": errors}


# ==========================================================================
# Etapa 5 — geração pela LLM (guard) + cena simplificada de segurança (R9)
# ==========================================================================
# SPEC-232 R10 (smoke real 2026-10-16): o schema antigo (dicts abertos +
# posições/inimigos/NPCs/reforços) fazia o provider gerar ~1.8k tokens de
# prosa fora do contrato (DeepSeek estourava o timeout; a cena voltava sem
# `base_narrativa` e caía no fallback). Agora o schema é ENXUTO e TIPADO — só o
# que o motor consome (zonas, objetos com interação do catálogo, eventos do
# Abismo, objetivos). Sem limites duros: tamanho/quantidade truncados em Python
# (`_trim_prepared`). Posições, inimigos e NPCs vêm do Python, nunca da LLM;
# reforços/condições de fim não têm consumidor no loop e saíram do pedido.
class PreparedEffectParams(BaseModel):
    model_config = ConfigDict(extra="ignore")
    target: str | None = Field(
        None, description="id de um participante listado (só p/ damage/apply_condition/reposition)"
    )
    condition: str | None = Field(None, description="nome da condição (apply_condition)")


class PreparedEffect(BaseModel):
    model_config = ConfigDict(extra="ignore")
    kind: str = Field(description="um kind do catálogo fechado")
    potency: str = Field("moderado", description="fraco|moderado|forte|devastador")
    params: PreparedEffectParams = Field(default_factory=PreparedEffectParams)


class PreparedInteraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str = Field(description="verbo curto, ex.: derrubar")
    effect: PreparedEffect


class PreparedObject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str = ""
    base_narrativa: str = Field("", description="onde o objeto aparece na cena (curto)")
    interactions: list[PreparedInteraction] = Field(default_factory=list)


class PreparedZone(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str = ""
    connections: list[str] = Field(default_factory=list)


class PreparedAbyssEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    base_na_cena: str = Field(description="id de um objeto da cena")
    effect: PreparedEffect


class PreparedScene(BaseModel):
    model_config = ConfigDict(extra="ignore")

    zones: list[PreparedZone] = Field(default_factory=list, description="1 a 3 zonas")
    objects: list[PreparedObject] = Field(default_factory=list, description="0 a 2 objetos")
    abyss_events: list[PreparedAbyssEvent] = Field(
        default_factory=list, description="0 ou 1 evento"
    )
    objectives: list[str] = Field(default_factory=list, description="até 2, curtos")


class PreparedObjective(BaseModel):
    """SPEC-331 R4: objetivo do catálogo fechado (tipo + alvo/n opcionais)."""

    model_config = ConfigDict(extra="ignore")
    tipo: str = Field("derrotar_todos", description="um tipo do catálogo de objetivos")
    alvo: str | None = Field(None, description="id de zona, objeto, aliado ou inimigo")
    n: int | None = Field(None, description="rodadas (sobreviver/interromper_ritual)")


class PreparedSceneWithCards(PreparedScene):
    """SPEC-331: só usada com `RPG_SCENE_CARDS` shadow/on - com `off` o schema que o
    provider vê é o `PreparedScene` de sempre (byte a byte)."""

    cartas_de_cena: list[str] = Field(
        default_factory=list, description="0 a 2 ids do catálogo de Cartas de Cena oferecido"
    )
    objetivo: PreparedObjective | None = Field(None, description="objetivo da cena (opcional)")


_PREP_TIMEOUT_DEFAULT = 12.0
_MAX_ZONES, _MAX_OBJECTS, _MAX_EVENTS, _MAX_TEXT = 3, 2, 1, 120


def _trim_prepared(scene: dict) -> dict:
    """Truncagem determinística (padrão do repo: limite em Python, não no schema)."""

    def cut(text) -> str:
        return str(text or "").strip()[:_MAX_TEXT]

    scene["zones"] = [
        {
            **z,
            "id": cut(z.get("id")),
            "name": cut(z.get("name")),
            "connections": [cut(c) for c in (z.get("connections") or [])][:_MAX_ZONES],
        }
        for z in (scene.get("zones") or [])[:_MAX_ZONES]
        if str(z.get("id") or "").strip()
    ]
    scene["objects"] = [
        {
            **o,
            "name": cut(o.get("name")) or cut(o.get("id")),
            "base_narrativa": cut(o.get("base_narrativa")),
            "interactions": list(o.get("interactions") or [])[:2],
        }
        for o in (scene.get("objects") or [])[:_MAX_OBJECTS]
    ]
    events = []
    for ev in (scene.get("abyss_events") or [])[:_MAX_EVENTS]:
        # gatilho é Python: só "sempre" (flags livres de cena não existem aqui).
        events.append({**ev, "base_na_cena": cut(ev.get("base_na_cena")), "gatilho": "sempre"})
    scene["abyss_events"] = events
    scene["objectives"] = [cut(o) for o in (scene.get("objectives") or [])[:2] if cut(o)]
    scene.setdefault("ending_conditions", [])
    scene.setdefault("reinforcement_triggers", [])
    return scene


def fallback_safe_scene(context: dict | None = None) -> dict:
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
    from services import scene_cards as _sc

    schema = PreparedSceneWithCards if _sc.enabled() else PreparedScene
    try:
        result = _invoke_with_deadline(
            lambda: llm.with_structured_output(schema).invoke(_prep_prompt(narrative_context))
        )
        if isinstance(result, PreparedScene):
            scene = _trim_prepared(_drop_none_params(result.model_dump()))
            # IDs mecânicos já conhecidos entram no conjunto de alvos válidos.
            scene["enemies"] = list(narrative_context.get("enemies") or scene.get("enemies") or [])
            scene["npcs"] = list(narrative_context.get("npcs") or scene.get("npcs") or [])
            scene = normalize_prepared_scene(
                scene, int(narrative_context.get("encounter_level", 1) or 1)
            )
            if validate_preparation(scene)["ok"]:
                scene.pop("_normalization_errors", None)
                if isinstance(result, PreparedSceneWithCards):  # SPEC-331 R2/R4
                    scene.pop("cartas_de_cena", None)  # só o saneado do catálogo entra
                    scene.pop("objetivo", None)
                    _sc.attach(
                        scene,
                        result.cartas_de_cena,
                        result.objetivo,
                        narrative_context.get("location"),
                        allies=narrative_context.get("allies"),
                    )
                return scene
    except Exception:
        pass
    return fallback_safe_scene(narrative_context)


def _drop_none_params(scene: dict) -> dict:
    def clean(holder: dict) -> None:
        effect = holder.get("effect")
        if isinstance(effect, dict) and isinstance(effect.get("params"), dict):
            effect["params"] = {k: v for k, v in effect["params"].items() if v is not None}

    for obj in scene.get("objects") or []:
        for it in obj.get("interactions") or []:
            clean(it)
    for ev in scene.get("abyss_events") or []:
        clean(ev)
    return scene


def _invoke_with_deadline(call):
    """SPEC-232 R10: teto curto dedicado (`RPG_PREP_TIMEOUT_SECONDS`, default 12 s)
    para a preparação não travar o turno. Estourou → None (o chamador cai na cena
    de segurança); a thread órfã termina sozinha e o resultado é descartado."""
    import concurrent.futures
    import contextvars

    try:
        timeout = float(os.getenv("RPG_PREP_TIMEOUT_SECONDS", _PREP_TIMEOUT_DEFAULT))
    except ValueError:
        timeout = _PREP_TIMEOUT_DEFAULT
    ctx = contextvars.copy_context()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(ctx.run, call)
    try:
        return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        _log_event("combat", "prep_timeout", level="warning", timeout_s=round(timeout))
        return None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _scene_cards_prompt(ctx: dict) -> str:
    """SPEC-331 R8: só ids/nome/sabor elegíveis (máx. 12) - nenhum número de efeito.
    Com a flag `off` devolve "" (prompt idêntico ao de antes)."""
    from services import scene_cards as _sc

    if not _sc.enabled():
        return ""
    options = _sc.prompt_options(ctx.get("location"))
    sep = chr(10)
    foes = [
        str(e.get("id") or e.get("name")) for e in ctx.get("enemies") or [] if isinstance(e, dict)
    ]
    friends = [str(a) for a in ctx.get("allies") or []]
    lines = [
        sep
        + "Objetivo opcional (objetivo.tipo SÓ de: "
        + ", ".join(_sc.OBJETIVOS)
        + "). objetivo.alvo: proteger = id de aliado ("
        + (", ".join(friends) or "nenhum")
        + "); alcancar_zona = id de uma zona criada nesta resposta; destruir_objeto = id de um "
        + "objeto criado nesta resposta; interromper_ritual = id de inimigo ("
        + (", ".join(foes) or "nenhum")
        + "). Sem alvo válido, omita o objetivo."
    ]
    if options:
        lines.append(
            "cartas_de_cena: 0-2 ids SÓ desta lista (ou vazio se nenhuma combina):"
            + sep
            + sep.join(f"- {o['id']}: {o['nome']} - {o['sabor']}" for o in options)
        )
    return sep.join(lines)


def _prep_prompt(ctx: dict) -> str:
    """Prompt COMPACTO (SPEC-232 R10): só nomes/ids — nunca o dict cru do contexto
    (fichas inteiras de inimigo estouravam tokens e latência)."""
    enemies = [e for e in (ctx.get("enemies") or []) if isinstance(e, dict)]
    ids = ["player"] + [
        str(e.get("id") or e.get("name")) for e in enemies if e.get("id") or e.get("name")
    ]
    foes = ", ".join(f"{e.get('name', e.get('id'))} ({e.get('id', '?')})" for e in enemies[:6])
    narrative = " ".join(str(ctx.get("narrative") or "").split())[:400]
    return (
        "Prepare a cena de conflito JOGÁVEL de Valoria em JSON curto (sem prosa).\n"
        f"Local: {ctx.get('location', 'Campo')}. Inimigos: {foes or 'nenhum'}.\n"
        f"Cena: {narrative or '—'}\n"
        "Regras: 1-3 zonas (id curto, name, connections por id); 0-2 objetos "
        "interativos coerentes com o local, cada um com base_narrativa curta e 1 "
        "interação; 0-1 evento do Abismo cujo base_na_cena é o id de um objeto.\n"
        f"effect.kind SÓ de: {', '.join(sorted(cs.EFFECT_KINDS))}. "
        "potency SÓ de: fraco, moderado, forte, devastador (nunca números).\n"
        f"params.target (obrigatório em damage/apply_condition/reposition) SÓ de: {', '.join(ids)}."
        + _scene_cards_prompt(ctx)
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

    virtudes = dict(
        npc.get("virtudes") or {"forca": 1, "agilidade": 1, "corpo": 1, "mente": 1, "carisma": 1}
    )
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
        "esquiva": compute_esquiva({"virtudes": virtudes}, include_modifiers=False),
        "categoria": npc.get("categoria", "padrao"),
        "active_conditions": [],
        "tactical_archetype": tactical_archetype,
        "tactical_profile": npc_profile_for_archetype(tactical_archetype),
        "status": "ativo",
    }
    return sheet


def gamedata_slug(name: str) -> str:
    return "npc_" + "".join(c if c.isalnum() else "_" for c in str(name).lower()).strip("_")
