"""
logic/adjudicator.py
O Juiz Universal. Valida intenções contra os Temas de Classe e Nível.
"""
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import Optional

from llm_setup import get_llm, ModelTier
from agents.class_themes import get_class_theme, get_power_guideline

class ActionJudgment(BaseModel):
    is_allowed: bool = Field(description="Se a ação é permitida para este personagem.")
    rejection_reason: Optional[str] = Field(description="Se negado, explique o motivo (ex: 'Nível insuficiente', 'Tema proibido').")
    flavor_text: str = Field(description="Descrição visual da ação (sucesso ou tentativa).")
    mechanical_effect: str = Field(description="Tradução para regras: Dano (ex: 4d6), CD (DC 15) ou Condição.")

def resolve_dynamic_action(player: dict, intent: str) -> dict:
    """
    Analisa a intenção do jogador e retorna o veredito do Juiz.
    """
    level = player.get("level", 1)
    p_class = player.get("class_name", "Aventureiro")
    concept = player.get("concept", "") # Ex: "Necromante de Fungos"
    
    # Busca dinâmica (Cria o tema se for classe nova)
    theme = get_class_theme(p_class, concept_desc=concept)
    power_scale = get_power_guideline(level)
    
    system_msg = SystemMessage(content=f"""
    <role>
    Você é o Adjudicador de Regras (Game Logic Judge).
    Sua função é validar a COERÊNCIA e o NÍVEL DE PODER da ação, não narrar a história.
    </role>
    
    <context>
    Personagem: {p_class} (Nível {level})
    Conceito: {concept}
    
    [LEIS DA CLASSE]
    - Permitido: {', '.join(theme.allowed)}
    - Proibido: {', '.join(theme.forbidden)}
    - Estilo Visual: {theme.style}
    
    [ESCALA DE PODER ATUAL]
    {power_scale}
    </context>

    <instructions>
    1. Ação Proibida? A intenção viola os temas 'Proibidos'? (Ex: Paladino usando Necromancia). Se sim, is_allowed=False.
    2. Nível Adequado? A intenção cabe na 'Escala de Poder'?
       - Se for muito forte (ex: Lv1 querendo Chuva de Meteoros), NÃO NEGUE. Apenas ENFRAQUEÇA o efeito (Nerf) em 'mechanical_effect'.
       - Ex: "Chuva de Meteoros" no Lv1 vira "Uma pedra quente cai do céu (1d4 dano)."
    3. Output: Gere o 'flavor_text' visual e o 'mechanical_effect' exato para o Agente de Combate usar.
    </instructions>
    """)

    llm = get_llm(temperature=0.1, tier=ModelTier.FAST)
    
    try:
        judge = llm.with_structured_output(ActionJudgment)
        return judge.invoke([system_msg, HumanMessage(content=intent)]).model_dump()
    except Exception as e:
        print(f"[ADJUDICATOR ERROR] {e}")
        # Fallback seguro
        return {
            "is_allowed": True,
            "rejection_reason": None,
            "flavor_text": "Você avança com determinação.",
            "mechanical_effect": "Ação Padrão (Dano da Arma ou CD 15)."
        }