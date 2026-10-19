"""
persistence.py
Gerencia o Salvamento e Carregamento do Estado do Jogo.
Salva em pasta dedicada 'saves/' e serializa novos campos de memória.

Fase 10: `save_path()` é o ÚNICO lugar que monta caminho de save a partir de
game_id vindo do cliente (valida UUID — anti path-traversal); saves carregam
`schema_version` e passam pelo hard cut de compatibilidade no load.
"""

import glob
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

import gamedata
from observability.telemetry import log_event as _log_event
from observability.telemetry import pseudonym as _pseudonym
from services.audit_trace import normalize_audit_trace
from services.conflict_summary import (
    ensure_conflict_id,
    normalize_consumed_conflict_ids,
)
from services.entity_identity import coalesce_runtime_npcs
from services.memory_provenance import (
    MAX_MEMORY_PROMOTIONS,
    MAX_MEMORY_REJECTIONS,
    bounded_audit_rows,
    normalize_memory_facts,
)
from services.memory_retry import normalize_pending_npc_memory
from services.memory_summary import compact_summary

# Configuração de Pastas
SAVES_DIR = "saves"
DEFAULT_SAVE_NAME = "autosave"


def _replace_with_retry(source: str, destination: str, *, attempts: int = 6) -> None:
    """Tolera locks efêmeros de antivírus/OneDrive sem perder atomicidade."""
    last_error: PermissionError | None = None
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError as exc:
            last_error = exc
            if attempt + 1 < attempts:
                _log_event(
                    "persistence",
                    "atomic_retry",
                    level="debug",
                    attempt=attempt + 1,
                    attempts=attempts,
                    error_type=type(exc).__name__,
                )
                time.sleep(0.01 * (2**attempt))
    assert last_error is not None
    _log_event(
        "persistence",
        "atomic_failed",
        level="error",
        attempts=attempts,
        error_type=type(last_error).__name__,
    )
    raise last_error


# Versão atual do schema de save (Fase 10). Save sem o campo = versão 0.
# v2 = campos de camada dos NPCs (spec npcs-3-camadas-traits).
# v3 = 10 classes antigas → 5 Posturas + Entropia (spec refatoracao-sistema-classes).
# v4 = Virtudes/Vitalidade/Ferimentos; v5 = Vitalidade canônica + aliases HP derivados.
# v6 = ledger visual; v7 = metatempo; v8 = crônica estável + progressão 1–20.
# SPEC-202 (`last_speaker` + speaker_* no histórico) é ADITIVA: sem bump; default
# no load (`_raw_to_state`) e rótulo legado derivado na leitura (history_page).
# SPEC-207 (`audit_trace`, ring buffer de refs por turno) também é ADITIVA: sem bump.
SCHEMA_VERSION = 8
MAX_REJECTED_ITEM_CLAIMS = 100


def normalize_rejected_item_claims(value) -> list[str]:
    """Ledger compacto de itens que a prosa tentou conceder sem autoridade."""
    if not isinstance(value, (list, tuple)):
        return []
    return list(
        dict.fromkeys(
            cleaned
            for item in value
            if (cleaned := " ".join(str(item or "").split())[:160].strip())
        )
    )[-MAX_REJECTED_ITEM_CLAIMS:]


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


# --- Compatibilidade de save (hard cut v4) ----------------------------------
def _migrate_v3_to_v4(raw: dict[str, Any]) -> dict[str, Any]:
    """spec conflito-01 R9/R10 (HARD CUTOVER): 6 atributos → 5 Virtudes +
    Vitalidade/Ferimentos. NÃO há conversão automática dos atributos antigos —
    a migração apenas MARCA o save como órfão/arquivado (mesma política dos saves
    pré-2.5b). O load devolve o estado somente-leitura; a API/CLI recusam ação com
    mensagem clara em vez de crashar."""
    raw = dict(raw)
    raw["archived"] = True
    raw["archived_reason"] = (
        "Personagem anterior à migração do Sistema de Conflitos (Virtudes/"
        "Vitalidade). Fichas antigas foram arquivadas — comece uma nova jornada."
    )
    return raw


def _normalize_vitality_actor(actor: Any) -> Any:
    """Normaliza uma ficha v4 sem permitir que HP vença a Vitalidade.

    Alguns companheiros/inimigos v4 ainda só possuíam HP. Para eles a migração
    cria a representação canônica sem alterar a quantidade observada; o
    adaptador de combate pode recalcular a escala anatômica quando houver
    Virtudes suficientes.
    """
    if not isinstance(actor, dict):
        return actor
    if not actor:
        return actor
    normalized = deepcopy(actor)
    has_vitality = normalized.get("vitalidade") is not None
    has_max_vitality = normalized.get("max_vitalidade") is not None
    if has_vitality or has_max_vitality:
        if not has_max_vitality:
            normalized["max_vitalidade"] = max(1, int(normalized.get("vitalidade", 0) or 0))
        if not has_vitality:
            normalized["vitalidade"] = int(normalized["max_vitalidade"])
        normalized["vitalidade"] = max(
            0,
            min(
                int(normalized["max_vitalidade"]),
                int(normalized.get("vitalidade", 0) or 0),
            ),
        )
        # Specs letalidade-v2/conflito-v4: saves de jogador anteriores ao bônus
        # de Postura ganham o novo teto preservando o dano já sofrido.
        # Só recalcula a escala anatômica quando o save realmente possui Corpo.
        # Fichas legadas/checkpoints sintéticos com apenas HP não podem inferir
        # Corpo=0: isso reduziria silenciosamente, por exemplo, 30 HP para 12.
        if (
            normalized.get("class_name") in gamedata.CLASSES
            and isinstance(normalized.get("virtudes"), dict)
            and normalized["virtudes"].get("corpo") is not None
        ):
            gamedata.sync_vitality(normalized)
        else:
            gamedata.sync_legacy_hp_aliases(normalized)
        return normalized

    # Compatibilidade de atores auxiliares v4 que ainda não tinham os campos
    # novos. A partir daqui HP deixa de ser lido pelo motor.
    legacy_max = max(1, int(normalized.get("max_hp", normalized.get("hp", 1)) or 1))
    legacy_current = max(0, min(legacy_max, int(normalized.get("hp", legacy_max) or 0)))
    normalized["max_vitalidade"] = legacy_max
    normalized["vitalidade"] = legacy_current
    gamedata.sync_legacy_hp_aliases(normalized)
    return normalized


def _migrate_v4_to_v5(raw: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(raw)
    if "player" in migrated:
        migrated["player"] = _normalize_vitality_actor(migrated.get("player"))
    if "party" in migrated:
        migrated["party"] = [
            _normalize_vitality_actor(actor) for actor in (migrated.get("party") or [])
        ]
    if "enemies" in migrated:
        migrated["enemies"] = [
            _normalize_vitality_actor(actor) for actor in (migrated.get("enemies") or [])
        ]
    if "consumed_conflict_ids" in migrated:
        migrated["consumed_conflict_ids"] = normalize_consumed_conflict_ids(
            migrated.get("consumed_conflict_ids")
        )
    pending = migrated.get("conflict_summary")
    if isinstance(pending, dict):
        pending = deepcopy(pending)
        world_turn = (migrated.get("world") or {}).get("turn_count")
        if (
            not pending.get("conflict_id")
            and pending.get("conflict_turn") is None
            and world_turn is not None
        ):
            pending["conflict_turn"] = int(world_turn)
        pending["conflict_id"] = ensure_conflict_id(
            pending,
            turn=pending.get("conflict_turn"),
        )
        migrated["conflict_summary"] = pending
    migrated["schema_version"] = 5
    return migrated


def _migrate_v5_to_v6(raw: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(raw)
    migrated["visual_seen_entity_ids"] = list(
        dict.fromkeys(
            str(value) for value in (migrated.get("visual_seen_entity_ids") or []) if value
        )
    )[-64:]
    migrated["visual_cue_ledger"] = [
        row
        for row in (migrated.get("visual_cue_ledger") or [])
        if isinstance(row, dict) and row.get("action_key")
    ][-64:]
    migrated["schema_version"] = 6
    return migrated


def _migrate_v6_to_v7(raw: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(raw)
    from services.continuity import normalize

    canonical_turn = int((migrated.get("world") or {}).get("turn_count", 0) or 0)
    migrated["continuity"] = normalize(
        migrated.get("continuity"),
        canonical_turn=canonical_turn,
    )
    migrated["schema_version"] = 7
    return migrated


def _migrate_v7_to_v8(raw: dict[str, Any]) -> dict[str, Any]:
    migrated = deepcopy(raw)
    from progression import normalize_player_progression
    from services.chronicle import ensure_chronicle_ids

    if isinstance(migrated.get("player"), dict):
        migrated["player"] = normalize_player_progression(migrated["player"])
    # Saves anteriores ao hard cut v4 permanecem como memoriais somente-leitura.
    # A crônica plana desses saves é parte do documento histórico e não deve ser
    # reinterpretada como o schema jogável por capítulos.
    chronicle = migrated.get("chronicle") or []
    if not migrated.get("archived") or all(isinstance(row, dict) for row in chronicle):
        migrated["chronicle"] = ensure_chronicle_ids(
            chronicle, game_id=str(migrated.get("game_id", "legacy"))
        )
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated


class IncompatibleSaveError(Exception):
    """Save gravado por um schema mais novo que o suportado (SPEC-228 R9)."""


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


def _game_ref(game_id: Any) -> str | None:
    return _pseudonym(game_id) if game_id else None


def migrate_state(raw: dict[str, Any]) -> dict[str, Any]:
    """Arquiva saves pré-v4 e normaliza v4→v6. Puro e idempotente."""
    version = int(raw.get("schema_version", 0) or 0)
    result = _migrate_state(raw, version)
    if version < SCHEMA_VERSION:
        _log_event(
            "persistence",
            "migrated",
            level="info",
            from_version=version,
            to_version=SCHEMA_VERSION,
            steps=SCHEMA_VERSION - version,
            game_ref=_game_ref(raw.get("game_id")),
        )
    return result


def _migrate_state(raw: dict[str, Any], version: int) -> dict[str, Any]:
    if version > SCHEMA_VERSION:
        _log_event(
            "persistence",
            "save_schema_newer",
            level="warning",
            found_version=version,
            supported_version=SCHEMA_VERSION,
            game_ref=_game_ref(raw.get("game_id")),
        )
        raise IncompatibleSaveError(f"save de versão mais nova (v{version} > v{SCHEMA_VERSION})")
    if version < 4:
        archived = _migrate_v3_to_v4(deepcopy(raw))
        archived["schema_version"] = 5
        return _migrate_v7_to_v8(_migrate_v6_to_v7(_migrate_v5_to_v6(archived)))
    if version >= SCHEMA_VERSION:
        return raw
    migrated = _migrate_v4_to_v5(raw) if version < 5 else deepcopy(raw)
    if version < 6:
        migrated = _migrate_v5_to_v6(migrated)
    if version < 7:
        migrated = _migrate_v6_to_v7(migrated)
    return _migrate_v7_to_v8(migrated)


def _serialize_messages(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    """Converte mensagens LangChain para dicts JSON (SPEC-228 R11: preserva
    ToolMessage, additional_kwargs, name, id e tool_calls)."""
    from langchain_core.messages import messages_to_dict

    return messages_to_dict(list(messages))


def _deserialize_messages(data: list[dict[str, Any]]) -> list[BaseMessage]:
    """Lê o formato novo (messages_to_dict) e o legado {type, content}."""
    from langchain_core.messages import messages_from_dict

    out: list[BaseMessage] = []
    for item in data or []:
        if not isinstance(item, dict):
            continue
        if "data" in item:
            try:
                out.extend(messages_from_dict([item]))
            except Exception:
                continue
            continue
        kind, content = item.get("type"), item.get("content", "")
        if kind == "human":
            out.append(HumanMessage(content=content))
        elif kind == "ai":
            out.append(AIMessage(content=content))
        elif kind == "system":
            out.append(SystemMessage(content=content))
    return out


def get_latest_save_file() -> str | None:
    """Retorna o caminho do arquivo de save mais recente na pasta saves/."""
    if not os.path.exists(SAVES_DIR):
        return None

    list_of_files = _iter_live_save_files()
    if not list_of_files:
        return None

    # Retorna o mais recente
    return max(list_of_files, key=os.path.getctime)


# --- spec polish-sessao (R1/R2): listar e excluir saves ----------------------

SESSION_MEMORY_DIR = os.path.join("data", "saves_memory")


def _iter_live_save_files() -> list[str]:
    """Arquivos de campanha, nunca slots internos de checkpoint."""
    return [
        path
        for path in glob.glob(os.path.join(SAVES_DIR, "*.json"))
        if not path.casefold().endswith(".checkpoint.json")
    ]


def list_saves() -> list[dict[str, Any]]:
    """Resumo de todos os saves de `saves/*.json`, ordenado por mtime desc.
    Leitura TOLERANTE: arquivo corrompido/ilegível é pulado, nunca derruba a
    lista (R1)."""
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        principal = current_principal()
        out = []
        for stored in get_runtime().game_store.list(principal):
            raw = stored.state
            player = raw.get("player") or {}
            world = raw.get("world") or {}
            clock = world.get("world_clock") or {}
            out.append(
                {
                    "game_id": str(stored.game_id),
                    "name": str(player.get("name", "?")),
                    "class_name": str(player.get("class_name", "")),
                    "level": int(player.get("level", 1) or 1),
                    "location": str(world.get("current_location", "")),
                    "day": int(clock.get("day", 1) or 1),
                    "game_over": bool(raw.get("game_over", False)),
                    "combat_simulation": bool((raw.get("combat_simulation") or {}).get("enabled")),
                    "updated_at": stored.updated_at.timestamp(),
                }
            )
        return out
    if not os.path.isdir(SAVES_DIR):
        return []
    out: list[dict[str, Any]] = []
    for path in _iter_live_save_files():
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            player = raw.get("player") or {}
            world = raw.get("world") or {}
            clock = world.get("world_clock") or {}
            out.append(
                {
                    "game_id": str(raw.get("game_id", "")),
                    "name": str(player.get("name", "?")),
                    "class_name": str(player.get("class_name", "")),
                    "level": int(player.get("level", 1) or 1),
                    "location": str(world.get("current_location", "")),
                    "day": int(clock.get("day", 1) or 1),
                    "game_over": bool(raw.get("game_over", False)),
                    "combat_simulation": bool((raw.get("combat_simulation") or {}).get("enabled")),
                    "updated_at": os.path.getmtime(path),
                }
            )
        except Exception:
            continue
    out.sort(key=lambda s: s["updated_at"], reverse=True)
    return out


def delete_save(game_id: str) -> bool:
    """Remove o save E o índice de memória da sessão (senão vira lixo órfão).
    ValueError se game_id não é UUID (mesmo padrão do save_path — Fase 10);
    False se o save não existe."""
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        from infrastructure.request_context import current_principal
        from infrastructure.runtime import get_runtime

        principal = current_principal()
        return get_runtime().game_store.delete(principal, uuid.UUID(str(game_id)))
    path = save_path(game_id)  # levanta ValueError se inválido
    checkpoint = _safe_save_path(game_id, suffix=".checkpoint")
    checkpoint_memory = checkpoint_memory_path(game_id)
    removed = False
    for candidate in (path, checkpoint):
        if os.path.exists(candidate):
            os.remove(candidate)
            removed = True
    if os.path.isdir(checkpoint_memory):
        removed = True
    shutil.rmtree(os.path.join(SESSION_MEMORY_DIR, str(game_id)), ignore_errors=True)
    shutil.rmtree(checkpoint_memory, ignore_errors=True)
    return removed


def _safe_session_memory_path(game_id: str) -> str:
    """Diretório de memória de uma sessão, fechado dentro da raiz configurada."""
    safe = "".join(c for c in str(game_id) if c.isalnum() or c in "-_")
    if not safe or safe != str(game_id):
        raise ValueError(f"game_id inválido para memória: {game_id!r}")
    root = os.path.abspath(SESSION_MEMORY_DIR)
    path = os.path.abspath(os.path.join(root, safe))
    if not path.startswith(root + os.sep):
        raise ValueError(f"memória fora de {SESSION_MEMORY_DIR}/: {game_id!r}")
    return path


def checkpoint_memory_path(game_id: str) -> str:
    checkpoint = _safe_save_path(game_id, suffix=".checkpoint")
    return checkpoint[:-5] + ".memory"


_EMPTY_MEMORY_MARKER = ".checkpoint-empty"


def _atomic_replace_directory(staged: str, destination: str) -> None:
    """Troca diretório com rollback local caso o rename novo falhe."""
    backup = destination + ".previous"
    shutil.rmtree(backup, ignore_errors=True)
    had_destination = os.path.exists(destination)
    if had_destination:
        _replace_with_retry(destination, backup)
    try:
        _replace_with_retry(staged, destination)
    except BaseException:
        if had_destination and os.path.exists(backup):
            _replace_with_retry(backup, destination)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def save_checkpoint_memory(game_id: str) -> bool:
    """Snapshot atômico de toda a árvore FAISS da sessão (raiz + NPCs)."""
    source = _safe_session_memory_path(game_id)
    destination = checkpoint_memory_path(game_id)
    os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
    staged = tempfile.mkdtemp(
        prefix=f".{game_id}.checkpoint-memory.", dir=os.path.dirname(os.path.abspath(destination))
    )
    try:
        if os.path.isdir(source):
            shutil.copytree(source, staged, dirs_exist_ok=True)
        else:
            with open(os.path.join(staged, _EMPTY_MEMORY_MARKER), "wb"):
                pass
        _atomic_replace_directory(staged, destination)
        return True
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise


def restore_checkpoint_memory(game_id: str) -> bool:
    """Restaura exatamente a árvore externa ligada ao checkpoint em disco."""
    snapshot_dir = checkpoint_memory_path(game_id)
    if not os.path.isdir(snapshot_dir):
        return False
    destination = _safe_session_memory_path(game_id)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    empty = os.path.exists(os.path.join(snapshot_dir, _EMPTY_MEMORY_MARKER))
    staged = tempfile.mkdtemp(
        prefix=f".{game_id}.restore-memory.", dir=os.path.dirname(destination)
    )
    try:
        if not empty:
            shutil.copytree(
                snapshot_dir,
                staged,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(_EMPTY_MEMORY_MARKER),
            )
        if empty:
            shutil.rmtree(staged)
            backup = destination + ".previous"
            shutil.rmtree(backup, ignore_errors=True)
            if os.path.exists(destination):
                _replace_with_retry(destination, backup)
            shutil.rmtree(backup, ignore_errors=True)
        else:
            _atomic_replace_directory(staged, destination)
        return True
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise


def capture_session_memory(game_id: str) -> dict[str, bytes] | None:
    """Representação portátil usada somente pelos snapshots in-memory do harness."""
    source = _safe_session_memory_path(game_id)
    if not os.path.isdir(source):
        return None
    captured: dict[str, bytes] = {}
    for root, _dirs, files in os.walk(source):
        for name in files:
            path = os.path.join(root, name)
            rel = os.path.relpath(path, source).replace("\\", "/")
            with open(path, "rb") as fh:
                captured[rel] = fh.read()
    return captured


def restore_captured_session_memory(game_id: str, captured: dict[str, bytes] | None) -> None:
    destination = _safe_session_memory_path(game_id)
    shutil.rmtree(destination, ignore_errors=True)
    if captured is None:
        return
    for rel, payload in captured.items():
        parts = rel.replace("\\", "/").split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ValueError(f"caminho inválido no snapshot de memória: {rel!r}")
        path = os.path.join(destination, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(payload)


def _safe_save_path(game_id: str, suffix: str = "") -> str:
    """Resolve o caminho do save (UUID canônico) ou sanitiza o legado. `suffix`
    (ex.: '.checkpoint') distingue o slot de checkpoint do save vivo."""
    try:
        base = save_path(game_id)
        if suffix:
            base = base[:-5] + f"{suffix}.json"  # troca '.json' final
        return base
    except ValueError:
        safe = "".join(c for c in str(game_id) if c.isalnum() or c in "-_") or DEFAULT_SAVE_NAME
        return os.path.join(SAVES_DIR, f"{safe}{suffix}.json")


def _atomic_write_json(file_path: str, data: dict[str, Any]) -> None:
    """Grava JSON completo e troca o destino atomicamente no mesmo volume."""
    directory = os.path.dirname(os.path.abspath(file_path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{os.path.basename(file_path)}.", suffix=".tmp", dir=directory
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        _replace_with_retry(tmp_path, file_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _projection_state(raw, state):
    from services.projections import normalize_projection_state

    return normalize_projection_state(raw, state)


def _knowledge(raw, *, legacy_default):
    from services.npc_knowledge import normalize_knowledge

    return normalize_knowledge(raw, legacy_default=legacy_default)


def _projection_plan(raw):
    from services.projections import normalize_plan

    return normalize_plan(raw)


def _state_to_save_data(state: dict[str, Any], game_id: str) -> dict[str, Any]:
    """Monta o dict serializável a partir do GameState (fonte única — save vivo
    E checkpoint reusam, pra nunca divergirem de campo)."""
    player = _normalize_vitality_actor(state.get("player") or {})
    party = [_normalize_vitality_actor(a) for a in (state.get("party") or [])]
    enemies = [_normalize_vitality_actor(a) for a in (state.get("enemies") or [])]
    pending_conflict = deepcopy(state.get("conflict_summary"))
    if isinstance(pending_conflict, dict):
        world_turn = (state.get("world") or {}).get("turn_count")
        if (
            not pending_conflict.get("conflict_id")
            and pending_conflict.get("conflict_turn") is None
            and world_turn is not None
        ):
            pending_conflict["conflict_turn"] = int(world_turn)
        pending_conflict["conflict_id"] = ensure_conflict_id(
            pending_conflict,
            turn=pending_conflict.get("conflict_turn"),
        )
    return {
        # --- Fase 10: versão do schema (migrations no load) ---
        "schema_version": SCHEMA_VERSION,
        # --- Identificação e Memória (Novos Campos) ---
        "game_id": game_id,
        "processed_action_ids": list(state.get("processed_action_ids", []) or [])[-64:],
        "visual_seen_entity_ids": list(state.get("visual_seen_entity_ids", []) or [])[-64:],
        "visual_cue_ledger": deepcopy(list(state.get("visual_cue_ledger", []) or [])[-64:]),
        "narrative_summary": compact_summary(state.get("narrative_summary", "")),
        "archivist_last_run": state.get("archivist_last_run", 0),
        "archive_due": bool(state.get("archive_due", False)),
        "chronicle": state.get("chronicle", []),
        "consumed_conflict_ids": normalize_consumed_conflict_ids(
            state.get("consumed_conflict_ids")
        ),
        "memory_fact_policy": state.get("memory_fact_policy"),
        "memory_canonical_facts": state.get("memory_canonical_facts", []),
        "memory_facts": normalize_memory_facts(state.get("memory_facts")),
        "pending_memory_facts": normalize_memory_facts(
            state.get("pending_memory_facts"),
            pending=True,
        ),
        "presentation_history": list(state.get("presentation_history") or []),
        # SPEC-207 (aditivo, sem bump): ring buffer de refs por turno p/ auditoria.
        "audit_trace": normalize_audit_trace(state.get("audit_trace")),
        # SPEC-213 (aditivo, sem bump): versão canônica + status das projeções.
        "projection_state": _projection_state(state.get("projection_state"), state),
        "pending_derived": _projection_plan(state.get("pending_derived")),
        # SPEC-215 (aditivo, sem bump): ledger privado de conhecimento por NPC.
        **_knowledge(state, legacy_default=False),
        "art_generation_ledger": deepcopy(state.get("art_generation_ledger") or []),
        "art_arc_budgets": deepcopy(state.get("art_arc_budgets") or {}),
        "art_offers": deepcopy(state.get("art_offers") or []),
        "evidence_rejections": list(state.get("evidence_rejections") or [])[-64:],
        "memory_rejections": bounded_audit_rows(
            state.get("memory_rejections"),
            limit=MAX_MEMORY_REJECTIONS,
        ),
        "memory_promotions": bounded_audit_rows(
            state.get("memory_promotions"),
            limit=MAX_MEMORY_PROMOTIONS,
        ),
        "rejected_item_claims": normalize_rejected_item_claims(state.get("rejected_item_claims")),
        "pending_npc_memory": normalize_pending_npc_memory(state.get("pending_npc_memory")),
        "rag_persistence_error": state.get("rag_persistence_error"),
        "continuity": deepcopy(state.get("continuity") or {}),
        # Canonical presentation receipts survive reload/idempotent retries.
        "last_turn_outcome": deepcopy(state.get("last_turn_outcome") or {}),
        "last_speaker": deepcopy(state.get("last_speaker") or {}),
        "last_interaction_outcome": deepcopy(state.get("last_interaction_outcome") or {}),
        # --- Dados Transicionais ---
        "combat_target": state.get("combat_target"),
        "loot_source": state.get("loot_source"),
        "combat": state.get("combat", {}),
        "conflict_summary": pending_conflict,
        # --- Dados Core ---
        "player": player,
        "world": state.get("world", {}),
        "party": party,
        "enemies": enemies,
        "factions": state.get("factions", []),
        "faction_intel": state.get("faction_intel", {}),
        "bestiary_knowledge": state.get("bestiary_knowledge", {}),
        "npcs": coalesce_runtime_npcs(state.get("npcs", {})),
        "inventory": state.get("inventory", []),
        "quests": state.get("quests", []),
        "campaign_plan": state.get("campaign_plan", {}),
        # --- Fase 2.5: eventos estruturados + projeção do mundo ---
        "event_log": state.get("event_log", []),
        "world_projection": state.get("world_projection", {}),
        "pending_world_events": state.get("pending_world_events", []),
        "event_rejections": state.get("event_rejections", []),
        # --- Fase 4.6: save morto vira memorial (não aceita ações) ---
        "game_over": bool(state.get("game_over", False)),
        # --- spec checkpoints-morte: tela de morte pendente (persiste entre requests) ---
        "death_pending": bool(state.get("death_pending", False)),
        "needs_replan": bool(state.get("needs_replan", False)),
        "archived": bool(state.get("archived", False)),
        "archived_reason": str(state.get("archived_reason") or ""),
        "combat_simulation": deepcopy(state.get("combat_simulation")),
        # --- Histórico ---
        "message_history": _serialize_messages(state.get("messages", [])),
    }


def save_game_state(state: dict[str, Any]) -> bool:
    """
    Salva o estado completo do jogo em JSON na pasta 'saves/'.
    Usa o 'game_id' como nome do arquivo.
    """
    _t0 = time.monotonic()
    if not state:
        return False

    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        try:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            principal = current_principal()
            game_id = uuid.UUID(str(state["game_id"]))
            store = get_runtime().game_store
            current = store.get(principal, game_id)
            if current is None:
                stored = store.create(principal, state)
            else:
                stored = store.save(principal, game_id, current.version, state)
            state["_storage_version"] = stored.version
            return True
        except Exception as e:
            _log_event(
                "persistence",
                "store_save_failed",
                level="error",
                error_type=type(e).__name__,
                game_ref=_game_ref(state.get("game_id")),
                duration_ms=_ms(_t0),
            )
            return False

    try:
        # Garante que a pasta existe
        if not os.path.exists(SAVES_DIR):
            os.makedirs(SAVES_DIR)

        # Define nome do arquivo baseado no ID.
        # Auditoria A3: game_id UUID passa pelo save_path (validação canônica);
        # legado não-UUID ("autosave", ids de teste) é SANITIZADO — nunca chega
        # cru ao filesystem (um save adulterado não escreve fora de saves/).
        game_id = state.get("game_id", DEFAULT_SAVE_NAME)
        file_path = _safe_save_path(game_id)
        save_data = _state_to_save_data(state, game_id)

        _atomic_write_json(file_path, save_data)

        return True

    except Exception as e:
        _log_event(
            "persistence",
            "save_failed",
            level="error",
            error_type=type(e).__name__,
            game_ref=_game_ref(state.get("game_id")),
            duration_ms=_ms(_t0),
        )
        return False


def load_game_state(specific_file: str = None) -> dict[str, Any]:
    """
    Carrega o jogo. Se specific_file não for passado, carrega o mais recente.
    """
    _t0 = time.monotonic()
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        try:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            principal = current_principal()
            store = get_runtime().game_store
            stored = None
            if specific_file:
                raw_id = os.path.basename(str(specific_file)).removesuffix(".json")
                stored = store.get(principal, uuid.UUID(raw_id))
            else:
                games = store.list(principal)
                stored = games[0] if games else None
            if stored is None:
                return None
            state = stored.state
            state["_storage_version"] = stored.version
            if get_runtime().resources:
                from infrastructure.pgvector_memory import PgVectorMemoryStore
                from services.chronicle_repository import ChronicleRepository

                memory = get_runtime().memory_store
                if isinstance(memory, PgVectorMemoryStore):
                    state = ChronicleRepository(
                        get_runtime().resources[0],
                        memory,
                    ).overlay(principal, state)
                    state["_storage_version"] = stored.version
            return state
        except IncompatibleSaveError:
            raise
        except Exception as e:
            _log_event(
                "persistence",
                "store_load_failed",
                level="warning",
                error_type=type(e).__name__,
                game_ref=_game_ref(
                    specific_file and os.path.basename(str(specific_file)).removesuffix(".json")
                ),
                duration_ms=_ms(_t0),
            )
            return None

    target_file = specific_file

    if not target_file:
        target_file = get_latest_save_file()

    if not target_file or not os.path.exists(target_file):
        return None

    try:
        with open(target_file, encoding="utf-8") as f:
            raw_data = json.load(f)
        return _raw_to_state(raw_data)

    except IncompatibleSaveError:
        raise
    except Exception as e:
        _log_event(
            "persistence",
            "load_failed",
            level="warning",
            error_type=type(e).__name__,
            game_ref=_game_ref(
                target_file and os.path.basename(str(target_file)).removesuffix(".json")
            ),
            duration_ms=_ms(_t0),
        )
        return None


_LEGACY_ID_KEY = re.compile(r"(?:^|_)ids?$")
_INSTANCE_SUFFIX = re.compile(r"\s+\d+$")


def _legacy_archetype(name: str) -> str:
    """Chave do bestiário com o mesmo nome (sem sufixo de instância) ou o próprio
    nome — o fallback que `bestiary_knowledge._archetype_id` já usava."""
    import gamedata

    base = _INSTANCE_SUFFIX.sub("", name).strip()
    for key, entry in (gamedata.BESTIARY or {}).items():
        if isinstance(entry, dict) and str(entry.get("name") or "") == base:
            return str(key)
    return name


def _rewrite_refs(value: Any, renames: dict[str, str], key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            renames.get(k, k) if isinstance(k, str) else k: _rewrite_refs(v, renames, k)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [
            renames.get(v, v) if isinstance(v, str) else _rewrite_refs(v, renames, key)
            for v in value
        ]
    if isinstance(value, str) and key and _LEGACY_ID_KEY.search(key):
        return renames.get(value, value)
    return value


def backfill_enemy_ids(raw: dict[str, Any]) -> dict[str, Any]:
    """SPEC-294 R4/R5: inimigo sem `id` (save legado) ganha id opaco e estável
    `enemy_legacy_<n>` — sem o nome canônico, que vazaria a fação oculta em
    `enemies[].id`/`valid_targets`. As referências do combate em curso que usavam o
    nome como id de participante passam ao novo id. Puro e idempotente: sem inimigo
    sem id, devolve `raw` (mesmo objeto)."""
    enemies = raw.get("enemies")
    if not isinstance(enemies, list) or not any(
        isinstance(e, dict) and not e.get("id") for e in enemies
    ):
        return raw
    taken = {str(e.get("id")) for e in enemies if isinstance(e, dict) and e.get("id")}
    renames: dict[str, str] = {}
    out_enemies: list[Any] = []
    for position, enemy in enumerate(enemies, start=1):
        if not isinstance(enemy, dict) or enemy.get("id"):
            out_enemies.append(deepcopy(enemy))
            continue
        counter = position
        while f"enemy_legacy_{counter}" in taken:
            counter += 1
        new_id = f"enemy_legacy_{counter}"
        taken.add(new_id)
        fixed = deepcopy(enemy)
        fixed["id"] = new_id
        name = str(enemy.get("name") or "")
        if name:
            renames.setdefault(name, new_id)
            fixed.setdefault("archetype_id", _legacy_archetype(name))
        out_enemies.append(fixed)
    migrated = dict(raw)
    migrated["enemies"] = out_enemies
    if renames and isinstance(raw.get("combat"), dict):
        migrated["combat"] = _rewrite_refs(raw["combat"], renames)
    return migrated


def _normalize_combat_on_load(raw_data: dict[str, Any]) -> dict[str, Any]:
    combat = raw_data.get("combat") or {}
    if not combat:
        return {}
    try:
        from services.encounter_manifest import normalize_combat

        return normalize_combat(
            combat, raw_data.get("enemies") or [], game_id=str(raw_data.get("game_id") or "game")
        )
    except Exception as exc:  # nunca derruba o load
        _log_event(
            "persistence", "combat_normalize_failed", level="warning", error=type(exc).__name__
        )
        return combat


def _raw_to_state(raw_data: dict[str, Any]) -> dict[str, Any]:
    """Reconstrói o GameState a partir do dict salvo (fonte única — save vivo E
    checkpoint reusam). Aplica o pipeline de migrations."""
    # Fase 10: pipeline de migrations (consolida os backfills 3.1/4.1/4.3/4.5)
    raw_data = migrate_state(raw_data)
    raw_data = backfill_enemy_ids(raw_data)  # SPEC-294: antes do manifesto/combate
    state = {
        # --- Recupera Memória ---
        "game_id": raw_data.get("game_id", "recovered_session"),
        "processed_action_ids": list(raw_data.get("processed_action_ids", []) or [])[-64:],
        "visual_seen_entity_ids": list(raw_data.get("visual_seen_entity_ids", []) or [])[-64:],
        "visual_cue_ledger": deepcopy(list(raw_data.get("visual_cue_ledger", []) or [])[-64:]),
        "narrative_summary": compact_summary(raw_data.get("narrative_summary", "")),
        "archivist_last_run": raw_data.get("archivist_last_run", 0),
        "archive_due": bool(raw_data.get("archive_due", False)),
        "chronicle": raw_data.get("chronicle", []),
        "consumed_conflict_ids": normalize_consumed_conflict_ids(
            raw_data.get("consumed_conflict_ids")
        ),
        "memory_fact_policy": raw_data.get("memory_fact_policy"),
        "memory_canonical_facts": raw_data.get("memory_canonical_facts", []),
        "memory_facts": normalize_memory_facts(raw_data.get("memory_facts")),
        "pending_memory_facts": normalize_memory_facts(
            raw_data.get("pending_memory_facts"),
            pending=True,
        ),
        "presentation_history": list(raw_data.get("presentation_history") or []),
        # SPEC-207 (aditivo, sem bump): save antigo sem a chave → [].
        "audit_trace": normalize_audit_trace(raw_data.get("audit_trace")),
        "art_generation_ledger": deepcopy(raw_data.get("art_generation_ledger") or []),
        "art_arc_budgets": deepcopy(raw_data.get("art_arc_budgets") or {}),
        "art_offers": deepcopy(raw_data.get("art_offers") or []),
        "evidence_rejections": list(raw_data.get("evidence_rejections") or [])[-64:],
        "memory_rejections": bounded_audit_rows(
            raw_data.get("memory_rejections"),
            limit=MAX_MEMORY_REJECTIONS,
        ),
        "memory_promotions": bounded_audit_rows(
            raw_data.get("memory_promotions"),
            limit=MAX_MEMORY_PROMOTIONS,
        ),
        "rejected_item_claims": normalize_rejected_item_claims(
            raw_data.get("rejected_item_claims")
        ),
        "pending_npc_memory": normalize_pending_npc_memory(raw_data.get("pending_npc_memory")),
        "rag_persistence_error": raw_data.get("rag_persistence_error"),
        "continuity": deepcopy(raw_data.get("continuity") or {}),
        "last_turn_outcome": deepcopy(raw_data.get("last_turn_outcome") or {}),
        # SPEC-215 (aditivo, sem bump): save sem ledger → vazio + legacy_knowledge.
        **_knowledge(raw_data, legacy_default=True),
        # SPEC-202 (aditivo, sem bump): save antigo/sem dict → {} (= narrador).
        "last_speaker": (
            deepcopy(raw_data["last_speaker"])
            if isinstance(raw_data.get("last_speaker"), dict)
            else {}
        ),
        "last_interaction_outcome": deepcopy(raw_data.get("last_interaction_outcome") or {}),
        # --- Recupera Core ---
        "player": raw_data.get("player", {}),
        "world": raw_data.get("world", {}),
        "party": raw_data.get("party", []),
        "enemies": raw_data.get("enemies", []),
        "factions": raw_data.get("factions", []),
        "faction_intel": raw_data.get("faction_intel", {}),
        "bestiary_knowledge": raw_data.get("bestiary_knowledge", {}),
        "npcs": coalesce_runtime_npcs(raw_data.get("npcs", {})),
        "inventory": raw_data.get("inventory", []),
        "quests": raw_data.get("quests", []),
        "campaign_plan": raw_data.get("campaign_plan", {}),
        # --- Fase 2.5: eventos estruturados + projeção do mundo ---
        "event_log": raw_data.get("event_log", []),
        "world_projection": raw_data.get("world_projection", {}),
        "pending_world_events": raw_data.get("pending_world_events", []),
        "event_rejections": raw_data.get("event_rejections", []),
        # --- Recupera Transicionais ---
        "combat_target": raw_data.get("combat_target"),
        "loot_source": raw_data.get("loot_source"),
        # SPEC-203: normalização ADITIVA e idempotente (sem bump de schema):
        # combate ativo legado ganha manifesto `legacy_migrated`; sem combate
        # ativo ganha phase=ended/outcome preservado.
        "combat": _normalize_combat_on_load(raw_data),
        "conflict_summary": raw_data.get("conflict_summary"),
        # --- Recupera Mensagens ---
        "messages": _deserialize_messages(raw_data.get("message_history", [])),
        # Fase 4.6: memorial
        "game_over": bool(raw_data.get("game_over", False)),
        # spec checkpoints-morte: tela de morte pendente
        "death_pending": bool(raw_data.get("death_pending", False)),
        "combat_simulation": deepcopy(raw_data.get("combat_simulation")),
        # spec conflito-01 R10: save pré-Virtudes marcado pela migração v3→v4
        "archived": bool(raw_data.get("archived", False)),
        "archived_reason": raw_data.get("archived_reason", ""),
        # Garante campos técnicos de fluxo
        "next": "storyteller",
        "needs_replan": bool(raw_data.get("needs_replan", False)),
    }
    # Saves produzidos antes do protocolo de transição podiam persistir uma
    # Última Ação/Estado Terminal sem combate ou tela de morte capaz de
    # resolvê-los. Repara somente essa combinação órfã; combate e death_pending
    # vivos mantêm seu dono normal.
    player = state.get("player") or {}
    if (
        not (state.get("combat") or {}).get("active")
        and not state.get("death_pending")
        and not state.get("game_over")
        and (player.get("last_stand_pending") or player.get("estado_terminal"))
    ):
        from services.actor_lifecycle import sanitize_interturn_state

        state = sanitize_interturn_state(state)
        state["needs_replan"] = True
    # SPEC-213 (aditivo, sem bump): save v8 sem a chave nasce `completed` em
    # canonical_version = continuity.session_action_count (R16).
    state["projection_state"] = _projection_state(raw_data.get("projection_state"), state)
    state["pending_derived"] = _projection_plan(raw_data.get("pending_derived"))
    # SPEC-227 R12: equipamento sem posse (venda antiga) é reconciliado no load,
    # idempotente e sem tocar no ouro. Sem bump de schema (D-C default).
    try:
        from inventory import reconcile_equipment

        player = state.get("player")
        inventory_ok = all(isinstance(e, dict) for e in (player or {}).get("inventory") or [])
        if isinstance(player, dict) and isinstance(player.get("equipment"), dict) and inventory_ok:
            state["player"], _ = reconcile_equipment(player)
    except Exception:  # pragma: no cover - nunca quebrar o load por isso
        pass
    return state


# --- spec checkpoints-morte: slot de checkpoint (1 por save, sobrescreve) -----


def _log_checkpoint_written(state: dict[str, Any], t0: float) -> None:
    _log_event(
        "persistence",
        "checkpoint_written",
        level="info",
        game_ref=_game_ref(state.get("game_id")),
        turn=int((state.get("world") or {}).get("turn_count", 0) or 0),
        duration_ms=_ms(t0),
    )


def save_checkpoint(state: dict[str, Any]) -> bool:
    """Grava o snapshot restaurável em `saves/{game_id}.checkpoint.json` (D5: 1
    slot, sobrescreve). Mesmo formato do save vivo — reusa `_state_to_save_data`."""
    _t0 = time.monotonic()
    if not state:
        return False
    from services.actor_lifecycle import transition_readiness

    if not transition_readiness(state)["ready"]:
        return False
    state = deepcopy(state)
    from services.continuity import mark_checkpoint

    state["continuity"] = mark_checkpoint(
        state.get("continuity"),
        canonical_turn=int((state.get("world") or {}).get("turn_count", 0) or 0),
    )
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        try:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            principal = current_principal()
            store = get_runtime().game_store
            stored = store.get(principal, uuid.UUID(str(state["game_id"])))
            if stored is None or not hasattr(store, "save_checkpoint"):
                return False
            store.save_checkpoint(principal, stored, state)
            _log_checkpoint_written(state, _t0)
            return True
        except Exception as e:
            _log_event(
                "persistence",
                "store_checkpoint_failed",
                level="error",
                error_type=type(e).__name__,
                game_ref=_game_ref(state.get("game_id")),
                duration_ms=_ms(_t0),
            )
            return False
    memory_backup: str | None = None
    memory_destination: str | None = None
    memory_existed = False
    try:
        if not os.path.exists(SAVES_DIR):
            os.makedirs(SAVES_DIR)
        game_id = state.get("game_id", DEFAULT_SAVE_NAME)
        path = _safe_save_path(game_id, suffix=".checkpoint")
        memory_destination = checkpoint_memory_path(game_id)
        memory_existed = os.path.isdir(memory_destination)
        if memory_existed:
            memory_backup = tempfile.mkdtemp(
                prefix=f".{game_id}.checkpoint-memory-rollback.",
                dir=os.path.dirname(os.path.abspath(memory_destination)),
            )
            shutil.copytree(memory_destination, memory_backup, dirs_exist_ok=True)
        save_checkpoint_memory(game_id)
        _atomic_write_json(path, _state_to_save_data(state, game_id))
        if memory_backup:
            shutil.rmtree(memory_backup, ignore_errors=True)
        _log_checkpoint_written(state, _t0)
        return True
    except Exception as e:
        if memory_destination:
            shutil.rmtree(memory_destination, ignore_errors=True)
            if memory_existed and memory_backup and os.path.isdir(memory_backup):
                _replace_with_retry(memory_backup, memory_destination)
        if memory_backup:
            shutil.rmtree(memory_backup, ignore_errors=True)
        _log_event(
            "persistence",
            "checkpoint_write_failed",
            level="error",
            error_type=type(e).__name__,
            game_ref=_game_ref(state.get("game_id")),
            duration_ms=_ms(_t0),
        )
        return False


def has_checkpoint(game_id: str) -> bool:
    """True só se o slot existe E é um save legível (SPEC-228 R1)."""
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        return load_checkpoint(game_id) is not None
    path = _safe_save_path(game_id, suffix=".checkpoint")
    if not os.path.exists(path):
        return False
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return False
    return isinstance(raw, dict) and "schema_version" in raw and isinstance(raw.get("player"), dict)


def checkpoint_turn(game_id: str) -> int | None:
    """Turno canônico do checkpoint REAL em disco (None se ausente/ilegível)."""
    cp = load_checkpoint(game_id)
    if not cp:
        return None
    return int((cp.get("world") or {}).get("turn_count", 0) or 0)


def ensure_synthetic_checkpoint(state: dict[str, Any]) -> bool:
    """SPEC-228 R4: save sem checkpoint válido ganha um checkpoint sintético do
    estado atual, marcado `synthetic_from_turn`. Retorna se gravou."""
    if (
        not state
        or not state.get("game_id")
        or state.get("archived")
        or state.get("game_over")
        or state.get("death_pending")
    ):
        return False
    if (state.get("combat_simulation") or {}).get("enabled"):
        return False
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        return False
    gid = str(state["game_id"])
    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    if has_checkpoint(gid):
        # SPEC-228 §7: crash entre gravar o checkpoint e gravar o save deixa o
        # slot um turno À FRENTE do save (linha do tempo abortada, com o
        # action_id já processado). Esse slot é descartado e substituído por
        # um sintético do save real.
        cp_turn = checkpoint_turn(gid)
        if cp_turn is None or cp_turn <= turn:
            return False
        _log_event(
            "persistence",
            "checkpoint_ahead_discarded",
            level="warning",
            checkpoint_turn=cp_turn,
            turn=turn,
        )
    snap = deepcopy(state)
    cont = dict(snap.get("continuity") or {})
    cont["synthetic_from_turn"] = turn
    snap["continuity"] = cont
    return save_checkpoint(snap)


def load_checkpoint(game_id: str) -> dict[str, Any] | None:
    """Carrega o checkpoint do `game_id` (None se não houver). Reconstrói via
    `_raw_to_state` (mesmo pipeline de migrations do save vivo)."""
    _t0 = time.monotonic()
    if os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() != "legacy":
        try:
            from infrastructure.request_context import current_principal
            from infrastructure.runtime import get_runtime

            principal = current_principal()
            store = get_runtime().game_store
            if not hasattr(store, "get_checkpoint"):
                return None
            return store.get_checkpoint(principal, uuid.UUID(str(game_id)))
        except Exception as e:
            _log_event(
                "persistence",
                "store_checkpoint_load_failed",
                level="warning",
                error_type=type(e).__name__,
                game_ref=_game_ref(game_id),
                duration_ms=_ms(_t0),
            )
            return None
    path = _safe_save_path(game_id, suffix=".checkpoint")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return _raw_to_state(json.load(f))
    except Exception as e:
        _log_event(
            "persistence",
            "checkpoint_load_failed",
            level="warning",
            error_type=type(e).__name__,
            game_ref=_game_ref(game_id),
            duration_ms=_ms(_t0),
        )
        return None
