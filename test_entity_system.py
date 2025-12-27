import os
import json
import sys
from typing import Dict

# Configuração de Path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports dos Agentes Refatorados
from agents.npc import generate_new_npc, npc_actor_node, load_npc_db, NPC_DB_FILE
from agents.bestiary import generate_new_enemy, load_bestiary, BESTIARY_FILE
from langchain_core.messages import HumanMessage, AIMessage

# Cores
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def print_test(msg):
    print(f"\n{CYAN}>>> TESTE: {msg}{RESET}")

def assert_true(condition, msg):
    if condition:
        print(f"{GREEN}✅ PASSOU: {msg}{RESET}")
    else:
        print(f"{RED}❌ FALHOU: {msg}{RESET}")

def clean_files():
    """Limpa os JSONs de teste para garantir integridade."""
    for fpath in [NPC_DB_FILE, BESTIARY_FILE]:
        if os.path.exists(fpath):
            with open(fpath, 'w') as f: json.dump({}, f)

# ==========================================
# 1. TESTE DE CRIAÇÃO E CACHE (CHECK-FIRST)
# ==========================================
def test_npc_creation_and_cache():
    print_test("NPC: Geração e Cache (Librarian)")
    
    npc_name = "Varg, o Açougueiro"
    
    # 1. Primeira Chamada (Deve criar do zero com RAG)
    print(f"1. Gerando '{npc_name}' pela primeira vez...")
    npc1 = generate_new_npc(npc_name, context="Um guerreiro orc em uma taverna suja.")
    
    assert_true(npc1 is not None, "NPC gerado com sucesso")
    assert_true(npc1.get("id") is not None, f"NPC tem ID: {npc1.get('id')}")
    
    # Verifica Lore/Persona (Visual inspection)
    print(f"   🎭 Persona Gerada: {YELLOW}{npc1.get('persona')[:100]}...{RESET}")

    # 2. Segunda Chamada (Deve recuperar do Cache)
    print(f"2. Pedindo '{npc_name}' novamente (Simulando Check-First)...")
    npc2 = generate_new_npc(npc_name, context="Não importa o contexto agora.")
    
    # A prova real: Os objetos devem ser idênticos e ter o mesmo ID
    assert_true(npc1["id"] == npc2["id"], f"IDs coincidem: {npc1['id']} == {npc2['id']}")
    
    # 3. Verifica Persistência em Disco
    with open(NPC_DB_FILE, 'r') as f:
        db_content = json.load(f)
    assert_true(npc1["id"] in db_content, "NPC salvo fisicamente no npc_database.json")

    return npc1 # Retorna para usar no teste de memória

# ==========================================
# 2. TESTE DE MEMÓRIA E INTERAÇÃO
# ==========================================
def test_npc_memory(npc_data):
    print_test("NPC: Memória e Interação (Actor Node)")
    
    npc_name = npc_data["name"] # Chave para o state
    
    # Mock do State (Como se o jogo estivesse rodando)
    state = {
        "messages": [HumanMessage(content="Olá! Eu sou o Kael, o Bardo. Você viu um dragão por aqui?")],
        "active_npc_name": npc_data["id"], # O sistema usa o ID ou Nome como chave
        "npcs": { npc_data["id"]: npc_data }, # O NPC carregado no mundo
        "world": {"turn_count": 5}
    }
    
    # Executa o Node de Atuação
    print(f"🗣️ Jogador diz: '{state['messages'][0].content}'")
    result = npc_actor_node(state)
    
    # Pega o NPC atualizado
    updated_npc = result["npcs"][npc_data["id"]]
    response_msg = result["messages"][0].content
    
    print(f"🗣️ NPC Responde: {YELLOW}{response_msg}{RESET}")
    
    # Validações de Memória
    memory_log = updated_npc.get("memory", [])
    has_memory = len(memory_log) > 0
    assert_true(has_memory, f"Memória atualizada. Logs: {len(memory_log)}")
    
    if has_memory:
        print(f"   🧠 Última Memória: {memory_log[-1]}")
        # Verifica se o nome Kael ou Dragão entrou na memória (Teste Semântico básico)
        relevant = "Kael" in memory_log[-1] or "dragão" in memory_log[-1] or "dragon" in memory_log[-1]
        assert_true(relevant, "Memória registrou tópicos relevantes da conversa")

# ==========================================
# 3. TESTE DE BESTIÁRIO (COMBAT READY)
# ==========================================
def test_bestiary_creation():
    print_test("Bestiário: Geração de Stats de Combate")
    
    monster_name = "Aranha de Cristal"
    
    # 1. Geração
    monster = generate_new_enemy(monster_name, context="Caverna subterrânea brilhante.")
    
    assert_true(monster is not None, "Monstro gerado")
    
    # 2. Validação de Stats Matemáticos (Crucial para o combat.py)
    has_hp = isinstance(monster.get("max_hp"), int) and monster["max_hp"] > 0
    has_ac = isinstance(monster.get("ac"), int)
    
    assert_true(has_hp, f"HP Válido: {monster.get('max_hp')}")
    assert_true(has_ac, f"AC Válido: {monster.get('ac')}")
    
    # 3. Validação de Ataques (Array estruturado)
    attacks = monster.get("attacks", [])
    assert_true(len(attacks) > 0, f"Possui {len(attacks)} ataques definidos")
    
    if attacks:
        atk = attacks[0]
        print(f"   ⚔️ Exemplo de Ataque: {atk}")
        # Verifica se tem fórmula de dados
        has_formula = "d" in str(atk.get("damage", ""))
        assert_true(has_formula, f"Fórmula de dano detectada: {atk.get('damage')}")

# ==========================================
# EXECUÇÃO
# ==========================================
if __name__ == "__main__":
    print(f"{CYAN}=== INICIANDO TESTES DE ENTIDADES E MEMÓRIA ==={RESET}")
    
    # Opcional: Limpar DBs antes (comente se quiser manter histórico entre testes)
    # clean_files() 
    
    try:
        # 1. Cria NPC
        created_npc = test_npc_creation_and_cache()
        
        # 2. Testa Memória usando o NPC criado
        if created_npc:
            test_npc_memory(created_npc)
            
        # 3. Testa Bestiário
        test_bestiary_creation()
        
        print(f"\n{GREEN}=== TESTES CONCLUÍDOS ==={RESET}")
        
    except Exception as e:
        print(f"\n{RED}❌ ERRO FATAL: {e}{RESET}")
        import traceback
        traceback.print_exc()