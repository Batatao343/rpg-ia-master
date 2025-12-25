"""
test_character.py
Script de teste isolado para o Character Creator V2.
"""
import json
import sys
from character_creator import create_player_character

def run_test():
    print("\n🧪 TESTE DE CRIAÇÃO DE PERSONAGEM (BACKSTORY + LEVEL)")
    print("="*50)
    
    name = input("Nome (ex: Batys): ") or "Batys"
    c_class = input("Classe (ex: Ladino): ") or "Ladino"
    race = input("Raça (ex: Elfo): ") or "Elfo"
    
    print("\n--- NÍVEL DE PODER ---")
    lvl_str = input("Nível inicial (1-20): ")
    level = int(lvl_str) if lvl_str.isdigit() else 1
    
    print("\n--- HISTÓRIA / CONCEITO ---")
    print("Escreva um resumo. Ex: 'Um mago de guerra que usa fogo para purificar hereges.'")
    backstory = input("Backstory: ") or "Aventureiro iniciante."

    input_data = {
        "name": name, "class_name": c_class, "race": race,
        "backstory": backstory, "level": level
    }

    print("\n⚙️  A IA está forjando seu herói...")
    
    try:
        sheet = create_player_character(input_data)
    except Exception as e:
        print(f"❌ Erro: {e}")
        return

    print("\n" + "="*20 + " FICHA GERADA " + "="*20)
    print(f"Nome: {sheet['name']} (Lv {sheet['level']})")
    print(f"Conceito Derivado: {sheet['concept']}")
    print(f"HP: {sheet['hp']}/{sheet['max_hp']} | AC: {sheet['defense']}")
    
    print("\n🎒 INVENTÁRIO:")
    for item in sheet.get('inventory', []):
        print(f" - {item}")

    print("\n🧠 ANÁLISE COMPLETA (JSON):")
    print(json.dumps(sheet, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    run_test()