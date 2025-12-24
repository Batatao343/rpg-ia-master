"""
gamedata/class_themes.py
Gerenciador de Temas de Classe com RAG.
Define o que cada classe pode ou não fazer, usando Lore do mundo para classes novas.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from llm_setup import get_llm, ModelTier
# Importação do RAG para garantir coerência com o mundo
try:
    from rag import query_rag
except ImportError:
    # Fallback caso o rag.py não esteja acessível no momento
    def query_rag(text, index_name="lore"): return "Lore indisponível."

# --- 1. Modelo de Dados ---
class ClassTheme(BaseModel):
    """Define as fronteiras temáticas de uma classe."""
    allowed: List[str] = Field(description="Temas e habilidades permitidos.")
    forbidden: List[str] = Field(description="Temas estritamente proibidos ou anti-temáticos.")
    style: str = Field(description="Descrição visual e sensorial do estilo da magia/habilidade.")

# --- 2. Cache em Memória ---
# Começa com classes básicas, mas aprende novas durante a execução.
_THEME_CACHE: Dict[str, ClassTheme] = {
    "Druid": ClassTheme(
        allowed=["Natureza", "Animais", "Elementos Primais (Vento, Raio)", "Cura", "Metamorfose"],
        forbidden=["Necromancia", "Tecnologia", "Metalurgia", "Arcano Abstrato"],
        style="Selvagem, orgânico, crescimento rápido, cheiro de terra e chuva."
    ),
    "Paladin": ClassTheme(
        allowed=["Luz Sagrada", "Proteção", "Cura Divina", "Smite", "Liderança", "Ordem"],
        forbidden=["Furtividade Mágica", "Invocação de Insetos", "Necromancia", "Veneno"],
        style="Brilhante, autoritário, dourado, ordenado, ressonante."
    ),
    "Rogue": ClassTheme(
        allowed=["Sombras", "Veneno", "Agilidade", "Precisão", "Truques Sujos", "Engenhosidade"],
        forbidden=["Magia de Área Explosiva", "Cura em Massa", "Tanque Pesado"],
        style="Sutil, rápido, letal, invisível, silêncio absoluto."
    ),
    "Mage": ClassTheme(
        allowed=["Elementos (Fogo, Gelo)", "Arcano Puro", "Tempo", "Espaço", "Ilusão"],
        forbidden=["Cura Divina", "Ressurreição Verdadeira (sem custo)"],
        style="Complexo, rúnico, energético, geométrico."
    )
}

# --- 3. Gerador Dinâmico (Just-in-Time) ---
def get_class_theme(class_name: str, concept_desc: str = "") -> ClassTheme:
    """
    Retorna o tema da classe. 
    Se não existir no cache, consulta a Lore (RAG) e gera as regras via IA.
    """
    key = class_name.title()
    
    # A. Cache Hit (Rápido)
    if key in _THEME_CACHE:
        return _THEME_CACHE[key]
    
    # B. Cache Miss (Gera nova classe)
    print(f"⚙️ [THEMES] Gerando regras para nova classe: {key}...")
    
    # 1. Consulta o RAG para ver se essa classe existe na história do mundo
    try:
        lore_context = query_rag(f"History, origins and magic source of {class_name}", index_name="lore")
    except Exception:
        lore_context = "Nenhuma lore específica encontrada."

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)
    
    system_msg = SystemMessage(content=f"""
    Você é um Arquiteto de Sistemas de RPG (Game Design).
    Sua tarefa é definir os LIMITES TEMÁTICOS (Hard Rules) para uma classe de personagem, baseando-se na LORE do mundo.
    
    <lore_context>
    {lore_context}
    </lore_context>
    
    <instructions>
    1. Analise a Lore. Se a classe for mencionada (ex: "Magos de Sangue de Valyria"), use essas regras.
    2. Se não houver Lore, use tropos clássicos de RPG mas mantenha coerência com o nome.
    3. Defina:
       - Allowed: O que é o 'pão com manteiga' dessa classe?
       - Forbidden: O que quebra a imersão se essa classe fizer?
       - Style: Como a magia se parece visualmente?
    </instructions>
    """)
    
    human_msg = HumanMessage(content=f"Classe: {class_name}\nConceito do Jogador: {concept_desc}")
    
    try:
        generator = llm.with_structured_output(ClassTheme)
        theme = generator.invoke([system_msg, human_msg])
        
        # Salva no cache para uso futuro
        _THEME_CACHE[key] = theme
        return theme
        
    except Exception as e:
        print(f"[THEME ERROR] Falha ao gerar tema: {e}")
        # Fallback de segurança
        return ClassTheme(
            allowed=["Habilidades Básicas"], 
            forbidden=["Feitos Divinos"], 
            style="Genérico."
        )

# --- 4. Escala de Poder (Nível) ---
def get_power_guideline(level: int) -> str:
    """Retorna as limitações físicas/mágicas para cada Tier de nível."""
    if level <= 4:
        return "TIER 1 (Iniciante): Dano baixo (1d6-2d6), alvo único. Magia sutil. Não voa, não revive."
    elif level <= 10:
        return "TIER 2 (Heroico): Dano médio (4d6-8d6), área pequena (sala). Voo curto/levitação. Pode destruir pedra."
    elif level <= 16:
        return "TIER 3 (Mestre): Dano alto (10d6+), área grande (campo de batalha). Ressurreição, controle climático local."
    else:
        return "TIER 4 (Lendário): Alteração da realidade, exércitos inteiros, dano massivo (20d6+). Imortalidade."