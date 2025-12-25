"""
agents/ruler_completo.py
(O Juiz Universal)
Define as regras. NÃO importa nada de agents.combat ou agents.storyteller.
"""
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from llm_setup import get_llm, ModelTier

# Fontes de Conhecimento (ajuste os caminhos conforme sua estrutura)
# Se você não tiver o arquivo themes ou rag, pode comentar os imports para testar
try:
    from agents.class_themes import get_class_theme, get_power_guideline
    from rag import query_rag
except ImportError:
    # Fallback para caso os arquivos não existam no teste isolado
    def get_class_theme(*args, **kwargs): return type('obj', (object,), {'style': 'Genérico', 'allowed': 'Tudo'})
    def get_power_guideline(*args): return "Nível Padrão"
    def query_rag(*args, **kwargs): return "Regras D&D 5e Padrão"

class Ruling(BaseModel):
    is_allowed: bool
    rejection_reason: str = ""
    flavor_text: str = Field(description="Explicação curta da regra aplicada.")
    dice_formula: str = Field(description="A fórmula exata. Ex: '1d20+5 Attack', 'DC 13 Str Save'.")
    mechanical_effect: str = Field(description="Efeito. Ex: 'Dano Contundente', 'Condição Caído'.")

def resolve_action(player: dict, intent: str, context: str = "geral") -> dict:
    """
    Decide a mecânica para qualquer ação.
    """
    level = player.get("level", 1)
    p_class = player.get("class_name", "Aventureiro")
    
    intent_lower = intent.lower()
    magic_keywords = ["conjuro", "magia", "cast", "spell", "invoco", "fireball", "curar"]
    is_magic = any(k in intent_lower for k in magic_keywords)
    
    combat_keywords = ["agarro", "grapple", "empurro", "shove", "derrub", "rasteira", "desarm", "esquiva", "dodge"]
    is_maneuver = any(k in intent_lower for k in combat_keywords)

    knowledge_context = ""

    if is_magic:
        concept = player.get("concept", "")
        theme = get_class_theme(p_class, concept_desc=concept)
        power = get_power_guideline(level)
        knowledge_context = f"Regras de Magia: {theme.style} | Permitido: {theme.allowed}"
    
    elif is_maneuver:
        try:
            rag_data = query_rag(f"combat rules for {intent}", index_name="rules")
            knowledge_context = f"Regras de Combate (RAG): {rag_data}"
        except:
            knowledge_context = "Regras Padrão de Combate D&D 5e."
            
    else:
        try:
            rag_data = query_rag(intent, index_name="rules")
            knowledge_context = f"Regras Gerais: {rag_data}"
        except:
            knowledge_context = "Regras Gerais D&D 5e."

    system_msg = SystemMessage(content=f"""
    <role>Juiz de Regras D&D 5e</role>
    <library>{knowledge_context}</library>
    <instructions>
    Analise a ação: "{intent}".
    Retorne a 'dice_formula' correta (Ex: 'DC 15 Dex Save', '1d20+5 Attack') e o 'mechanical_effect'.
    </instructions>
    """)

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)
    
    try:
        judge = llm.with_structured_output(Ruling)
        res = judge.invoke([system_msg, HumanMessage(content=intent)])
        return res.model_dump()
    except Exception as e:
        print(f"[RULER ERROR] {e}")
        return {
            "is_allowed": True,
            "dice_formula": "1d20 Check",
            "flavor_text": "Ação genérica.",
            "mechanical_effect": "Nenhum"
        }