"""
engine_utils.py
Gerencia o ciclo de execução da LLM (Re-Act Loop).
CORREÇÃO: Garante narrativa final e suporta turnos longos.
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
            "description": "Rola dados. Ex: '1d20+5', 'DC 15 Dex, 8d6 fire'.",
            "parameters": {"type": "object", "properties": {"formula": {"type": "string"}}, "required": ["formula"]}
        },
        {
            "name": "update_hp",
            "description": "Aplica dano (negativo) ou cura (positivo).",
            "parameters": {
                "type": "object", 
                "properties": {
                    "target": {"type": "string"}, 
                    "amount": {"type": "integer"}
                }, 
                "required": ["target", "amount"]
            }
        }
    ]
    
    if getattr(llm, "is_fallback", False):
        return {"messages": history + [AIMessage(content="Erro de API.")]}

    llm_with_tools = llm.bind_tools(tools_schema)
    
    current_player = state.get("player", {}).copy()
    current_enemies = [e.copy() for e in state.get("enemies", [])]
    
    # Inicia histórico
    current_messages = [system_message] + history
    
    # 2. Loop de Execução (Até 8 passos para garantir turno complexo)
    steps = 0
    max_steps = 8
    
    for _ in range(max_steps):
        steps += 1
        try:
            ai_msg = llm_with_tools.invoke(current_messages)
        except Exception as e:
            print(f"[{node_name} ERROR] {e}")
            ai_msg = AIMessage(content="Ação interrompida.")
            break

        current_messages.append(ai_msg)
        
        if not ai_msg.tool_calls:
            break # É texto, terminamos
            
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
                
                # Player
                if "player" in tgt or "hero" in tgt or current_player['name'].lower() in tgt:
                    old = current_player['hp']
                    current_player['hp'] = max(0, old + amt)
                    result = f"Player HP updated: {old}->{current_player['hp']}"
                    print(f"   ❤️ [{node_name}] Player HP: {amt} (Atual: {current_player['hp']})")
                
                # Enemies
                for e in current_enemies:
                    if e['id'] in tgt or e['name'].lower() in tgt or "enemy" in tgt:
                        old = e['hp']
                        e['hp'] = max(0, old + amt)
                        if e['hp'] <= 0: e['status'] = "morto"
                        result = f"Enemy {e['name']} HP updated: {old}->{e['hp']}"
                        print(f"   💀 [{node_name}] Enemy HP: {amt} (Atual: {e['hp']})")

            tool_outputs.append(ToolMessage(tool_call_id=t_id, content=result or "Done"))
            
        current_messages.extend(tool_outputs)

    # 3. GARANTIA DE NARRATIVA (A Correção Principal)
    # Se o loop acabou e a última mensagem foi um ToolMessage (resultado de HP),
    # a IA ainda não narrou o final. Forçamos uma chamada extra.
    last_msg = current_messages[-1]
    if isinstance(last_msg, ToolMessage):
        print(f"   📝 [{node_name}] Forçando narrativa final...")
        try:
            # Chamamos o LLM puro (sem tools obrigatórias) apenas para narrar
            final_narrative = llm.invoke(current_messages)
            current_messages.append(final_narrative)
        except Exception:
            pass

    # 4. Retorno
    start_index = 1 + len(history)
    new_messages = current_messages[start_index:]
    
    return {
        "messages": new_messages,
        "player": current_player,
        "enemies": current_enemies,
        "world": state.get("world", {}),
        "combat_target": state.get("combat_target"),
        "next": state.get("next")
    }