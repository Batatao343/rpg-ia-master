"""
engine_utils.py
Gerencia o ciclo de execução da LLM (Re-Act Loop).
ATUALIZAÇÃO: Suporte seguro a Party (Aliados) sem quebrar lógica existente.
"""
from typing import Dict, Any, List
from langchain_core.messages import AIMessage, ToolMessage, SystemMessage, BaseMessage
from langchain_core.runnables import Runnable
from dice_system import roll_formula

def execute_engine(
    llm: Runnable, 
    system_message: SystemMessage, 
    history: List[BaseMessage], 
    state: Dict[str, Any], 
    node_name: str = "Engine"
) -> Dict[str, Any]:
    
    # 1. Ferramentas
    tools_schema = [
        {
            "name": "roll_dice",
            "description": "Rola dados. Ex: '1d20+5', 'DC 15 Dex', '2d6 damage'.",
            "parameters": {"type": "object", "properties": {"formula": {"type": "string"}}, "required": ["formula"]}
        },
        {
            "name": "update_hp",
            "description": "Aplica dano (negativo) ou cura (positivo) em Player, Aliados ou Inimigos.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "target": {"type": "string", "description": "Nome exato do alvo."}, 
                    "amount": {"type": "integer"}
                }, 
                "required": ["target", "amount"]
            }
        }
    ]
    
    # Proteção contra falha de API
    if getattr(llm, "is_fallback", False):
        return {"messages": history + [AIMessage(content="Erro de API.")]}

    llm_with_tools = llm.bind_tools(tools_schema)
    
    # --- CARREGA ESTADO MÚTAVEL (Cópias seguras) ---
    current_player = state.get("player", {}).copy()
    current_enemies = [e.copy() for e in state.get("enemies", [])]
    current_party = [p.copy() for p in state.get("party", [])] # <--- NOVA LISTA (Segura)
    
    current_messages = [system_message] + history
    
    steps = 0
    max_steps = 8
    
    for _ in range(max_steps):
        steps += 1
        try:
            ai_msg = llm_with_tools.invoke(current_messages)
        except Exception as e:
            print(f"[{node_name} ERROR] {e}")
            # Em caso de erro crítico, aborta o loop mas salva o que já foi feito
            break

        current_messages.append(ai_msg)
        
        if not ai_msg.tool_calls:
            break # É texto, terminamos o turno
            
        # Executa Tools
        tool_outputs = []
        for tool in ai_msg.tool_calls:
            t_id, t_name, t_args = tool["id"], tool["name"], tool["args"]
            result = ""
            
            if t_name == "roll_dice":
                f = t_args.get("formula") or "1d20"
                result = roll_formula(str(f))
                print(f"   🎲 [{node_name}] Rolagem: {f} -> {result}")

            elif t_name == "update_hp":
                tgt = str(t_args.get("target", "")).lower()
                amt = int(t_args.get("amount", 0))
                found = False
                
                # 1. Tenta Player
                if tgt in ["player", "hero", "herói", current_player.get('name', '').lower()]:
                    old = current_player.get('hp', 0)
                    current_player['hp'] = max(0, old + amt)
                    result = f"Player HP updated: {old}->{current_player['hp']}"
                    found = True
                    print(f"   ❤️ [{node_name}] Player HP: {amt} (Atual: {current_player['hp']})")
                
                # 2. Tenta Party (Aliados) - LÓGICA NOVA
                if not found:
                    for ally in current_party:
                        if ally['name'].lower() in tgt:
                            old = ally.get('hp', 0)
                            ally['hp'] = max(0, old + amt)
                            
                            status_msg = ""
                            if ally['hp'] <= 0: 
                                status_msg = " (CAIU INCONSCIENTE!)"
                            
                            result = f"Ally {ally['name']} HP updated: {old}->{ally['hp']}{status_msg}"
                            found = True
                            print(f"   🛡️ [{node_name}] Ally {ally['name']} HP: {amt}{status_msg}")
                            break

                # 3. Tenta Inimigos
                if not found:
                    for e in current_enemies:
                        # Busca flexível por nome ou ID
                        if e['name'].lower() in tgt or "enemy" in tgt or e.get('id', '').lower() in tgt:
                            old = e.get('hp', 0)
                            e['hp'] = max(0, old + amt)
                            
                            status_msg = ""
                            if e['hp'] <= 0: 
                                e['status'] = "morto"
                                status_msg = " (MORTO)"
                                
                            result = f"Enemy {e['name']} HP updated: {old}->{e['hp']}{status_msg}"
                            found = True
                            print(f"   💀 [{node_name}] Enemy {e['name']} HP: {amt}{status_msg}")
                            break
                
                if not found:
                    result = f"Target '{tgt}' not found. Available: Player, Party, Enemies."

            tool_outputs.append(ToolMessage(tool_call_id=t_id, content=result or "Done"))
            
        current_messages.extend(tool_outputs)

    # 3. GARANTIA DE NARRATIVA
    # Se a última mensagem foi um ToolMessage (resultado de dado), a IA ainda precisa narrar o final.
    if isinstance(current_messages[-1], ToolMessage):
        try:
            # Chamada extra apenas para texto final
            final_narrative = llm.invoke(current_messages)
            current_messages.append(final_narrative)
        except Exception:
            pass

    # 4. Retorno Seguro
    # Filtra as mensagens antigas para não duplicar histórico
    new_messages = current_messages[1 + len(history):]
    
    return {
        "messages": new_messages,
        "player": current_player,
        "enemies": current_enemies,
        "party": current_party, # <--- Retorna a party atualizada
        "world": state.get("world", {}),
        "combat_target": state.get("combat_target"),
        "next": state.get("next")
    }