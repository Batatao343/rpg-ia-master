import sys
import os
import time
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Imports do Sistema
from gamedata import save_custom_artifact
from agents.combat import combat_node

# --- CORES DO TERMINAL ---
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ==========================================
# 1. SETUP (Itens e Inimigos)
# ==========================================
def setup_game():
    # Cria a Espada OP
    item_id = "lamina_infernal_player"
    item_data = {
        "name": "Lâmina Infernal",
        "type": "weapon",
        "rarity": "legendary",
        "value_gold": 5000,
        "combat_stats": {
            "attack_bonus": 10,
            "damage_dice": "1d10",
            "attribute": "str",
            "ac_bonus": 0
        },
        "mechanics": {
            "passive_effects": ["Chamas Eternas: Acertos causam +3d6 de fogo."],
            "active_ability": {"name": "Explosão Solar", "cost": "1 Ação", "effect": "Causa 4d6 em área."}
        }
    }
    save_custom_artifact(item_id, item_data)

    # Estado Inicial
    state = {
        "player": {
            "name": "Você (Herói)",
            "hp": 100, "max_hp": 100,
            "attributes": {"str": 18, "dex": 14}, 
            "inventory": [item_id], 
            "gold": 50
        },
        "party": [],
        "enemies": [
            {
                "name": "General de Ferro (BOSS)", 
                "type": "BOSS", 
                "hp": 250, "max_hp": 250, 
                "ac": 14, 
                "status": "ativo",
                "attacks": [{"name": "Esmagar", "bonus": 8, "damage": "2d8+5"}]
            }
        ],
        "messages": [], # Histórico vazio
        "combat_target": None
    }
    return state

# ==========================================
# 2. INTERFACE GRÁFICA (ASCII)
# ==========================================
def draw_health_bar(name, hp, max_hp, color_code):
    width = 30
    # Garante que não divida por zero e hp não seja negativo
    safe_max = max(1, max_hp)
    safe_hp = max(0, hp)
    
    percent = max(0, min(1.0, safe_hp / safe_max))
    filled = int(width * percent)
    bar = "█" * filled + "░" * (width - filled)
    
    # Formatação bonita
    print(f"{color_code}{BOLD}{name:<25}{RESET} [{bar}] {color_code}{safe_hp}/{safe_max} HP{RESET}")

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def draw_interface(state):
    player = state["player"]
    boss = state["enemies"][0]
    
    print("\n" + "="*60)
    draw_health_bar(boss["name"], boss["hp"], boss["max_hp"], RED)
    print("-" * 60)
    draw_health_bar(player["name"], player["hp"], player["max_hp"], GREEN)
    print("="*60 + "\n")
    
    print(f"{YELLOW}Equipado: {RESET}Lâmina Infernal (+10 Atk, +3d6 Fogo)")
    print(f"{CYAN}Dica: Digite sua ação livremente. Ex: 'Ataco o pescoço', 'Tento derrubar ele'.{RESET}")

# ==========================================
# 3. LOOP DO JOGO
# ==========================================
def game_loop():
    state = setup_game()
    turn = 1
    
    # Mensagem inicial do sistema para situar a IA
    state["messages"].append(SystemMessage(content="COMBATE INICIADO. O Jogador enfrenta o General de Ferro."))

    while True:
        clear_screen()
        draw_interface(state)
        
        # Checa vitória/derrota
        player_hp = state["player"]["hp"]
        boss_hp = state["enemies"][0]["hp"]
        
        if boss_hp <= 0:
            print(f"\n{GREEN}🎉 VICTORY! O General caiu!{RESET}")
            break
        if player_hp <= 0:
            print(f"\n{RED}💀 DEFEAT! Você foi esmagado...{RESET}")
            break

        # INPUT DO JOGADOR
        print(f"\n{BOLD}Turno {turn}{RESET}")
        user_action = input(f"{GREEN}> O que você faz? {RESET}")
        
        if user_action.lower() in ["sair", "exit", "quit"]:
            print("Fugindo do combate...")
            break

        # Adiciona ação ao histórico
        state["messages"].append(HumanMessage(content=user_action))
        
        print(f"\n{YELLOW}Processando turno... (IA Pensando){RESET}")
        
        # --- CHAMADA REAL DO COMBAT NODE ---
        result = combat_node(state)
        # -----------------------------------
        
        # Atualiza o estado
        state["player"] = result["player"]
        state["enemies"] = result["enemies"]
        state["messages"] = result["messages"]
        
        # Exibe a Narrativa de forma segura
        last_msg = result["messages"][-1].content
        print(f"\n{BLUE}📜 Narrativa:{RESET}")
        print(f"{content_box(last_msg)}")
        
        input(f"\n{BOLD}[Pressione ENTER para o próximo turno...]{RESET}")
        turn += 1

def content_box(text):
    """Cria uma caixinha bonita ao redor do texto da IA. Lida com listas se necessário."""
    
    # --- CORREÇÃO DO ERRO 'LIST HAS NO ATTRIBUTE SPLIT' ---
    if isinstance(text, list):
        # Se for lista de blocos (content blocks), extrai apenas o texto
        text_parts = []
        for block in text:
            if isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
            else:
                text_parts.append(str(block))
        text = "".join(text_parts)
    
    # Garante que é string
    text = str(text)
    # -----------------------------------------------------

    lines = text.split('\n')
    boxed = ""
    for line in lines:
        boxed += f"| {line}\n"
    return boxed

if __name__ == "__main__":
    try:
        game_loop()
    except KeyboardInterrupt:
        print("\nJogo encerrado.")