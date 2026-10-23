"""
agents/bestiary.py
Gerador de Inimigos V8 (Refatorado Check-First + RAG).
Correção: Prompt reforçado para garantir lista de ataques estruturada.
"""

import json
import os
import re
import unicodedata
from typing import Dict, List, Literal, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

import gamedata
from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event

try:
    from rag import query_rag
except ImportError:

    def query_rag(*args, **kwargs):
        return ""


from agents.librarian import find_existing_entity

BESTIARY_FILE = "data/bestiary.json"


# --- SCHEMA ---------------------------------------------------------------
# A IA descreve o CONCEITO. Nenhum número mecânico atravessa esta fronteira;
# a ficha v4 é materializada abaixo por tabelas Python (spec hardening inputs).
class EnemySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    categoria: Literal["lacaio", "padrao", "elite", "chefe"] = "padrao"
    arquetipo: Literal["equilibrado", "bruto", "agil", "astuto", "mistico"] = "equilibrado"
    estilo_ataque: Literal["corpo_a_corpo", "distancia", "magico", "area"] = "corpo_a_corpo"
    nome_ataque: str = "Ataque"
    abilities: list[str] = Field(default_factory=list)
    loot: list[str] = Field(default_factory=list)
    regions: list[str] = Field(
        default_factory=list,
        description="Ids das regiões onde a criatura ocorre (ex.: 'skallgard')",
    )


_VIRTUDE_TEMPLATES: dict[str, dict[str, int]] = {
    "equilibrado": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 2, "carisma": 1},
    "bruto": {"forca": 3, "agilidade": 1, "corpo": 3, "mente": 1, "carisma": 1},
    "agil": {"forca": 1, "agilidade": 3, "corpo": 2, "mente": 2, "carisma": 1},
    "astuto": {"forca": 1, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2},
    "mistico": {"forca": 1, "agilidade": 2, "corpo": 1, "mente": 3, "carisma": 3},
}
_CATEGORY_BONUS = {"lacaio": -1, "padrao": 0, "elite": 1, "chefe": 2}
_LEGACY_TYPE = {"lacaio": "Minion", "padrao": "Standard", "elite": "Elite", "chefe": "BOSS"}
_ATTACK_TYPE = {
    "corpo_a_corpo": "melee",
    "distancia": "ranged",
    "magico": "magic",
    "area": "area",
}


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", ascii_text.lower()).strip("_") or "desconhecido"


def _profile_for_archetype(archetype: str) -> dict:
    hints = {
        "bruto": "Engaja o alvo mais próximo e pressiona sem recuar.",
        "agil": "Busca flanco, mobilidade e o alvo mais exposto.",
        "astuto": "Explora terreno, cobertura e a fraqueza já revelada.",
        "mistico": "Prioriza controle e mantém distância quando possível.",
        "equilibrado": "Ataca o alvo mais ameaçador sem abandonar a posição.",
    }
    return {
        "priorities": [
            {
                "trigger": "sempre",
                "tipo": "obrigatorio",
                "action_hint": hints.get(archetype, hints["equilibrado"]),
                "resistance": "flexivel",
                "blocks": [],
            }
        ]
    }


def materialize_enemy_concept(concept: dict | EnemySchema, *, encounter_level: int = 1) -> dict:
    """Converte conceito categórico em ficha v4. Ignora deliberadamente qualquer
    HP/AC/atributo/dano livre que exista no dict de entrada."""
    raw = concept.model_dump() if isinstance(concept, EnemySchema) else dict(concept or {})
    category_alias = {
        "minion": "lacaio",
        "standard": "padrao",
        "boss": "chefe",
        "lacaio": "lacaio",
        "padrao": "padrao",
        "elite": "elite",
        "chefe": "chefe",
    }
    category = category_alias.get(
        str(raw.get("categoria") or raw.get("type") or "padrao").strip().lower(),
        "padrao",
    )
    archetype = str(raw.get("arquetipo") or "equilibrado").strip().lower()
    if archetype not in _VIRTUDE_TEMPLATES:
        archetype = "equilibrado"
    style = str(raw.get("estilo_ataque") or "corpo_a_corpo").strip().lower()
    if style not in _ATTACK_TYPE:
        style = "corpo_a_corpo"

    virtues = dict(_VIRTUDE_TEMPLATES[archetype])
    category_bonus = _CATEGORY_BONUS[category]
    for key in virtues:
        virtues[key] = max(0, min(5, virtues[key] + category_bonus))
    # Nível só amplia as duas assinaturas do arquétipo; nunca usa número da IA.
    level_bonus = min(2, max(0, int(encounter_level or 1) - 1) // 4)
    ranked = sorted(virtues, key=lambda key: (-virtues[key], key))[:2]
    for key in ranked:
        virtues[key] = min(5, virtues[key] + level_bonus)

    corpo = virtues["corpo"]
    max_vitality = gamedata.vitalidade_para_corpo(corpo)
    from services.conflict_resolution import compute_esquiva

    esquiva = compute_esquiva({"virtudes": virtues}, include_modifiers=False)
    name = str(raw.get("name") or "Inimigo Desconhecido").strip() or "Inimigo Desconhecido"
    attack_name = str(raw.get("nome_ataque") or "Ataque").strip() or "Ataque"
    data = {
        "id": str(raw.get("id") or f"enemy_{_slug(name)}"),
        "name": name,
        "description": str(raw.get("description") or "Uma ameaça de Valoria."),
        "type": _LEGACY_TYPE[category],
        "categoria": category,
        "arquetipo": archetype,
        "virtudes": virtues,
        "vitalidade": max_vitality,
        "max_vitalidade": max_vitality,
        "ferimento_espacos": gamedata.espacos_ferimento_para_corpo(corpo),
        "ferimentos": {"leve": [], "grave": [], "critico": []},
        "esquiva": esquiva,
        "active_conditions": [],
        "tactical_profile": _profile_for_archetype(archetype),
        "cartas": ["bst_defesa_instintiva"],
        "attacks": [{"name": attack_name, "type": _ATTACK_TYPE[style], "potency": "moderado"}],
        "abilities": list(raw.get("abilities") or []),
        "loot": list(raw.get("loot") or []),
        "regions": list(raw.get("regions") or []),
        "status": "ativo",
        # aliases derivados para consumidores de borda ainda legados
        "hp": max_vitality,
        "max_hp": max_vitality,
        "ac": esquiva,
    }
    if category in DEFAULT_SURVIVAL_PER_LEVEL:  # SPEC-290
        data["vitalidade_por_nivel_encontro"] = DEFAULT_SURVIVAL_PER_LEVEL[category]
    if category in DEFAULT_ACTIONS_PER_ROUND:  # SPEC-295
        data["acoes_por_rodada"] = DEFAULT_ACTIONS_PER_ROUND[category]
    return data


# --- PERSISTÊNCIA (spec isolar-cache-runtime) -------------------------------
# data/bestiary.json = base CURADA (2.5b), READ-ONLY em runtime. Criatura gerada
# pelo LLM vai pro OVERLAY gitignored (RPG_RUNTIME_CACHE_DIR/bestiary_runtime.json).


def _overlay_path() -> str:
    from gamedata import runtime_cache_path

    return runtime_cache_path("bestiary_runtime.json")


def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log_event("bestiary", "read_failed", level="warning", error=type(e).__name__)
        return {}


def _pool_creature_template(entry) -> dict:
    """SPEC-297 R27: o documento do pool é só CONCEITO; a ficha numérica é do motor."""
    doc = dict(entry.document)
    concept = {
        "id": str(doc.get("id") or entry.entry_id),
        "name": entry.name,
        "description": str(doc.get("description") or ""),
        "categoria": doc.get("categoria") or "padrao",
        "arquetipo": doc.get("arquetipo") or "equilibrado",
        "estilo_ataque": doc.get("estilo_ataque") or "corpo_a_corpo",
        "nome_ataque": doc.get("nome_ataque") or "Ataque",
        "regions": list(doc.get("region_tags") or []),
    }
    out = materialize_enemy_concept(concept, encounter_level=1)
    out["id"] = concept["id"]
    out["pool_entry_id"] = entry.entry_id
    return out


def _pool_bestiary_view(game_id: str, region_id: str = "") -> dict:
    """Criaturas do próprio jogo (qualquer status) + promovidas (só com a flag `on`)."""
    from services import shared_pool
    from services.shared_pool_models import PoolNamespace, PoolStatus

    view: dict = {}
    try:
        pool = []
        if shared_pool.pool_mode() == "on" and region_id:
            # P2-10: só as promovidas da região atual (indexado, com teto).
            pool += shared_pool.get_store().select(
                namespace=PoolNamespace.CREATURE,
                statuses=[PoolStatus.PROMOTED],
                region_id=region_id,
                limit=100,
            )
        pool += shared_pool.own_entries(PoolNamespace.CREATURE, game_id=game_id, limit=200)
        for entry in pool:
            template = _pool_creature_template(entry)
            view[template["id"]] = template
    except Exception as exc:
        _log_event("bestiary", "pool_view_failed", level="warning", error=type(exc).__name__)
    return view


def load_bestiary(game_id: str = "", region_id: str = "") -> dict:
    """View unificada: curadoria ∪ overlay runtime (curadoria VENCE conflito de
    id — gerado nunca sombreia entrada curada). SPEC-297: com o pool ligado e
    `game_id`, soma as criaturas do pool (curadoria e overlay vencem)."""
    from agents.npc import catalog_owner_id
    from infrastructure.runtime import get_runtime

    store = get_runtime().runtime_catalog
    overlay = store.list("bestiary_template", owner_id=None, game_id=None)
    owner = catalog_owner_id()  # SPEC-223 R7: gerado do dono, nunca de outro tenant
    own = store.list("bestiary_template", owner_id=owner, game_id=None) if owner else {}
    pooled = _pool_bestiary_view(game_id, region_id) if game_id and _pool_enabled() else {}
    return {**pooled, **own, **overlay, **_read_json(BESTIARY_FILE)}


def _pool_enabled() -> bool:
    from services.shared_pool import enabled

    return enabled()


def save_enemy(data: dict):
    """Grava SÓ no overlay runtime — nunca em data/bestiary.json."""
    from infrastructure.runtime import get_runtime

    # Usa ID se existir, senão gera slug
    key = data.get("id", data["name"].lower().replace(" ", "_"))
    if "id" not in data:
        data["id"] = key

    from agents.npc import catalog_owner_id

    owner = catalog_owner_id()  # SPEC-223 R7: escopo do dono em perfis com principal
    get_runtime().runtime_catalog.put(
        "bestiary_template",
        key,
        data,
        scope="user" if owner else "global",
        owner_id=owner,
        game_id=None,
    )


def _infer_tier_from_name(name: str) -> ModelTier:
    """SPEC-223 R7 (D-C): nome vindo do jogador não escala para SMART."""
    del name
    return ModelTier.FAST


# SPEC-287: a "sobrevivência específica" do Chefe/Nomeado (regras §27.3) vale a
# partir deste Nível do Encontro; abaixo dele a ficha é a do bestiário.
ENCOUNTER_SURVIVAL_FROM_LEVEL = 3
# Revisão P2-3: teto de passos (perigo máximo 4 → 2 passos). Bônus de evento no
# Nível do Encontro (até 10) não multiplica a Vitalidade sem limite.
ENCOUNTER_SURVIVAL_MAX_STEPS = 2


# SPEC-290: valor canônico quando a ficha de Chefe/Nomeado não traz o campo
# (Chefe gerado pelo LLM, overlay runtime antigo). Espelha o gerador oficial.
DEFAULT_SURVIVAL_PER_LEVEL = {"chefe": 12, "nomeado": 12}

# SPEC-295 (K2): ações por rodada do Chefe/Nomeado quando a ficha não traz o
# campo (Chefe gerado pelo LLM, overlay antigo). Espelha `ACOES_POR_RODADA` do
# gerador oficial.
DEFAULT_ACTIONS_PER_ROUND = {"chefe": 2, "nomeado": 2}

# SPEC-295: Proteção natural do Chefe/Nomeado por Nível do Encontro (perigo
# absoluto, §5.1 — nunca o nível da party). Absorve dano por golpe como a
# Proteção de Carta; DoT e auto-dano passam (`bypass_armor`). Ausente = 0.
# [BALANCEAR] Com 2 ações por rodada, a arena da SPEC-285 (10 seeds) fecha
# `Chefe > Elite + 3 pp` em toda célula, exceto no Nível do Encontro 1 com o bot
# `basico` (níveis 1–2: −1,3/−2,5 pp) e no Nível 3 com o bot `cartas` (nível 6:
# +2,4 pp). 2 no Nível 1 e 1 no Nível 3 são os menores valores com folga ≥ 1 pp
# sobre a barra de 3 pp (Proteção 1 no Nível 1 deixa 0,1 pp no nível 2 `basico`).
# Nos Níveis 2 e 4 qualquer Proteção é dispensável, e no 2 estoura o teto de
# Elite + 20 pp (nível 4 `cartas`). Tabela e sondas: SPEC-295 §8.
CHEFE_PROTECAO_POR_NIVEL_ENCONTRO = {1: 2, 3: 1}


def apply_encounter_survival(data: dict, encounter_level: int) -> dict:
    """SPEC-287: soma `vitalidade_por_nivel_encontro` × min(2, Nível do Encontro − 2).

    O campo vem do gerador oficial (`scripts/migrate_bestiary_v4.py`) e só existe
    em Chefe/Nomeado. Muda a cópia recebida (nunca o bestiário em memória).
    SPEC-295: no Chefe/Nomeado também grava `protecao_natural` pelo Nível do
    Encontro e o default de `acoes_por_rodada` quando a ficha não o traz."""
    from combat_mechanics import normalize_categoria

    try:
        categoria = normalize_categoria(data)
        level = int(encounter_level or 1)
    except (TypeError, ValueError):
        return data
    per_level = data.get("vitalidade_por_nivel_encontro")
    if per_level is None:
        per_level = DEFAULT_SURVIVAL_PER_LEVEL.get(categoria, 0)
    try:
        per_level = int(per_level or 0)
    except (TypeError, ValueError):
        # Revisão P3-3: campo inválido só zera o bônus de Vitalidade; o Chefe
        # mantém as ações extras e a Proteção abaixo.
        per_level = 0
    steps = min(ENCOUNTER_SURVIVAL_MAX_STEPS, max(0, level - (ENCOUNTER_SURVIVAL_FROM_LEVEL - 1)))
    bonus = max(0, per_level) * steps
    if bonus:
        data["max_vitalidade"] = int(data.get("max_vitalidade") or 0) + bonus
    if categoria in DEFAULT_ACTIONS_PER_ROUND:
        data.setdefault("acoes_por_rodada", DEFAULT_ACTIONS_PER_ROUND[categoria])
        protection = CHEFE_PROTECAO_POR_NIVEL_ENCONTRO.get(level, 0)
        if protection:
            data["protecao_natural"] = protection
        else:
            data.pop("protecao_natural", None)
    return data


def _scaled_copy(data: dict, encounter_level: int) -> dict:
    """SPEC-290: ficha devolvida com o bônus de sobrevivência; o overlay salvo fica na base."""
    out = dict(data)
    apply_encounter_survival(out, encounter_level)
    return _ready_v4_vitals(out)


def _ready_v4_vitals(data: dict) -> dict:
    data["vitalidade"] = int(data.get("max_vitalidade") or 0)
    data["hp"] = data["vitalidade"]
    data["max_hp"] = data["vitalidade"]
    return data


def _ready_v4(data: dict, encounter_level: int) -> dict:
    apply_encounter_survival(data, encounter_level)
    data["vitalidade"] = int(data.get("max_vitalidade") or 0)
    data["hp"] = data["vitalidade"]
    data["max_hp"] = int(data.get("max_vitalidade") or 0)
    data["status"] = "ativo"
    return data


def _submit_generated_enemy(res, data: dict, game_id: str, location_id: str, name_origin: str):
    """SPEC-297 R9/R27: só o CONCEITO vai ao pool (em hold); números são do motor."""
    from services import shared_pool
    from services.shared_pool_models import PoolNamespace

    doc = {
        "id": str(data.get("id") or _slug(res.name)),
        "name": res.name,
        "description": res.description,
        "categoria": res.categoria,
        "arquetipo": res.arquetipo,
        "estilo_ataque": res.estilo_ataque,
        "nome_ataque": res.nome_ataque,
        "region_tags": list(res.regions or []),
    }
    region = shared_pool._region_of(location_id) or (res.regions[0] if res.regions else "")
    try:
        shared_pool.submit(
            PoolNamespace.CREATURE,
            doc,
            game_id=str(game_id),
            region_id=region,
            name_origin=name_origin,
        )
    except Exception as exc:
        _log_event("bestiary", "pool_submit_failed", level="warning", error=type(exc).__name__)


# --- GERADOR ---
def template_by_id(enemy_id: str, *, encounter_level: int = 1) -> dict | None:
    """SPEC-203 R3: ficha de um id canônico do bestiário, SEM LLM (nem librarian).
    Mesmo contrato do cache-hit de `generate_new_enemy`."""
    db = load_bestiary()
    if enemy_id not in db:
        return None
    data = dict(db[enemy_id])
    data["id"] = enemy_id
    if data.get("virtudes") and data.get("max_vitalidade") is not None:
        return _ready_v4(data, encounter_level)
    normalized = materialize_enemy_concept(data, encounter_level=encounter_level)
    normalized["id"] = enemy_id
    return normalized


def generate_new_enemy(
    name: str,
    context: str = "",
    *,
    encounter_level: int = 1,
    game_id: str = "",
    location_id: str = "",
    name_origin: str = "player",
) -> dict:
    from services.prompt_guard import sanitize_entity_name

    pool_on = bool(game_id) and _pool_enabled()
    name = sanitize_entity_name(name) or "Criatura"  # SPEC-223 R7
    # 1. CHECK-FIRST
    if pool_on:
        from services.shared_pool import _region_of

        db = load_bestiary(game_id, _region_of(location_id))
    else:
        db = load_bestiary()
    existing_ids = list(db.keys())

    found_id = find_existing_entity(name, "Monster", existing_ids)
    if found_id:
        _log_event("bestiary", "cache_hit", level="debug", entity_id=found_id)
        data = dict(db[found_id])

        # Auto-correção de legado
        if "id" not in data:
            _log_event("bestiary", "legacy_monster_without_id", level="info")
            data["id"] = found_id
            if not pool_on:  # SPEC-297 R13: cache-hit nunca reescreve o pool
                save_enemy(data)

        if data.get("virtudes") and data.get("max_vitalidade") is not None:
            return _ready_v4(data, encounter_level)
        # Overlay legado gerado por IA: números livres são descartados.
        normalized = materialize_enemy_concept(data, encounter_level=encounter_level)
        if not pool_on:
            save_enemy(normalized)
        return _scaled_copy(normalized, encounter_level)

    # 2. GERAÇÃO
    _log_event("bestiary", "creating", level="info")

    lore = query_rag(f"{name} {context}", index_name="lore")
    if not lore:
        lore = "Standard RPG Monster."

    llm = get_llm(temperature=0.5, tier=_infer_tier_from_name(name))

    sys_msg = SystemMessage(
        content=f"""
    <role>Designer narrativo de criaturas de Valoria</role>
    <lore_context>{lore}</lore_context>

    Descreva apenas identidade, categoria, arquétipo, estilo e flavor.
    NUNCA forneça HP, AC, Virtudes, bônus, dano, duração, dificuldade ou qualquer
    outro número mecânico. A ficha é calculada exclusivamente pelo motor Python.
    """
    )

    try:
        designer = llm.with_structured_output(EnemySchema)
        res = designer.invoke(
            [sys_msg, HumanMessage(content=f"Create monster: {name}. Context: {context}")]
        )
        if not isinstance(res, EnemySchema):
            raise TypeError(f"structured output inválido: {type(res).__name__}")
        data = materialize_enemy_concept(res, encounter_level=encounter_level)

        if pool_on:
            _submit_generated_enemy(res, data, game_id, location_id, name_origin)
        else:
            save_enemy(data)
        return _scaled_copy(data, encounter_level)

    except Exception as e:
        _log_event("bestiary", "generation_failed", level="error", error=type(e).__name__)
        # Fallback de segurança para não quebrar o jogo
        return materialize_enemy_concept(
            {
                "name": name,
                "id": f"fallback_{_slug(name)}",
                "description": "Criatura genérica materializada pelo fallback seguro.",
                "categoria": "lacaio",
                "arquetipo": "equilibrado",
                "estilo_ataque": "corpo_a_corpo",
                "nome_ataque": "Ataque Básico",
            },
            encounter_level=encounter_level,
        )
