"""
test_loot_system.py
Script para validar os modos CRAFT, SHOP e TREASURE do agente de Loot.
"""
import sys
import os
from langchain_core.messages import HumanMessage

# Adiciona raiz ao path para imports funcionarem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.loot import loot_node

# --- CORES ---
class C:
    OK = '\033[92m'
    FAIL = '\033[91m'
    WARN = '\033[93m'
    END = '\033[0m'

# --- MOCK STATE ---
def get_mock_state():
    """Gera um estado limpo para cada teste."""
    return {
        "player": {
            "name": "Tester",
            "inventory": ["espada_quebrada", "pocao_cura", "couro_lobo"],
            "gold": 100,
            "level": 1
        },
        "world": {
            "danger_level": 2,
            "current_location": "Oficina de Teste"
        },
        "messages": [],
        "loot_source": "TREASURE"
    }

def run_test_scenario(scenario_name, loot_mode, user_input, expected_check=None):
    print(f"\n{C.WARN}=== TESTE: {scenario_name} ==={C.END}")
    state = get_mock_state()
    
    # Configura o Input
    state["loot_source"] = loot_mode
    state["messages"] = [HumanMessage(content=user_input)]
    
    print(f"📥 Input: '{user_input}' (Modo: {loot_mode})")
    print(f"🎒 Inv. Antes: {state['player']['inventory']} | 💰 Ouro: {state['player']['gold']}")
    
    try:
        # Executa o Agente
        result = loot_node(state)
        
        # Analisa Resultado
        p_after = result.get("player", state["player"])
        msg = result.get("messages", [])[0].content
        
        print(f"🤖 Resposta: {msg}")
        print(f"🎒 Inv. Depois: {p_after['inventory']} | 💰 Ouro: {p_after['gold']}")
        
        # Validação Opcional
        if expected_check:
            if expected_check(state['player'], p_after):
                print(f"{C.OK}✅ PASSOU{C.END}")
            else:
                print(f"{C.FAIL}❌ FALHOU (Verifique lógica){C.END}")
                
    except Exception as e:
        print(f"{C.FAIL}❌ ERRO CRÍTICO: {e}{C.END}")

if __name__ == "__main__":
    print("🛠️ INICIANDO BATERIA DE TESTES DE LOOT")

    # CENÁRIO 1: Treasure (Exploração)
    run_test_scenario(
        "Abrir Baú", 
        "TREASURE", 
        "Abro o baú antigo.",
        lambda p1, p2: p2['gold'] > p1['gold'] # Deve ganhar ouro
    )

    # CENÁRIO 2: Crafting Sucesso (Melhorar Espada)
    # Requer: espada_quebrada + ouro -> espada_nova
    run_test_scenario(
        "Crafting: Consertar Espada", 
        "CRAFT", 
        "Ferreiro, use esta espada_quebrada e 50 moedas para forjar uma Espada Restaurada.",
        lambda p1, p2: "espada_quebrada" not in p2['inventory'] and p2['gold'] == 50
    )

    # CENÁRIO 3: Shop Venda (Vender Couro)
    run_test_scenario(
        "Venda: Couro de Lobo", 
        "SHOP", 
        "Vendo meu couro_lobo.",
        lambda p1, p2: "couro_lobo" not in p2['inventory'] and p2['gold'] > 100
    )

    # CENÁRIO 4: Falha (Sem item necessário)
    # Tenta craftar algo com um item que não tem ('diamante')
    run_test_scenario(
        "Crafting: Falha (Item Inexistente)", 
        "CRAFT", 
        "Use meu diamante para fazer um anel.",
        lambda p1, p2: p1['inventory'] == p2['inventory'] # Nada deve mudar
    )