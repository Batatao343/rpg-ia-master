"""
agents/character_creator.py
Gera a ficha do personagem baseada em História (Backstory) e Nível.
Versão V3.3: Correção de Sintaxe f-string (Escaping curly braces).
"""
from typing import Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field, ValidationError

from llm_setup import get_llm, ModelTier

# --- SCHEMAS ---

class PlayerStatsSchema(BaseModel):
    """Gera atributos numéricos baseados na classe/raça/nível."""
    hp: int = Field(ge=1, description="HP Inicial (Inteiro).")
    max_hp: int = Field(ge=1, description="HP Máximo (Inteiro).")
    defense: int = Field(description="Classe de Armadura (AC).")
    attributes: Dict[str, int] = Field(description="Força, Destreza, Const, Int, Sab, Car (Apenas números).")
    inventory: List[str] = Field(description="Lista de itens. Nível alto exige itens mágicos nomeados.")

class BackstoryAnalysis(BaseModel):
    """A IA extrai a essência mecânica da história."""
    archetype_summary: str = Field(description="Resumo curto do estilo de combate/magia.")
    key_traits: List[str] = Field(description="3 características principais citadas na história.")

class InventoryOnly(BaseModel):
    """Schema auxiliar para o fallback (só gera itens)."""
    items: List[str]

# --- LÓGICA AUXILIAR ---

def _analyze_backstory(name: str, p_class: str, backstory: str) -> Dict:
    """Lê o texto livre e converte em tags mecânicas."""
    if not backstory or len(backstory) < 10:
        return {"archetype_summary": p_class, "key_traits": ["Aventureiro Padrão"]}

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)
    
    # System define a persona, Human entrega o dado.
    system_msg = SystemMessage(content="Você é um Especialista em RPG. Extraia o ARQUÉTIPO MECÂNICO do texto.")
    human_msg = HumanMessage(content=f"Backstory: {backstory}")
    
    try:
        analyzer = llm.with_structured_output(BackstoryAnalysis)
        result = analyzer.invoke([system_msg, human_msg])
        if result is None: raise ValueError("IA retornou vazio")
        return result.model_dump()
    except Exception:
        return {"archetype_summary": p_class, "key_traits": ["Aventureiro"]}


def _generate_smart_inventory_fallback(name: str, concept: str, level: int) -> List[str]:
    """
    Gera apenas o inventário se a ficha completa falhar. 
    """
    print(f"🎒 [CHAR CREATOR] Gerando inventário de fallback (SMART) para Nível {level}...")
    
    llm = get_llm(temperature=0.7, tier=ModelTier.SMART)
    
    system_msg = SystemMessage(content="Você é um Mestre de Armaria em um RPG de Fantasia Sombria.")
    
    prompt_text = f"""
    Gere um inventário de RPG D&D para: {name} ({concept}), Nível {level}.
    
    DIRETRIZES DE RARIDADE:
    - Nível 1-4: Equipamento básico.
    - Nível 5-10: Armas +1, itens mágicos incomuns.
    - Nível 11+: Armas +2/3, relíquias, itens raros com nomes épicos.
    
    Retorne APENAS uma lista de strings. Ex: ["Lâmina do Crepúsculo", "Poção Maior", "Manto Élfico"]
    """
    human_msg = HumanMessage(content=prompt_text)
    
    try:
        gen = llm.with_structured_output(InventoryOnly)
        res = gen.invoke([system_msg, human_msg])
        return res.items
    except Exception as e:
        print(f"❌ [FALLBACK ERROR] Inventário falhou: {e}")
        return ["Mochila", "Equipamento de Aventureiro", "Adaga Simples"]


# --- FUNÇÃO PRINCIPAL ---

def create_player_character(user_input: Dict[str, Any]) -> Dict[str, Any]:
    """Cria a ficha completa processando a história e o nível."""
    
    name = user_input.get("name", "Herói")
    p_class = user_input.get("class_name", "Aventureiro")
    race = user_input.get("race", "Humano")
    backstory = user_input.get("backstory", "")
    try:
        level = int(user_input.get("level", 1))
    except (ValueError, TypeError):
        level = 1

    print(f"🧠 [CHAR CREATOR] Analisando {name} (Nível {level})...")
    
    # 1. Análise de Conceito
    analysis = _analyze_backstory(name, p_class, backstory)
    derived_concept = analysis["archetype_summary"]
    print(f"✨ [CHAR CREATOR] Conceito: '{derived_concept}'")

    # 2. Geração de Stats Numéricos
    llm = get_llm(temperature=0.5, tier=ModelTier.SMART)
    
    # MUDANÇA: Removemos o exemplo JSON confuso e demos instruções diretas.
    system_msg = SystemMessage(content=f"""
    Você é um Motor de Regras para D&D 5e (Dark Fantasy).
    
    REGRAS DE ESCALONAMENTO (SCALING):
    1. HP (Vida):
       - Nível 1: ~10-15
       - Nível 5: ~40-60
       - Nível 10: ~80-110
       - Nível 15+: ~150+
    
    2. ATRIBUTOS (IMPORTANTE):
       - Use APENAS números inteiros.
       - As chaves do JSON DEVEM ser exatamente: "str", "dex", "con", "int", "wis", "cha".
       - Distribuição: Para o Nível {level}, os atributos principais da classe DEVEM ser altos.
         (Ex: Um Mago Nível 10 deve ter 'int': 20. Um Guerreiro Nível 1 deve ter 'str': 16).
    
    3. INVENTÁRIO:
       - DEVE refletir a história e o nível de poder.
       - Nível {level} exige itens mágicos/raros com nomes temáticos.
    """)

    human_msg = HumanMessage(content=f"""
    Gere a ficha para:
    - Nome: {name}
    - Raça/Classe: {race} {p_class}
    - Nível Atual: {level}
    - Conceito/Arquétipo: {derived_concept}
    """)

    stats_data = {}
    
    # --- BLOCO DE TENTATIVA E DEBUG ---
    try:
        print("⏳ [DEBUG] Chamando LLM (SMART) para gerar JSON completo...")
        generator = llm.with_structured_output(PlayerStatsSchema)
        
        stats = generator.invoke([system_msg, human_msg])
        
        if stats is None: 
            raise ValueError("LLM retornou None (Filtro de Segurança Ativado)")
        
        stats_data = stats.model_dump()
        print("✅ [DEBUG] JSON gerado e validado com sucesso!")
        
    except ValidationError as e:
        print("\n" + "!"*50)
        print("❌ [DEBUG] ERRO DE VALIDAÇÃO DO PYDANTIC DETECTADO")
        print("!"*50)
        print(e.json(indent=2))
        print("!"*50 + "\n")
        print("⚠️ Iniciando Fallback para não travar o jogo...")
        stats_data = None 

    except Exception as e:
        print(f"\n❌ [DEBUG] Erro genérico na criação: {type(e).__name__}: {e}")
        stats_data = None

    # --- FALLBACK ---
    if stats_data is None:
        con_mod = 3 if level >= 5 else 2
        base_hp = 12 + (6 * (level - 1)) + (con_mod * level)
        
        # Fallback de atributos usando as chaves corretas
        base_attrs = {"str": 14, "dex": 14, "int": 14, "wis": 14, "cha": 14, "con": 16}
        
        smart_inventory = _generate_smart_inventory_fallback(name, derived_concept, level)
        
        stats_data = {
            "hp": base_hp, 
            "max_hp": base_hp, 
            "defense": 12 + (level // 4), 
            "attributes": base_attrs,
            "inventory": smart_inventory
        }

    # 3. Montagem do Objeto Final
    player_sheet = {
        "name": name,
        "class_name": p_class,
        "race": race,
        "backstory": backstory,
        "concept": derived_concept,
        "traits": analysis["key_traits"],
        "hp": stats_data["hp"],
        "max_hp": stats_data["max_hp"],
        "defense": stats_data["defense"],
        "attributes": stats_data["attributes"],
        "inventory": stats_data["inventory"],
        "level": level,
        "xp": 0
    }
    
    return player_sheet