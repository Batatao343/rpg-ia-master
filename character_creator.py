"""
agents/character_creator.py
Gera a ficha do personagem baseada em História, Nível e Região.
Versão V6.0: Híbrida (IA para Criatividade + JSON para Regras Oficiais).
"""
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from llm_setup import get_llm, ModelTier
from combat_mechanics import normalize_attr

# --- IMPORTAÇÕES ESSENCIAIS ---
try:
    from rag import query_rag
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    def query_rag(*args, **kwargs): return ""

# Importa os dados oficiais para garantir consistência
try:
    from gamedata import CLASSES, load_json_data
except ImportError:
    CLASSES = {}
    def load_json_data(_): return {}

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

def find_race(race: str) -> Dict:
    """Resolve a raça de data/origins.json por id ou nome (case-insensitive)."""
    races = (load_json_data("origins.json") or {}).get("races", [])
    key = str(race or "").strip().lower()
    for r in races:
        if key in (str(r.get("id", "")).lower(), str(r.get("name", "")).lower()):
            return r
    return {}


def apply_racial_traits(sheet: Dict[str, Any], race: str) -> Dict[str, Any]:
    """
    Aplica os traits mecânicos da raça (Fase 2.5b) sobre a ficha, em Python
    determinístico — pós-LLM, nunca confiando na IA para números.
    Muta e retorna a própria `sheet`.
    """
    race_data = find_race(race)
    traits = race_data.get("traits", []) or []
    names: List[str] = []
    resists: List[str] = []
    save_bonus: Dict[str, int] = {}

    for t in traits:
        names.append(t.get("name", t.get("id", "?")))
        fx = t.get("effects", {}) or {}
        for attr, inc in (fx.get("attr_bonus") or {}).items():
            k = normalize_attr(attr)
            attrs = sheet.setdefault("attributes", {})
            attrs[k] = int(attrs.get(k, 10)) + int(inc)
        for field, key in (("hp_bonus", "hp"), ("mana_bonus", "mana"), ("stamina_bonus", "stamina")):
            inc = int(fx.get(field, 0) or 0)
            if inc:
                sheet[key] = int(sheet.get(key, 0)) + inc
                sheet[f"max_{key}"] = int(sheet.get(f"max_{key}", 0)) + inc
        if fx.get("defense_bonus"):
            sheet["defense"] = int(sheet.get("defense", 10)) + int(fx["defense_bonus"])
        if fx.get("gold_bonus"):
            sheet["gold"] = int(sheet.get("gold", 0)) + int(fx["gold_bonus"])
        for item in fx.get("start_items") or []:
            # Fase 4.3: inventário estruturado ({id, qty}); nome vira id se resolver
            from inventory import add_item, item_display
            inv = sheet.setdefault("inventory", [])
            if not any(item_display(e) == item or e.get("id") == item
                       for e in inv if isinstance(e, dict)):
                sheet["inventory"] = add_item(inv, item, 1)
        resists.extend(str(c).lower() for c in fx.get("condition_resist") or [])
        for attr, inc in (fx.get("save_bonus") or {}).items():
            k = normalize_attr(attr)
            save_bonus[k] = save_bonus.get(k, 0) + int(inc)

    sheet["racial_traits"] = names
    sheet["condition_resists"] = resists
    sheet["racial_save_bonus"] = save_bonus
    return sheet


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
    
    # Cálculo de HP Base Oficial (Base da Classe + Nível)
    base_stats = class_data.get("base_stats", {})
    base_hp_class = base_stats.get("hp", 12)
    # Fórmula simples: Base + (6 por nível extra)
    final_hp = base_hp_class + (6 * (level - 1))

    # Recursos secundários (stamina/mana) escalam levemente com o nível
    final_stamina = base_stats.get("stamina", 10) + (2 * (level - 1))
    final_mana = base_stats.get("mana", 10) + (2 * (level - 1))

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
        if stats:
            dumped = stats.model_dump()
            # Só aceita se vier no formato esperado (sem API key, o FallbackLLM
            # devolve um AIMessage cujo dump não tem 'attributes').
            if isinstance(dumped, dict) and "attributes" in dumped:
                # Normaliza chaves de atributo (Gemini pode devolver nomes longos/PT:
                # "dexterity"/"destreza" -> "dex"). Sem isso, mods/attack_bonus saem
                # errados pois a leitura abaixo usa as chaves curtas.
                raw_attrs = dumped.get("attributes") or {}
                dumped["attributes"] = {normalize_attr(k): v for k, v in raw_attrs.items()}
                stats_data = dumped
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
    # Fase 4.1 (R6): known_abilities guarda SÓ ids canônicos da árvore.
    # A passiva vive em CLASSES[classe]["passive"] (exibição busca lá);
    # flavor do LLM é descartado (nunca teve efeito mecânico).
    final_abilities = ["ataque_basico"] + [
        aid for aid in class_data.get("starting_abilities", [])
        if aid not in ("ataque_basico",)
    ]

    sheet = {
        "name": name,
        "class_name": p_class,
        "race": race,
        "region": region,
        "backstory": backstory,
        "concept": f"{race} {p_class} de {region}",
        "traits": [], # Simplificado para focar no resto
        "hp": final_hp,
        "max_hp": final_hp,
        "stamina": final_stamina,
        "max_stamina": final_stamina,
        "mana": final_mana,
        "max_mana": final_mana,
        "attributes": stats_data["attributes"],
        "inventory": [],  # Fase 4.3: preenchido abaixo (ids canônicos + flavor)
        "known_abilities": final_abilities,
        "level": level,
        "xp": 0,
        "pending_choices": []
    }

    # Fase 4.3: inventário estruturado — starting_equipment CANÔNICO da classe
    # (arma inicial COM stats — fecha o bug da "Espada Gasta") + flavor do LLM
    # (resolve para id quando der; senão vira item_desconhecido com display_name).
    from inventory import add_item, backfill_inventory
    inv = []
    for iid in class_data.get("starting_equipment", []) or []:
        inv = add_item(inv, iid, 1)
    for free_name in stats_data.get("inventory", []) or []:
        inv = add_item(inv, str(free_name), 1)
    sheet["inventory"] = inv

    # 5. TRAITS RACIAIS (Fase 2.5b) — determinístico, ANTES de defesa/ataque
    #    (bônus racial de atributo deve refletir nos mods derivados).
    apply_racial_traits(sheet, race)

    # Fase 4.3: slots de equipamento (auto-equipa melhor arma/armadura UMA vez)
    sheet.update(backfill_inventory(sheet))

    # Cálculo de Defesa (Simples: 10 + Dex Mod, ou valor base da classe se for maior)
    dex_mod = _get_mod(sheet["attributes"].get("dex", 10))
    base_def = class_data.get("base_stats", {}).get("defense", 10)
    # Se a classe usa armadura pesada (def alta no JSON), mantemos. Se for leve, usa Dex.
    # defense_bonus racial (se houver) já foi somado em sheet["defense"] — preserva.
    racial_def_bonus = int(sheet.get("defense", 0) or 0) - 10 if "defense" in sheet else 0
    sheet["defense"] = max(base_def, 10 + dex_mod) + max(0, racial_def_bonus)
    sheet["attack_bonus"] = _calculate_attack_bonus(p_class, sheet["attributes"], level)
    return sheet

def _get_region_lore(region_name: str) -> str:
    if not RAG_AVAILABLE: return ""
    try: return query_rag(f"Describe {region_name}", index_name="lore")
    except: return ""