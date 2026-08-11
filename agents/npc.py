"""
agents/npc.py
Gerador de NPCs com Persistência, Memória, RAG e Filtro de Ignorância.
Contém tanto a fábrica de NPCs (generate_new_npc) quanto o ator (npc_actor_node).
"""
import json
import os
import re
import inspect
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import ModelTier, get_llm
from world_utils import apply_faction_reveal, ensure_factions, ensure_faction_intel
from services import graph_resolver as gr
from services import quest_log
from services.context_builder import build_context_pack
from services.memory_retry import (
    enqueue_npc_memory,
    normalize_pending_npc_memory,
)
from services.memory_provenance import make_memory_fact, memory_metadata
from services.prose_guard import sanitize_meta_preamble
from services.input_normalization import optional_entity_ref
from services.structured_outputs import ProposedQuest

# Fallback para RAG
try:
    from rag import query_rag, add_npc_memory, query_npc_memory
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    def query_rag(*args, **kwargs): return ""
    def add_npc_memory(*args, **kwargs): return None
    def query_npc_memory(*args, **kwargs): return ""


def _npc_id(npc_data: dict, name: str) -> str:
    """id estável do NPC para namespacing da memória vetorial."""
    return npc_data.get("id") or f"npc_{(name or 'desconhecido').lower().replace(' ', '_')}"


def _canonical_npc_id(name: str) -> str:
    """Id canônico (entities.json, type npc) por match de nome — "" se não achar.

    Fase 3.3: habilita falha sistêmica de quest (origin_entity_id) só para NPCs do
    grafo canônico — NPC gerado em runtime não tem id aqui (mesma restrição de
    `_v_npc_killed`, que só aceita npc_killed contra ids canônicos).
    """
    try:
        entities = gr.load_entities()
    except Exception:
        return ""
    name_l = (name or "").strip().lower()
    for eid, ent in entities.items():
        if ent.get("type") == "npc" and ent.get("name", "").strip().lower() == name_l:
            return eid
    return ""

# Importa Librarian para verificar duplicatas
try:
    from agents.librarian import find_existing_entity
except ImportError:
    def find_existing_entity(*args, **kwargs): return None

NPC_DB_FILE = "data/npc_database.json"

# --- SCHEMAS ---
class NPCSchema(BaseModel):
    name: str
    role: str
    location: str
    persona: str
    appearance: str
    initial_relationship: int = 5
    attributes: Dict[str, int] = Field(
        description="Stats base: str, dex, con, int, wis, cha. Padrão humano é 10.",
        json_schema_extra={"example": {"str": 10, "dex": 12, "con": 10, "int": 14, "wis": 16, "cha": 18}}
    )
    combat_stats: Dict = Field(description="HP, AC e Attacks", default={"hp": 10, "ac": 10, "attacks": []})

class FactionReveal(BaseModel):
    faction_id: str = Field(description="id EXATO de uma facção listada em <FACÇÕES_DO_MUNDO>.")
    reveal_level: str = Field(
        description="O QUANTO este NPC revelou: 'existencia' (citou a facção), "
                    "'objetivo' (contou o plano) ou 'progresso' (sabe quão perto está)."
    )


class NPCResponse(BaseModel):
    dialogue: str
    action_description: str
    memory_update: str
    relationship_change: int = 0
    faction_reveals: List[FactionReveal] = Field(
        default_factory=list,
        description=(
            "Facções sobre as quais ESTE NPC contou algo ao jogador NESTE turno. "
            "Só preencha se o personagem plausivelmente saberia (ocupação/local) E o papo levou a isso. "
            "Vazio caso contrário. Use o faction_id EXATO da lista."
        ),
    )
    proposed_quests: List[ProposedQuest] = Field(
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


def load_npc_db():
    path = _npc_db_path()
    if not os.path.exists(path):
        path = NPC_DB_FILE               # fallback legado (migração transparente)
    if not os.path.exists(path): return {}
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        print(f"⚠️ [NPC DB] Falha ao ler {path}: {e}")
        return {}

def save_npc_template(data):
    db = load_npc_db()                   # 1º save carrega o legado → migra tudo
    key = data.get("id", f"npc_{data['name'].lower().replace(' ', '_')}")
    if "id" not in data: data["id"] = key

    # Garante atributos mínimos
    if "attributes" not in data:
        data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

    db[key] = data
    path = _npc_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)


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
    lowered = name.lower()
    if any(m in lowered for m in ["king", "queen", "boss", "lord", "archmage"]): return ModelTier.SMART
    return ModelTier.FAST

# --- FÁBRICA DE NPCs (A FUNÇÃO QUE FALTAVA) ---
def generate_new_npc(name, context=""):
    """
    Gera um novo NPC do zero usando IA ou recupera do cache se já existir.
    Usado pelo Storyteller para popular o mundo dinamicamente.
    """
    # 1. CHECK-FIRST: Verifica se já existe
    db = load_npc_db()
    existing_ids = list(db.keys())
    
    found_id = find_existing_entity(name, "NPC", existing_ids)
    if found_id:
        print(f"♻️ [NPC] Cache Hit: {found_id}")
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
    print(f"🎭 [NPC] Criando: {name}...")
    lore_info = query_rag(f"{name} {context}", index_name="lore")
    
    llm = get_llm(temperature=0.7, tier=_infer_tier_from_name(name))
    
    try:
        designer = llm.with_structured_output(NPCSchema)
        res = designer.invoke([
            SystemMessage(content=f"""
            <role>RPG Character Designer</role>
            <lore>{lore_info}</lore>
            <task>Create NPC '{name}'. Include all 6 attributes and a detailed persona.</task>
            """), 
            HumanMessage(content=f"Context: {context}")
        ])
        
        data = res.model_dump()
        # Identidade pedida pelo router é canônica. Providers (e especialmente o
        # MockLLM) podem devolver outro nome apesar do schema estar válido.
        data["name"] = name
        data["id"] = f"npc_{name.lower().replace(' ', '_')}"
        
    except Exception as e: 
        print(f"❌ Erro NPC AI: {e}")
        # Fallback de segurança
        data = {
            "name": name, "role": "Desconhecido", "id": "fallback", "persona": "Genérico",
            "initial_relationship": 5,
            "attributes": {"str":10, "dex":10, "con":10, "int":10, "wis":10, "cha":10},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []}
        }

    data = _materialize_npc_combat_sheet(data)
    try:
        save_npc_template(data)
    except Exception as exc:
        print(f"⚠️ [NPC DB] Falha ao persistir ficha v4 de '{name}': {exc}")
    return data

_MISSION_RE = re.compile(
    r"miss|objetiv|quest|o que.*(faç|faz|devo)|para onde|pr[óo]ximo passo|tarefa|rumo")


def _mission_hint_block(state: GameState, last_msg: str) -> str:
    """spec npc-fallback-sem-alvo (R4): se a fala do jogador pergunta sobre a
    missão/objetivo, devolve um bloco com o beat atual do plano para o NPC
    orientar. Pura — testável sem invocar o LLM. Vazio se não é pergunta de
    missão ou não há beat."""
    if not _MISSION_RE.search((last_msg or "").lower()):
        return ""
    plan = state.get("campaign_plan") or {}
    beats = plan.get("beats") or []
    step = int(plan.get("current_step", 0) or 0)
    cur = beats[step] if 0 <= step < len(beats) else (beats[0] if beats else None)
    desc = cur.get("description") if isinstance(cur, dict) else None
    if not desc:
        return ""
    return (f"\n    <OBJETIVO_ATUAL>\n    O rumo agora: {desc}\n"
            "    Se o jogador perguntar o que fazer/aonde ir, oriente com isto "
            "(do seu jeito, pela sua persona).\n    </OBJETIVO_ATUAL>\n")


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
        if candidatos:
            npc_name = candidatos[0]
        else:
            # R2: ninguém para responder → o storyteller narra a solidão + gancho
            # útil (nunca a string seca). Aresta condicional npc_actor→storyteller.
            action = str(getattr(messages[-1], "content", "")) if messages else ""
            return {"next": "storyteller", "npc_fallback_hint": action}

    npcs_db = state.get("npcs", {})
    npc_data = npcs_db.get(npc_name)
    from_state = npc_data is not None

    # --- Camada 3 (spec npcs-3-camadas, R4): NPC conhecido mas FORA de cena não
    # conversa — resposta determinística, ZERO chamada de LLM. Membro de party
    # está sempre com o jogador (estado próprio, 4.5). ---
    in_party = any(isinstance(c, dict) and c.get("name") == npc_name
                   for c in state.get("party") or [])
    if from_state and not in_party and not npc_layers.is_in_scene(npc_data):
        home = npc_data.get("home_location_id") or npc_data.get("location", "")
        hint = f" Foi visto pela última vez em {home}." if home else ""
        return {"messages": [AIMessage(content=f"🗣️ {npc_name} não está aqui.{hint}")]}

    if not npc_data:
        db = load_npc_db()
        npc_data = db.get(npc_name)
    if not npc_data:
        # NPC ainda não existe na cena: gera na hora (persona + ficha) em vez de falhar.
        loc = state.get("world", {}).get("current_location", "")
        npc_data = generate_new_npc(npc_name, context=f"Local: {loc}")
        npc_data.setdefault("location", loc)
        npc_data.setdefault("relationship", 5)
        npc_data.setdefault("memory", [])
    # Campos de camada + traits seeded (R1/R3); quem chegou aqui está na cena.
    home_id = state.get("world", {}).get("current_location_id", "")
    npc_data = npc_layers.ensure_npc_fields(
        npc_data, str(state.get("game_id", "")),
        home_location_id=npc_data.get("home_location_id") or home_id,
        in_scene=True if not from_state else None)
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
            new_party, reason = party_mod.recruit(
                {**state, "npcs": {**npcs_db, npc_name: npc_data}}, npc_name)
            if new_party is None:
                return {"messages": [AIMessage(content=f'🗣️ {npc_name} recusa: "{reason}"')],
                        "archive_due": True}
            return {"party": new_party,
                    "messages": [AIMessage(content=(
                        f"🗣️ {npc_name} ajeita o equipamento e assente. "
                        f'"Estou com você." ({npc_name} junta-se ao grupo.)'))],
                    "archive_due": True}
        if cmd == "dismiss":
            new_party, found = party_mod.dismiss(state, npc_name)
            msg = (f"{npc_name} assente e segue o próprio caminho."
                   if found else f"{npc_name} não está no seu grupo.")
            return {"party": new_party, "messages": [AIMessage(content=f"🗣️ {msg}")],
                    "archive_due": found}
        if cmd == "wait":
            new_party, found = party_mod.set_waiting(state, npc_name, loc)
            msg = (f"{npc_name} monta guarda em {loc} e espera."
                   if found else f"{npc_name} não está no seu grupo.")
            return {"party": new_party, "messages": [AIMessage(content=f"🗣️ {msg}")]}
        if cmd == "follow":
            new_party, found = party_mod.set_following(state, npc_name)
            msg = (f"{npc_name} retoma a marcha ao seu lado."
                   if found else f"{npc_name} não está no seu grupo.")
            return {"party": new_party, "messages": [AIMessage(content=f"🗣️ {msg}")]}

    # Memória vetorizada DESTE npc: recupera por relevância o que viveu com o jogador
    # (além das 3 últimas linhas). Inerte sem chave (get_embeddings -> None).
    game_id = state.get("game_id")
    npc_id = _npc_id(npc_data, npc_name)
    # Fase 2.8: pack centraliza memória do NPC + estado atual do mundo (NPC ciente de
    # mudanças: líder morto, controle trocado). purpose="npc".
    npc_location = str(
        npc_data.get("location")
        or state.get("world", {}).get("current_location", "")
        or "")
    pack = build_context_pack(
        state,
        query=f"{npc_data.get('name', npc_name)} {npc_location} {last_msg}".strip(),
                              purpose="npc", game_id=game_id, npc_id=npc_id)
    relevant_memory = pack.memory_block
    public_lore = pack.lore_block

    # Fações do mundo: o NPC PODE saber delas (e revelar ao jogador). O conhecimento do
    # jogador (faction_intel) só avança por aqui — fora daqui ele não é onisciente.
    factions = ensure_factions(state.get("factions"))
    faccoes_mundo = "\n".join(
        f"- id={f.get('id')} · {f.get('name')} ({f.get('region','')}) · plano: {f.get('goal','')}"
        for f in factions if not f.get("defeated")
    ) or "Nenhuma facção conhecida no mundo."

    llm = get_llm(temperature=0.8, tier=ModelTier.FAST)

    # R2 (fix-playtest-achados): última fala DESTE npc — p/ não repetir verbatim
    # quando o jogador insiste no mesmo assunto (achado do playtest real).
    _nome = npc_data.get("name", npc_name)
    ultima_fala = "—"
    for _m in reversed(messages):
        _c = str(getattr(_m, "content", "") or "").strip()
        if getattr(_m, "type", "") == "ai" and _c.startswith(f"**{_nome}"):
            ultima_fala = _c
            break

    # spec npc-fallback-sem-alvo (R4): pergunta sobre missão/objetivo → o NPC
    # orienta com o beat atual do plano (antes: silêncio quando o quester
    # perguntava "o que a missão exige agora?").
    objetivo_block = _mission_hint_block(state, str(last_msg))

    system_msg = SystemMessage(content=f"""
    <ROLE>
    Você é {npc_data.get('name')}.
    Ocupação: {npc_data.get('role')}.
    Persona: {npc_data.get('persona')}.
    Local: {npc_data.get('location')}.
    Traços que o jogador JÁ percebeu em você (aja de acordo): {
        ", ".join(t["name"] + " — " + t["description"]
                  for t in npc_layers.trait_names(npc_data.get("revealed_traits") or [])) or "—"}
    </ROLE>

    <MEMORIA>
    {npc_data.get('memory', [])[-3:]}
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
    (O mundo mudou desde que você o conheceu? O estado atual acima é a verdade de AGORA.)

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
    """)

    try:
        actor = llm.with_structured_output(NPCResponse)
        res = actor.invoke([system_msg] + messages[-3:])
        if not isinstance(res, NPCResponse):
            raise TypeError(f"structured output inválido: {type(res).__name__}")
        dialogue = sanitize_meta_preamble(res.dialogue)
        action_description = sanitize_meta_preamble(res.action_description)
        
        # Atualiza memória e relação (com guardas contra chaves ausentes)
        turn = state.get('world', {}).get('turn_count', 0)
        npc_data['relationship'] = max(0, min(10, npc_data.get('relationship', 5) + res.relationship_change))
        npc_data.setdefault('memory', [])
        # Memória registra a EXPERIÊNCIA observável (fala/resposta), não promove
        # `memory_update` livre da IA a verdade canônica.
        player_said = str(last_msg).strip().replace("\n", " ")[:180]
        npc_said = str(dialogue).strip().replace("\n", " ")[:240]
        fato = (f'Turno {turn}: o jogador disse "{player_said}"; '
                f'{npc_data.get("name", npc_name)} respondeu "{npc_said}".')
        npc_data['memory'].append(fato)

        # spec npcs-3-camadas (R7): interação conta; trait maduro é revelado (Python).
        npc_data, trait_revelados = npc_layers.tick_interaction(npc_data)
        reveal_note = ""
        if trait_revelados:
            nomes = [t["name"] for t in npc_layers.trait_names(trait_revelados)]
            reveal_note = "\n" + "\n".join(
                f"*(Você percebe que {npc_data.get('name', npc_name)} é {n}.)*" for n in nomes)

        # Memória de longo prazo: vetoriza o fato no índice deste npc (inerte sem chave).
        rag_ok = True
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
                    parameter.name == "metadatas"
                    or parameter.kind == inspect.Parameter.VAR_KEYWORD
                    for parameter in parameters
                )
                if accepts_metadata:
                    rag_ok = add_npc_memory(
                        game_id, npc_id, [fato],
                        metadatas=[memory_metadata(record)],
                    ) is not False
                else:
                    rag_ok = add_npc_memory(game_id, npc_id, [fato]) is not False
            except Exception:
                rag_ok = False
        pending_npc_memory = normalize_pending_npc_memory(
            state.get("pending_npc_memory")
        )
        if not rag_ok:
            pending_npc_memory = enqueue_npc_memory(
                pending_npc_memory, npc_id, fato,
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

        # Atualiza o estado global
        new_npcs = npcs_db.copy()
        new_npcs[npc_name] = npc_data

        # Não-onisciência: o que o NPC contou vira conhecimento do jogador (Python grava).
        intel = ensure_faction_intel(state.get("faction_intel"))
        for rev in getattr(res, "faction_reveals", []) or []:
            intel = apply_faction_reveal(
                intel, factions, getattr(rev, "faction_id", ""), getattr(rev, "reveal_level", ""), turn
            )

        updates = {
            "messages": [AIMessage(content=f"**{npc_data['name']}:** \"{dialogue}\"\n*({action_description})*{reveal_note}")],
            "npcs": new_npcs,
            "faction_intel": intel,
            "archive_due": True,  # conversa com NPC = evento relevante p/ o arquivista
            # O diálogo continua útil como memória relacional do NPC, mas rumor
            # ou improviso livre não é promovido a fato global canônico.
            "memory_fact_policy": "canonical_only",
            "pending_npc_memory": pending_npc_memory,
            "rag_persistence_error": memory_error,
        }

        # Fase 3.3: quem originou a missão é o NPC em cena — resolvido em Python
        # (não confiado ao LLM). Só title/description/location_id/reward_hint vêm do LLM.
        proposals = getattr(res, "proposed_quests", []) or []
        if proposals:
            canonical_id = _canonical_npc_id(npc_data.get("name", npc_name))
            stamped = []
            for p in proposals:
                p = p.model_dump() if hasattr(p, "model_dump") else dict(p)
                p["origin_name"] = npc_data.get("name", npc_name)
                p["origin_entity_id"] = canonical_id
                stamped.append(p)
            new_quests, created = quest_log.register_proposed_quests(
                state.get("quests", []), stamped, turn=turn
            )
            if created:
                updates["quests"] = new_quests

        return updates
    except Exception as e:
        print(f"Erro NPC Actor: {e}")
        return {"messages": [AIMessage(content="...")]}
