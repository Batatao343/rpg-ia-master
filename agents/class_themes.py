"""
gamedata/class_themes.py
Define o que cada classe pode ou não fazer.
"""
from typing import Dict, List
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from llm_setup import get_llm, ModelTier

# Tenta importar RAG, falha silenciosamente se não existir
try:
    from rag import query_rag
except ImportError:
    def query_rag(*args, **kwargs): return "Lore indisponível."

class ClassTheme(BaseModel):
    allowed: List[str]
    forbidden: List[str]
    style: str

# Cache em memória
_THEME_CACHE: Dict[str, ClassTheme] = {}

def get_class_theme(class_name: str, concept_desc: str = "") -> ClassTheme:
    """Retorna o tema da classe. Gera via IA se for nova."""
    key = class_name.title()
    
    if key in _THEME_CACHE:
        return _THEME_CACHE[key]
    
    print(f"⚙️ [THEMES] Gerando regras para: {key}...")
    
    # Consulta Lore para consistência
    try:
        lore_context = query_rag(f"Magic and origins of {class_name}", index_name="lore")
    except Exception:
        lore_context = ""

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)
    
    system_msg = SystemMessage(content=f"""
    Defina os LIMITES TEMÁTICOS (Hard Rules) para uma classe de RPG.
    LORE: {lore_context}
    Defina:
    - Allowed: Temas centrais permitidos.
    - Forbidden: O que quebra a imersão se essa classe fizer.
    - Style: Descrição visual.
    """)
    
    human_msg = HumanMessage(content=f"Classe: {class_name}\nConceito: {concept_desc}")
    
    try:
        gen = llm.with_structured_output(ClassTheme)
        theme = gen.invoke([system_msg, human_msg])
        if theme:
            _THEME_CACHE[key] = theme
            return theme
    except Exception as e:
        print(f"[THEME ERROR] {e}")

    # Fallback
    return ClassTheme(allowed=["Habilidades Básicas"], forbidden=["Deuses"], style="Genérico")

def get_power_guideline(level: int) -> str:
    if level <= 4: return "TIER 1 (Iniciante): Dano baixo, local, sem voo."
    if level <= 10: return "TIER 2 (Heroico): Dano médio, área pequena, voo curto."
    if level <= 16: return "TIER 3 (Mestre): Dano alto, exércitos, ressurreição."
    return "TIER 4 (Lenda): Alteração da realidade."