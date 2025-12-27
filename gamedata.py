"""
gamedata.py
Central de Dados Estáticos e Dinâmicos.
Gerencia o carregamento de regras, itens, bestiário e a persistência de criações da IA.
"""
import json
import os

# --- CONFIGURAÇÃO DE CAMINHOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def load_json_data(filename: str) -> dict:
    """Carrega um arquivo JSON da pasta data. Retorna dict vazio se falhar."""
    file_path = os.path.join(DATA_DIR, filename)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            # Tenta carregar. Se o arquivo estiver vazio, json.load falha.
            content = f.read().strip()
            if not content: return {}
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        # Se não existir ou estiver corrompido, retorna vazio para evitar crash
        if "custom" in filename:
            return {}
        print(f"⚠️ Aviso: Arquivo '{filename}' não encontrado ou inválido em {DATA_DIR}.")
        return {}
    except Exception as e:
        print(f"❌ Erro ao ler '{filename}': {e}")
        return {}

def save_custom_artifact(item_id: str, item_data: dict):
    """
    Salva um item criado pela IA no arquivo de cache persistente.
    Atualiza tanto o arquivo físico quanto a memória RAM.
    """
    file_path = os.path.join(DATA_DIR, "custom_artifacts.json")
    
    # 1. Carrega dados atuais do disco
    current_data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content: current_data = json.loads(content)
        except:
            current_data = {}
    
    # 2. Adiciona/Atualiza o novo item
    current_data[item_id] = item_data
    
    # 3. Salva no disco
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
        print(f"💾 [SYSTEM] Item '{item_id}' salvo em custom_artifacts.json")
    except Exception as e:
        print(f"❌ Erro ao salvar artifact: {e}")

    # 4. Atualiza a memória global (Hot Reload)
    ARTIFACTS_DB[item_id] = item_data
    CUSTOM_ARTIFACTS[item_id] = item_data # <--- CORREÇÃO: Atualiza a lista de custom também
    if item_id not in ALL_ARTIFACT_IDS:
        ALL_ARTIFACT_IDS.append(item_id)

# --- CARREGAMENTO DE DADOS (Load on Startup) ---

# 1. Dados Estáticos de Regras
CLASSES = load_json_data("classes.json")
ABILITIES = load_json_data("player_abilities.json")
BESTIARY = load_json_data("bestiary.json")

# 2. Sistema de Artefatos (Híbrido)
BASE_ARTIFACTS = load_json_data("artifacts.json")         
CUSTOM_ARTIFACTS = load_json_data("custom_artifacts.json") 

# Fusão: Une os dois dicionários.
ARTIFACTS_DB = {**BASE_ARTIFACTS, **CUSTOM_ARTIFACTS}

# Lista rápida de IDs
ALL_ARTIFACT_IDS = list(ARTIFACTS_DB.keys())

# Alias para compatibilidade
ITEMS_DB = ARTIFACTS_DB

# --- TABELA DE XP ---
XP_TABLE = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
    11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
    16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000
}

# Loot Genérico
COMMON_LOOT_TABLE = ["moeda_ouro", "corda", "pocao_cura", "adaga_ferro"]