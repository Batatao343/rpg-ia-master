"""
persistence.py
Gerencia o Salvamento e Carregamento do Estado do Jogo.
Salva em pasta dedicada 'saves/' e serializa novos campos de memória.

Fase 10: `save_path()` é o ÚNICO lugar que monta caminho de save a partir de
game_id vindo do cliente (valida UUID — anti path-traversal); saves carregam
`schema_version` e passam pelo pipeline `_MIGRATIONS` no load.
"""
import os
import json
import glob
import uuid
from typing import Any, Callable, Dict, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

# Configuração de Pastas
SAVES_DIR = "saves"
DEFAULT_SAVE_NAME = "autosave"

# Versão atual do schema de save (Fase 10). Save sem o campo = versão 0.
# v2 = campos de camada dos NPCs (spec npcs-3-camadas-traits).
# v3 = 10 classes antigas → 5 Posturas + Entropia (spec refatoracao-sistema-classes).
SCHEMA_VERSION = 3

# spec refatoracao-sistema-classes (R10/§3.10): mapa determinístico antigo→nova classe.
_OLD_TO_NEW_CLASS = {
    "Cavaleiro da Vigília": "Devoto do Abismo",
    "Inquisidor da Cinza": "Devoto do Abismo",
    "Sombra da Corte": "Sangromante",
    "Pastor de Pragas": "Corruptor",
    "Guardião Selvagem": "Corruptor",
    "Batedor das Fronteiras": "Arcanista Cinzento",
    "Sapador da Fuligem": "Médico de Campo",
    # (Sangromante / Arcanista Cinzento / Médico de Campo mantêm o nome)
}


def save_path(game_id: str) -> str:
    """Caminho canônico do save de `game_id`.

    Levanta ValueError se o game_id não for UUID ou se o caminho resolvido
    escapar de `saves/` — input do cliente nunca chega cru ao filesystem.
    """
    try:
        uuid.UUID(str(game_id))
    except (ValueError, TypeError):
        raise ValueError(f"game_id inválido (esperado UUID): {game_id!r}")
    path = os.path.join(SAVES_DIR, f"{game_id}.json")
    root = os.path.abspath(SAVES_DIR)
    if not os.path.abspath(path).startswith(root + os.sep):
        raise ValueError(f"caminho de save fora de {SAVES_DIR}/: {game_id!r}")
    return path


# --- Migrations de save (Fase 10) ------------------------------------------

def _migrate_v0_to_v1(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Consolida os backfills heurísticos pré-Fase 10 num passo único:
    chronicle List[str] -> capítulos (3.1); known_abilities -> ids canônicos
    (4.1); inventário strings -> {id, qty} + slots (4.3); party sem ficha ->
    ficha default (4.5); game_over default (4.6). Idempotente."""
    raw = dict(raw)

    chron = raw.get("chronicle", [])
    if chron and isinstance(chron[0], str):
        raw["chronicle"] = [{
            "title": "Crônica da jornada", "started_turn": 0, "location": "",
            "entries": [{"text": t, "turn": 0, "kind": "prose"} for t in chron],
        }]

    player = raw.get("player", {})
    if player:
        from progression import canonicalize_known_abilities
        from inventory import backfill_inventory
        player = canonicalize_known_abilities(player)
        player = backfill_inventory(player)
        raw["player"] = player

    from party import backfill_party
    raw["party"] = backfill_party(raw.get("party", []))

    raw["game_over"] = bool(raw.get("game_over", False))
    return raw


def _migrate_v1_to_v2(raw: Dict[str, Any]) -> Dict[str, Any]:
    """spec npcs-3-camadas (R1): NPCs antigos ganham campos de camada + traits
    sorteados (seed npc_id+game_id — determinístico). `in_scene` fica AUSENTE
    de propósito (gate trata ausente como presente — save no meio de cena não
    fica órfão; a primeira viagem normaliza). Idempotente."""
    raw = dict(raw)
    npcs = raw.get("npcs") or {}
    if npcs:
        from services.npc_layers import ensure_npc_fields
        game_id = str(raw.get("game_id", ""))
        home = str((raw.get("world") or {}).get("current_location_id", ""))
        raw["npcs"] = {
            nome: ensure_npc_fields(npc, game_id, home_location_id=home)
            if isinstance(npc, dict) else npc
            for nome, npc in npcs.items()
        }
    return raw


def _migrate_v2_to_v3(raw: Dict[str, Any]) -> Dict[str, Any]:
    """spec refatoracao-sistema-classes (R10): 10 classes antigas → 5 Posturas.
    Mapeia class_name, backfilla entropy/max_entropy/abyss_charge da nova classe
    (Entropia escala como o HP), zera mana/stamina do jogador e descarta
    known_abilities que não existem mais (canonicalize) — somando as iniciais da
    nova classe. Save fica narrativamente órfão (mesma política do corte 2.5b)."""
    raw = dict(raw)
    player = dict(raw.get("player") or {})
    if not player:
        return raw
    from gamedata import CLASSES
    old = player.get("class_name", "")
    new = _OLD_TO_NEW_CLASS.get(old, old)
    player["class_name"] = new
    cd = CLASSES.get(new) or {}
    if "max_entropy" not in player or "entropy" not in player:
        base = cd.get("base_stats", {})
        gains = cd.get("level_gains", {})
        level = int(player.get("level", 1) or 1)
        max_ent = int(base.get("entropy", 0) or 0) + int(gains.get("entropy", 0) or 0) * (level - 1)
        player["max_entropy"] = max_ent
        player["entropy"] = max_ent
    player.setdefault("abyss_charge", 0)
    player["mana"] = 0
    player["max_mana"] = 0
    player["stamina"] = 0
    player["max_stamina"] = 0
    from progression import canonicalize_known_abilities
    player = canonicalize_known_abilities(player)
    known = list(player.get("known_abilities") or [])
    for aid in cd.get("starting_abilities") or []:
        if aid not in known:
            known.append(aid)
    player["known_abilities"] = known
    raw["player"] = player
    return raw


_MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    0: _migrate_v0_to_v1,
    1: _migrate_v1_to_v2,
    2: _migrate_v2_to_v3,
}


def migrate_state(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Aplica migrations de raw['schema_version'] (default 0) até SCHEMA_VERSION.

    Puro e idempotente: save já na versão atual não passa por migration nenhuma.
    """
    version = int(raw.get("schema_version", 0) or 0)
    while version < SCHEMA_VERSION:
        raw = _MIGRATIONS[version](raw)
        version += 1
        raw["schema_version"] = version
    return raw

def _serialize_messages(messages: List[BaseMessage]) -> List[Dict[str, str]]:
    """Converte objetos Message do LangChain para dicionários simples (JSON)."""
    serialized = []
    for msg in messages:
        msg_type = "unknown"
        if isinstance(msg, HumanMessage): msg_type = "human"
        elif isinstance(msg, AIMessage): msg_type = "ai"
        elif isinstance(msg, SystemMessage): msg_type = "system"
        
        serialized.append({
            "type": msg_type,
            "content": msg.content
        })
    return serialized

def _deserialize_messages(data: List[Dict[str, str]]) -> List[BaseMessage]:
    """Reconstrói objetos Message do LangChain a partir de dicionários."""
    messages = []
    for item in data:
        if item["type"] == "human":
            messages.append(HumanMessage(content=item["content"]))
        elif item["type"] == "ai":
            messages.append(AIMessage(content=item["content"]))
        elif item["type"] == "system":
            messages.append(SystemMessage(content=item["content"]))
    return messages

def get_latest_save_file() -> Optional[str]:
    """Retorna o caminho do arquivo de save mais recente na pasta saves/."""
    if not os.path.exists(SAVES_DIR):
        return None
    
    # Lista todos os .json na pasta saves
    list_of_files = glob.glob(os.path.join(SAVES_DIR, "*.json"))
    if not list_of_files:
        return None
        
    # Retorna o mais recente
    return max(list_of_files, key=os.path.getctime)

# --- spec polish-sessao (R1/R2): listar e excluir saves ----------------------

SESSION_MEMORY_DIR = os.path.join("data", "saves_memory")


def list_saves() -> List[Dict[str, Any]]:
    """Resumo de todos os saves de `saves/*.json`, ordenado por mtime desc.
    Leitura TOLERANTE: arquivo corrompido/ilegível é pulado, nunca derruba a
    lista (R1)."""
    if not os.path.isdir(SAVES_DIR):
        return []
    out: List[Dict[str, Any]] = []
    for path in glob.glob(os.path.join(SAVES_DIR, "*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            player = raw.get("player") or {}
            world = raw.get("world") or {}
            clock = world.get("world_clock") or {}
            out.append({
                "game_id": str(raw.get("game_id", "")),
                "name": str(player.get("name", "?")),
                "class_name": str(player.get("class_name", "")),
                "level": int(player.get("level", 1) or 1),
                "location": str(world.get("current_location", "")),
                "day": int(clock.get("day", 1) or 1),
                "game_over": bool(raw.get("game_over", False)),
                "updated_at": os.path.getmtime(path),
            })
        except Exception:
            continue
    out.sort(key=lambda s: s["updated_at"], reverse=True)
    return out


def delete_save(game_id: str) -> bool:
    """Remove o save E o índice de memória da sessão (senão vira lixo órfão).
    ValueError se game_id não é UUID (mesmo padrão do save_path — Fase 10);
    False se o save não existe."""
    import shutil
    path = save_path(game_id)  # levanta ValueError se inválido
    if not os.path.exists(path):
        return False
    os.remove(path)
    shutil.rmtree(os.path.join(SESSION_MEMORY_DIR, str(game_id)),
                  ignore_errors=True)
    return True


def save_game_state(state: Dict[str, Any]) -> bool:
    """
    Salva o estado completo do jogo em JSON na pasta 'saves/'.
    Usa o 'game_id' como nome do arquivo.
    """
    if not state: return False

    try:
        # Garante que a pasta existe
        if not os.path.exists(SAVES_DIR):
            os.makedirs(SAVES_DIR)

        # Define nome do arquivo baseado no ID.
        # Auditoria A3: game_id UUID passa pelo save_path (validação canônica);
        # legado não-UUID ("autosave", ids de teste) é SANITIZADO — nunca chega
        # cru ao filesystem (um save adulterado não escreve fora de saves/).
        game_id = state.get("game_id", DEFAULT_SAVE_NAME)
        try:
            file_path = save_path(game_id)
        except ValueError:
            safe = "".join(c for c in str(game_id)
                           if c.isalnum() or c in "-_") or DEFAULT_SAVE_NAME
            file_path = os.path.join(SAVES_DIR, f"{safe}.json")

        # Prepara os dados serializáveis
        save_data = {
            # --- Fase 10: versão do schema (migrations no load) ---
            "schema_version": SCHEMA_VERSION,
            # --- Identificação e Memória (Novos Campos) ---
            "game_id": game_id,
            "narrative_summary": state.get("narrative_summary", ""),
            "archivist_last_run": state.get("archivist_last_run", 0),
            "chronicle": state.get("chronicle", []),
            
            # --- Dados Transicionais ---
            "combat_target": state.get("combat_target"),
            "loot_source": state.get("loot_source"),
            "combat": state.get("combat", {}),

            # --- Dados Core ---
            "player": state.get("player", {}),
            "world": state.get("world", {}),
            "party": state.get("party", []),
            "enemies": state.get("enemies", []),
            "factions": state.get("factions", []),
            "faction_intel": state.get("faction_intel", {}),
            "bestiary_knowledge": state.get("bestiary_knowledge", {}),
            "npcs": state.get("npcs", {}),
            "inventory": state.get("inventory", []),
            "quests": state.get("quests", []),
            "campaign_plan": state.get("campaign_plan", {}),

            # --- Fase 2.5: eventos estruturados + projeção do mundo ---
            "event_log": state.get("event_log", []),
            "world_projection": state.get("world_projection", {}),
            "pending_world_events": state.get("pending_world_events", []),

            # --- Fase 4.6: save morto vira memorial (não aceita ações) ---
            "game_over": bool(state.get("game_over", False)),

            # --- Histórico ---
            "message_history": _serialize_messages(state.get("messages", []))
        }

        # Escreve no disco
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
        
        return True

    except Exception as e:
        print(f"❌ Erro crítico ao salvar jogo: {e}")
        return False

def load_game_state(specific_file: str = None) -> Dict[str, Any]:
    """
    Carrega o jogo. Se specific_file não for passado, carrega o mais recente.
    """
    target_file = specific_file
    
    if not target_file:
        target_file = get_latest_save_file()
    
    if not target_file or not os.path.exists(target_file):
        return None

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        # Fase 10: pipeline de migrations (consolida os backfills 3.1/4.1/4.3/4.5)
        raw_data = migrate_state(raw_data)

        # Reconstrói o Estado compatível com GameState
        state = {
            # --- Recupera Memória ---
            "game_id": raw_data.get("game_id", "recovered_session"),
            "narrative_summary": raw_data.get("narrative_summary", ""),
            "archivist_last_run": raw_data.get("archivist_last_run", 0),
            "chronicle": raw_data.get("chronicle", []),

            # --- Recupera Core ---
            "player": raw_data.get("player", {}),
            "world": raw_data.get("world", {}),
            "party": raw_data.get("party", []),
            "enemies": raw_data.get("enemies", []),
            "factions": raw_data.get("factions", []),
            "faction_intel": raw_data.get("faction_intel", {}),
            "bestiary_knowledge": raw_data.get("bestiary_knowledge", {}),
            "npcs": raw_data.get("npcs", {}),
            "inventory": raw_data.get("inventory", []),
            "quests": raw_data.get("quests", []),
            "campaign_plan": raw_data.get("campaign_plan", {}),

            # --- Fase 2.5: eventos estruturados + projeção do mundo ---
            "event_log": raw_data.get("event_log", []),
            "world_projection": raw_data.get("world_projection", {}),
            "pending_world_events": raw_data.get("pending_world_events", []),

            # --- Recupera Transicionais ---
            "combat_target": raw_data.get("combat_target"),
            "loot_source": raw_data.get("loot_source"),
            "combat": raw_data.get("combat", {}),

            # --- Recupera Mensagens ---
            "messages": _deserialize_messages(raw_data.get("message_history", [])),
            
            # Fase 4.6: memorial
            "game_over": bool(raw_data.get("game_over", False)),

            # Garante campos técnicos de fluxo
            "next": "storyteller",
            "needs_replan": False
        }

        return state

    except Exception as e:
        print(f"⚠️ Erro ao carregar save '{target_file}': {e}")
        return None