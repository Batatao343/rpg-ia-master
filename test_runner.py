import sys
import random
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Imports dos Agentes e Estado
from state import GameState
from agents.router import dm_router_node
from agents.combat import combat_node
from agents.rules import rules_node
from agents.npc import npc_actor_node, generate_new_npc # Importa o gerador direto
from agents.storyteller import storyteller_node

# Imports da Engine para testar Spawn de Inimigo
from engine_utils import apply_state_update, EngineUpdate 

def create_base_state() -> GameState:
    return {
        "messages": [],
        "player": {
            "name": "Tester", 
            "class_name": "Debug", 
            "hp": 30, 
            "max_hp": 30, 
            
            # --- CORREÇÃO: Adicionados os limites máximos ---
            "stamina": 20, 
            "max_stamina": 20, 
            "mana": 10, 
            "max_mana": 10,
            # ------------------------------------------------
            
            "gold": 100, 
            "xp": 0, 
            "level": 1, 
            "alignment": "N",
            "attributes": {
                "strength": 10, "dexterity": 10, "constitution": 10, 
                "intelligence": 10, "wisdom": 10, "charisma": 10
            },
            "inventory": ["Espada"], 
            "known_abilities": [], 
            "defense": 10, 
            "attack_bonus": 0, 
            "active_conditions": []
        },
        "world": {
            "current_location": "Lab de Testes",
            "time_of_day": "Dia",
            "turn_count": 0,
            "weather": "Neutro",
            "quest_plan": [],
            "quest_plan_origin": None,
        },
        "enemies": [], 
        "party": [], 
        "npcs": {}, 
        "active_npc_name": None, 
        "next": None
    }

# --- 2. FERRAMENTAS DE VISUALIZAÇÃO ---
def print_header(title):
    print(f"\n{'='*10} {title} {'='*10}")

def print_result(old_state, new_state, agent_name):
    print(f"🔍 ANÁLISE DO AGENTE: {agent_name}")
    
    # HP Player
    hp_diff = new_state['player']['hp'] - old_state['player']['hp']
    if hp_diff != 0: print(f"   ❤️ HP Player: {hp_diff}")
    
    # Inimigos
    if new_state.get('enemies'):
        for e in new_state['enemies']:
            old_e = next((x for x in old_state.get('enemies', []) if x['id'] == e['id']), None)
            if not old_e:
                print(f"   🆕 INIMIGO NOVO: {e['name']} (HP: {e['hp']})")
                print(f"      Desc: {e.get('desc', 'N/A')}")
                print(f"      Habilidades: {e.get('abilities', [])}")
            else:
                dmg = e['hp'] - old_e['hp']
                if dmg != 0: print(f"   ⚔️ Dano no {e['name']}: {dmg}")
            
            if e.get('active_conditions'):
                print(f"   ✨ Condições {e['name']}: {e['active_conditions']}")

    # Próximo Nó
    if new_state.get('next'):
        print(f"   ➡️ Próximo Destino: {new_state['next']}")

# --- 3. SUÍTE DE TESTES ---

def test_router():
    print_header("TESTE 1: ROUTER (NAVEGAÇÃO)")
    state = create_combat_state()
    state['messages'].append(HumanMessage(content="Soco a cara do boneco!"))
    print("\nInput: 'Soco a cara do boneco!' (Com inimigo ativo)")
    res = dm_router_node(state)
    print(f"Resultado: {res['next']} (Esperado: combat_agent)")
    
    state = create_base_state()
    state['messages'].append(HumanMessage(content="Falo com o Xuxu."))
    print("\nInput: 'Falo com o Xuxu.' (NPC não existe)")
    res = dm_router_node(state)
    print(f"Resultado: {res['next']} (Esperado: storyteller)")

def test_combat():
    print_header("TESTE 2: COMBATE (MECÂNICA)")
    state = create_combat_state()
    state['messages'].append(HumanMessage(content="Ataco o Boneco com minha espada."))
    print("\nInput: Ataque básico.")
    res = combat_node(state)
    
    # Simula merge para visualização
    new_state = state.copy()
    new_state.update(res)
    if 'messages' in res: new_state['messages'].extend(res['messages'])
    print_result(state, new_state, "Combat Agent")

def test_rules():
    print_header("TESTE 3: RULES (CRIATIVIDADE)")
    state = create_combat_state() 
    state['messages'].append(HumanMessage(content="Jogo areia nos olhos do Boneco para cegá-lo."))
    print("\nInput: Truque Sujo (Cegar).")
    res = rules_node(state)
    
    new_state = state.copy()
    new_state.update(res)
    if 'messages' in res: new_state['messages'].extend(res['messages'])
    print_result(state, new_state, "Rules Agent")

def test_npc():
    print_header("TESTE 4: NPC ACTOR")
    state = create_social_state()
    state['active_npc_name'] = "Bob"
    state['messages'].append(HumanMessage(content="Me dê um desconto?"))
    print("\nInput: Negociação com Bob.")
    res = npc_actor_node(state)
    
    if 'messages' in res:
        print(f"Resposta NPC: {res['messages'][0].content}")
        bob_data = res['npcs']['Bob']
        print(f"Relacionamento: {bob_data['relationship']}")

def test_spawning():
    print_header("TESTE 5: SPAWNERS (CRIAÇÃO DINÂMICA)")
    
    # 1. TESTE BESTIÁRIO (Engine Utils)
    print("\n--- A. Testando Bestiário Automático ---")
    monster_name = f"Tigre Cibernético {random.randint(100, 999)}"
    print(f"Tentando spawnar inimigo inexistente: '{monster_name}'")
    
    state = create_base_state()
    
    # Simulamos um EngineUpdate vindo de algum agente pedindo esse monstro
    update = EngineUpdate(
        reasoning_trace="Teste de Spawn",
        narrative_reason="Um monstro aparece!",
        spawn_enemy_type=monster_name # O GATILHO
    )
    
    # O apply_state_update contém a lógica que chama o bestiary_agent se não achar no JSON
    print("⏳ Chamando Agente Designer (pode demorar uns segundos)...")
    res = apply_state_update(update, state)
    
    # Verificação
    new_state = state.copy()
    new_state.update(res)
    
    created_enemy = new_state['enemies'][0] if new_state['enemies'] else None
    if created_enemy:
        print(f"✅ SUCESSO! Inimigo criado: {created_enemy['name']}")
        print(f"   HP: {created_enemy['hp']} | AC: {created_enemy['defense']}")
        print(f"   Habilidades: {created_enemy['abilities']}")
        print(f"   (Ficha salva em data/bestiary.json)")
    else:
        print("❌ FALHA: Inimigo não foi criado.")

    # 2. TESTE NPC (Simulando Storyteller)
    print("\n--- B. Testando NPC Designer ---")
    npc_name = f"Conde Drácula Tech {random.randint(100, 999)}"
    print(f"Storyteller decidiu introduzir: '{npc_name}'")
    
    print("⏳ Chamando NPC Designer...")
    # Chamamos a função diretamente para testar a integração com o banco de dados
    # (No jogo real, o storyteller.py faz exatamente essa chamada)
    template = generate_new_npc(npc_name, context="Um vampiro futurista em uma nave espacial.")
    
    if template:
        print(f"✅ SUCESSO! NPC criado: {template['name']}")
        print(f"   Role: {template['role']}")
        print(f"   Persona: {template['persona'][:50]}...")
        print(f"   (Ficha salva em data/npc_database.json)")
    else:
        print("❌ FALHA: Template de NPC vazio.")

def run_menu():
    while True:
        print("\n=== 🧪 LABORATÓRIO DE TESTES RPG V8 ===")
        print("1. Testar Router (Navegação)")
        print("2. Testar Combate (Dano)")
        print("3. Testar Regras (Improviso/Status)")
        print("4. Testar NPC (Atuação)")
        print("5. Testar Spawners (Criação de Mundo)")
        print("0. Sair")
        
        opt = input("Escolha: ")
        
        if opt == "1": test_router()
        elif opt == "2": test_combat()
        elif opt == "3": test_rules()
        elif opt == "4": test_npc()
        elif opt == "5": test_spawning()
        elif opt == "0": break
        else: print("Opção inválida.")

if __name__ == "__main__":
    run_menu()