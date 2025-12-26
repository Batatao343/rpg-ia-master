"""
agents/character_creator.py
Gera a ficha do personagem baseada em História, Nível e Região.
Versão V6.0: Híbrida (IA para Criatividade + JSON para Regras Oficiais).
"""
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from llm_setup import get_llm, ModelTier

# --- IMPORTAÇÕES ESSENCIAIS ---
try:
    from rag import query_rag
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    def query_rag(*args, **kwargs): return ""

# Importa os dados oficiais para garantir consistência
try:
    from gamedata import CLASSES
except ImportError:
    CLASSES = {}

# --- MAPA DE ATRIBUTOS (Fallback se o JSON falhar) ---
CLASS_ATTR_MAP = {
    "Guerreiro": "str", "Cavaleiro da Vigília": "str", "Inquisidor da Cinza": "str", "Guardião Selvagem": "str",
    "Ladino": "dex", "Batedor das Fronteiras": "dex", "Sombra da Corte": "dex",
    "Mago": "int", "Arcanista Cinzento": "int", "Sapador da Fuligem": "int", "Médico de Campo": "int",
    "Sangromante": "con", "Pastor de Pragas": "wis"
}

# --- SCHEMAS DA IA ---

class PlayerStatsSchema(BaseModel):
    """A IA sugere a distribuição, mas respeitamos limites."""
    attributes: Dict[str, int] = Field(description="Atributos: str, dex, con, int, wis, cha.")
    inventory: List[str] = Field(description="Itens baseados na Região e Lore.")
    flavor_abilities: List[str] = Field(description="2 ou 3 magias/truques extras (Flavor) além da passiva.")

class BackstoryAnalysis(BaseModel):
    archetype_summary: str
    key_traits: List[str]

# --- LÓGICA AUXILIAR ---

def _get_mod(score: int) -> int:
    return (score - 10) // 2

def _calculate_attack_bonus(class_name: str, attributes: Dict[str, int], level: int) -> int:
    # Tenta pegar atributo principal do JSON oficial, se não tiver, usa o mapa
    if class_name in CLASSES and "base_stats" in CLASSES[class_name]:
        # Tenta deduzir o maior atributo base da classe
        base = CLASSES[class_name]["base_stats"]["attributes"]
        primary_attr = max(base, key=base.get)
    else:
        primary_attr = CLASS_ATTR_MAP.get(class_name, "str")

    score = attributes.get(primary_attr, 10)
    mod = _get_mod(score)
    prof_bonus = 2 + ((level - 1) // 4)
    return mod + prof_bonus

def _get_class_data(class_name: str) -> Dict:
    """Retorna os dados oficiais da classe ou um padrão genérico."""
    if class_name in CLASSES:
        return CLASSES[class_name]
    return {
        "passive": "Determinação: +1 em testes de Vontade.",
        "base_stats": {"hp": 10, "stamina": 10, "mana": 10}
    }

# --- FUNÇÃO PRINCIPAL ---

def create_player_character(user_input: Dict[str, Any]) -> Dict[str, Any]:
    name = user_input.get("name", "Herói")
    p_class = user_input.get("class_name", "Aventureiro")
    race = user_input.get("race", "Humano")
    region = user_input.get("region", "Nova Arcádia")
    backstory = user_input.get("backstory", "")
    
    raw_level = str(user_input.get("level", "1"))
    clean_level = "".join(filter(str.isdigit, raw_level))
    level = int(clean_level) if clean_level else 1

    # 1. BUSCA DADOS OFICIAIS (A "Regra")
    class_data = _get_class_data(p_class)
    official_passive = class_data.get("passive", "Habilidade Básica")
    
    # Cálculo de HP Base Oficial (Base da Classe + Nível)
    base_hp_class = class_data.get("base_stats", {}).get("hp", 12)
    # Fórmula simples: Base + (6 por nível extra)
    final_hp = base_hp_class + (6 * (level - 1))

    # 2. BUSCA O LORE (O "Sabor")
    region_lore = _get_region_lore(region)

    # 3. Geração de Stats via IA
    llm = get_llm(temperature=0.6, tier=ModelTier.SMART)
    
    system_msg = SystemMessage(content=f"""
    Você é um Motor de Regras para RPG.
    
    CONTEXTO DO MUNDO: {region_lore}
    CLASSE: {p_class} (Atributo Principal Sugerido: Consulte o arquétipo).
    
    TAREFA:
    1. Gere atributos (str, dex...) coerentes com a classe e nível {level}.
    2. Gere um inventário temático da região {region}.
    3. Sugira 2 habilidades extras (flavor) que combinem com a classe.
    """)

    human_msg = HumanMessage(content=f"Personagem: {name}, {race} {p_class}. Conceito: {backstory}")

    stats_data = {}
    try:
        stats = llm.with_structured_output(PlayerStatsSchema).invoke([system_msg, human_msg])
        if stats: stats_data = stats.model_dump()
    except Exception as e:
        print(f"⚠️ Erro IA: {e}")

    # Fallback
    if not stats_data:
        stats_data = {
            "attributes": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "inventory": ["Kit Básico"],
            "flavor_abilities": []
        }

    # 4. MONTAGEM FINAL (MERGE)
    # A lista de habilidades começa com a PASSIVA OFICIAL do JSON
    final_abilities = [f"[Passiva] {official_passive}"] + stats_data.get("flavor_abilities", [])
    
    # Cálculo de Defesa (Simples: 10 + Dex Mod, ou valor base da classe se for maior)
    dex_mod = _get_mod(stats_data["attributes"].get("dex", 10))
    base_def = class_data.get("base_stats", {}).get("defense", 10)
    # Se a classe usa armadura pesada (def alta no JSON), mantemos. Se for leve, usa Dex.
    final_defense = max(base_def, 10 + dex_mod)

    return {
        "name": name,
        "class_name": p_class,
        "race": race,
        "region": region,
        "backstory": backstory,
        "concept": f"{race} {p_class} de {region}",
        "traits": [], # Simplificado para focar no resto
        "hp": final_hp,
        "max_hp": final_hp,
        "defense": final_defense,
        "attributes": stats_data["attributes"],
        "inventory": stats_data["inventory"],
        "known_abilities": final_abilities, # <--- AQUI ESTÁ A CORREÇÃO
        "attack_bonus": _calculate_attack_bonus(p_class, stats_data["attributes"], level),
        "level": level,
        "xp": 0
    }

def _get_region_lore(region_name: str) -> str:
    if not RAG_AVAILABLE: return ""
    try: return query_rag(f"Describe {region_name}", index_name="lore")
    except: return ""