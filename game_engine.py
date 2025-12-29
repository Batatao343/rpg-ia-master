"""
game_engine.py
Controlador Principal do Jogo (CLI).
100% integrado com Classes/Raças Oficiais + Criação via IA + Seleção de Nível.
"""
import os
import sys
import time
from langchain_core.messages import HumanMessage, SystemMessage

# Adiciona raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- IMPORTS DO PROJETO ---
from main import app  # O Grafo compilado
from persistence import save_game_state, load_game_state
from gamedata import CLASSES, load_json_data # Dados oficiais
from character_creator import create_player_character # Gerador Inteligente

# Carrega Raças e Regiões
ORIGINS_DATA = load_json_data("origins.json")
RACES = ORIGINS_DATA.get("races", [])
REGIONS = ORIGINS_DATA.get("regions", [])

# --- CORES E ESTILO ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'      # Narrativa
    CYAN = '\033[96m'      # Sistema / Info
    GREEN = '\033[92m'     # Sucesso / HP / NPC
    WARNING = '\033[93m'   # Loot / Ouro
    FAIL = '\033[91m'      # Combate / Dano
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# ==========================================
# SELEÇÃO DE MENU (Helper)
# ==========================================
def select_from_list(options, title_key="name", prompt="Escolha"):
    """Lista opções genéricas e retorna a escolhida."""
    print(f"\n--- {prompt} ---")
    
    if isinstance(options, dict):
        options_list = [{"id": k, **v} for k, v in options.items()]
    else:
        options_list = options

    for i, opt in enumerate(options_list):
        name = opt.get(title_key) or opt.get("id")
        desc = opt.get("description") or opt.get("desc") or "..."
        print(f"{i+1}. {Colors.BOLD}{name}{Colors.ENDC}: {desc}")
    
    while True:
        try:
            choice = int(input(f"\nOpção [1-{len(options_list)}]: "))
            if 1 <= choice <= len(options_list):
                return options_list[choice-1]
        except ValueError:
            pass
        print(f"{Colors.FAIL}Opção inválida.{Colors.ENDC}")

# ==========================================
# CRIAÇÃO DE PERSONAGEM (WIZARD V2)
# ==========================================
def create_character_wizard():
    clear_screen()
    print(f"{Colors.HEADER}=== CRIAÇÃO DE PERSONAGEM (Dark Fantasy) ==={Colors.ENDC}")
    
    # 1. Nome
    name = input("Nome do Herói: ").strip() or "Desconhecido"
    
    # 2. Raça
    selected_race = select_from_list(RACES, title_key="name", prompt="Selecione sua Origem (Raça)")
    print(f"-> Raça: {Colors.GREEN}{selected_race['name']}{Colors.ENDC}")

    # 3. Classe
    classes_list = [{"name": k, **v} for k, v in CLASSES.items()]
    selected_class = select_from_list(classes_list, title_key="name", prompt="Selecione sua Vocação (Classe)")
    print(f"-> Classe: {Colors.GREEN}{selected_class['name']}{Colors.ENDC}")
    print(f"   Passiva: {selected_class.get('passive')}")

    # 4. Região
    selected_region = select_from_list(REGIONS, title_key="name", prompt="Região Inicial")
    print(f"-> Região: {Colors.GREEN}{selected_region['name']}{Colors.ENDC}")
    print(f"   Bônus: {selected_region.get('bonus')}")

    # 5. Nível (NOVO)
    print("\n--- Nível Inicial ---")
    print("1. Iniciante (Nível 1)")
    print("2. Aventureiro (Nível 3)")
    print("3. Veterano (Nível 5)")
    print("4. Herói (Nível 10)")
    print("5. Lenda (Nível 20)")
    print("0. Personalizado")
    
    lvl_choice = input("Escolha [1]: ").strip()
    level = 1
    
    if lvl_choice == "2": level = 3
    elif lvl_choice == "3": level = 5
    elif lvl_choice == "4": level = 10
    elif lvl_choice == "5": level = 20
    elif lvl_choice == "0":
        try:
            custom_lvl = int(input("Digite o nível (1-20): "))
            level = max(1, min(20, custom_lvl))
        except:
            level = 1
            
    print(f"-> Nível Selecionado: {Colors.GREEN}{level}{Colors.ENDC}")

    # 6. Background
    print("\n(Opcional) Descreva brevemente seu passado ou personalidade.")
    backstory = input("> ").strip()

    print(f"\n{Colors.CYAN}... Invocando a IA para gerar sua ficha (Nível {level}) ...{Colors.ENDC}")
    
    # --- CHAMADA AO GERADOR ---
    char_input = {
        "name": name,
        "class_name": selected_class['name'],
        "race": selected_race['name'],
        "region": selected_region['name'],
        "backstory": backstory,
        "level": level # Passamos o nível escolhido
    }
    
    # A IA vai escalar HP, Inventário e Habilidades baseada no nível
    final_char = create_player_character(char_input)

    print(f"\n{Colors.GREEN}✨ Personagem Gerado com Sucesso! ✨{Colors.ENDC}")
    print(f"HP: {final_char['hp']} | Defesa: {final_char['defense']}")
    print(f"Atributos: {final_char['attributes']}")
    print(f"Habilidades: {final_char['known_abilities']}")
    time.sleep(2)

    # Retorna o GameState pronto
    return {
        "player": {
            "name": final_char["name"],
            "class": final_char["class_name"],
            "race": final_char["race"],
            "level": final_char["level"],
            "xp": 0, # Poderia calcular XP baseada no nível, mas deixamos 0 para o next level
            "hp": final_char["hp"],
            "max_hp": final_char["max_hp"],
            "gold": 50 * level, # Bônus de ouro por nível
            "attributes": final_char["attributes"],
            "inventory": final_char["inventory"],
            "equipment": {},
            "abilities": final_char["known_abilities"]
        },
        "world": {
            "current_location": final_char["region"],
            "time_of_day": "Amanhecer",
            "turn_count": 0,
            "danger_level": level # O mundo escala com você
        },
        "messages": [
            SystemMessage(content=f"A jornada de {name} começa em {final_char['region']}."),
            HumanMessage(content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {level}.")
        ],
        "party": [],
        "enemies": [],
        "npcs": {},
        "quests": [],
        "campaign_plan": {},
        "next": "storyteller"
    }

# ==========================================
# LOOP PRINCIPAL
# ==========================================
def run_game_loop():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.CYAN}🐉 RPG IA ENGINE V8.2 - SYSTEM READY{Colors.ENDC}")
    
    # 1. Carregar ou Criar
    state = load_game_state()
    if not state:
        state = create_character_wizard()
        save_game_state(state)

    print("\n--- INÍCIO DA SESSÃO ---")
    print(f"{Colors.CYAN}Dica: Digite 'sair' para salvar ou 'status' para ver ficha.{Colors.ENDC}\n")
    
    # 2. Boot Inicial
    try:
        last_msg = state["messages"][-1]
        if isinstance(last_msg, SystemMessage) or (isinstance(last_msg, HumanMessage) and len(state["messages"]) <= 2):
            print(f"{Colors.CYAN}... Gerando cena inicial ...{Colors.ENDC}", end="\r")
            initial_res = app.invoke(state)
            state = initial_res
            if state["messages"]:
                print(f"\n{Colors.BLUE}📜 {state['messages'][-1].content}{Colors.ENDC}")
        else:
            print(f"\n{Colors.BLUE}📜 (Anterior): {state['messages'][-1].content}{Colors.ENDC}")

    except Exception as e:
        print(f"⚠️ Erro no boot inicial: {e}")

    # 3. Loop de Ação
    while True:
        try:
            # A. Input
            p = state["player"]
            status_line = f"[{p['name']} (Lv {p['level']}) | HP: {p['hp']}/{p['max_hp']} | Ouro: {p['gold']}]"
            
            user_input = input(f"\n{Colors.BOLD}{status_line}\n> Você: {Colors.ENDC}").strip()
            
            if not user_input: continue
            
            # Comandos de Meta-Game
            if user_input.lower() in ["sair", "exit", "quit", "salvar"]:
                save_game_state(state)
                print(f"{Colors.CYAN}Até a próxima aventura!{Colors.ENDC}")
                break
            
            if user_input.lower() == "status":
                print(f"\n{Colors.CYAN}--- FICHA DE {p['name'].upper()} ---")
                print(f"Vocação: {p.get('race', '')} {p['class']} (Nvl {p['level']})")
                print(f"HP: {p['hp']}/{p['max_hp']} | XP: {p['xp']}")
                print(f"Atributos: {p['attributes']}")
                print(f"Habilidades: {p.get('abilities', [])}")
                print(f"Inventário: {p['inventory']}")
                print(f"Local: {state['world']['current_location']}")
                print(f"Quests: {len(state.get('quests', []))} ativas{Colors.ENDC}")
                continue

            # B. Histórico
            current_msgs = state.get("messages", [])
            current_msgs.append(HumanMessage(content=user_input))
            state["messages"] = current_msgs[-15:]

            # C. Engine
            print(f"{Colors.CYAN}... Pensando ...{Colors.ENDC}", end="\r")
            
            result = app.invoke(state)
            state = result
            
            # D. Output
            last_msg = state["messages"][-1]
            content = last_msg.content
            
            if "⚔️" in content or "dano" in content.lower():
                print(f"\n{Colors.FAIL}⚔️  {content}{Colors.ENDC}")
            elif "💰" in content or "item" in content.lower():
                print(f"\n{Colors.WARNING}💰 {content}{Colors.ENDC}")
            elif "🗣️" in content or '"' in content:
                print(f"\n{Colors.GREEN}🗣️  {content}{Colors.ENDC}")
            else:
                print(f"\n{Colors.BLUE}📜 {content}{Colors.ENDC}")

            # Game Over
            if state["player"]["hp"] <= 0:
                print(f"\n{Colors.FAIL}💀 VOCÊ MORREU.{Colors.ENDC}")
                break

        except KeyboardInterrupt:
            print("\nEncerrando...")
            save_game_state(state)
            break
        except Exception as e:
            print(f"\n{Colors.FAIL}❌ Erro Crítico: {e}{Colors.ENDC}")

if __name__ == "__main__":
    run_game_loop()