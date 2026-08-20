"""
agents/bestiary.py
Gerador de Inimigos V8 (Refatorado Check-First + RAG).
Correção: Prompt reforçado para garantir lista de ataques estruturada.
"""
import json
import os
import re
import unicodedata
from typing import Dict, List, Literal
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, ConfigDict, Field
from llm_setup import ModelTier, get_llm
import gamedata

try:
    from rag import query_rag
except ImportError:
    def query_rag(*args, **kwargs): return ""

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
    abilities: List[str] = Field(default_factory=list)
    loot: List[str] = Field(default_factory=list)
    regions: List[str] = Field(default_factory=list, description="Ids das regiões onde a criatura ocorre (ex.: 'skallgard')")


_VIRTUDE_TEMPLATES: Dict[str, Dict[str, int]] = {
    "equilibrado": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 2, "carisma": 1},
    "bruto": {"forca": 3, "agilidade": 1, "corpo": 3, "mente": 1, "carisma": 1},
    "agil": {"forca": 1, "agilidade": 3, "corpo": 2, "mente": 2, "carisma": 1},
    "astuto": {"forca": 1, "agilidade": 2, "corpo": 2, "mente": 3, "carisma": 2},
    "mistico": {"forca": 1, "agilidade": 2, "corpo": 1, "mente": 3, "carisma": 3},
}
_CATEGORY_BONUS = {"lacaio": -1, "padrao": 0, "elite": 1, "chefe": 2}
_LEGACY_TYPE = {"lacaio": "Minion", "padrao": "Standard", "elite": "Elite", "chefe": "BOSS"}
_ATTACK_TYPE = {
    "corpo_a_corpo": "melee", "distancia": "ranged", "magico": "magic", "area": "area",
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
    return {"priorities": [{
        "trigger": "sempre", "tipo": "obrigatorio",
        "action_hint": hints.get(archetype, hints["equilibrado"]),
        "resistance": "flexivel", "blocks": [],
    }]}


def materialize_enemy_concept(concept: dict | EnemySchema, *,
                              encounter_level: int = 1) -> Dict:
    """Converte conceito categórico em ficha v4. Ignora deliberadamente qualquer
    HP/AC/atributo/dano livre que exista no dict de entrada."""
    raw = concept.model_dump() if isinstance(concept, EnemySchema) else dict(concept or {})
    category_alias = {
        "minion": "lacaio", "standard": "padrao", "boss": "chefe",
        "lacaio": "lacaio", "padrao": "padrao", "elite": "elite", "chefe": "chefe",
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
    esquiva = compute_esquiva({"virtudes": virtues})
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
        "attacks": [{"name": attack_name, "type": _ATTACK_TYPE[style],
                     "potency": "moderado"}],
        "abilities": list(raw.get("abilities") or []),
        "loot": list(raw.get("loot") or []),
        "regions": list(raw.get("regions") or []),
        "status": "ativo",
        # aliases derivados para consumidores de borda ainda legados
        "hp": max_vitality,
        "max_hp": max_vitality,
        "ac": esquiva,
    }
    return data

# --- PERSISTÊNCIA (spec isolar-cache-runtime) -------------------------------
# data/bestiary.json = base CURADA (2.5b), READ-ONLY em runtime. Criatura gerada
# pelo LLM vai pro OVERLAY gitignored (RPG_RUNTIME_CACHE_DIR/bestiary_runtime.json).

def _overlay_path() -> str:
    from gamedata import runtime_cache_path
    return runtime_cache_path("bestiary_runtime.json")


def _read_json(path: str) -> Dict:
    if not os.path.exists(path): return {}
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        print(f"⚠️ [BESTIARY] Falha ao ler {path}: {e}")
        return {}


def load_bestiary() -> Dict:
    """View unificada: curadoria ∪ overlay runtime (curadoria VENCE conflito de
    id — gerado nunca sombreia entrada curada)."""
    from infrastructure.runtime import get_runtime

    overlay = get_runtime().runtime_catalog.list(
        "bestiary_template", owner_id=None, game_id=None,
    )
    return {**overlay, **_read_json(BESTIARY_FILE)}


def save_enemy(data: Dict):
    """Grava SÓ no overlay runtime — nunca em data/bestiary.json."""
    from infrastructure.runtime import get_runtime

    # Usa ID se existir, senão gera slug
    key = data.get("id", data["name"].lower().replace(" ", "_"))
    if "id" not in data: data["id"] = key

    get_runtime().runtime_catalog.put(
        "bestiary_template", key, data,
        scope="global", owner_id=None, game_id=None,
    )

def _infer_tier_from_name(name: str) -> ModelTier:
    if any(x in name.lower() for x in ["dragon", "lich", "boss", "god", "lord"]): return ModelTier.SMART
    return ModelTier.FAST

# --- GERADOR ---
def generate_new_enemy(name: str, context: str = "", *,
                       encounter_level: int = 1) -> Dict:
    # 1. CHECK-FIRST
    db = load_bestiary()
    existing_ids = list(db.keys())
    
    found_id = find_existing_entity(name, "Monster", existing_ids)
    if found_id:
        print(f"♻️ [BESTIARY] Cache Hit: {found_id}")
        data = dict(db[found_id])
        
        # Auto-correção de legado
        if "id" not in data:
             print(f"🔧 [BESTIARY] Corrigindo monstro legado sem ID: {name}")
             data["id"] = found_id
             save_enemy(data)

        if data.get("virtudes") and data.get("max_vitalidade") is not None:
            data["vitalidade"] = int(data.get("max_vitalidade") or 0)
            data["hp"] = data["vitalidade"]
            data["max_hp"] = int(data.get("max_vitalidade") or 0)
            data["status"] = "ativo"
            return data
        # Overlay legado gerado por IA: números livres são descartados.
        normalized = materialize_enemy_concept(data, encounter_level=encounter_level)
        save_enemy(normalized)
        return normalized

    # 2. GERAÇÃO
    print(f"👾 [BESTIARY] Criando: {name}...")
    
    lore = query_rag(f"{name} {context}", index_name="lore")
    if not lore: lore = "Standard RPG Monster."

    llm = get_llm(temperature=0.5, tier=_infer_tier_from_name(name))
    
    sys_msg = SystemMessage(content=f"""
    <role>Designer narrativo de criaturas de Valoria</role>
    <lore_context>{lore}</lore_context>

    Descreva apenas identidade, categoria, arquétipo, estilo e flavor.
    NUNCA forneça HP, AC, Virtudes, bônus, dano, duração, dificuldade ou qualquer
    outro número mecânico. A ficha é calculada exclusivamente pelo motor Python.
    """)
    
    try:
        designer = llm.with_structured_output(EnemySchema)
        res = designer.invoke([sys_msg, HumanMessage(content=f"Create monster: {name}. Context: {context}")])
        if not isinstance(res, EnemySchema):
            raise TypeError(f"structured output inválido: {type(res).__name__}")
        data = materialize_enemy_concept(res, encounter_level=encounter_level)

        save_enemy(data)
        return data
        
    except Exception as e:
        print(f"❌ [BESTIARY ERROR] {e}")
        # Fallback de segurança para não quebrar o jogo
        return materialize_enemy_concept({
            "name": name, "id": f"fallback_{_slug(name)}",
            "description": "Criatura genérica materializada pelo fallback seguro.",
            "categoria": "lacaio", "arquetipo": "equilibrado",
            "estilo_ataque": "corpo_a_corpo", "nome_ataque": "Ataque Básico",
        }, encounter_level=encounter_level)
