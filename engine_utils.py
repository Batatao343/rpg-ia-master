"""
engine_utils.py
Gerencia o ciclo de execução da LLM e Ferramentas (Roll, UpdateHP, Transaction).
"""
from typing import Dict, Any, List
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, BaseMessage
from langchain_core.runnables import Runnable
from dice_system import roll_formula
from gamedata import ARTIFACTS_DB

def execute_engine(
    llm: Runnable, 
    system_message: SystemMessage, 
    history: List[BaseMessage], 
    state: Dict[str, Any], 
    node_name: str = "Engine"
) -> Dict[str, Any]:
    
    # 1. Ferramentas (Schema)
    tools_schema = [
        {
            "name": "roll_dice",
            "description": "Rola dados. Ex: '1d20+5'.",
            "parameters": {"type": "object", "properties": {"formula": {"type": "string"}}, "required": ["formula"]}
        },
        {
            "name": "update_hp",
            "description": "Dano/Cura em Player/NPCs.",
            "parameters": {
                "type": "object", 
                "properties": {"target": {"type": "string"}, "amount": {"type": "integer"}}, 
                "required": ["target", "amount"]
            }
        },
        {
            "name": "transaction",
            "description": "Compra ou Venda de itens.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "action": {"type": "string", "enum": ["buy", "sell"]},
                    "item_id": {"type": "string", "description": "ID exato do item"}
                },
                "required": ["action", "item_id"]
            }
        }
    ]
    
    if getattr(llm, "is_fallback", False): return {"messages": history + [AIMessage("Erro API.")]}

    llm_with_tools = llm.bind_tools(tools_schema)
    
    # Cópias seguras do estado
    current_player = state.get("player", {}).copy()
    current_enemies = [e.copy() for e in state.get("enemies", [])]
    current_party = [p.copy() for p in state.get("party", [])]
    
    current_messages = [system_message] + history
    
    steps = 0
    max_steps = 8
    
    for _ in range(max_steps):
        steps += 1
        try:
            ai_msg = llm_with_tools.invoke(current_messages)
        except Exception as e:
            print(f"[{node_name} ERROR] {e}")
            break

        current_messages.append(ai_msg)
        
        if not ai_msg.tool_calls:
            break
            
        tool_outputs = []
        for tool in ai_msg.tool_calls:
            t_id, t_name, t_args = tool["id"], tool["name"], tool["args"]
            result = ""
            
            # --- TOOL: ROLL DICE ---
            if t_name == "roll_dice":
                f = t_args.get("formula") or "1d20"
                result = roll_formula(str(f))
                print(f"   🎲 [{node_name}] {f} -> {result}")

            # --- TOOL: TRANSACTION (ECONOMIA) ---
            elif t_name == "transaction":
                action = t_args.get("action")
                iid = t_args.get("item_id")
                item = ARTIFACTS_DB.get(iid)
                
                if not item:
                    result = f"Item ID '{iid}' não encontrado no banco de dados."
                else:
                    price = item.get("value_gold", 0)
                    if action == "buy":
                        if current_player.get("gold", 0) >= price:
                            current_player["gold"] -= price
                            current_player["inventory"].append(iid)
                            result = f"Sucesso: Comprou {item['name']} por {price} ouro."
                            print(f"   💰 Buy: {iid} (-{price}g)")
                        else:
                            result = f"Falha: Ouro insuficiente ({current_player.get('gold')} < {price})."
                    elif action == "sell":
                        if iid in current_player.get("inventory", []):
                            current_player["inventory"].remove(iid)
                            current_player["gold"] += price
                            result = f"Sucesso: Vendeu {item['name']} por {price} ouro."
                            print(f"   💰 Sell: {iid} (+{price}g)")
                        else:
                            result = "Falha: Você não possui este item."

            # --- TOOL: UPDATE HP ---
            elif t_name == "update_hp":
                tgt = str(t_args.get("target", "")).lower()
                amt = int(t_args.get("amount", 0))
                found = False
                
                # Player
                if tgt in ["player", "hero", current_player.get('name', '').lower()]:
                    old = current_player.get('hp', 0)
                    current_player['hp'] = max(0, old + amt)
                    result = f"Player HP: {old}->{current_player['hp']}"
                    found = True
                
                # Party
                if not found:
                    for ally in current_party:
                        if ally['name'].lower() in tgt:
                            old = ally.get('hp', 0)
                            ally['hp'] = max(0, old + amt)
                            result = f"Ally {ally['name']} HP: {old}->{ally['hp']}"
                            found = True
                            break
                
                # Enemies
                if not found:
                    for e in current_enemies:
                        if e['name'].lower() in tgt or e.get('id', '').lower() in tgt:
                            old = e.get('hp', 0)
                            e['hp'] = max(0, old + amt)
                            if e['hp'] <= 0: e['status'] = "morto"
                            result = f"Enemy {e['name']} HP: {old}->{e['hp']}"
                            found = True
                            break
                
                if not found: result = f"Target '{tgt}' not found."

            tool_outputs.append(ToolMessage(tool_call_id=t_id, content=result or "Done"))
            
        current_messages.extend(tool_outputs)

    if isinstance(current_messages[-1], ToolMessage):
        try:
            final_narrative = llm.invoke(current_messages)
            current_messages.append(final_narrative)
        except: pass

    # Filtra histórico original
    new_messages = current_messages[1 + len(history):]
    
    return {
        "messages": new_messages,
        "player": current_player,
        "enemies": current_enemies,
        "party": current_party,
        "world": state.get("world", {}),
        "combat_target": state.get("combat_target"),
        "next": state.get("next")
    }