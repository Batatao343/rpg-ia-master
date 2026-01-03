"""
test_npc_interaction.py
Script isolado para testar interações sociais com NPCs.
Verifica: Persona, Memória e Reatividade.
"""
import sys
import os
import random
from langchain_core.messages import HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gamedata import load_json_data
from agents.npc import npc_actor_node

# --- CORES ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def get_diverse_npcs():
    """Tenta selecionar 3 NPCs de locais diferentes."""
    db = load_json_data("npc_database.json")
    if not db:
        print("❌ Erro: npc_database.json vazio ou não encontrado.")
        return []

    # Agrupa por local
    by_location = {}
    for nid, data in db.items():
        loc = data.get("location", "Desconhecido")
        if loc not in by_location: by_location[loc] = []
        # Adiciona ID ao objeto para referência
        data["id"] = nid
        by_location[loc].append(data)

    selected = []
    locations = list(by_location.keys())
    
    # Tenta pegar 1 de cada local (até 3)
    for loc in locations[:3]:
        npc = random.choice(by_location[loc])
        selected.append(npc)
    
    # Se faltar (menos de 3 locais), preenche com aleatórios
    while len(selected) < 3 and len(db) > len(selected):
        remaining = [d for nid, d in db.items() if d not in selected]
        if remaining:
            selected.append(random.choice(remaining))
            
    return selected

def run_chat_session(npc_data):
    clear_screen()
    npc_name = npc_data['name']
    npc_id = npc_data['id']
    location = npc_data.get('location', 'Desconhecido')
    
    print(f"{Colors.HEADER}=== TESTE DE INTERAÇÃO SOCIAL ==={Colors.ENDC}")
    print(f"Alvo: {Colors.BOLD}{npc_name}{Colors.ENDC}")
    print(f"Local: {location}")
    print(f"Persona: {npc_data.get('persona', 'N/A')}")
    print("-" * 50)
    print("Digite 'sair' para voltar ao menu ou 'memoria' para ver o que o NPC lembra.\n")

    # Estado Mockado (Simulado)
    state = {
        "player": {"name": "Tester", "class": "Game Master", "level": 99, "gold": 1000},
        "world": {"current_location": location, "time_of_day": "Tarde"},
        "active_npc_name": npc_id,
        "npcs": {npc_id: npc_data}, # Carrega o NPC no estado
        "messages": [],
        "next": "npc_actor"
    }
    
    # Boot inicial (O jogador se aproxima)
    print(f"{Colors.YELLOW}[Sistema] Você se aproxima de {npc_name}...{Colors.ENDC}")

    while True:
        try:
            user_input = input(f"\n{Colors.BOLD}Você: {Colors.ENDC}").strip()
            if not user_input: continue
            
            if user_input.lower() in ["sair", "exit"]:
                break
                
            if user_input.lower() == "memoria":
                mem = state["npcs"][npc_id].get("memory", [])
                print(f"\n{Colors.CYAN}🧠 Memória de {npc_name}:{Colors.ENDC}")
                for m in mem:
                    print(f" - {m}")
                continue

            # Adiciona mensagem e roda o agente
            current_msgs = state.get("messages", [])
            current_msgs.append(HumanMessage(content=user_input))
            state["messages"] = current_msgs
            
            print(f"{Colors.GREEN}... {npc_name} está pensando ...{Colors.ENDC}", end="\r")
            
            # --- EXECUÇÃO DO NÓ ---
            result = npc_actor_node(state)
            # ----------------------
            
            # Atualiza estado
            state["npcs"] = result["npcs"] # Importante: Atualiza memória
            state["messages"] = result["messages"]
            
            last_msg = result["messages"][-1].content
            print(f"\n{Colors.GREEN}{npc_name}: {Colors.ENDC}{last_msg}")

        except Exception as e:
            print(f"\n❌ Erro: {e}")
            break

def main():
    while True:
        clear_screen()
        print(f"{Colors.HEADER}🔍 SELETOR DE NPC PARA TESTE{Colors.ENDC}")
        
        candidates = get_diverse_npcs()
        if not candidates: return

        for i, npc in enumerate(candidates):
            print(f"{i+1}. {Colors.BOLD}{npc['name']}{Colors.ENDC} ({npc.get('location')}) - {npc.get('role')}")
        
        print("0. Sair")
        
        opt = input("\nEscolha com quem conversar [1-3]: ").strip()
        
        if opt == "0": break
        
        if opt in ["1", "2", "3"] and int(opt) <= len(candidates):
            selected = candidates[int(opt)-1]
            run_chat_session(selected)
        else:
            input("Opção inválida. Enter para continuar...")

if __name__ == "__main__":
    main()