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
import progression
from character_creator import create_player_character
from services.chronicle import default_chapter_title
from world_utils import starting_world


def _save_or_raise(state: dict) -> None:
    if not save_game_state(state):
        raise RuntimeError("não foi possível persistir o jogo")


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


def _resolve_pending_choices(player: dict) -> dict:
    """Fase 4.1: prompt de level up no fim do turno. ENTER adia (não bloqueia)."""
    while player.get("pending_choices"):
        choice = player["pending_choices"][0]
        kind = choice.get("kind")
        print(f"\n{Colors.HEADER}⬆ NÍVEL {choice.get('level')} — "
              f"{'nova Carta/evolução' if kind == 'carta' else 'ponto de Virtude'}!{Colors.ENDC}")

        if kind == "carta":
            from services import cards
            elig = progression.eligible_cards(player)
            if not elig:
                print(f"{Colors.WARNING}Nenhuma Carta elegível agora — escolha fica pendente.{Colors.ENDC}")
                return player
            for i, cid in enumerate(elig, 1):
                card = cards.get_card(cid) or {}
                tag = f" [{card.get('subclasse')}]" if card.get("subclasse") else ""
                print(f"  {i}. {card.get('name', cid)}{tag} — "
                      f"{card.get('descricao', '')[:70]}")
            raw = input(f"{Colors.BOLD}Escolha (número, ENTER = depois): {Colors.ENDC}").strip()
            if not raw:
                return player
            try:
                cid = elig[int(raw) - 1]
            except (ValueError, IndexError):
                print(f"{Colors.WARNING}Opção inválida — escolha fica pendente.{Colors.ENDC}")
                return player
            player, err = progression.apply_choice(player, choice["id"], card_id=cid)
        else:
            raw = input(f"{Colors.BOLD}+1 em qual Virtude (forca/agilidade/corpo/mente/carisma, "
                        f"ENTER = depois)? {Colors.ENDC}").strip()
            if not raw:
                return player
            player, err = progression.apply_choice(player, choice["id"], virtude=raw)

        if err:
            print(f"{Colors.WARNING}{err}{Colors.ENDC}")
            return player
        print(f"{Colors.GREEN}✔ Escolha aplicada.{Colors.ENDC}")
    return player

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
    import gamedata
    gamedata.sync_vitality(final_char)

    print(f"\n{Colors.GREEN}✨ Personagem Gerado com Sucesso! ✨{Colors.ENDC}")
    print(
        f"Vitalidade: {final_char['vitalidade']}/{final_char['max_vitalidade']} "
        f"| Defesa: {final_char['defense']}")
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
            # spec refatoracao-sistema-classes: Entropia = pool das 5 classes.
            "entropy": final_char.get("entropy", 0),
            "max_entropy": final_char.get("max_entropy", 0),
            "abyss_charge": final_char.get("abyss_charge", 0),
            "gold": 50 * level,
            "alignment": "Neutro",
            # spec conflito-01: Virtudes + Vitalidade/Ferimentos (mana/stamina/attributes saíram)
            "virtudes": final_char["virtudes"],
            "vitalidade": final_char.get("vitalidade", final_char.get("max_vitalidade", final_char["max_hp"])),
            "max_vitalidade": final_char.get("max_vitalidade", final_char["max_hp"]),
            "vitalidade_max_penalty": final_char.get("vitalidade_max_penalty", 0),
            "ferimento_espacos": final_char.get("ferimento_espacos", {}),
            "ferimentos": final_char.get("ferimentos", {"leve": [], "grave": [], "critico": []}),
            "inventory": final_char["inventory"],
            # Fase 4.3: slots do creator (auto-equip)
            "equipment": final_char.get("equipment",
                                        {"weapon": None, "armor": None, "accessory": None}),
            "known_cards": final_char.get("known_cards", []),
            "prepared_cards": final_char.get("prepared_cards", []),
            "card_usage": final_char.get("card_usage", {}),
            "virtue_cards": final_char.get("virtue_cards", []),
            "evolved_cards": final_char.get("evolved_cards", {}),
            "pending_choices": final_char.get("pending_choices", []),
            "defense": final_char["defense"],
            "attack_bonus": final_char.get("attack_bonus", 0),
            "active_conditions": [],
            "racial_traits": final_char.get("racial_traits", []),
            "condition_resists": final_char.get("condition_resists", []),
            "racial_save_bonus": final_char.get("racial_save_bonus", {}),
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
        "bestiary_knowledge": {},
        "quests": [],
        "archive_due": False,
        "game_over": False,
        "death_pending": False,
        "npcs": {},
        "campaign_plan": {},
        "needs_replan": False,
        "next": "storyteller",
        "combat_target": None,
        "loot_source": None,
        # --- Fase 2.5: mundo estruturado ---
        "event_log": [],
        "world_projection": {},
        "pending_world_events": [],
        "event_rejections": [],
    }

def run_game_loop():
    clear_screen()
    print(f"{Colors.BOLD}{Colors.CYAN}🐉 RPG IA ENGINE V9.0 - HYBRID MEMORY{Colors.ENDC}")
    
    # Carregar ou Criar
    state = load_game_state()
    if not state:
        state = create_character_wizard()
        _save_or_raise(state)

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
            # spec checkpoints-morte (D7): checkpoint inicial = início da sessão.
            from persistence import save_checkpoint
            save_checkpoint(state)
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
            pend = len(p.get("pending_choices", []) or [])
            badge = f" | ⬆ {pend} escolha(s) de nível" if pend else ""
            status_line = (
                f"[{p['name']} (Lv {p['level']}) | Vitalidade: "
                f"{p.get('vitalidade', 0)}/{p.get('max_vitalidade', 0)} "
                f"| Ouro: {p['gold']}{badge}]")
            
            user_input = input(f"\n{Colors.BOLD}{status_line}\n> Você: {Colors.ENDC}").strip()
            
            if not user_input: continue
            
            if user_input.lower() in ["sair", "exit", "quit", "salvar"]:
                _save_or_raise(state)
                print(f"{Colors.CYAN}Até a próxima aventura!{Colors.ENDC}")
                break
            
            if user_input.lower() == "status":
                from inventory import item_display
                eq = p.get("equipment") or {}
                inv_txt = ", ".join(
                    f"{item_display(e)} x{e.get('qty', 1)}" +
                    (" [equipado]" if e.get("id") in eq.values() else "")
                    for e in (p.get("inventory") or []) if isinstance(e, dict)
                ) or "vazio"
                print(f"\n{Colors.CYAN}--- FICHA DE {p['name'].upper()} ---")
                print(f"Resumo da História: {state.get('narrative_summary')}")
                print(f"Inventário: {inv_txt}{Colors.ENDC}")
                continue

            # Fase 4.3: "equipar <item>" resolve local, sem gastar turno de LLM
            if user_input.lower().startswith("equipar "):
                from inventory import equip
                novo, err = equip(p, user_input[8:].strip())
                if err:
                    print(f"{Colors.WARNING}{err}{Colors.ENDC}")
                else:
                    state["player"] = novo
                    print(f"{Colors.GREEN}✔ Equipado.{Colors.ENDC}")
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

            # Fase 4.1: level up pendente? Resolve no fim do turno (não bloqueia o jogo:
            # ENTER pula e a escolha continua pendente para depois).
            state["player"] = _resolve_pending_choices(state["player"])
            _save_or_raise(state)

            # spec checkpoints-morte (D2): queda letal → tela de morte no terminal.
            if state.get("death_pending"):
                from services import checkpoints as _cp
                print(f"\n{Colors.FAIL}☠️  Você tombou.{Colors.ENDC}")
                esc = input("  [1] Continuar do checkpoint   [2] Aceitar o fim\n  Escolha [1]: ").strip()
                choice = "accept" if esc == "2" else "continue"
                state = _cp.resolve_death_choice(state, choice)
                _save_or_raise(state)
                if state.get("game_over"):
                    print(f"\n{Colors.FAIL}💀 A saga termina. A crônica permanece como memorial.{Colors.ENDC}")
                    break
                print(f"\n{Colors.GREEN}A Roda do Abismo te devolve ao último respiro seguro.{Colors.ENDC}")
                continue
            # checkpoint na cadência (10 turnos) — o restore acima o consome.
            from services import checkpoints as _cp
            if _cp.should_checkpoint(state) and not _cp.maybe_write(state):
                raise RuntimeError("não foi possível persistir o checkpoint")

        except KeyboardInterrupt:
            print("\nEncerrando...")
            _save_or_raise(state)
            break
        except Exception as e:
            print(f"\n{Colors.FAIL}❌ Erro Crítico: {e}{Colors.ENDC}")

if __name__ == "__main__":
    run_game_loop()
