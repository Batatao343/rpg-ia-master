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

# Temas de classe (gating de habilidades abertas — Fase 0)
try:
    from agents.class_themes import get_class_theme
except ImportError:
    def get_class_theme(_name): return {"allowed": [], "forbidden": [], "style": ""}

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

    # Tema da classe: o que faz (ou não) sentido este personagem tentar.
    class_name = player.get("class_name") or player.get("class") or ""
    theme = get_class_theme(class_name)
    abilities = player.get("known_abilities", [])

    # Monta o Prompt
    system_msg = SystemMessage(content=f"""
    Você é o JUIZ DE REGRAS (Game Master) de um RPG Dark Fantasy.
    Sua função é traduzir a narração do jogador em MECÂNICA DE DADOS.

    <CONTEXTO DO JOGADOR>
    Nome: {player.get('name')}
    Classe: {class_name}
    Atributos: {player.get('attributes')}
    Habilidades conhecidas: {abilities}
    </CONTEXTO>

    <TEMA DA CLASSE>
    PERMITIDO (faz sentido): {theme.get('allowed')}
    PROIBIDO (quebra o personagem): {theme.get('forbidden')}
    Estilo: {theme.get('style')}
    </TEMA>

    <BIBLIOTECA DE REGRAS>
    {ability_context}
    {rag_context}
    </BIBLIOTECA>

    <INSTRUÇÕES>
    1. AÇÃO ABERTA: o jogador pode TENTAR qualquer coisa. Só permita o que faz sentido
       para esta classe e ficha. Se a ação está em PROIBIDO ou exige poder que esta classe
       não tem (ex.: um Guerreiro lançando magia arcana), retorne is_allowed=False e explique
       no flavor_text por que falha — sem humilhar, mas deixando claro o limite.
    2. Se for plausível porém difícil, permita com um teste de atributo coerente
       (ex.: Força para arrombar, Destreza para furtividade).
    3. Se usou uma Habilidade Oficial (listada acima), USE EXATAMENTE os dados dela.
    4. Se for manobra física (agarrar, empurrar), use regras de D&D 5e.
    5. Em 'dice_formula', retorne APENAS a string de rolagem (ex: '1d20+5'). Se for
       auto-sucesso, custo ou falha automática, use '0'.
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