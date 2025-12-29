"""
agents/loot.py
Gerenciador de Loot, Comércio e Crafting.
Versão Corrigida: Prompt de Venda melhorado e tratamento de erro reforçado.
"""
import random
import unicodedata
from typing import List, Optional
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from pydantic import BaseModel, Field

from state import GameState
from llm_setup import get_llm, ModelTier
from gamedata import save_custom_artifact, ARTIFACTS_DB

# --- SCHEMAS DE DADOS (IA) ---

class ItemGeneration(BaseModel):
    name: str = Field(description="Nome épico do item.")
    item_id: str = Field(description="ID único (snake_case). Ex: espada_fogo_azul")
    description: str
    type: str = Field(description="weapon, armor, potion, ou material")
    rarity: str
    gold_value: int
    combat_stats: dict = Field(description="Ex: {'attack_bonus': 2, 'damage': '1d8'}")
    mechanics: dict = Field(description="Efeitos passivos ou ativos.")

class TransactionResult(BaseModel):
    """Resultado de uma operação de Crafting ou Comércio."""
    success: bool = Field(description="Se a transação foi possível.")
    message: str = Field(description="Narrativa do resultado.")
    items_to_remove: List[str] = Field(default=[], description="IDs exatos dos itens consumidos/vendidos.")
    gold_cost: int = Field(default=0, description="Ouro gasto pelo jogador (negativo se o jogador GANHOU ouro).")
    new_item: Optional[ItemGeneration] = Field(None, description="O novo item criado. DEIXE NULL SE FOR VENDA.")

# --- LÓGICA DO NÓ ---

def loot_node(state: GameState):
    player = state["player"]
    loot_source = state.get("loot_source", "TREASURE")
    
    # Recupera última msg
    last_user_msg = "Gerar loot"
    if state.get("messages"):
        last_msg = state["messages"][-1]
        if isinstance(last_msg, HumanMessage):
            last_user_msg = last_msg.content
    
    llm = get_llm(temperature=0.4, tier=ModelTier.SMART)

    # =========================================================
    # MODO 1: CRAFTING / SHOP
    # =========================================================
    if loot_source in ["CRAFT", "SHOP"]:
        inventory_list = ", ".join(player["inventory"])
        gold_available = player["gold"]
        
        sys_prompt = """
        Você é o Motor de Comércio e Crafting de um RPG.
        
        TAREFA: Decida a transação baseada no pedido e inventário.
        
        MODOS:
        1. CRAFT/UPGRADE/COMPRA: 
           - Gera um 'new_item'.
           - Cobra 'gold_cost' (positivo).
           - Remove itens usados em 'items_to_remove'.
           
        2. VENDA (Jogador vendendo item):
           - Remove o item em 'items_to_remove'.
           - 'gold_cost' deve ser NEGATIVO (ex: -50 significa que o jogador GANHA 50).
           - 'new_item' DEVE SER NULL (None).
        
        Se faltar recurso ou item, success=False.
        """

        user_prompt = f"""
        INVENTÁRIO: [{inventory_list}]
        OURO: {gold_available}
        PEDIDO: "{last_user_msg}"
        """
        
        try:
            trans_engine = llm.with_structured_output(TransactionResult)
            result = trans_engine.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            if not result.success:
                return {
                    "messages": [AIMessage(content=f"🚫 {result.message}")],
                    "loot_source": None
                }
            
            # --- APLICAÇÃO DA MECÂNICA ---
            
            # A. Remove Itens
            for item_id in result.items_to_remove:
                if item_id in player["inventory"]:
                    player["inventory"].remove(item_id)
            
            # B. Atualiza Ouro
            player["gold"] -= result.gold_cost
            
            # C. Adiciona Item (Se houver)
            # Verifica explicitamente se new_item existe e não é vazio
            if result.new_item and result.new_item.name:
                raw_id = result.new_item.item_id.lower().replace(" ", "_")
                item_data = result.new_item.model_dump()
                item_data["item_id"] = raw_id
                save_custom_artifact(raw_id, item_data)
                
                player["inventory"].append(raw_id)
                msg_final = f"{result.message}\n\n[SISTEMA] +1 {result.new_item.name} | {result.gold_cost * -1} Ouro"
            else:
                # Caso de Venda (sem item novo)
                msg_final = f"{result.message}\n\n[SISTEMA] Ouro: {player['gold']} (Variação: {result.gold_cost * -1})"

            return {
                "player": player,
                "messages": [AIMessage(content=msg_final)],
                "loot_source": None
            }

        except Exception as e:
            print(f"Erro Crafting Detail: {e}")
            return {"messages": [AIMessage(content="O mercador franze a testa. (Transação falhou)")]}

    # =========================================================
    # MODO 2: TREASURE
    # =========================================================
    else: 
        class LootSchema(BaseModel):
            items: List[ItemGeneration]
            gold: int
            narrative: str

        sys_prompt = "Você é um Gerador de Loot de RPG."
        danger_lvl = state.get('world',{}).get('danger_level', 1)
        user_prompt = f"Gere loot para perigo nível {danger_lvl}. Máx 2 itens."

        try:
            loot_llm = llm.with_structured_output(LootSchema)
            res = loot_llm.invoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            added_names = []
            for item in res.items:
                raw_id = item.item_id.lower().replace(" ", "_")
                save_custom_artifact(raw_id, item.model_dump())
                player["inventory"].append(raw_id)
                added_names.append(item.name)
            
            player["gold"] += res.gold
            
            msg = f"{res.narrative}\n[+ {', '.join(added_names)} | +{res.gold} Ouro]"
            return {
                "player": player,
                "messages": [AIMessage(content=msg)],
                "loot_source": None
            }
        except Exception as e:
            return {"messages": [AIMessage(content="Você vasculha, mas não encontra nada.")]}