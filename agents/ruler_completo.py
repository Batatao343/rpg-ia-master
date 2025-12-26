"""
agents/ruler_completo.py
(O Juiz Universal)
Define as regras e interpreta intenções complexas usando o RAG e o Banco de Habilidades.
"""
from typing import Optional, Dict
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from llm_setup import get_llm, ModelTier

# --- INTEGRAÇÕES ---
try:
    from rag import query_rag
except ImportError:
    def query_rag(*args, **kwargs): return "Regras D&D 5e Padrão."

# Tenta carregar as habilidades oficiais para o Juiz não alucinar
try:
    from gamedata import ABILITIES
except ImportError:
    ABILITIES = {}

# --- SCHEMA ROBUSTO ---
class Ruling(BaseModel):
    """Estrutura da decisão do Juiz."""
    is_allowed: bool = Field(description="Se a ação é possível nas regras.")
    dice_formula: str = Field(description="A fórmula exata. Ex: '1d20+5', 'DC 13 Str Save', '0' se não tiver rolagem.")
    mechanical_effect: str = Field(description="O efeito técnico. Ex: 'Dano Cortante', 'Condição Caído', 'Gasta 5 HP'.")
    flavor_text: str = Field(description="Explicação curta da regra aplicada.")

def _find_ability_rule(intent: str) -> str:
    """Procura se a intenção cita alguma habilidade cadastrada."""
    intent_lower = intent.lower()
    for key, data in ABILITIES.items():
        # Verifica se o nome da habilidade (ou chave) está na frase
        if key.lower() in intent_lower or data.get("name", "").lower() in intent_lower:
            return f"""
            [REGRA OFICIAL ENCONTRADA]
            Habilidade: {data.get('name')}
            Custo: {data.get('cost')} {data.get('resource_type')}
            Efeito: {data.get('effect')}
            Fórmula de Dano/Cura: {data.get('damage_formula', 'N/A')}
            Condições: {data.get('conditions', [])}
            """
    return ""

def resolve_action(player: dict, intent: str) -> dict:
    """
    Decide a mecânica para qualquer ação complexa.
    """
    # 1. Preparação do Contexto
    if not intent:
        return {"dice_formula": "0", "mechanical_effect": "Nenhuma ação detectada."}

    # Busca regras específicas no Banco de Habilidades (Prioridade 1)
    ability_context = _find_ability_rule(intent)
    
    # Busca regras gerais no RAG (Prioridade 2)
    try:
        rag_context = query_rag(f"rules for {intent}", index_name="rules")
    except:
        rag_context = ""

    # Monta o Prompt
    system_msg = SystemMessage(content=f"""
    Você é o JUIZ DE REGRAS (Game Master) de um RPG Dark Fantasy.
    Sua função é traduzir a narração do jogador em MECÂNICA DE DADOS.

    <CONTEXTO DO JOGADOR>
    Nome: {player.get('name')}
    Classe: {player.get('class_name')}
    Atributos: {player.get('attributes')}
    </CONTEXTO>

    <BIBLIOTECA DE REGRAS>
    {ability_context}
    {rag_context}
    </BIBLIOTECA>

    <INSTRUÇÕES>
    1. Se o jogador usou uma Habilidade Oficial (listada acima), USE EXATAMENTE os dados dela.
       - Ex: Se "Juramento de Sangue" diz "Gasta 5 HP", o efeito deve ser "Gasta 5 HP, Ganha Buff".
    2. Se for uma manobra física (agarrar, empurrar), use regras de D&D 5e (Atletismo vs Acrobacia/Força).
    3. Se for algo impossível, retorne is_allowed=False.
    4. Em 'dice_formula', retorne APENAS a string de rolagem (ex: '1d20+5'). Se for auto-sucesso ou custo, use '0'.
    """)

    # 2. Chamada da IA
    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
    
    try:
        # Structured Output para garantir o JSON
        judge = llm.with_structured_output(Ruling)
        res = judge.invoke([system_msg, HumanMessage(content=intent)])
        
        print(f"⚖️ [RULER] Decisão: {res.dice_formula} | Efeito: {res.mechanical_effect}")
        return res.model_dump()

    except Exception as e:
        print(f"❌ [RULER ERROR] Falha ao interpretar: {e}")
        # Fallback seguro para não travar o jogo
        return {
            "is_allowed": True,
            "dice_formula": "1d20",
            "flavor_text": "Ação improvisada (Fallback).",
            "mechanical_effect": "Efeito Genérico"
        }