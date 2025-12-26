"""
gamedata.py
Carrega os dados do jogo (Classes, Itens, Bestiário) a partir dos JSONs.
"""
import json
import os

def load_json_data(filename: str):
    """Carrega um JSON da pasta data/, retornando dict vazio se falhar."""
    # Ajuste o caminho conforme sua estrutura de pastas
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, "data", filename)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ [GAMEDATA] Arquivo não encontrado: {filename}")
        return {}
    except Exception as e:
        print(f"❌ [GAMEDATA] Erro ao ler {filename}: {e}")
        return {}

# --- CARREGAMENTO DINÂMICO ---

# 1. Classes (Vem de data/classes.json)
CLASSES = load_json_data("classes.json")

# 2. Habilidades (Vem de data/player_abilities.json)
ABILITIES = load_json_data("player_abilities.json")

# 3. Bestiário (Vem de data/bestiary.json)
BESTIARY = load_json_data("bestiary.json")

# 4. Itens (Ainda podemos manter hardcoded ou criar data/items.json)
# Se quiser migrar itens também, crie items.json e use load_json_data("items.json")
ITEMS_DB = {
    "Espada Longa": {"type": "weapon", "bonus": 3, "attr": "str", "desc": "Lâmina de aço (+3 Atk)."},
    "Adaga Sombria": {"type": "weapon", "bonus": 2, "attr": "dex", "desc": "Lâmina rápida (+2 Atk)."},
    "Machado de Guerra": {"type": "weapon", "bonus": 5, "attr": "str", "desc": "Pesado e brutal (+5 Atk)."},
    "Besta Pesada": {"type": "weapon", "bonus": 4, "attr": "dex", "desc": "Dispara virotes de ferro."},
    "Cajado de Cristal": {"type": "weapon", "bonus": 2, "attr": "int", "desc": "Foco arcano."},
    "Poção de Cura": {"type": "consumable", "effect": "heal_hp", "value": 15, "desc": "Recupera 15 HP."},
    "Poção de Mana": {"type": "consumable", "effect": "heal_mana", "value": 10, "desc": "Recupera 10 Mana."},
    "Adaga de Vidro (Zhur)": {"type": "weapon", "bonus": 4, "attr": "dex", "desc": "Muito afiada, mas frágil."},
    "Máscara de Gás": {"type": "armor", "bonus": 1, "desc": "Essencial contra a névoa."}
}

# Fallback se os arquivos não existirem (Para não quebrar o jogo)
if not CLASSES:
    CLASSES = {
        "Aventureiro": {
            "description": "Classe padrão de teste.",
            "base_stats": {"hp": 20, "mana": 10, "stamina": 10, "defense": 12, "attributes": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}}
        }
    }