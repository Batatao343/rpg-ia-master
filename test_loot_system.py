"""
test_loot_system.py
Valida os modos CRAFT, SHOP e TREASURE do agente de Loot.
Versão v2: Com DeepCopy para evitar falsos negativos em comparações de estado.
"""
import sys
import os
import copy # <--- IMPORTANTE
from langchain_core.messages import HumanMessage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from agents.loot import loot_node

# --- CORES ---
class C:
    OK = '\033[92m'
    FAIL = '\033[91m'
    WARN = '\033[93m'
    END = '\033[0m'

def get_mock_state():
    return {
        "player": {
            "name": "Tester",
            "inventory": ["espada_quebrada", "pocao_cura", "couro_lobo"],
            "gold": 100,
            "level": 1
        },
        "world": {"danger_level": 1, "current_location": "Vila Teste"},
        "messages": [],
        "loot_source": "TREASURE"
    }

def run_test_scenario(scenario_name, loot_mode, user_input, expected_check=None):
    print(f"\n{C.WARN}=== TESTE: {scenario_name} ==={C.END}")
    state = get_mock_state()
    
    # Snapshot do estado ANTES da execução (Cópia profunda)
    p_before = copy.deepcopy(state["player"])
    
    state["loot_source"] = loot_mode
    state["messages"] = [HumanMessage(content=user_input)]
    
    print(f"📥 Input: '{user_input}' (Modo: {loot_mode})")
    print(f"🎒 Inv. Antes: {p_before['inventory']} | 💰 Ouro: {p_before['gold']}")
    
    try:
        # Executa o Agente
        result = loot_node(state)
        
        # Estado DEPOIS
        p_after = result.get("player", state["player"])
        msg = result.get("messages", [])[0].content
        
        print(f"🤖 Resposta: {msg}")
        print(f"🎒 Inv. Depois: {p_after['inventory']} | 💰 Ouro: {p_after['gold']}")
        
        if expected_check:
            # Compara a cópia antiga (p_before) com a nova (p_after)
            if expected_check(p_before, p_after):
                print(f"{C.OK}✅ PASSOU{C.END}")
            else:
                print(f"{C.FAIL}❌ FALHOU (Lógica não bateu){C.END}")
                
    except Exception as e:
        print(f"{C.FAIL}❌ ERRO CRÍTICO: {e}{C.END}")

if __name__ == "__main__":
    print("🛠️ INICIANDO BATERIA DE TESTES DE LOOT v2")

    # 1. TREASURE: Deve ganhar ouro
    run_test_scenario(
        "Abrir Baú", 
        "TREASURE", 
        "Abro o baú antigo.",
        lambda p1, p2: p2['gold'] > p1['gold']
    )

    # 2. CRAFT: Sucesso (Espada nova, menos ouro)
    run_test_scenario(
        "Crafting: Consertar Espada", 
        "CRAFT", 
        "Ferreiro, use esta espada_quebrada e 50 moedas para forjar uma Espada Restaurada.",
        lambda p1, p2: "espada_quebrada" not in p2['inventory'] and p2['gold'] == 50
    )

    # 3. SHOP: Venda (Perde item, ganha ouro)
    run_test_scenario(
        "Venda: Couro de Lobo", 
        "SHOP", 
        "Vendo meu couro_lobo.",
        lambda p1, p2: "couro_lobo" not in p2['inventory'] and p2['gold'] > 100
    )

    # 4. CRAFT: Falha (Sem item)
    run_test_scenario(
        "Crafting: Falha (Item Inexistente)", 
        "CRAFT", 
        "Use meu diamante para fazer um anel.",
        lambda p1, p2: p1['inventory'] == p2['inventory'] # Nada muda
    )