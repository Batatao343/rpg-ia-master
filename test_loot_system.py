import os
import json
import sys
from typing import Dict

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do Sistema
import gamedata
from agents.loot import loot_node
from gamedata import ARTIFACTS_DB, save_custom_artifact
from engine_utils import execute_engine # Para testar a tool transaction (simulado)

# Cores para o terminal
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_test(msg):
    print(f"\n{CYAN}>>> TESTE: {msg}{RESET}")

def assert_true(condition, msg):
    if condition:
        print(f"{GREEN}✅ PASSOU: {msg}{RESET}")
    else:
        print(f"{RED}❌ FALHOU: {msg}{RESET}")

def setup_clean_db():
    """Limpa o custom_artifacts.json para o teste ser limpo."""
    path = "data/custom_artifacts.json"
    if os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)
    # Recarrega o gamedata para garantir memória limpa
    gamedata.CUSTOM_ARTIFACTS = {}
    gamedata.ARTIFACTS_DB = {**gamedata.BASE_ARTIFACTS}

# ==========================================
# 1. TESTE DE COMBATE (DROP DE BOSS + XP)
# ==========================================
def test_combat_loot():
    print_test("Gerando Loot de Boss (Região: Zhur)")
    
    # Mock do Estado
    state = {
        "player": {"name": "TestHero", "level": 1, "xp": 0, "gold": 0, "inventory": [], "hp": 20, "max_hp": 20},
        "world": {"current_location": "Deserto de Zhur"}, # Contexto da Lore
        "enemies": [
            {"name": "General Escorpião", "type": "BOSS", "max_hp": 50} # Boss garante item único
        ],
        "loot_source": "COMBAT",
        "messages": []
    }

    # Executa o Nó
    result = loot_node(state)
    player = result["player"]
    messages = result["messages"]

    # Validações
    print(f"Mensagem da IA: {messages[0].content}")
    
    # 1. XP Ganho?
    xp_ganho = player["xp"]
    assert_true(xp_ganho > 0, f"XP Ganho: {xp_ganho}")

    # 2. Item Único Gerado?
    # Bosses geram IDs como 'unique_loot_nome_boss'
    expected_id = "unique_loot_general_escorpiao"
    has_item = expected_id in player["inventory"]
    assert_true(has_item, f"Item do Boss '{expected_id}' adicionado ao inventário")

    # 3. Item existe na Database?
    db_item = ARTIFACTS_DB.get(expected_id)
    assert_true(db_item is not None, "Item registrado no ARTIFACTS_DB em memória")
    
    if db_item:
        print(f"   📝 Stats do Item Gerado: {db_item.get('combat_stats')}")
        # Verifica persistência em disco
        with open("data/custom_artifacts.json", "r") as f:
            disk_db = json.load(f)
        assert_true(expected_id in disk_db, "Item salvo fisicamente no JSON")

# ==========================================
# 2. TESTE DE TESOURO (BAÚ)
# ==========================================
def test_treasure_loot():
    print_test("Abrindo Baú (Região: Cripta Antiga)")
    
    state = {
        "player": {"name": "TestHero", "gold": 0, "inventory": []},
        "world": {"current_location": "Cripta dos Esquecidos"},
        "loot_source": "TREASURE",
        "messages": []
    }

    result = loot_node(state)
    player = result["player"]
    
    # Validações
    assert_true(player["gold"] > 0, f"Ouro encontrado: {player['gold']}")
    assert_true(len(player["inventory"]) > 0, "Itens encontrados no baú")
    print(f"   Inventário pós-baú: {player['inventory']}")

# ==========================================
# 3. TESTE DE MERCADO (GERAÇÃO + COMPRA)
# ==========================================
def test_market_and_purchase():
    print_test("Gerando Mercado e Testando Compra")
    
    # Passo A: Gerar a Loja
    state = {
        "player": {"name": "TestHero", "gold": 1000, "inventory": []}, # Rico para poder comprar
        "world": {"current_location": "Nova Arcádia"},
        "loot_source": "SHOP",
        "messages": []
    }

    result = loot_node(state)
    msg_content = result["messages"][0].content
    print("--- Vitrine da Loja ---")
    print(msg_content)
    
    # Passo B: Extrair um ID gerado para tentar comprar
    # O loot_node no modo SHOP gera itens no custom_artifacts.json mas não põe no inventário
    # Vamos pegar o último item adicionado ao DB para simular que o jogador escolheu ele
    all_custom = gamedata.CUSTOM_ARTIFACTS
    if not all_custom:
        print(f"{RED}❌ Erro: Loja não gerou itens customizados.{RESET}")
        return

    # Pega um item arbitrário da loja (o último criado)
    target_item_id = list(all_custom.keys())[-1]
    target_item = all_custom[target_item_id]
    price = target_item.get("value_gold", 9999)
    
    print(f"\n🛒 Tentando comprar: {target_item['name']} (ID: {target_item_id}) por {price} ouro.")

    # Passo C: Simular a Tool 'transaction' (Lógica do engine_utils)
    player = state["player"]
    initial_gold = player["gold"]
    
    # -- Lógica da Tool Transaction (replicada para teste unitário) --
    success = False
    if player["gold"] >= price:
        player["gold"] -= price
        player["inventory"].append(target_item_id)
        success = True
    # ---------------------------------------------------------------

    assert_true(success, "Transação de compra realizada")
    assert_true(player["gold"] == initial_gold - price, f"Ouro descontado corretamente ({player['gold']})")
    assert_true(target_item_id in player["inventory"], "Item está no inventário")

# ==========================================
# MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    print(f"{CYAN}=== INICIANDO BATERIA DE TESTES DO LOOT SYSTEM ==={RESET}")
    
    # Limpeza opcional (cuidado em prod)
    # setup_clean_db() 
    
    try:
        test_combat_loot()
        test_treasure_loot()
        test_market_and_purchase()
        print(f"\n{GREEN}=== TODOS OS TESTES FINALIZADOS ==={RESET}")
    except Exception as e:
        print(f"\n{RED}❌ ERRO FATAL NO TESTE: {e}{RESET}")
        import traceback
        traceback.print_exc()