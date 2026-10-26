"""
agents/npc.py
Gerador de NPCs com Persistência, Memória, RAG e Filtro de Ignorância.
Contém tanto a fábrica de NPCs (generate_new_npc) quanto o ator (npc_actor_node).
"""

import inspect
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services import graph_resolver as gr
from services import latency_flags, quest_log
from services.ambient import ambient_block
from services.context_builder import build_context_pack
from services.input_normalization import optional_entity_ref
from services.lore_query import compose_lore_query
from services.memory_provenance import (
    MAX_MEMORY_PROMOTIONS,
    bounded_audit_rows,
    commit_memory_facts,
    make_memory_fact,
    memory_metadata,
    normalize_memory_facts,
)
from services.memory_retry import (
    enqueue_npc_memory,
    normalize_pending_npc_memory,
)
from services.perceived_world import perceived_world_block
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages
from services.prompt_layout import compose as compose_prompt
from services.prose_guard import (
    log_if_repeats,
    openings_clause,
    sanitize_meta_preamble,
    semantic_opening,
    strip_outer_quotes,
    vary_repeated_opening,
)
from services.structured_outputs import CrimeClaim, ProposedQuest, coerce_crime_claims
from state import GameState
from world_utils import apply_faction_reveal, ensure_faction_intel, ensure_factions

# Fallback para RAG
try:
    from rag import add_npc_memory, query_npc_memory, query_rag

    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

    def query_rag(*args, **kwargs):
        return ""

    def add_npc_memory(*args, **kwargs):
        return None

    def query_npc_memory(*args, **kwargs):
        return ""


# SPEC-215: texto do `world_state_block`. `off`/`shadow` mantêm o texto anterior
# byte a byte; `on` fala só do que o personagem sabe (R6).
_WORLD_TRUTH_NOTE_OFF = (
    "(O mundo mudou desde que você o conheceu? O estado atual acima é a verdade de AGORA.)"
)
_WORLD_TRUTH_NOTE_ON = (
    "(Acima está SÓ o que você sabe do mundo: [VIU] = você presenciou; [OUVIU DE …] = "
    "contaram e você acredita; [BOATO, não confirmado] = ouviu dizer, pode ser mentira. "
    "Se não está aqui nem na sua memória, você não sabe.)"
)


def _npc_id(npc_data: dict, name: str) -> str:
    """id estável do NPC para namespacing da memória vetorial."""
    return npc_data.get("id") or f"npc_{(name or 'desconhecido').lower().replace(' ', '_')}"


def _interaction_outcome(
    state: dict, *, kind: str, subject_id: str, code: str, progressed: bool
) -> dict:
    fingerprint = f"{kind}:{subject_id}:{code}"
    previous = state.get("last_interaction_outcome") or {}
    repeat = (
        int(previous.get("repeat_count", 0) or 0) + 1
        if previous.get("fingerprint") == fingerprint and not progressed
        else 1
    )
    return {
        "kind": kind,
        "subject_id": subject_id,
        "code": code,
        "progressed": progressed,
        "fingerprint": fingerprint,
        "repeat_count": repeat,
        "turn": int((state.get("world") or {}).get("turn_count", 0) or 0),
    }


def _canonical_npc_id(name: str) -> str:
    """Id canônico (entities.json, type npc) por match de nome — "" se não achar.

    Fase 3.3: habilita falha sistêmica de quest (origin_entity_id) só para NPCs do
    grafo canônico — NPC gerado em runtime não tem id aqui (mesma restrição de
    `_v_npc_killed`, que só aceita npc_killed contra ids canônicos).
    """
    from services.entity_identity import resolve_npc_entity_id

    return resolve_npc_entity_id({}, name) or ""


# Importa Librarian para verificar duplicatas
try:
    from agents.librarian import find_existing_entity
except ImportError:

    def find_existing_entity(*args, **kwargs):
        return None


NPC_DB_FILE = "data/npc_database.json"


# --- SCHEMAS ---
class NPCSchema(BaseModel):
    name: str
    role: str
    location: str
    persona: str
    appearance: str
    initial_relationship: int = 5  # ignorado pelo motor (SPEC-298 R8: relação inicial é Python)
    race_id: str = ""  # SPEC-298 R6: id de data/origins.json; inválido -> "" (neutro)
    attributes: dict[str, int] = Field(
        description="Stats base: str, dex, con, int, wis, cha. Padrão humano é 10.",
        json_schema_extra={
            "example": {"str": 10, "dex": 12, "con": 10, "int": 14, "wis": 16, "cha": 18}
        },
    )
    combat_stats: dict = Field(
        description="HP, AC e Attacks", default={"hp": 10, "ac": 10, "attacks": []}
    )
    legend: str = Field(
        default="",
        description="SPEC-297: 'o que se diz dele' em <=160 chars (só com o pool ligado).",
    )


def _valid_race_id(value: object) -> str:
    from services.reputation import VALID_RACES

    return value if isinstance(value, str) and value in VALID_RACES else ""


class FactionReveal(BaseModel):
    faction_id: str = Field(
        description=(
            "id EXATO que aparece em <FACÇÕES_DO_MUNDO> (inclui 'sua_irmandade'); "
            "facção fora da lista = vazio."
        )
    )
    reveal_level: str = Field(
        description="O QUANTO este NPC revelou: 'existencia' (citou a facção), "
        "'objetivo' (contou o plano) ou 'progresso' (sabe quão perto está)."
    )


class MembershipAction(BaseModel):
    """SPEC-301 R20: o recrutador só PROPÕE; Python valida requisito/limite/local."""

    action: str = Field(
        default="",
        description="'join' | 'leave' | 'ask_mission'; vazio se o jogador não pediu isso.",
    )
    faction_id: str = Field(
        default="",
        description=(
            "id EXATO que aparece em <FACÇÕES_DO_MUNDO> (inclui 'sua_irmandade'); "
            "facção fora da lista = vazio."
        ),
    )


RELATIONSHIP_STEP_CAP = 1  # SPEC-230 R7 (D-A default ±1 por turno); SPEC-223 R4 reusa


class NPCResponse(BaseModel):
    dialogue: str
    action_description: str
    memory_update: str
    # SPEC-223 R4: teto por turno no PRÓPRIO schema (fonte única = SPEC-230).
    # A truncagem roda antes da validação: valor fora da faixa nunca derruba a
    # resposta inteira (padrão SPEC-045), só é clampado.
    relationship_change: int = Field(
        0,
        ge=-RELATIONSHIP_STEP_CAP,
        le=RELATIONSHIP_STEP_CAP,
        description="Variação da relação NESTE turno: -1, 0 ou +1.",
    )

    @field_validator("relationship_change", mode="before")
    @classmethod
    def _clamp_relationship(cls, value):
        return clamp_relationship_change(value)

    faction_reveals: list[FactionReveal] = Field(
        default_factory=list,
        description=(
            "Facções sobre as quais ESTE NPC contou algo ao jogador NESTE turno. "
            "Só preencha se o personagem plausivelmente saberia (ocupação/local) E o papo levou a isso. "
            "Vazio caso contrário. Use o faction_id EXATO da lista."
        ),
    )
    membership_action: MembershipAction | None = Field(
        default=None,
        description=(
            "SOMENTE se o jogador pediu EXPLICITAMENTE a você, neste turno, para entrar "
            "numa fação, sair dela ou pedir uma missão a ela. faction_id EXATO que aparece em "
            "<FACÇÕES_DO_MUNDO> (inclui 'sua_irmandade'); fora da lista = vazio. "
            "Na dúvida, vazio: o motor decide se é possível."
        ),
    )
    proposed_quests: list[ProposedQuest] = Field(
        default_factory=list,
        description=(
            "APENAS se você (o NPC) pediu algo CONCRETO ao jogador NESTE turno (uma "
            "tarefa, um recado, um favor com objetivo claro). title/description curtos, "
            "location_id só se o destino é claro. Vazio caso contrário — não invente "
            "missão de um papo qualquer."
        ),
    )
    crime_claims: list[CrimeClaim] = Field(
        default_factory=list,
        description=(
            "Crimes que a AÇÃO do jogador cometeu CONTRA você ou diante de você NESTE turno "
            "(furto, agressao, homicidio, dano_propriedade, magia_ilegal). Vazio se não houve "
            "crime — na dúvida, vazio."
        ),
    )

    @field_validator("crime_claims", mode="before")
    @classmethod
    def _drop_invalid_crimes(cls, v: object) -> list:
        return coerce_crime_claims(v)


# --- PERSISTÊNCIA (spec isolar-cache-runtime) -------------------------------
# O cache de NPCs gerados mora no overlay runtime gitignored; o arquivo antigo
# data/npc_database.json vira LEGADO (fallback de leitura até o 1º save, que
# migra o conteúdo inteiro pro overlay).


def _npc_db_path() -> str:
    from gamedata import runtime_cache_path

    return runtime_cache_path("npc_database.json")


def clamp_relationship_change(delta, who: str = "") -> int:
    """Relação é mecânica Python: o LLM propõe, o teto por turno decide."""
    try:
        delta = int(delta or 0)
    except (TypeError, ValueError):
        return 0
    clamped = max(-RELATIONSHIP_STEP_CAP, min(RELATIONSHIP_STEP_CAP, delta))
    if clamped != delta:
        logging.getLogger("rpg.npc.relationship_clamped").info(
            "npc=%s proposed=%s applied=%s", who, delta, clamped
        )
    return clamped


def _npc_entry_broken(entry) -> bool:
    return (
        not isinstance(entry, dict)
        or entry.get("id") == "fallback"
        or ("role" in entry and not entry["role"])
        or ("persona" in entry and not entry["persona"])
    )


def _own_pool_npcs(game_id: str) -> dict:
    """SPEC-297 R10/R25: NPCs criados por ESTE jogo (hold/local/promovido). Nunca de outro."""
    from services import shared_pool
    from services.shared_pool_models import PoolNamespace

    out: dict = {}
    try:
        for entry in shared_pool.own_entries(PoolNamespace.NPC, game_id=game_id, limit=200):
            doc = dict(entry.document)
            out[str(doc.get("id") or entry.entry_id)] = {**doc, "pool_entry_id": entry.entry_id}
    except Exception as exc:
        _log_event("npc", "pool_own_read_failed", level="warning", error=type(exc).__name__)
    return out


def _pool_flag_on() -> bool:
    from services.shared_pool import enabled

    return enabled()


def _npc_db_for_game(game_id: str):
    from services.shared_pool import enabled

    return load_npc_db(game_id) if enabled() and game_id else load_npc_db()


def load_npc_db(game_id: str = ""):
    """SPEC-230: descarta (com log) entradas quebradas já persistidas."""
    raw = _load_npc_db_raw()
    if game_id:
        from services.shared_pool import enabled as _pool_enabled

        if _pool_enabled():
            raw = {**raw, **_own_pool_npcs(game_id)}
    clean = {k: v for k, v in raw.items() if not _npc_entry_broken(v)}
    if len(clean) != len(raw):
        logging.getLogger("rpg.npc").warning(
            "npc_database: %d entrada(s) quebrada(s) descartada(s): %s",
            len(raw) - len(clean),
            sorted(set(raw) - set(clean)),
        )
    return clean


def catalog_owner_id():
    """SPEC-223 R7 (D-B default: por owner). Dono do catálogo gerado em runtime.

    Perfis com principal (DB/hosted): o usuário da request. Legado/CLI sem
    principal: ``None`` → catálogo global local (comportamento histórico)."""
    try:
        from infrastructure.request_context import current_principal

        principal = current_principal(required=False)
    except Exception:  # silent-ok: sem principal e o caso esperado em legacy/CLI
        principal = None
    return getattr(principal, "user_id", None)


def _load_legacy_npc_file() -> dict:
    if not os.path.exists(NPC_DB_FILE):
        return {}
    try:
        from services.file_cache import read_json_cached

        return read_json_cached(NPC_DB_FILE)
    except Exception as e:
        _log_event("npc", "db_read_failed", level="warning", error=type(e).__name__)
        return {}


def _load_npc_db_raw():
    from infrastructure.runtime import get_runtime

    store = get_runtime().runtime_catalog
    shared = store.list("npc_template", owner_id=None, game_id=None) or _load_legacy_npc_file()
    owner = catalog_owner_id()
    if owner is None:
        return shared
    # Global (curado/legado) é read-only e VENCE conflito de id; o gerado do
    # próprio dono complementa — nunca o de outro tenant.
    own = store.list("npc_template", owner_id=owner, game_id=None)
    return {**own, **shared}


def save_npc_template(data):
    """SPEC-223 R7: grava SÓ o template novo (1 put), no escopo do dono."""
    from infrastructure.runtime import get_runtime

    key = data.get("id", f"npc_{data['name'].lower().replace(' ', '_')}")
    if "id" not in data:
        data["id"] = key

    # Garante atributos mínimos
    if "attributes" not in data:
        data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

    store = get_runtime().runtime_catalog
    owner = catalog_owner_id()
    if owner is not None:
        store.put("npc_template", key, data, scope="user", owner_id=owner, game_id=None)
        return
    # Legado local: 1º save migra o arquivo antigo para o overlay (uma vez só).
    if not store.list("npc_template", owner_id=None, game_id=None):
        for item_id, item in _load_legacy_npc_file().items():
            if item_id != key and not _npc_entry_broken(item):
                store.put(
                    "npc_template", item_id, item, scope="global", owner_id=None, game_id=None
                )
    store.put("npc_template", key, data, scope="global", owner_id=None, game_id=None)


_NPC_V4_FIELDS = (
    "virtudes",
    "vitalidade",
    "max_vitalidade",
    "ferimento_espacos",
    "ferimentos",
    "esquiva",
    "tactical_profile",
)


def _has_complete_npc_combat_sheet(data: dict) -> bool:
    if not all(field in data and data[field] is not None for field in _NPC_V4_FIELDS):
        return False
    profile = data.get("tactical_profile")
    return isinstance(profile, dict) and bool(profile.get("priorities"))


def _materialize_npc_combat_sheet(data: dict) -> dict:
    """Normaliza cache legado/geração nova sem resetar uma ficha v4 viva."""
    if _has_complete_npc_combat_sheet(data):
        return data

    from services.encounter_preparation import build_npc_combat_sheet

    sheet = build_npc_combat_sheet(data)
    normalized = {**data, **sheet}
    # Compatibilidade com consumidores legados: os números vêm da ficha v4
    # determinística; `combat_stats` proposto pela LLM nunca atravessa a borda.
    normalized["combat_stats"] = {
        "hp": normalized["max_vitalidade"],
        "ac": normalized["esquiva"],
        "attacks": [],
    }
    return normalized


def _infer_tier_from_name(name: str) -> ModelTier:
    """SPEC-223 R7 (D-C): o NOME (texto do jogador) não escala custo — tier fixo
    FAST. SMART só por decisão do motor (ex.: Nomeado curado), nunca por palavra."""
    del name
    return ModelTier.FAST


# --- FÁBRICA DE NPCs (A FUNÇÃO QUE FALTAVA) ---
_POOL_DOC_KEYS = (
    "id",
    "name",
    "role",
    "persona",
    "appearance",
    "attributes",
    "initial_relationship",
    "race_id",
    "origin_region_id",
    "faction_id",
    "profession_id",
    "legend",
)


def _pool_generation_prompt(name: str, context: str, lore_info: str, labels: dict) -> str:
    """SPEC-297 R7: semente + nome sanitizado + local + lore pública. SEM a cena narrada."""
    seed_lines = "\n".join(f"- {k}: {v}" for k, v in labels.items() if v)
    return f"""
            <role>RPG Character Designer</role>
            <lore>{lore_info}</lore>
            <semente>
            {seed_lines}
            </semente>
            <task>Create NPC '{name}' honoring EVERY item of <semente> (do not contradict
            it). Include all 6 attributes, a detailed persona and appearance. Also fill
            'legend': one sentence (max 160 chars) of what rumor says about them, derived
            from their desire and epithet.</task>
            """


def generate_new_npc(
    name,
    context="",
    *,
    game_id="",
    location_id="",
    name_origin="narrator",
    turn=0,
    player_inputs=(),
):
    """
    Gera um novo NPC do zero usando IA ou recupera do cache se já existir.
    Usado pelo Storyteller para popular o mundo dinamicamente.

    SPEC-297: com `RPG_SHARED_POOL` != off (e `game_id`), o motor sorteia uma semente,
    o prompt NÃO recebe a cena e o resultado é submetido ao pool em hold (em vez de
    gravar no catálogo de runtime).
    """
    from services import shared_pool
    from services.prompt_guard import sanitize_entity_name

    pool_on = shared_pool.enabled() and bool(game_id)
    name = sanitize_entity_name(name) or "Desconhecido"  # SPEC-223 R7
    # 1. CHECK-FIRST: Verifica se já existe
    db = load_npc_db(game_id) if pool_on else load_npc_db()
    existing_ids = list(db.keys())

    found_id = find_existing_entity(name, "NPC", existing_ids)
    if found_id:
        _log_event("npc", "cache_hit", level="debug")
        data = db[found_id]
        changed = False
        if "attributes" not in data:  # Auto-fix legado
            data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
            changed = True
        normalized = _materialize_npc_combat_sheet(data)
        # SPEC-297 R13: cache-hit nunca reescreve o pool; só o catálogo legado (flag off).
        if not pool_on and (normalized is not data or changed):
            save_npc_template(normalized)
        return normalized

    # 2. GERAÇÃO
    _log_event("npc", "creating", level="info")
    seed = None
    labels: dict = {}
    if pool_on:
        from services import npc_seed
        from services.shared_pool_models import PoolNamespace

        seed = npc_seed.roll_unique_seed(
            game_id=str(game_id),
            turn=int(turn or 0),
            location_id=str(location_id or ""),
            signature_taken=lambda sig: shared_pool.signature_taken(PoolNamespace.NPC, sig),
        )
        if seed is not None:
            labels = npc_seed.seed_labels(seed)
        lore_info = query_rag(f"{name} {labels.get('local_de_origem', '')}", index_name="lore")
    else:
        lore_info = query_rag(f"{name} {context}", index_name="lore")

    llm = get_llm(temperature=0.7, tier=_infer_tier_from_name(name))

    try:
        designer = llm.with_structured_output(NPCSchema)
        if pool_on:
            system_text = _pool_generation_prompt(name, context, lore_info, labels)
            human_text = f"Local: {labels.get('local_de_origem', '')}"
        else:
            system_text = f"""
            <role>RPG Character Designer</role>
            <lore>{lore_info}</lore>
            <task>Create NPC '{name}'. Include all 6 attributes and a detailed persona.</task>
            """
            human_text = f"Context: {context}"
        res = designer.invoke(
            [SystemMessage(content=system_text), HumanMessage(content=human_text)]
        )

        if not isinstance(res, NPCSchema):  # SPEC-230 R1: FallbackLLM -> AIMessage
            raise TypeError("structured output inválido (FallbackLLM)")
        data = res.model_dump()
        # Identidade pedida pelo router é canônica. Providers (e especialmente o
        # MockLLM) podem devolver outro nome apesar do schema estar válido.
        data["name"] = name
        data["id"] = f"npc_{name.lower().replace(' ', '_')}"

    except Exception as e:
        _log_event("npc", "generation_failed", level="error", error=type(e).__name__)
        # Fallback de segurança
        data = {
            "name": name,
            "role": "Desconhecido",
            "id": "fallback",
            "persona": "Genérico",
            "initial_relationship": 5,
            "attributes": {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []},
        }

    if data.get("id") == "fallback":
        return _materialize_npc_combat_sheet(data)  # SPEC-230 R1: nunca envenena o cache/pool
    if pool_on:
        return _submit_generated_npc(data, seed, game_id, name_origin, player_inputs)
    data = _materialize_npc_combat_sheet(data)
    try:
        save_npc_template(data)
    except Exception as exc:
        _log_event("npc", "db_persist_failed", level="warning", error=type(exc).__name__)
    return data


def seed_motives_of(seed) -> dict:
    """SPEC-310 R13: ids de motivação da semente que viram campo privado da ficha runtime."""
    return {
        "desire_id": seed.desire_id,
        "fear_id": seed.fear_id,
        "secret_id": seed.secret_id,
        "contradiction_id": seed.contradiction_id,
        "mannerism_id": seed.mannerism_id,
    }


def _submit_generated_npc(data, seed, game_id, name_origin, player_inputs) -> dict:
    """SPEC-297 R9: projeta à allowlist, submete em hold e devolve a ficha LOCAL."""
    from services import shared_pool
    from services.shared_pool_models import PoolNamespace

    data = dict(data)
    data["legend"] = str(data.get("legend") or "")[:160]
    if seed is not None:
        data.update(
            race_id=seed.race_id,
            origin_region_id=seed.origin_region_id,
            faction_id=seed.faction_id,
            profession_id=seed.profession_id,
            seed_motives=seed_motives_of(seed),  # SPEC-310 R13 (só ids; fora da allowlist do pool)
        )
    doc = {k: data[k] for k in _POOL_DOC_KEYS if k in data and data[k] is not None}
    try:
        entry = shared_pool.submit(
            PoolNamespace.NPC,
            doc,
            game_id=str(game_id),
            region_id=seed.origin_region_id if seed is not None else "",
            name_origin=name_origin,
            seed=seed,
            player_inputs=list(player_inputs or ()),
        )
        data["pool_entry_id"] = entry.entry_id
    except Exception as exc:
        _log_event("npc", "pool_submit_failed", level="warning", error=type(exc).__name__)
    return _materialize_npc_combat_sheet(data)


_CHAT_BASE_KEYS = frozenset(
    {
        "messages",
        "npcs",
        "active_npc_name",
        "faction_intel",
        "archive_due",
        "memory_fact_policy",
        "pending_npc_memory",
        "rag_persistence_error",
        "memory_facts",
        "memory_promotions",
        "companion_voice_ack",
        "social_intent",
    }
)

_MISSION_RE = re.compile(
    r"miss|objetiv|quest|o que.*(faç|faz|devo)|para onde|pr[óo]ximo passo|tarefa|rumo"
)


def _npc_self_prompt(state, npc_key, npc_data, npc_id, evidence_ids) -> str:
    """SPEC-310: blocos `<SOBRE_VOCE>`/`<MOTIVACOES_INTERNAS>`/`<O_QUE_VOCE_SABE>` (vazio = sem linha)."""
    from services import npc_self

    try:
        return npc_self.npc_self_blocks(
            state, str(npc_key), npc_data, pack_evidence_ids=evidence_ids, knowledge_id=npc_id
        ).text()
    except Exception as exc:  # defesa extra; o módulo já protege a si mesmo
        from observability.telemetry import log_fallback

        log_fallback("npc", "self_block_failed", exc)
        return ""


def _own_faction(state, npc_key, npc_data) -> str:
    """SPEC-314 R13: fação do próprio NPC (exceção do lore redigido). Falha = ''."""
    try:
        from services import npc_self

        return npc_self.self_faction(state, str(npc_key), npc_data)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("npc", "own_faction_failed", exc)
        return ""


def _lore_menu(state, npc_key: str) -> tuple[str, list]:
    """SPEC-313 R11: `<GANCHOS_POSSIVEIS>` (vazio sem nada elegivel). Nunca derruba o turno."""
    try:
        from services import lore_quests

        return lore_quests.anchor_menu(state, npc_key)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("npc", "lore_menu_failed", exc)
        return "", []


def _apply_lore_proposals(
    state, quests: list, pending: list, npc_key: str, menu: list, canonical_id: str, turn: int
) -> tuple[list, dict]:
    """SPEC-313 R6/R7/R9: propostas ancoradas do NPC em cena viram quest do MOTOR (ou, com
    ancora invalida, quest comum). Devolve `(quests, updates_extras)`. Nunca levanta."""
    from services import lore_quests, npc_world, world_quests

    extras: dict = {}
    wturn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    mission_now = any(
        q.get("faction_id")
        and int(q.get("created_turn", -1) or -1) == wturn
        and q.get("status") == "active"
        for q in quests
    )
    day = int(((state.get("world") or {}).get("world_clock") or {}).get("day", 1) or 1)
    for p in pending:
        if mission_now:  # R9: a missao de facção do mesmo turno ja ocupa a oferta
            lore_quests._log("ignored", kind=str(p.get("kind")), reason="faction_mission_same_turn")
            continue
        view = {**state, "quests": quests, **extras}
        try:
            new_quests, created, reason = world_quests.offer_from_proposal(
                view, p, npc_key, menu, day, origin_entity_id=canonical_id
            )
        except Exception as exc:  # silent-ok: ancora falha = quest comum (comportamento antigo)
            from observability.telemetry import log_fallback

            log_fallback("npc", "lore_offer_failed", exc)
            new_quests, created, reason = quests, None, "invalid_anchor"
        if created is not None:
            quests = new_quests
            if created.get("world_kind") == "escoltar":
                anchor = created.get("lore_anchor") or {}
                sim = npc_world.escort_start(
                    view, str(anchor.get("id")), created["id"], str(anchor.get("to")), day
                )
                extras[npc_world.sim_key()] = sim
        elif reason in lore_quests.DOWNGRADE_REASONS:
            quests, _c = quest_log.register_proposed_quests(quests, [p], turn=turn)
    return quests, extras


def _commerce_block(state, npc_data) -> str:
    """SPEC-311 R15: `<SEU_COMERCIO>` do keeper presente no próprio mercado ('' sem motivo).

    Direção geral + motivos qualitativos de `economy.price_reasons`; nunca números."""
    try:
        keeper_of = str((npc_data or {}).get("keeper_of") or "")
        if not keeper_of:
            return ""
        from services import economy

        merchant = economy.MERCHANTS.get(keeper_of)
        here = str(((state or {}).get("world") or {}).get("current_location_id") or "")
        if not merchant or merchant.get("location_id") != here:
            return ""
        reasons = economy.price_reasons(
            state, mode="buy", item_id=None, merchant=merchant, exclude=("relacao",)
        )  # a relação já vem no <ATITUDE> (SPEC-298)
        if not reasons:
            return ""
        direction = economy.market_direction(state, merchant)
        lines = ["<SEU_COMERCIO>"]
        if direction == "alta":
            lines.append("Seus preços hoje estão mais altos que o normal.")
        elif direction == "baixa":
            lines.append("Seus preços hoje estão mais baixos que o normal.")
        lines += [f"- {r['text']}" for r in reasons]
        lines.append(
            "Fale disso só se a conversa for sobre comércio. Nunca diga números nem porcentagens."
        )
        lines.append("</SEU_COMERCIO>")
        return "\n    ".join(lines)
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("npc", "commerce_block_failed", exc)
        return ""


def _mission_hint_block(state: GameState, last_msg: str) -> str:
    """spec npc-fallback-sem-alvo (R4): se a fala do jogador pergunta sobre a
    missão/objetivo, devolve um bloco com o beat atual do plano para o NPC
    orientar. Pura — testável sem invocar o LLM. Vazio se não é pergunta de
    missão ou não há beat."""
    if not _MISSION_RE.search((last_msg or "").lower()):
        return ""
    from services.objectives import public_objective

    desc = public_objective(
        state.get("campaign_plan"),
        state.get("quests"),
        state.get("world"),
    )["objective"]
    return (
        f"\n    <OBJETIVO_ATUAL>\n    O rumo público agora: {desc}\n"
        "    Se o jogador perguntar o que fazer/aonde ir, oriente com isto "
        "(do seu jeito, pela sua persona).\n    </OBJETIVO_ATUAL>\n"
    )


# --- NÓ DE ATUAÇÃO (COM FILTRO DE IGNORÂNCIA) ---
def _resolve_social(state, key: str, npc_data: dict, intent: dict) -> tuple[dict, dict, dict, list]:
    """SPEC-298 R20-R24: abordagem social resolvida em Python ANTES do LLM.

    Devolve ``(social, npc_row, extra_updates, notices)``; o LLM só narra o resultado."""
    from services import reputation as rep

    approach = str(intent.get("approach") or "conversar")
    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    nid = str(npc_data.get("id") or key)
    row, extra, notices = dict(npc_data), {}, []
    social: dict = {"approach": approach, "success": None}
    if approach in ("intimidar", "sondar"):
        social = rep.social_check(state, row, approach)
        if social.get("rel_delta"):
            new_row, notice = rep.apply_npc_delta(
                {**state, "npcs": {key: row}},
                key,
                social["rel_delta"],
                reason=approach,
                source="engine",
            )
            if new_row:
                row = new_row
            if notice:
                notices.append(notice)
        tid = social.get("reveal_trait")
        if tid and tid in (row.get("hidden_traits") or []):
            row["hidden_traits"] = [t for t in row["hidden_traits"] if t != tid]
            row["revealed_traits"] = [*(row.get("revealed_traits") or []), tid]
        if social.get("notice"):
            notices.append(
                {"kind": "social", "subject_id": nid, "text": social["notice"], "turn": turn}
            )
    elif approach == "pedir_favor":
        kind = intent.get("favor_kind")
        decision = rep.favor_decision(state, row, kind or "")
        social = {"approach": approach, "success": bool(decision["ok"])}
        if decision["ok"]:
            patch = rep.apply_favor(state, key, row, kind)
            row = patch.pop("npc")
            notices.append(patch.pop("notice"))
            extra.update(patch)
            social["favor_prompt"] = f"o jogador pediu um favor ({kind}) e você ACEITOU."
        else:
            social["favor_prompt"] = (
                "o jogador pediu um favor e você RECUSA (pelo momento ou pela confiança)."
            )
    elif approach == "pagar_divida":
        result = rep.pay_debt(state, key, row)
        social = {"approach": approach, "success": bool(result["ok"])}
        if result["ok"]:
            row = result["npc"]
            extra["player"] = result["player"]
            notices.append(result["notice"])
            social["favor_prompt"] = "o jogador quitou a dívida com você."
        else:
            social["favor_prompt"] = (
                "o jogador tenta pagar uma dívida que não existe ou não tem como pagar."
            )
    return social, row, extra, notices


def npc_actor_node(state: GameState):
    messages = state.get("messages", [])
    npc_name = optional_entity_ref(state.get("active_npc_name"))

    # Busca dados (Prioridade: Estado -> DB -> Fallback)
    from services import npc_layers

    # spec npc-fallback-sem-alvo: rota NPC sem alvo NÃO desiste com "Ninguém
    # responde" (o quester perdia 7+ turnos assim, com Gorim na cena).
    if not npc_name:
        candidatos = [
            normalized
            for candidate in npc_layers.npcs_in_scene(state)
            if (normalized := optional_entity_ref(candidate)) is not None
        ]  # R1: NPC em cena / aliado presente
        # SPEC-202 R5: alvo dito pelo jogador e inexistente não cai no 1º da cena.
        if candidatos and state.get("interlocutor_reason") != "npc_unknown_absent":
            npc_name = candidatos[0]
        else:
            # R2: ninguém para responder → o storyteller narra a solidão + gancho
            # útil (nunca a string seca). Aresta condicional npc_actor→storyteller.
            action = str(getattr(messages[-1], "content", "")) if messages else ""
            return {"next": "storyteller", "npc_fallback_hint": action}

    from services.entity_identity import find_runtime_npc_key, runtime_npc_aliases

    npcs_db = state.get("npcs", {})
    npc_state_key = find_runtime_npc_key(npcs_db, npc_name)
    npc_data = npcs_db.get(npc_state_key) if npc_state_key is not None else None
    from_state = npc_data is not None

    # --- Camada 3 (spec npcs-3-camadas, R4): NPC conhecido mas FORA de cena não
    # conversa — resposta determinística, ZERO chamada de LLM. Membro de party
    # está sempre com o jogador (estado próprio, 4.5). ---
    target_aliases = runtime_npc_aliases(npc_state_key or npc_name, npc_data)
    member = next(
        (
            c
            for c in state.get("party") or []
            if isinstance(c, dict)
            and bool(target_aliases & runtime_npc_aliases(str(c.get("name") or ""), c))
        ),
        None,
    )
    # SPEC-230 R3/R5: morto não conversa; membro esperando só fala no próprio local.
    if (member is not None and not npc_layers.npc_alive(member)) or (
        from_state and not npc_layers.npc_alive(npc_data)
    ):
        dname = (npc_data or member or {}).get("name") or npc_state_key or npc_name
        return {
            "messages": [
                AIMessage(
                    content=f"{dname} está morto. Não há resposta — só o silêncio onde antes havia uma voz."
                )
            ],
            "interlocutor_reason": "npc_absent_known",
        }
    in_party = False
    if member is not None:
        cur = state.get("world", {}) or {}
        here = {
            str(cur.get("current_location") or ""),
            str(cur.get("current_location_id") or ""),
        } - {""}
        waiting = str(member.get("waiting_at") or "")
        if member.get("active", True) or not waiting:
            in_party = bool(member.get("active")) or not waiting
        else:
            in_party = waiting in here
        if not in_party:
            dname = member.get("name") or npc_name
            # SPEC-325 B-P2-5: `waiting_at` pode ser id de local (abandono/lei) ou nome já exibível
            from gamedata import get_location as _get_location

            waiting = str((_get_location(waiting) or {}).get("name") or waiting)
            return {
                "messages": [
                    AIMessage(content=f"🗣️ {dname} não está aqui. Está esperando em {waiting}.")
                ],
                "interlocutor_reason": "npc_absent_known",
            }
    if from_state and not in_party and not npc_layers.is_in_scene(npc_data):
        home = npc_data.get("home_location_id") or npc_data.get("location", "")
        hint = f" Foi visto pela última vez em {home}." if home else ""
        display_name = npc_data.get("name") or npc_state_key or npc_name
        return {
            "messages": [AIMessage(content=f"🗣️ {display_name} não está aqui.{hint}")],
            "interlocutor_reason": "npc_absent_known",
        }

    # SPEC-202 R5/R6: alvo sem ficha no estado/party NUNCA vira identidade nova,
    # exceto papel genérico autorizado pelo router (generic_role_spawn, P2).
    # Companheiro de party sem ficha segue o caminho antigo (persona gerada p/ um
    # membro que JÁ existe — não é identidade nova). O
    # narrador explica a ausência (SPEC-041 R2) — nenhum NPC fala em 1ª pessoa.
    if (
        not npc_data
        and member is None
        and (state.get("interlocutor_reason") != "generic_role_spawn")
    ):
        action = str(getattr(messages[-1], "content", "")) if messages else ""
        return {
            "next": "storyteller",
            "npc_fallback_hint": action or npc_name,
            "active_npc_name": None,
            "interlocutor_reason": "npc_unknown_absent",
        }
    if not npc_data:
        db = _npc_db_for_game(str(state.get("game_id", "")))
        db_key = find_runtime_npc_key(db, npc_name)
        npc_data = db.get(db_key) if db_key is not None else None
    if not npc_data:
        # NPC ainda não existe na cena: gera na hora (persona + ficha) em vez de falhar.
        loc = state.get("world", {}).get("current_location", "")
        gen_kwargs = {}
        if _pool_flag_on():
            gen_kwargs = {
                "game_id": str(state.get("game_id", "")),
                "location_id": str(state.get("world", {}).get("current_location_id", "")),
                "name_origin": "player",  # R8/D1: nome do jogador/router nunca promove
                "turn": int(state.get("world", {}).get("turn_count", 0) or 0),
            }
        npc_data = generate_new_npc(npc_name, context=f"Local: {loc}", **gen_kwargs)
        npc_data.setdefault("location", loc)
        npc_data.setdefault("relationship", 5)
        npc_data.setdefault("memory", [])
    npc_name = str(npc_data.get("name") or npc_state_key or npc_name)
    if npc_state_key is None:
        npc_state_key = find_runtime_npc_key(npcs_db, npc_name, npc_data) or npc_name
    # Campos de camada + traits seeded (R1/R3); quem chegou aqui está na cena.
    home_id = state.get("world", {}).get("current_location_id", "")
    npc_data = npc_layers.ensure_npc_fields(
        npc_data,
        str(state.get("game_id", "")),
        home_location_id=npc_data.get("home_location_id") or home_id,
        in_scene=True if not from_state else None,
    )
    npc_data["known_by_player"] = True
    if not from_state and not npc_data.get("relationship_basis"):
        # SPEC-298 R8: relação inicial calculada em Python (raça/origem/fama/fação);
        # o `initial_relationship` do LLM é ignorado. Só NPC novo na sessão.
        from services import reputation

        npc_data["race_id"] = _valid_race_id(npc_data.get("race_id")) or reputation.npc_race_id(
            npc_data
        )
        rel0, basis = reputation.initial_relationship(state, npc_data)
        npc_data["relationship"] = rel0
        npc_data["relationship_basis"] = basis

    # O NPC NÃO é uma wikipédia: age por persona + memória própria (sem dump de lore global).
    last_msg = messages[-1].content if messages else ""

    # --- Fase 4.5: comandos de party são DETERMINÍSTICOS (gate em Python; o LLM
    # nunca decide se o NPC aceita — no máximo narraria; aqui nem precisa dele). ---
    import party as party_mod

    cmd = party_mod.detect_party_command(str(last_msg))
    if cmd:
        loc = state.get("world", {}).get("current_location", "")
        if cmd == "recruit":
            decision = party_mod.recruitment_decision(
                {**state, "npcs": {**npcs_db, npc_name: npc_data}}, npc_name
            )
            new_party, reason = party_mod.recruit(
                {**state, "npcs": {**npcs_db, npc_name: npc_data}}, npc_name
            )
            if new_party is None:
                return {
                    "messages": [AIMessage(content=f'🗣️ {npc_name} recusa: "{reason}"')],
                    "last_interaction_outcome": _interaction_outcome(
                        state,
                        kind="recruit",
                        subject_id=_npc_id(npc_data, npc_name),
                        code=decision["code"],
                        progressed=False,
                    ),
                    "archive_due": True,
                }
            return {
                "party": new_party,
                "last_interaction_outcome": _interaction_outcome(
                    state,
                    kind="recruit",
                    subject_id=_npc_id(npc_data, npc_name),
                    code="ok",
                    progressed=True,
                ),
                "messages": [
                    AIMessage(
                        content=(
                            f"🗣️ {npc_name} ajeita o equipamento e assente. "
                            f'"Estou com você." ({npc_name} junta-se ao grupo.)'
                        )
                    )
                ],
                "archive_due": True,
            }
        if cmd == "dismiss":
            new_party, found = party_mod.dismiss(state, npc_name)
            msg = (
                f"{npc_name} assente e segue o próprio caminho."
                if found
                else f"{npc_name} não está no seu grupo."
            )
            return {
                "party": new_party,
                "messages": [AIMessage(content=f"🗣️ {msg}")],
                "archive_due": found,
            }
        if cmd == "wait":
            new_party, found = party_mod.set_waiting(state, npc_name, loc)
            msg = (
                f"{npc_name} monta guarda em {loc} e espera."
                if found
                else f"{npc_name} não está no seu grupo."
            )
            return {"party": new_party, "messages": [AIMessage(content=f"🗣️ {msg}")]}
        if cmd == "follow":
            new_party, found = party_mod.set_following(state, npc_name)
            msg = (
                f"{npc_name} retoma a marcha ao seu lado."
                if found
                else f"{npc_name} não está no seu grupo."
            )
            return {"party": new_party, "messages": [AIMessage(content=f"🗣️ {msg}")]}

    # Memória vetorizada DESTE npc: recupera por relevância o que viveu com o jogador
    # (além das 3 últimas linhas). Inerte sem chave (get_embeddings -> None).
    game_id = state.get("game_id")
    npc_id = _npc_id(npc_data, npc_name)
    # Fase 2.8: pack centraliza memória do NPC + estado atual do mundo (NPC ciente de
    # mudanças: líder morto, controle trocado). purpose="npc".
    # SPEC-215: com o flag != off, a fala do jogador (R9) e a herança local de
    # NPC recém-gerado (R10) entram no ledger ANTES do invoke. `off` = no-op.
    from services import npc_knowledge

    knowledge_mode = npc_knowledge.mode()
    knowledge_new: list = []
    pack_state = state
    if knowledge_mode != "off":
        try:
            k_clock = npc_knowledge.clock_index(state.get("world") or {})
            base_kstate = {**state, "npcs": {**npcs_db, npc_state_key: npc_data}}
            if not from_state:
                knowledge_new += npc_knowledge.inherit_local(
                    base_kstate, npc_id, str(home_id or ""), k_clock
                )
            told_state = {
                **base_kstate,
                "knowledge_links": [*(state.get("knowledge_links") or []), *knowledge_new],
            }
            knowledge_new += npc_knowledge.record_player_told(
                told_state, npc_id, str(last_msg), k_clock
            )
            if knowledge_new:
                pack_state = {
                    **state,
                    "knowledge_links": [*(state.get("knowledge_links") or []), *knowledge_new],
                }
        except Exception as exc:  # o turno segue; o gate falha fechado
            _log_event("npc", "knowledge_failed", level="warning", error=type(exc).__name__)
            knowledge_new = []
    own_faction = _own_faction(pack_state, npc_state_key or npc_name, npc_data)  # SPEC-314 R13
    pack = build_context_pack(
        pack_state,
        query=compose_lore_query(
            pack_state, f"{npc_data.get('name', npc_name)} {last_msg}".strip()
        ),  # SPEC-311 R18
        purpose="npc",
        game_id=game_id,
        npc_id=npc_id,
        **({"own_faction": own_faction} if own_faction else {}),
    )
    relevant_memory = pack.memory_block
    public_lore = pack.lore_block

    # Fações do mundo: o NPC PODE saber delas (e revelar ao jogador). O conhecimento do
    # jogador (faction_intel) só avança por aqui — fora daqui ele não é onisciente.
    factions = ensure_factions(state.get("factions"))
    # SPEC-314: o bloco é montado em Python (faction_gate), depois de `tier_now`.

    llm = get_llm(temperature=0.8, tier=ModelTier.FAST)

    # R2 (fix-playtest-achados): última fala DESTE npc — p/ não repetir verbatim
    # quando o jogador insiste no mesmo assunto (achado do playtest real).
    _nome = npc_data.get("name", npc_name)
    ultima_fala = "—"
    aberturas_recentes: list[str] = []
    for _m in reversed(messages):
        _c = str(getattr(_m, "content", "") or "").strip()
        if getattr(_m, "type", "") == "ai" and _c.startswith(f"**{_nome}"):
            if ultima_fala == "—":
                ultima_fala = _c
            _abertura = semantic_opening(_c, words=12)
            if _abertura:
                aberturas_recentes.append(_abertura)
            if len(aberturas_recentes) >= 2:
                break

    # spec npc-fallback-sem-alvo (R4): pergunta sobre missão/objetivo → o NPC
    # orienta com o beat atual do plano (antes: silêncio quando o quester
    # perguntava "o que a missão exige agora?").
    objetivo_block = _mission_hint_block(state, str(last_msg))

    # SPEC-298 R20-R25: abordagem social resolvida em Python; o LLM só narra.
    from services import reputation as _rep

    social: dict | None = None
    social_extra: dict = {}
    social_notices: list = []
    _intent = state.get("social_intent")
    _turn_now = int((state.get("world") or {}).get("turn_count", 0) or 0)
    if (
        isinstance(_intent, dict)
        and _intent.get("turn") == _turn_now
        and _intent.get("approach") not in (None, "conversar")
    ):
        try:
            social, npc_data, social_extra, social_notices = _resolve_social(
                state, npc_state_key, npc_data, _intent
            )
        except Exception as exc:  # silent-ok: abordagem falha = conversa normal
            social = None
            _log_event("npc", "social_failed", level="warning", error=type(exc).__name__)
    # SPEC-299: fato de cena da lei + aviso de NPC amistoso (nunca heat/bounty/nível).
    from services import law as _law_mod

    _law_text, _law_scene_updates = _law_mod.scene_block(state, for_npc=npc_name)
    lei_block = _law_text
    if _law_mod.crime_hint_enabled(state):
        lei_block = chr(10).join(p for p in (lei_block, _law_mod.CRIME_CLAIM_HINT) if p)
    atitude_block = _rep.attitude_block(state, npc_data, social)
    tier_now = _rep.npc_tier(npc_data.get("relationship"))
    from services import faction_gate

    faction_view = faction_gate.npc_faction_view(
        pack_state, npc_state_key or npc_name, npc_data, tier_now
    )  # SPEC-314 R1-R8
    # SPEC-300 R11: interlocutor companheiro recebe o bloco da alma (sem chamada extra).
    try:
        from services.companion_prompt import companion_prompt_block

        companion_block, companion_ack = companion_prompt_block(
            state, "npc", target=str(npc_data.get("id") or npc_data.get("name") or npc_name)
        )
    except Exception as exc:
        from observability.telemetry import log_fallback

        log_fallback("npc", "companion_block_failed", exc)
        companion_block, companion_ack = "", []
    from services import faction_membership as _fm

    faction_member_block = _fm.prompt_block(state)  # SPEC-301 R21 (vazio sem vínculo)
    self_knowledge_block = _npc_self_prompt(
        pack_state, npc_state_key or npc_name, npc_data, npc_id, getattr(pack, "evidence_ids", ())
    )  # SPEC-310
    if self_knowledge_block:  # bloco vazio não deixa linha em branco
        self_knowledge_block = chr(10) + self_knowledge_block
    comercio_block = _commerce_block(state, npc_data)  # SPEC-311 R15
    if comercio_block:
        comercio_block = chr(10) + comercio_block
    ganchos_block, lore_menu = _lore_menu(state, npc_state_key or npc_name)  # SPEC-313 R11
    if ganchos_block:
        ganchos_block = chr(10) + ganchos_block

    # SPEC-317 R9: prompt em pedaços (texto, estático?) — ver services/prompt_layout.
    _npc_head = f"""
    <ROLE>
    Você é {npc_data.get("name")}.
    Ocupação: {npc_data.get("role")}.
    Persona: {npc_data.get("persona")}.
    Local: {npc_data.get("location")}.
    Traços que o jogador JÁ percebeu em você (aja de acordo): {
        ", ".join(
            t["name"] + " — " + t["description"]
            for t in npc_layers.trait_names(npc_data.get("revealed_traits") or [])
        )
        or "—"
    }
    </ROLE>{self_knowledge_block}
    {atitude_block}{comercio_block}
    {companion_block}

    <MEMORIA>
    {npc_data.get("memory", [])[-3:]}
    </MEMORIA>

    <SUA_ULTIMA_FALA>
    {ultima_fala}
    </SUA_ULTIMA_FALA>

    <MEMORIA_RELEVANTE>
    {relevant_memory or "—"}
    </MEMORIA_RELEVANTE>

    <LORE_PUBLICO_CANONICO>
    {public_lore or "—"}
    </LORE_PUBLICO_CANONICO>
    {objetivo_block}
    {pack.world_state_block}
    {ambient_block(state.get("world") or {}, state.get("player") or {}, audience="npc")}
    {perceived_world_block(state, audience="npc")}
    {lei_block}
    {_WORLD_TRUTH_NOTE_ON if knowledge_mode == "on" else _WORLD_TRUTH_NOTE_OFF}

    <FACÇÕES_DO_MUNDO>
    {faction_view.block}
    </FACÇÕES_DO_MUNDO>

    {faction_member_block}
    """
    _npc_mission = """<MISSÃO>
    Se seu personagem tem um pedido/tarefa CONCRETA para o jogador (recuperar algo,
    entregar algo, investigar algo, resgatar alguém), registre em 'proposed_quests'.
    Vazio se a conversa não chegou a um pedido concreto.
    </MISSÃO>"""
    _npc_rules_a = """

    <REGRAS DE ATUAÇÃO - CRÍTICO>
    1. NÃO SEJA UMA WIKIPÉDIA. Você é uma pessoa limitada pela sua ocupação e local.
    2. FILTRO DE CONHECIMENTO: Ignore fatos que seu personagem não saberia.
       Você só pode repetir um rumor factual se ele estiver no LORE PÚBLICO ou
       na MEMÓRIA acima. Se não houver base, admita que não sabe, demonstre
       desconfiança ou mude de assunto — NUNCA invente um fato/rumor canônico.
    3. Mantenha a persona (gírias, erros, arrogância) o tempo todo.
    4. Resposta curta e direta.
    5. NÃO REPITA: veja <SUA_ULTIMA_FALA>. Se o jogador insistir no mesmo assunto,
       NUNCA repita sua fala anterior literalmente — traga um detalhe NOVO, mude o
       ângulo, demonstre impaciência ("já te disse..."), ou avance a conversa.
    """
    _npc_rules_b = f"""
    6. {PLAYER_INPUT_RULE}
    """
    system_msg = SystemMessage(
        content=compose_prompt(
            [
                (_npc_head, False),
                (_npc_mission, True),
                (ganchos_block, False),
                (_npc_rules_a, True),
                (openings_clause(aberturas_recentes), False),
                (_npc_rules_b, True),
            ]
        )
    )

    try:
        from services.narrative_sink import narrate_structured

        # SPEC-319: a fala (`dialogue`, 1o campo) sai token a token; a mensagem final
        # e `**Nome:** "fala"` — o prefixo evita um `replace` so por causa do rotulo/aspa.
        res = narrate_structured(
            llm,
            NPCResponse,
            [system_msg] + guard_messages(messages[-3:]),
            state=state,
            key="dialogue",
            prefix=f'**{npc_data["name"]}:** "',
            normalize="meta",
        )
        if not isinstance(res, NPCResponse):
            raise TypeError(f"structured output inválido: {type(res).__name__}")
        dialogue = strip_outer_quotes(sanitize_meta_preamble(res.dialogue))
        if aberturas_recentes:
            log_if_repeats(dialogue, aberturas_recentes[0], where="npc")
        varied_dialogue = vary_repeated_opening(
            dialogue,
            aberturas_recentes,
            salt=(
                f"{game_id}:{npc_id}:{int((state.get('world') or {}).get('turn_count', 0) or 0)}"
            ),
        )
        dialogue_transition = (
            varied_dialogue[: -len(dialogue)]
            if dialogue and varied_dialogue.endswith(dialogue)
            else ""
        )
        action_description = sanitize_meta_preamble(res.action_description)

        # Atualiza memória e relação (com guardas contra chaves ausentes)
        turn = state.get("world", {}).get("turn_count", 0)
        delta = clamp_relationship_change(res.relationship_change, npc_data.get("name", npc_name))
        from services import reputation

        npc_data["relationship"] = npc_data.get("relationship", 5)
        _row, rel_notice = reputation.apply_npc_delta(
            {**state, "npcs": {npc_state_key: npc_data}},
            npc_state_key,
            delta,
            reason="dialogue",
            source="llm",
        )
        if _row:
            npc_data.update(_row)
        npc_data.setdefault("memory", [])
        # Memória registra a EXPERIÊNCIA observável (fala/resposta), não promove
        # `memory_update` livre da IA a verdade canônica.
        player_said = str(last_msg).strip().replace("\n", " ")[:180]
        npc_said = str(dialogue).strip().replace("\n", " ")[:240]
        fato = (
            f'Turno {turn}: o jogador disse "{player_said}"; '
            f'{npc_data.get("name", npc_name)} respondeu "{npc_said}".'
        )
        npc_data["memory"].append(fato)
        npc_data["memory"] = npc_data["memory"][-20:]  # SPEC-234 R11

        # spec npcs-3-camadas (R7): interação conta; trait maduro é revelado (Python).
        npc_data, trait_revelados = npc_layers.tick_interaction(npc_data)
        reveal_note = ""
        if trait_revelados:
            nomes = [t["name"] for t in npc_layers.trait_names(trait_revelados)]
            reveal_note = "\n" + "\n".join(
                f"*(Você percebe que {npc_data.get('name', npc_name)} é {n}.)*" for n in nomes
            )

        # Memória de longo prazo: vetoriza o fato no índice deste npc (inerte sem chave).
        rag_ok = True
        record = None
        # SPEC-318 R2: o embedding sai do no. O fato entra na fila `pending_npc_memory` e o
        # arquivista (que roda em seguida, `pending_npc_memory` forca o gate) grava o vetor.
        defer_memory = latency_flags.two_phase_on() and bool(RAG_AVAILABLE and game_id and npc_said)
        if defer_memory:
            rag_ok = False
        elif RAG_AVAILABLE and game_id and npc_said:
            try:
                record = make_memory_fact(
                    fato,
                    provenance="npc_claim",
                    source_id=f"npc:{npc_id}",
                    source_turn=int(turn),
                    canonical_entity_ids=[npc_id],
                )
                parameters = inspect.signature(add_npc_memory).parameters.values()
                accepts_metadata = any(
                    parameter.name == "metadatas" or parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters
                )
                if accepts_metadata:
                    rag_ok = (
                        add_npc_memory(
                            game_id,
                            npc_id,
                            [fato],
                            metadatas=[memory_metadata(record)],
                        )
                        is not False
                    )
                else:
                    rag_ok = add_npc_memory(game_id, npc_id, [fato]) is not False
            except Exception as exc:
                from observability.telemetry import log_fallback

                log_fallback("npc", "rag_unavailable", exc)
                rag_ok = False
        pending_npc_memory = normalize_pending_npc_memory(state.get("pending_npc_memory"))
        if not rag_ok:
            pending_npc_memory = enqueue_npc_memory(
                pending_npc_memory,
                npc_id,
                fato,
            )
        memory_error = state.get("rag_persistence_error")
        if defer_memory:
            pass  # pendente por desenho (nao e falha); o arquivista limpa ou sinaliza
        elif not rag_ok:
            memory_error = f"Falha ao persistir memória de {npc_id}."
        elif not pending_npc_memory:
            # Só uma interação bem-sucedida sem backlog pode limpar diretamente.
            # Backlog antigo precisa do retry operation-scoped no archivist.
            memory_error = None
        elif not memory_error:
            memory_error = "Há memórias de NPC aguardando persistência."

        # A escrita vetorial direta e o ledger do save representam o MESMO fato.
        # O merge ocorre somente depois do sucesso físico; falhas continuam
        # exclusivamente na fila operation-scoped para o archivist tentar depois.
        memory_facts = normalize_memory_facts(state.get("memory_facts"))
        memory_promotions = bounded_audit_rows(
            state.get("memory_promotions"),
            limit=MAX_MEMORY_PROMOTIONS,
        )
        if rag_ok and record is not None:
            memory_facts, promoted = commit_memory_facts(memory_facts, [record])
            if promoted:
                memory_promotions = bounded_audit_rows(
                    [
                        *memory_promotions,
                        {
                            "turn": int(turn),
                            "count": promoted,
                            "reason": "npc_claim_direct_write",
                        },
                    ],
                    limit=MAX_MEMORY_PROMOTIONS,
                )

        # Atualiza o estado global
        new_npcs = npcs_db.copy()
        new_npcs[npc_state_key] = npc_data

        # Não-onisciência: o que o NPC contou vira conhecimento do jogador (Python grava).
        intel = ensure_faction_intel(state.get("faction_intel"))
        for rev in getattr(res, "faction_reveals", []) or []:
            # SPEC-298 R23: a faixa de relação limita o que o NPC revela (Python decide).
            real_fid = faction_gate.resolve_proposed_id(
                faction_view, getattr(rev, "faction_id", "")
            )  # SPEC-314 R9
            if not real_fid:
                continue
            allowed = _rep.clamp_reveal(
                getattr(rev, "reveal_level", ""), tier_now, (social or {}).get("reveal_mode")
            )
            allowed = faction_gate.cap_reveal(faction_view, real_fid, allowed, tier_now)  # R10
            if not allowed:
                continue
            intel = apply_faction_reveal(
                intel,
                factions,
                real_fid,
                allowed,
                turn,
            )

        updates = {
            "messages": [
                AIMessage(
                    content=(
                        f"**{npc_data['name']}:** {dialogue_transition}"
                        f'"{dialogue}"\n*({action_description})*{reveal_note}'
                    )
                )
            ],
            "npcs": new_npcs,
            # SPEC-202 R9: chave de estado de quem falou (speaker canônico).
            "active_npc_name": npc_state_key,
            "faction_intel": intel,
            "archive_due": True,  # conversa com NPC = evento relevante p/ o arquivista
            # O diálogo continua útil como memória relacional do NPC, mas rumor
            # ou improviso livre não é promovido a fato global canônico.
            "memory_fact_policy": "canonical_only",
            "pending_npc_memory": pending_npc_memory,
            "rag_persistence_error": memory_error,
            "memory_facts": memory_facts,
            "memory_promotions": memory_promotions,
        }
        _new_notices = [*social_notices, *([rel_notice] if rel_notice else [])]
        if _new_notices:  # SPEC-298 R26: aviso do turno (substituído no finalizer a cada turno)
            updates["reputation_notices"] = [
                n
                for n in (state.get("reputation_notices") or [])
                if isinstance(n, dict) and n.get("turn") == _turn_now
            ] + _new_notices
        if companion_ack:  # SPEC-300 R13: só o caminho feliz consome reação/intenção
            updates["companion_voice_ack"] = list(companion_ack)
        updates.update(social_extra)  # player/world patches do favor (ouro, abrigo)
        if state.get("social_intent"):
            updates["social_intent"] = None

        # Fase 3.3: quem originou a missão é o NPC em cena — resolvido em Python
        # (não confiado ao LLM). Só title/description/location_id/reward_hint vêm do LLM.
        # SPEC-223 R1(b): conversa real com quem deu a missão é evidência Python
        # (entrega/retorno à origem) — registrada antes de novas propostas.
        base_quests = list(state.get("quests", []) or [])
        quests_now = quest_log.sync_npc_interaction(
            base_quests, npc_data.get("name", npc_name), turn=int(turn or 0)
        )
        proposals = getattr(res, "proposed_quests", []) or []
        lore_pending: list = []
        if proposals:
            canonical_id = _canonical_npc_id(npc_data.get("name", npc_name))
            stamped = []
            for p in proposals:
                p = p.model_dump() if hasattr(p, "model_dump") else dict(p)
                p["origin_name"] = npc_data.get("name", npc_name)
                p["origin_entity_id"] = canonical_id
                if str(p.get("kind") or "comum") == "comum":
                    stamped.append(p)
                else:  # SPEC-313: ancorada => depois da missão de facção (R9)
                    lore_pending.append(p)
            quests_now, _created = quest_log.register_proposed_quests(
                quests_now, stamped, turn=turn
            )
        # SPEC-301 R20: o recrutador propõe entrada/saída/missão; Python valida e decide.
        # FallbackLLM nunca chega aqui (isinstance acima); campo ausente = no-op.
        member_action = getattr(res, "membership_action", None)
        if isinstance(member_action, MembershipAction) and member_action.action:
            speaking = dict(new_npcs.get(npc_state_key) or {})
            speaking["in_scene"] = True
            fm_view = {
                **state,
                "npcs": {**new_npcs, npc_state_key: speaking},
                "quests": quests_now,
                "factions": factions,
                "faction_intel": intel,
            }
            fm_fid = faction_gate.resolve_proposed_id(faction_view, member_action.faction_id)
            fm_upd, fm_events, fm_note = (
                _fm.apply_intent(fm_view, member_action.action, fm_fid) if fm_fid else ({}, [], "")
            )  # SPEC-314 R9/R11
            if "quests" in fm_upd:
                quests_now = fm_upd["quests"]
            for key in ("faction_membership", "faction_intel"):
                if key in fm_upd:
                    updates[key] = fm_upd[key]
            if "factions" in fm_upd:
                updates["factions"] = fm_upd["factions"]
            if fm_events:
                updates["pending_world_events"] = list(
                    state.get("pending_world_events", []) or []
                ) + list(fm_events)
            if fm_note:
                updates["messages"] = [
                    AIMessage(content=f"{updates['messages'][0].content}\n\n{fm_note}")
                ]
        if lore_pending:
            quests_now, lore_extras = _apply_lore_proposals(
                {**state, "npcs": new_npcs},
                quests_now,
                lore_pending,
                npc_state_key or npc_name,
                lore_menu,
                _canonical_npc_id(npc_data.get("name", npc_name)),
                int(turn or 0),
            )
            updates.update(lore_extras)
        if quests_now != base_quests:
            updates["quests"] = quests_now
        # SPEC-299 R4(a)/R7: crimes classificados pelo LLM (guard: só NPCResponse chega aqui).
        try:
            updates.update(_law_scene_updates)
            updates.update(
                _law_mod.apply_claims(
                    {**state, **_law_scene_updates},
                    getattr(res, "crime_claims", []) or [],
                    player_text=str(last_msg or ""),
                )
            )
        except Exception as exc:  # silent-ok: lei nunca derruba o turno
            _log_event("law", "claims_failed", level="warning", error=type(exc).__name__)
        if knowledge_new:
            updates["knowledge_links"] = npc_knowledge.normalize_knowledge(
                {"knowledge_links": [*(state.get("knowledge_links") or []), *knowledge_new]},
            )["knowledge_links"]

        # SPEC-318 R5: conversa sem consequência (relação, traço, fação, missão, lei, evento)
        # é "baixo valor": a política `lean` do arquivista a pula (marca vale só neste turno).
        _plain_keys = _CHAT_BASE_KEYS | {"archive_low"}
        if (
            latency_flags.archive_low_wanted()
            and not rel_notice
            and not trait_revelados
            and intel == ensure_faction_intel(state.get("faction_intel"))
            and not (set(updates) - _plain_keys)
            and not _new_notices
        ):
            updates["archive_low"] = int(_turn_now or 0)
        return updates
    except Exception as e:
        _log_event("npc", "actor_failed", level="error", error=type(e).__name__)
        return {"messages": [AIMessage(content="...")]}
