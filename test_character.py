"""
test_character.py
Script de teste isolado para o Character Creator V4.
Atualizado para suportar Regiões e Classes do Lore.
"""
import json
import sys

# Tenta importar as classes do gamedata para mostrar sugestões
try:
    from gamedata import CLASSES
    AVAILABLE_CLASSES = list(CLASSES.keys())
except ImportError:
    # Fallback caso o gamedata ainda não esteja configurado
    AVAILABLE_CLASSES = ["Guerreiro", "Mago", "Ladino"]

from character_creator import create_player_character

def run_test():
    print("\n🧪 TESTE DE CRIAÇÃO DE PERSONAGEM (LORE INTEGRADO)")
    print("="*60)
    
    # 1. Dados Básicos
    name = input("Nome do Herói (ex: Kael): ") or "Kael"
    
    # 2. Seleção de Classe (Mostra as que existem no JSON)
    print(f"\n--- CLASSES DISPONÍVEIS ---")
    print(", ".join(AVAILABLE_CLASSES))
    c_class = input("Escolha a Classe: ") or "Aventureiro"
    
    # 3. Raça e Região (Essencial para o novo Lore)
    race = input("\nRaça (ex: Anão da Fuligem, Elfo de Cristal): ") or "Humano"
    
    print("\n--- REGIÃO DE ORIGEM (Define o Inventário) ---")
    print("Sugestões: Nova Arcádia, Floresta dos Sussurros, Montanhas Afiadas, Deserto de Zhur, O Norte Gelado")
    region = input("Região: ") or "Nova Arcádia"
    
    # 4. Nível e Backstory
    print("\n--- NÍVEL DE PODER ---")
    lvl_str = input("Nível inicial (1-20): ")
    level = int(lvl_str) if lvl_str.isdigit() else 1
    
    print("\n--- HISTÓRIA / CONCEITO ---")
    print("Resumo curto. Ex: 'Um ex-mineiro que busca vingança contra o capataz goblin.'")
    backstory = input("Backstory: ") or "Sobrevivente buscando glória."

    # Monta o pacote de dados
    input_data = {
        "name": name, 
        "class_name": c_class, 
        "race": race,
        "region": region,    # <--- O CAMPO NOVO IMPORTANTE
        "backstory": backstory, 
        "level": level
    }

    print("\n⚙️  A IA está consultando o Lore e forjando seu herói...")
    
    try:
        sheet = create_player_character(input_data)
    except Exception as e:
        print(f"❌ Erro Crítico: {e}")
        return

    # Exibição dos Resultados
    print("\n" + "="*20 + " FICHA DE VALORIA " + "="*20)
    print(f"Nome: {sheet['name']} (Lv {sheet['level']})")
    print(f"Linhagem: {sheet['race']} de {sheet.get('region', 'Desconhecida')}")
    print(f"Classe: {sheet['class_name']}")
    print(f"Conceito: {sheet['concept']}")
    print("-" * 40)
    print(f"❤️  HP: {sheet['hp']}/{sheet['max_hp']}")
    print(f"🛡️  AC: {sheet['defense']}")
    
    print("\n📊 ATRIBUTOS:")
    attrs = sheet.get('attributes', {})
    print(f"STR: {attrs.get('str', 10)} | DEX: {attrs.get('dex', 10)} | CON: {attrs.get('con', 10)}")
    print(f"INT: {attrs.get('int', 10)} | WIS: {attrs.get('wis', 10)} | CHA: {attrs.get('cha', 10)}")
    
    print("\n🎒 INVENTÁRIO (Baseado no Lore):")
    for item in sheet.get('inventory', []):
        print(f" - {item}")

    print("\n🧠 DUMP TÉCNICO (JSON):")
    print(json.dumps(sheet, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    run_test()