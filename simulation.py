import sys
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from main import app # Importa o grafo V8
from state import GameState

# Configuração Inicial de Teste
initial_state: GameState = {
    "messages": [],
    "player": {
        "name": "Tester", "class_name": "Debug Warrior",
        "hp": 30, "max_hp": 30, "mana": 10, "max_mana": 10, 
        "stamina": 20, "max_stamina": 20, "gold": 100, "xp": 0, "level": 1, "alignment": "N",
        "attributes": {"strength": 18, "dexterity": 14, "constitution": 14, "intelligence": 10, "wisdom": 12, "charisma": 10},
        "inventory": ["Espada de Debug", "Poção de Teste"],
        "known_abilities": ["Golpe Devastador"],
        "defense": 16, "attack_bonus": 5, "active_conditions": []
    },
    "world": {
        "current_location": "Arena de Debug", "time_of_day": "Eterno", "turn_count": 0, "weather": "Estático", "quest_plan": [], "quest_plan_origin": None
    },
    # Listas vazias cruciais para V8 não crashar
    "enemies": [], "party": [], "npcs": {}, "active_npc_name": None, "next": None
}

def run_simulation():
    print("=== RPG ENGINE V8 (TERMINAL MODE) ===")
    print("Digite 'sair' para encerrar. Digite 'status' para ver stats.")
    
    state = initial_state
    
    # Loop do Jogo
    while True:
        user_input = input("\n👤 Você: ")
        
        if user_input.lower() in ["sair", "exit"]:
            break
            
        if user_input.lower() == "status":
            p = state['player']
            print(f"\n📊 STATUS: HP {p['hp']}/{p['max_hp']} | ST {p['stamina']} | MANA {p['mana']}")
            print(f"🗡️ INIMIGOS: {len([e for e in state.get('enemies',[]) if e['status'] == 'ativo'])}")
            continue

        # Adiciona input
        state["messages"].append(HumanMessage(content=user_input))
        
        print("🤖 Pensando...", end="\r")
        
        try:
            # Executa o Grafo
            # O Graph V8 retorna o estado final após passar por todos os nós necessários
            state = app.invoke(state)
            
            # Pega a última resposta da IA para exibir
            last_msg = state["messages"][-1]
            if isinstance(last_msg, AIMessage):
                print(f"\n🎲 Mestre: {last_msg.content}")
                
            # Mostra diffs rápidos de combate
            if state.get('enemies'):
                active = [e for e in state['enemies'] if e['status'] == 'ativo']
                if active:
                    print(f"\n[COMBATE] Inimigos Ativos: {len(active)}")
                    for e in active:
                        conds = f" {e['active_conditions']}" if e['active_conditions'] else ""
                        print(f"   - {e['name']}: {e['hp']} HP{conds}")

        except Exception as e:
            print(f"\n❌ ERRO CRÍTICO: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_simulation()