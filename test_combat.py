"""
test_combat.py
Cenário: Horda de Goblins (Teste de Multi-Target e AoE).
"""
import sys
from langchain_core.messages import AIMessage, HumanMessage
from agents.combat import combat_node
from character_creator import create_player_character

class C:
    HEADER = '\033[95m'; BLUE = '\033[94m'; GREEN = '\033[92m'; RED = '\033[91m'; YELLOW = '\033[93m'; RESET = '\033[0m'

def print_hud(state):
    p = state['player']
    print(f"\n{C.HEADER}HERÓI: {p['name']} (HP {p['hp']}/{p['max_hp']}){C.RESET}")
    print("-" * 40)
    
    active = [e for e in state['enemies'] if e['status'] == 'ativo']
    if not active:
        print(f"{C.GREEN}Nenhum inimigo vivo.{C.RESET}")
    
    for e in active:
        # Minions em amarelo, Bosses em vermelho
        color = C.RED if e.get('type') == 'BOSS' else C.YELLOW
        print(f"💀 {e['name']} (HP {e['hp']}/{e.get('max_hp', e['hp'])}) [AC {e['ac']}]")
    print("="*60)

def run_test():
    print(f"{C.HEADER}⚔️  ARENA DE TESTE: EMBOSCADA GOBLIN ⚔️{C.RESET}")
    
    player = create_player_character({
        "name": "Kalel", "class_name": "Mago", "race": "Tritão", "level": 10,
        "backstory": "Especialista em magias de área."
    })
    
    # --- SETUP DA HORDA ---
    # 3 Goblins e 1 Chefe Hobgoblin para liderar
    enemies = [
        {
            "id": "goblin_1", "name": "Goblin Cortador", "type": "Minion",
            "hp": 12, "max_hp": 12, "ac": 15, "status": "ativo",
            "attacks": [{"name": "Cimitarra Enferrujada", "bonus": 4, "damage": "1d6+2 slashing"}]
        },
        {
            "id": "goblin_2", "name": "Goblin Arqueiro", "type": "Minion",
            "hp": 10, "max_hp": 10, "ac": 14, "status": "ativo",
            "attacks": [{"name": "Arco Curto", "bonus": 4, "damage": "1d6+2 piercing"}]
        },
        {
            "id": "goblin_3", "name": "Goblin Arqueiro", "type": "Minion",
            "hp": 10, "max_hp": 10, "ac": 14, "status": "ativo",
            "attacks": [{"name": "Arco Curto", "bonus": 4, "damage": "1d6+2 piercing"}]
        },
        {
            "id": "hobgoblin_1", "name": "Capitão Hobgoblin", "type": "Elite", # Não é BOSS, então sem ToT complexo
            "hp": 40, "max_hp": 40, "ac": 18, "status": "ativo",
            "attacks": [{"name": "Espada Longa", "bonus": 6, "damage": "1d8+3 slashing"}]
        }
    ]
    
    state = {
        "player": player, "enemies": enemies,
        "messages": [AIMessage(content="Você entra na clareira e 4 criaturas saltam dos arbustos! É uma emboscada!")],
        "combat_target": None, "world": {}
    }

    while True:
        print_hud(state)
        
        # Condição de Vitória/Derrota
        alive_enemies = [e for e in state['enemies'] if e['hp'] > 0]
        if state['player']['hp'] <= 0:
            print(f"\n{C.RED}💀 GAME OVER - A horda te dominou.{C.RESET}"); break
        if not alive_enemies:
            print(f"\n{C.GREEN}🏆 VITÓRIA - A clareira está segura.{C.RESET}"); break

        action = input(f"\n{C.GREEN}➤ Ação: {C.RESET}")
        if action in ['sair', 'exit']: break
        
        state['messages'].append(HumanMessage(content=action))
        print(f"{C.YELLOW}⚙️  Processando turno da horda...{C.RESET}")
        
        try:
            result = combat_node(state)
            
            if "player" in result: state['player'] = result['player']
            if "enemies" in result: state['enemies'] = result['enemies']
            
            if "messages" in result:
                msgs = result['messages']
                state['messages'].extend(msgs)
                # Filtra a narrativa final
                last_text = next((m.content for m in reversed(msgs) if isinstance(m, AIMessage) and m.content and not m.tool_calls), None)
                if last_text:
                    print(f"\n{C.BLUE}🤖 DM:{C.RESET} {last_text}")
                else:
                    print(f"\n{C.BLUE}🤖 DM:{C.RESET} (Verifique logs)")

        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback; traceback.print_exc()

if __name__ == "__main__":
    run_test()