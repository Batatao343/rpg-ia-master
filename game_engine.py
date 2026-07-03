"""
game_engine.py
Controlador Principal do Jogo (CLI).
"""
import os
import sys
import time
import uuid
from langchain_core.messages import HumanMessage, SystemMessage

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from persistence import save_game_state, load_game_state
from gamedata import CLASSES, load_json_data, seed_factions
from character_creator import create_player_character
from services.chronicle import default_chapter_title
from world_utils import starting_world

ORIGINS_DATA = load_json_data("origins.json")
RACES = ORIGINS_DATA.get("races", [])
REGIONS = ORIGINS_DATA.get("regions", [])

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'      
    CYAN = '\033[96m'      
    GREEN = '\033[92m'     
    WARNING = '\033[93m'   
    FAIL = '\033[91m'      
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def select_from_list(options, title_key="name", prompt="Escolha"):
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

def create_character_wizard():
    clear_screen()
    print(f"{Colors.HEADER}=== CRIAÇÃO DE PERSONAGEM (Dark Fantasy) ==={Colors.ENDC}")
    
    name = input("Nome do Herói: ").strip() or "Desconhecido"
    selected_race = select_from_list(RACES, title_key="name", prompt="Selecione sua Origem (Raça)")
    print(f"-> Raça: {Colors.GREEN}{selected_race['name']}{Colors.ENDC}")
    for trait in selected_race.get("traits", []) or []:
        print(f"   Trait: {Colors.BOLD}{trait.get('name')}{Colors.ENDC} — {trait.get('desc')}")

    classes_list = [{"name": k, **v} for k, v in CLASSES.items()]
    selected_class = select_from_list(classes_list, title_key="name", prompt="Selecione sua Vocação (Classe)")
    print(f"-> Classe: {Colors.GREEN}{selected_class['name']}{Colors.ENDC}")
    print(f"   Passiva: {selected_class.get('passive')}")

    selected_region = select_from_list(REGIONS, title_key="name", prompt="Região Inicial")
    print(f"-> Região: {Colors.GREEN}{selected_region['name']}{Colors.ENDC}")

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
        except: level = 1
            
    print(f"-> Nível Selecionado: {Colors.GREEN}{level}{Colors.ENDC}")
    print("\n(Opcional) Descreva brevemente seu passado ou personalidade.")
    backstory = input("> ").strip()

    print(f"\n{Colors.CYAN}... Invocando a IA para gerar sua ficha (Nível {level}) ...{Colors.ENDC}")
    
    char_input = {
        "name": name,
        "class_name": selected_class['name'],
        "race": selected_race['name'],
        "region": selected_region['name'],
        "backstory": backstory,
        "level": level
    }
    
    final_char = create_player_character(char_input)

    print(f"\n{Colors.GREEN}✨ Personagem Gerado com Sucesso! ✨{Colors.ENDC}")
    print(f"HP: {final_char['hp']} | Defesa: {final_char['defense']}")
    time.sleep(2)

    return {
        "game_id": str(uuid.uuid4()),
        "narrative_summary": f"A jornada de {name} começa em {final_char['region']}. {backstory}",
        "archivist_last_run": 0,
        # Fase 3.1: capítulo 1 existe desde o turno 0 (determinístico, sem LLM)
        "chronicle": [{"title": default_chapter_title(final_char["region"]),
                       "started_turn": 0, "location": final_char["region"], "entries": []}],
        "player": {
            "name": final_char["name"],
            "class_name": final_char["class_name"],
            "race": final_char["race"],
            "level": final_char["level"],
            "xp": 0,
            "hp": final_char["hp"],
            "max_hp": final_char["max_hp"],
            "mana": final_char["mana"],
            "max_mana": final_char["max_mana"],
            "stamina": final_char["stamina"],
            "max_stamina": final_char["max_stamina"],
            "gold": 50 * level,
            "alignment": "Neutro",
            "attributes": final_char["attributes"],
            "inventory": final_char["inventory"],
            "known_abilities": final_char["known_abilities"],
            "defense": final_char["defense"],
            "attack_bonus": final_char.get("attack_bonus", 0),
            "active_conditions": []
        },
        "world": starting_world(final_char["region"], level),
        "messages": [
            SystemMessage(content=f"A jornada de {name} começa em {final_char['region']}."),
            HumanMessage(content=f"Descreva o cenário ao meu redor. Sou um {final_char['class_name']} de nível {level}.")
        ],
        "party": [],
        "enemies": [],
        "factions": seed_factions(),
        "faction_intel": {},  # não-onisciência: jogador começa sem saber de nenhuma facção
        "archive_due": False,
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        "combat_target": None,
        "loot_source": None,
        # --- Fase 2.5: mundo estruturado ---
        "event_log": [],
        "world_projection": {},
        "pending_world_events": []
    }

def run_game_loop():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.CYAN}🐉 RPG IA ENGINE V9.0 - HYBRID MEMORY{Colors.ENDC}")
    
    # Carregar ou Criar
    state = load_game_state()
    if not state:
        state = create_character_wizard()
        save_game_state(state)

    print("\n--- INÍCIO DA SESSÃO ---")
    print(f"ID Sessão: {state.get('game_id')}")
    print(f"{Colors.CYAN}Dica: Digite 'sair' para salvar.{Colors.ENDC}\n")
    
    # Boot Inicial
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

    # Loop de Ação
    while True:
        try:
            p = state["player"]
            status_line = f"[{p['name']} (Lv {p['level']}) | HP: {p['hp']}/{p['max_hp']} | Ouro: {p['gold']}]"
            
            user_input = input(f"\n{Colors.BOLD}{status_line}\n> Você: {Colors.ENDC}").strip()
            
            if not user_input: continue
            
            if user_input.lower() in ["sair", "exit", "quit", "salvar"]:
                save_game_state(state)
                print(f"{Colors.CYAN}Até a próxima aventura!{Colors.ENDC}")
                break
            
            if user_input.lower() == "status":
                print(f"\n{Colors.CYAN}--- FICHA DE {p['name'].upper()} ---")
                print(f"Resumo da História: {state.get('narrative_summary')}")
                print(f"Inventário: {p['inventory']}{Colors.ENDC}")
                continue

            current_msgs = state.get("messages", [])
            current_msgs.append(HumanMessage(content=user_input))
            state["messages"] = current_msgs[-15:]

            print(f"{Colors.CYAN}... Pensando ...{Colors.ENDC}", end="\r")
            
            result = app.invoke(state)
            state = result
            
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