"""
test_combat.py
Teste de Estresse: Combate em Grupo (Party) vs Horda com Boss.
Valida: Party AI, Boss Strategy (ToT), Habilidades Complexas e Uso de Recursos.
"""
import json
from langchain_core.messages import HumanMessage
from agents.combat import combat_node

# --- 1. O JOGADOR (Build: Inquisidor da Cinza - Tanque Ofensivo) ---
MOCK_PLAYER = {
    "name": "Kael",
    "class_name": "Inquisidor da Cinza",
    "level": 3,
    "hp": 35,
    "max_hp": 35,
    "mana": 20,
    "max_mana": 20,
    "stamina": 20,
    "max_stamina": 20,
    "defense": 16, # Cota de Malha
    "attributes": {"str": 16, "dex": 10, "con": 14, "int": 10, "wis": 12, "cha": 14},
    "inventory": ["Martelo de Guerra", "Símbolo Sagrado de Ferro"],
    # Habilidades que gastam recursos diferentes para testar a engine
    "known_abilities": [
        "Ataque Básico", 
        "Juramento de Sangue (Custa 5 Stamina, +Dano)", 
        "Destruição Divina (Custa 10 Mana, Dano Radiante)"
    ]
}

# --- 2. OS INIMIGOS (Horda + Boss Tático) ---
MOCK_ENEMIES = [
    {
        "id": "boss_grognak",
        "name": "Grognak, o Quebra-Crânios",
        "type": "BOSS",  # <--- Isso ativa a IA Tática (ToT)
        "hp": 60,
        "max_hp": 60,
        "defense": 15,
        "status": "ativo",
        "attacks": [
            "Machado Grande: +6 hit, 1d12+4 cortante",
            "Grito de Guerra (Buff Aliados)"
        ]
    },
    {
        "id": "gob_1",
        "name": "Goblin Lanceiro",
        "hp": 12,
        "max_hp": 12,
        "defense": 12,
        "status": "ativo",
        "attack": "Lança Curta: +4 hit, 1d6+2 perfurante"
    },
    {
        "id": "gob_2",
        "name": "Goblin Arqueiro",
        "hp": 10,
        "max_hp": 10,
        "defense": 12,
        "status": "ativo",
        "attack": "Arco Curto: +4 hit, 1d6 perfurante"
    }
]

# --- 3. A PARTY (Varg, o Açougueiro) ---
MOCK_PARTY = [
    {
        "name": "Varg",
        "role": "Tanque Sádico",
        "persona": "Varg gargalha alto quando vê sangue. Ele ignora arqueiros e foca sempre no inimigo maior para provar força.",
        "hp": 45,
        "max_hp": 45,
        "active": True,
        "stats": {
            "attack": "Cutelo Enferrujado: +5 hit, 2d6+3 cortante",
            "AC": 13
        }
    }
]

def run_combat_test():
    print("\n🔥 TESTE DE COMBATE ÉPICO: PARTY vs BOSS")
    print("="*60)
    print(f"HERÓIS: {MOCK_PLAYER['name']} (Inquisidor) & {MOCK_PARTY[0]['name']} (Açougueiro)")
    print(f"INIMIGOS: Grognak (BOSS) + 2 Goblins")
    print("-" * 60)

    # CENÁRIO: Kael usa uma habilidade complexa logo de cara
    action = "Eu ativo meu 'Juramento de Sangue' cortando a mão e avanço para esmagar o Goblin Lanceiro com meu Martelo!"
    
    state = {
        "messages": [HumanMessage(content=action)],
        "player": MOCK_PLAYER,
        "enemies": MOCK_ENEMIES,
        "party": MOCK_PARTY,
        "world": {"current_location": "Salão do Trono Goblin"}
    }

    print(f"📢 AÇÃO DO JOGADOR: \"{action}\"\n")
    print("⚙️  Processando Turno (Aguarde a IA Tática e Party AI)...\n")

    try:
        result = combat_node(state)
        
        print("\n📝 NARRATIVA DE COMBATE:")
        print("="*60)
        
        narrative_found = False
        for m in result['messages']:
            if m.type == "ai" and not m.tool_calls:
                print(f"\n{m.content}\n")
                narrative_found = True
        
        if not narrative_found:
            print("⚠️ Erro: Nenhuma narrativa gerada.")

        print("="*60)
        print("📊 RELATÓRIO PÓS-BATAHLA:")
        
        p = result['player']
        print(f"🔹 Kael: {p['hp']}/{MOCK_PLAYER['max_hp']} HP | Mana: {p['mana']} | Stamina: {p['stamina']}")
        
        for ally in result.get('party', []):
            print(f"🛡️  {ally['name']}: {ally['hp']} HP")
            
        print("-" * 20)
        for e in result.get('enemies', []):
            status = "MORTO 💀" if e['hp'] <= 0 else "VIVO"
            print(f"👹 {e['name']}: {e['hp']} HP [{status}]")

    except Exception as e:
        print(f"❌ CRASH: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_combat_test()