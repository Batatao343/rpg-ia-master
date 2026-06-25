"""
agents/archivist.py
Gerencia a Memória de Curto (Resumo) e Longo Prazo (RAG) da sessão.
"""
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field
from llm_setup import get_llm, ModelTier
from rag import add_memory_to_session
from state import GameState

class MemoryUpdate(BaseModel):
    new_summary: str = Field(description="Um parágrafo atualizado resumindo a situação ATUAL e imediata da história.")
    important_facts: list[str] = Field(description="Lista de fatos PERMANENTES para salvar no banco de dados (ex: 'Player matou o Rei'). Se nada importante, lista vazia.")
    chronicle_entry: str = Field(
        default="",
        description=(
            "Se algo digno de uma CANÇÃO aconteceu neste turno (uma batalha, uma morte, uma "
            "descoberta, um pacto, uma traição), escreva 1 mini-parágrafo curto (1 a 3 frases) em "
            "PROSA DE MENESTREL — terceira pessoa, evocativo, épico-sombrio, citando o herói pelo nome. "
            "Se o turno foi banal (andar, observar, conversa fiada), deixe VAZIO ('')."
        ),
    )

def archive_node(state: GameState):
    """
    Compacta o histórico recente em um resumo e extrai fatos para o RAG.
    """
    messages = state.get("messages", [])
    game_id = state.get("game_id")
    
    # Se não tiver game_id, aborta
    if not game_id: return {}

    current_summary = state.get("narrative_summary", "A aventura segue.")
    
    # Executa com modelo inteligente para garantir qualidade do resumo
    llm = get_llm(temperature=0.3, tier=ModelTier.SMART)

    sys_msg = SystemMessage(content=f"""
    <ROLE>Memory Manager do RPG</ROLE>
    
    <INPUTS>
    1. Resumo Anterior: "{current_summary}"
    2. Histórico Recente: (Ver mensagens abaixo)
    </INPUTS>
    
    <TAREFA>
    1. ATUALIZAR O RESUMO: Escreva um novo parágrafo que combine o resumo anterior com os novos eventos recentes. Mantenha foco no "Aqui e Agora".
    2. EXTRAIR FATOS (LONG TERM): Identifique fatos cruciais que devem ser lembrados para sempre e salvos no banco de dados.
    3. CRÔNICA DO MENESTREL: se um feito digno de canção ocorreu, escreva 'chronicle_entry' como um mini-parágrafo narrado por um bardo (3ª pessoa, evocativo). Caso contrário, deixe vazio ('').
    
    Se nada grandioso aconteceu, 'important_facts' deve ser [] (vazio).
    """)

    try:
        archivist = llm.with_structured_output(MemoryUpdate)
        # Usa as últimas 8 mensagens para contexto
        context_msgs = messages[-8:] if len(messages) > 8 else messages
        
        result = archivist.invoke([sys_msg] + context_msgs)
        
        updates = {}
        
        # 1. Atualiza RAG (Longo Prazo)
        if result.important_facts:
            add_memory_to_session(game_id, result.important_facts)
            print(f"📚 [ARCHIVIST] Fatos: {result.important_facts}")

        # 2. Retorna atualização de estado (Curto Prazo)
        updates["narrative_summary"] = result.new_summary

        # 3. Crônica do menestrel (longo prazo, exibível): acumula se houve feito notável.
        entry = (getattr(result, "chronicle_entry", "") or "").strip()
        if entry:
            prev = state.get("chronicle", []) or []
            updates["chronicle"] = prev + [entry]

        # Atualiza timestamp da última execução
        turn = state.get("world", {}).get("turn_count", 0)
        updates["archivist_last_run"] = turn

        return updates

    except Exception as e:
        print(f"⚠️ Erro no Arquivista: {e}")
        return {} # Falha segura: não altera estado

# Helper para compatibilidade
def archive_narrative(text: str):
    pass