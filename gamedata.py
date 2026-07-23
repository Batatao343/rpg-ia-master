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


def runtime_cache_path(name: str) -> str:
    """spec isolar-cache-runtime: caches gerados em RUNTIME (bestiário gerado,
    NPC db, artefatos custom) moram FORA dos dados curados. O diretório é
    resolvido em tempo de CHAMADA (env `RPG_RUNTIME_CACHE_DIR`; default
    `data/runtime/`, gitignored) — suíte e playtest redirecionam sem depender
    de ordem de import."""
    base = os.getenv("RPG_RUNTIME_CACHE_DIR") or os.path.join(DATA_DIR, "runtime")
    return os.path.join(base, name)

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

def _read_json_file(file_path: str) -> dict:
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except Exception:
        return {}


def save_custom_artifact(item_id: str, item_data: dict):
    """
    Salva um item criado pela IA no cache persistente (overlay runtime — spec
    isolar-cache-runtime: nunca grava em data/; o legado data/custom_artifacts.json
    segue sendo LIDO no startup).
    Atualiza tanto o arquivo físico quanto a memória RAM.
    """
    file_path = runtime_cache_path("custom_artifacts.json")

    # 1. Carrega dados atuais do disco (legado + overlay, overlay vence)
    current_data = {**_read_json_file(os.path.join(DATA_DIR, "custom_artifacts.json")),
                    **_read_json_file(file_path)}

    # 2. Adiciona/Atualiza o novo item
    current_data[item_id] = item_data

    # 3. Salva no disco
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
        print(f"💾 [SYSTEM] Item '{item_id}' salvo em custom_artifacts.json (runtime)")
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
# custom = legado (data/, pré-spec) + overlay runtime (overlay vence)
CUSTOM_ARTIFACTS = {**load_json_data("custom_artifacts.json"),
                    **_read_json_file(runtime_cache_path("custom_artifacts.json"))}

# Fusão: Une os dois dicionários.
ARTIFACTS_DB = {**BASE_ARTIFACTS, **CUSTOM_ARTIFACTS}

# Lista rápida de IDs
ALL_ARTIFACT_IDS = list(ARTIFACTS_DB.keys())

# 3. Mundo (grafo de locais) e Temas de Classe (Fase 0)
WORLD_MAP = load_json_data("world_map.json")
CLASS_THEMES = load_json_data("class_themes.json")

# 4. Fações (Fase 2 — mundo vivo): objetivos próprios que avançam no tempo
FACTIONS = load_json_data("factions.json")


def seed_factions() -> list:
    """Lista fresca de fações para uma nova partida (cópia profunda dos seeds)."""
    import copy
    return [copy.deepcopy(f) for f in FACTIONS.values()]

_LOCATIONS_BY_ID = {loc["id"]: loc for loc in WORLD_MAP.get("locations", [])}
START_LOCATION_ID = WORLD_MAP.get("start_location") or next(iter(_LOCATIONS_BY_ID), None)
# Local inicial por nome de região (ex.: "Nova Arcádia" -> "nova_arcadia")
REGION_START_ID = {
    loc["region"]: loc["id"]
    for loc in WORLD_MAP.get("locations", [])
    if loc.get("start")
}


def get_location(loc_id: str) -> dict:
    """Retorna o nó de um local pelo id, ou {} se não existir."""
    return _LOCATIONS_BY_ID.get(loc_id, {})


def get_connections(loc_id: str) -> list:
    """Locais (dicts) conectados ao local informado."""
    loc = _LOCATIONS_BY_ID.get(loc_id, {})
    return [_LOCATIONS_BY_ID[c] for c in loc.get("connections", []) if c in _LOCATIONS_BY_ID]


def interiors_of(loc_id: str) -> list:
    """Interiores (masmorras/prédios, kind='interior') filhos do local (spec mapa-sublocais)."""
    return [
        loc for loc in _LOCATIONS_BY_ID.values()
        if loc.get("kind") == "interior" and loc.get("parent_id") == loc_id
    ]


def find_location_by_name(name: str) -> dict:
    """Resolve um local pelo nome de exibição (case-insensitive)."""
    if not name:
        return {}
    low = name.strip().lower()
    for loc in _LOCATIONS_BY_ID.values():
        if loc["name"].lower() == low:
            return loc
    return {}


def start_location_for_region(region_name: str) -> dict:
    """Local inicial de uma região (pelo nome). Cai no start global se não achar."""
    loc_id = REGION_START_ID.get(region_name)
    if not loc_id:
        # tenta casar por nome de local direto, senão start global
        direct = find_location_by_name(region_name)
        loc_id = direct.get("id") if direct else START_LOCATION_ID
    return _LOCATIONS_BY_ID.get(loc_id, {})

# --- TABELA DE XP ---
XP_TABLE = {
    1: 0, 2: 300, 3: 900, 4: 2700, 5: 6500,
    6: 14000, 7: 23000, 8: 34000, 9: 48000, 10: 64000,
    11: 85000, 12: 100000, 13: 120000, 14: 140000, 15: 165000,
    16: 195000, 17: 225000, 18: 265000, 19: 305000, 20: 355000
}

# --- CONFLITO v2 (spec conflito-01): Virtudes / Vitalidade / Ferimentos ---
# Doc: docs/valoria_conflict_migration_v2/01_..._CONFLITOS.md §8.1
# 5 Virtudes (chaves curtas): mente/agilidade/forca/carisma/corpo (0-5).
VIRTUDES = ("mente", "agilidade", "forca", "carisma", "corpo")

# Distribuição fixa oferecida na criação (multiset livre entre as 5 Virtudes).
DISTRIBUICAO_VIRTUDES_INICIAL = (4, 3, 2, 1, 1)

VIRTUDE_MAX = 5          # teto por Virtude
NIVEL_MAX = 10           # conflito-01 R3: nível máximo passa de 20 para 10
# Níveis em que o jogador escolhe +1 numa Virtude (R3).
NIVEIS_GANHO_VIRTUDE = (2, 4, 6, 8, 10)

# --- CONFLITO v2 (spec conflito-05): armadura / escudo / dano-base ---
# Dano-base por categoria de arma (R1).
DANO_BASE_ARMA = {"leve": 3, "marcial": 4, "versatil": 6, "pesada": 8}

# Armaduras (R5): protecao / integridade_max / penalidade_esquiva / reducoes_max_por_ataque.
ARMADURAS = {
    "leve":   {"protecao": 1, "integridade_max": 4, "penalidade_esquiva": 0, "reducoes_max": 1},
    "media":  {"protecao": 2, "integridade_max": 6, "penalidade_esquiva": 1, "reducoes_max": 2},
    "pesada": {"protecao": 3, "integridade_max": 8, "penalidade_esquiva": 2, "reducoes_max": 3},
}

# Escudos (R6): protecao / integridade_max / requisito_forca.
ESCUDOS = {
    "broquel": {"protecao": 1, "integridade_max": 3, "requisito_forca": 0},
    "comum":   {"protecao": 2, "integridade_max": 5, "requisito_forca": 2},
    "pesado":  {"protecao": 3, "integridade_max": 7, "requisito_forca": 3},
}

# Ajuste de dano por Resistência/Vulnerabilidade (R4).
RESIST_MODIFIER = {
    "resistencia": -2, "resistencia_maior": -4,
    "vulnerabilidade": 2, "vulnerabilidade_maior": 4,
}

DANO_FISICO = ("cortante", "perfurante", "impactante")
DANO_SOBRENATURAL = ("igneo", "gelido", "eletrico", "arcano", "corrosivo", "abissal")


def make_armor(categoria: str) -> dict:
    """Instancia uma armadura pela categoria (R5), Integridade cheia."""
    base = ARMADURAS.get(categoria, ARMADURAS["leve"])
    return {"categoria": categoria, "protecao": base["protecao"],
            "integridade_max": base["integridade_max"],
            "integridade_atual": base["integridade_max"],
            "penalidade_esquiva": base["penalidade_esquiva"],
            "reducoes_max": base["reducoes_max"], "comprometida": False}


def make_shield(categoria: str) -> dict:
    base = ESCUDOS.get(categoria, ESCUDOS["broquel"])
    return {"categoria": categoria, "protecao": base["protecao"],
            "integridade_max": base["integridade_max"],
            "integridade_atual": base["integridade_max"],
            "requisito_forca": base["requisito_forca"], "comprometida": False}


# Cartas preparadas por faixa de nível (spec conflito-02 R2).
def prepared_slots_for_level(level) -> int:
    try:
        lv = int(level)
    except (TypeError, ValueError):
        lv = 1
    lv = max(1, min(NIVEL_MAX, lv))
    if lv <= 3:
        return 4
    if lv <= 6:
        return 5
    if lv <= 9:
        return 6
    return 7


# Estágio de evolução das Cartas de Virtude pela Virtude relacionada (R7).
def virtue_card_stage(virtude_value) -> int:
    try:
        v = int(virtude_value)
    except (TypeError, ValueError):
        v = 0
    if v <= 2:
        return 1
    if v <= 4:
        return 2
    return 3


# Vitalidade máxima derivada de Corpo (R4).
VITALIDADE_POR_CORPO = {0: 6, 1: 8, 2: 10, 3: 12, 4: 14, 5: 16}

# Espaços de Ferimento por categoria derivados de Corpo (R4).
ESPACOS_FERIMENTO_POR_CORPO = {
    0: {"leve": 2, "grave": 1, "critico": 1},
    1: {"leve": 3, "grave": 1, "critico": 1},
    2: {"leve": 3, "grave": 2, "critico": 1},
    3: {"leve": 4, "grave": 2, "critico": 2},
    4: {"leve": 4, "grave": 3, "critico": 2},
    5: {"leve": 5, "grave": 3, "critico": 3},
}

# Limites de Gravidade: faixa de EXCEDENTE de dano -> categoria de Ferimento (R5).
# Tuplas (min, max); crítico é aberto (max=None).
LIMITES_GRAVIDADE_POR_CORPO = {
    0: {"leve": (1, 3), "grave": (4, 6), "critico": (7, None)},
    1: {"leve": (1, 4), "grave": (5, 8), "critico": (9, None)},
    2: {"leve": (1, 5), "grave": (6, 10), "critico": (11, None)},
    3: {"leve": (1, 6), "grave": (7, 12), "critico": (13, None)},
    4: {"leve": (1, 7), "grave": (8, 14), "critico": (15, None)},
    5: {"leve": (1, 8), "grave": (9, 16), "critico": (17, None)},
}


# Aliases legados (chaves D&D / nomes longos / PT) -> chave curta de Virtude.
# wis/int caem em "mente" (sem Virtude dedicada de percepção).
_VIRTUDE_ALIASES = {
    "str": "forca", "strength": "forca", "forca": "forca", "força": "forca",
    "dex": "agilidade", "dexterity": "agilidade", "agilidade": "agilidade", "destreza": "agilidade",
    "con": "corpo", "constitution": "corpo", "corpo": "corpo", "constituicao": "corpo",
    "int": "mente", "intelligence": "mente", "mente": "mente", "inteligencia": "mente",
    "wis": "mente", "wisdom": "mente", "sabedoria": "mente",
    "cha": "carisma", "charisma": "carisma", "carisma": "carisma",
}


def _fold_key(key: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(key or "").strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalize_virtude(key: str) -> str:
    """Normaliza uma chave de atributo/Virtude (D&D longo/PT/acento) para a chave
    curta canônica de Virtude. Fonte única — usada por creator/progressão/API."""
    raw = str(key or "").strip().lower()
    if raw in _VIRTUDE_ALIASES:
        return _VIRTUDE_ALIASES[raw]
    return _VIRTUDE_ALIASES.get(_fold_key(raw), _fold_key(raw))


def _clamp_corpo(corpo) -> int:
    try:
        c = int(corpo)
    except (TypeError, ValueError):
        c = 0
    return max(0, min(VIRTUDE_MAX, c))


def vitalidade_para_corpo(corpo) -> int:
    """Vitalidade máxima para um valor de Corpo (0-5, clampado)."""
    return VITALIDADE_POR_CORPO[_clamp_corpo(corpo)]


def espacos_ferimento_para_corpo(corpo) -> dict:
    """Espaços {leve,grave,critico} para um valor de Corpo (cópia nova)."""
    return dict(ESPACOS_FERIMENTO_POR_CORPO[_clamp_corpo(corpo)])


def categoria_ferimento(corpo, excedente) -> "str | None":
    """Mapeia o EXCEDENTE de dano (dano - absorção) para a categoria de Ferimento
    conforme os Limites de Gravidade do Corpo. Excedente <= 0 -> nenhum Ferimento."""
    try:
        exc = int(excedente)
    except (TypeError, ValueError):
        return None
    if exc <= 0:
        return None
    faixas = LIMITES_GRAVIDADE_POR_CORPO[_clamp_corpo(corpo)]
    for cat in ("leve", "grave", "critico"):
        lo, hi = faixas[cat]
        if exc >= lo and (hi is None or exc <= hi):
            return cat
    return "critico"


def sync_player_vitals(player: dict, *, heal_to_full: bool = False) -> dict:
    """Recalcula Vitalidade/espaços de Ferimento a partir de Corpo (R4).

    Chamado na criação, no bump de Corpo (level-up) e na migração. NUNCA lazy —
    `max_vitalidade`/`ferimento_espacos` ficam sempre coerentes com Corpo. A
    Vitalidade atual sobe junto com o teto (ganho de Corpo cura o delta) e é
    clampada ao novo máximo; `heal_to_full` força cheia (criação)."""
    virtudes = player.get("virtudes") or {}
    corpo = virtudes.get("corpo", 0)
    novo_max = vitalidade_para_corpo(corpo)
    antigo_max = int(player.get("max_vitalidade", 0) or 0)
    atual = int(player.get("vitalidade", novo_max) or 0)
    player["max_vitalidade"] = novo_max
    player["ferimento_espacos"] = espacos_ferimento_para_corpo(corpo)
    player.setdefault("ferimentos", {"leve": [], "grave": [], "critico": []})
    if heal_to_full or "vitalidade" not in player:
        player["vitalidade"] = novo_max
    else:
        # ganho de teto (Corpo subiu) soma no atual; clampa ao novo máximo
        atual += max(0, novo_max - antigo_max)
        player["vitalidade"] = max(0, min(novo_max, atual))
    return player
