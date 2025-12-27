"""
agents/librarian.py
Utilitário de consistência. Verifica se entidades já existem antes de criar novas.
"""
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from llm_setup import get_llm, ModelTier

class EntityMatch(BaseModel):
    match_found: bool = Field(description="True se o pedido se refere a algo que já existe na lista.")
    existing_id: Optional[str] = Field(description="O ID exato da lista que corresponde ao pedido. Null se não houver match.")

def find_existing_entity(user_query: str, entity_type: str, existing_ids: List[str]) -> Optional[str]:
    """
    Usa IA para verificar se 'Varg' é o mesmo que 'Varg, o Açougueiro'.
    Retorna o ID existente ou None se for algo novo.
    """
    # 1. Otimização: Se a lista estiver vazia, nem chama a IA.
    if not existing_ids:
        return None

    # 2. Otimização Clássica: Tenta match exato primeiro (economiza tokens)
    query_slug = user_query.lower().replace(" ", "_")
    if query_slug in existing_ids:
        return query_slug

    # 3. Match Semântico com IA
    # Se a lista for gigantesca, pegar apenas os primeiros 100 ou fazer filtro fuzzy antes seria ideal
    # Para este escopo, assumimos listas gerenciáveis.
    
    print(f"🔍 [LIBRARIAN] Verificando duplicatas para: '{user_query}' em {entity_type}...")
    
    llm = get_llm(temperature=0.0, tier=ModelTier.FAST)
    
    ids_str = ", ".join(existing_ids[:200]) # Limite de segurança para context window
    
    system_msg = SystemMessage(content=f"""
    Você é um Bibliotecário de Banco de Dados de um RPG.
    Identifique se o pedido do usuário se refere a uma entidade que JÁ EXISTE no banco.
    
    TIPO DE ENTIDADE: {entity_type}
    BANCO DE DADOS (IDs existentes):
    [{ids_str}]
    
    REGRAS DE MATCH:
    1. Ignore diferenças de títulos (Ex: "Varg" == "npc_varg_acougueiro").
    2. Ignore sinônimos óbvios (Ex: "Espada de Fogo" == "item_lamina_chamas").
    3. Se houver ambiguidade ou certeza baixa, retorne match_found=False.
    4. Se for algo GENÉRICO (ex: "Um goblin") e houver vários, retorne False (crie um novo).
    5. Apenas nomes PRÓPRIOS ou itens ÚNICOS devem dar match.
    """)
    
    human_msg = HumanMessage(content=f"Query: {user_query}")
    
    try:
        matcher = llm.with_structured_output(EntityMatch)
        result = matcher.invoke([system_msg, human_msg])
        
        if result.match_found and result.existing_id in existing_ids:
            print(f"✅ [LIBRARIAN] Match encontrado: '{user_query}' -> '{result.existing_id}'")
            return result.existing_id
        
    except Exception as e:
        print(f"⚠️ Erro no Librarian: {e}")
        
    print(f"🆕 [LIBRARIAN] Nenhum match. Entidade nova.")
    return None