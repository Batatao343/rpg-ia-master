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
from services import quest_log
from services.ambient import ambient_block
from services.context_builder import build_context_pack
from services.input_normalization import optional_entity_ref
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
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages
from services.prose_guard import (
    log_if_repeats,
    openings_clause,
    sanitize_meta_preamble,
    semantic_opening,
    strip_outer_quotes,
    vary_repeated_opening,
)
from services.structured_outputs import ProposedQuest
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
    initial_relationship: int = 5
    attributes: dict[str, int] = Field(
        description="Stats base: str, dex, con, int, wis, cha. Padrão humano é 10.",
        json_schema_extra={
            "example": {"str": 10, "dex": 12, "con": 10, "int": 14, "wis": 16, "cha": 18}
        },
    )
    combat_stats: dict = Field(
        description="HP, AC e Attacks", default={"hp": 10, "ac": 10, "attacks": []}
    )


class FactionReveal(BaseModel):
    faction_id: str = Field(description="id EXATO de uma facção listada em <FACÇÕES_DO_MUNDO>.")
    reveal_level: str = Field(
        description="O QUANTO este NPC revelou: 'existencia' (citou a facção), "
        "'objetivo' (contou o plano) ou 'progresso' (sabe quão perto está)."
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
    proposed_quests: list[ProposedQuest] = Field(
        default_factory=list,
        description=(
            "APENAS se você (o NPC) pediu algo CONCRETO ao jogador NESTE turno (uma "
            "tarefa, um recado, um favor com objetivo claro). title/description curtos, "
            "location_id só se o destino é claro. Vazio caso contrário — não invente "
            "missão de um papo qualquer."
        ),
    )


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


def load_npc_db():
    """SPEC-230: descarta (com log) entradas quebradas já persistidas."""
    raw = _load_npc_db_raw()
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
        with open(NPC_DB_FILE, encoding="utf-8") as f:
            return json.load(f)
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
def generate_new_npc(name, context=""):
    """
    Gera um novo NPC do zero usando IA ou recupera do cache se já existir.
    Usado pelo Storyteller para popular o mundo dinamicamente.
    """
    from services.prompt_guard import sanitize_entity_name

    name = sanitize_entity_name(name) or "Desconhecido"  # SPEC-223 R7
    # 1. CHECK-FIRST: Verifica se já existe
    db = load_npc_db()
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
        if normalized is not data or changed:
            save_npc_template(normalized)
        return normalized

    # 2. GERAÇÃO
    _log_event("npc", "creating", level="info")
    lore_info = query_rag(f"{name} {context}", index_name="lore")

    llm = get_llm(temperature=0.7, tier=_infer_tier_from_name(name))

    try:
        designer = llm.with_structured_output(NPCSchema)
        res = designer.invoke(
            [
                SystemMessage(
                    content=f"""
            <role>RPG Character Designer</role>
            <lore>{lore_info}</lore>
            <task>Create NPC '{name}'. Include all 6 attributes and a detailed persona.</task>
            """
                ),
                HumanMessage(content=f"Context: {context}"),
            ]
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

    data = _materialize_npc_combat_sheet(data)
    if data.get("id") == "fallback":
        return data  # SPEC-230 R1: o fallback nunca envenena o cache de runtime
    try:
        save_npc_template(data)
    except Exception as exc:
        _log_event("npc", "db_persist_failed", level="warning", error=type(exc).__name__)
    return data


_MISSION_RE = re.compile(
    r"miss|objetiv|quest|o que.*(faç|faz|devo)|para onde|pr[óo]ximo passo|tarefa|rumo"
)


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
        db = load_npc_db()
        db_key = find_runtime_npc_key(db, npc_name)
        npc_data = db.get(db_key) if db_key is not None else None
    if not npc_data:
        # NPC ainda não existe na cena: gera na hora (persona + ficha) em vez de falhar.
        loc = state.get("world", {}).get("current_location", "")
        npc_data = generate_new_npc(npc_name, context=f"Local: {loc}")
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
    npc_location = str(
        npc_data.get("location") or state.get("world", {}).get("current_location", "") or ""
    )
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
    pack = build_context_pack(
        pack_state,
        query=f"{npc_data.get('name', npc_name)} {npc_location} {last_msg}".strip(),
        purpose="npc",
        game_id=game_id,
        npc_id=npc_id,
    )
    relevant_memory = pack.memory_block
    public_lore = pack.lore_block

    # Fações do mundo: o NPC PODE saber delas (e revelar ao jogador). O conhecimento do
    # jogador (faction_intel) só avança por aqui — fora daqui ele não é onisciente.
    factions = ensure_factions(state.get("factions"))
    faccoes_mundo = (
        "\n".join(
            f"- id={f.get('id')} · {f.get('name')} ({f.get('region', '')}) · plano: {f.get('goal', '')}"
            for f in factions
            if not f.get("defeated")
        )
        or "Nenhuma facção conhecida no mundo."
    )

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

    system_msg = SystemMessage(
        content=f"""
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
    </ROLE>

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
    {_WORLD_TRUTH_NOTE_ON if knowledge_mode == "on" else _WORLD_TRUTH_NOTE_OFF}

    <FACÇÕES_DO_MUNDO>
    {faccoes_mundo}
    Se — e SOMENTE se — seu personagem plausivelmente saber de uma destas facções (pela ocupação/local)
    E a conversa levar a isso, você pode contar ao jogador. Registre em 'faction_reveals' o faction_id
    EXATO e o nível: 'existencia' (só citou), 'objetivo' (contou o plano), 'progresso' (sabe quão perto está).
    Um camponês comum NÃO conhece os planos de cultos distantes. Na dúvida, deixe vazio ou solte só um rumor.
    </FACÇÕES_DO_MUNDO>

    <MISSÃO>
    Se seu personagem tem um pedido/tarefa CONCRETA para o jogador (recuperar algo,
    entregar algo, investigar algo, resgatar alguém), registre em 'proposed_quests'.
    Vazio se a conversa não chegou a um pedido concreto.
    </MISSÃO>

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
    {openings_clause(aberturas_recentes)}
    6. {PLAYER_INPUT_RULE}
    """
    )

    try:
        actor = llm.with_structured_output(NPCResponse)
        res = actor.invoke([system_msg] + guard_messages(messages[-3:]))
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
        rel_now = npc_data.get("relationship")
        rel_now = 5 if rel_now is None else int(rel_now)
        npc_data["relationship"] = max(0, min(10, rel_now + delta))
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
        if RAG_AVAILABLE and game_id and npc_said:
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
        if not rag_ok:
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
            intel = apply_faction_reveal(
                intel,
                factions,
                getattr(rev, "faction_id", ""),
                getattr(rev, "reveal_level", ""),
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

        # Fase 3.3: quem originou a missão é o NPC em cena — resolvido em Python
        # (não confiado ao LLM). Só title/description/location_id/reward_hint vêm do LLM.
        # SPEC-223 R1(b): conversa real com quem deu a missão é evidência Python
        # (entrega/retorno à origem) — registrada antes de novas propostas.
        base_quests = list(state.get("quests", []) or [])
        quests_now = quest_log.sync_npc_interaction(
            base_quests, npc_data.get("name", npc_name), turn=int(turn or 0)
        )
        proposals = getattr(res, "proposed_quests", []) or []
        if proposals:
            canonical_id = _canonical_npc_id(npc_data.get("name", npc_name))
            stamped = []
            for p in proposals:
                p = p.model_dump() if hasattr(p, "model_dump") else dict(p)
                p["origin_name"] = npc_data.get("name", npc_name)
                p["origin_entity_id"] = canonical_id
                stamped.append(p)
            quests_now, _created = quest_log.register_proposed_quests(
                quests_now, stamped, turn=turn
            )
        if quests_now != base_quests:
            updates["quests"] = quests_now
        if knowledge_new:
            updates["knowledge_links"] = npc_knowledge.normalize_knowledge(
                {"knowledge_links": [*(state.get("knowledge_links") or []), *knowledge_new]},
            )["knowledge_links"]

        return updates
    except Exception as e:
        _log_event("npc", "actor_failed", level="error", error=type(e).__name__)
        return {"messages": [AIMessage(content="...")]}
