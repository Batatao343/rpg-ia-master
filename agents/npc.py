"""
agents/npc.py
Gerador de NPCs com Persistência, Memória, RAG e Filtro de Ignorância.
Contém tanto a fábrica de NPCs (generate_new_npc) quanto o ator (npc_actor_node).
"""
import json
import os
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from state import GameState
from llm_setup import ModelTier, get_llm
from world_utils import apply_faction_reveal, ensure_factions, ensure_faction_intel

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

# --- PERSISTÊNCIA ---
def load_npc_db():
    if not os.path.exists(NPC_DB_FILE): return {}
    try:
        with open(NPC_DB_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except Exception as e:
        print(f"⚠️ [NPC DB] Falha ao ler {NPC_DB_FILE}: {e}")
        return {}

def save_npc_template(data):
    db = load_npc_db()
    key = data.get("id", f"npc_{data['name'].lower().replace(' ', '_')}")
    if "id" not in data: data["id"] = key
    
    # Garante atributos mínimos
    if "attributes" not in data:
        data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    
    db[key] = data
    if not os.path.exists("data"): os.makedirs("data")
    with open(NPC_DB_FILE, 'w', encoding='utf-8') as f: json.dump(db, f, indent=4, ensure_ascii=False)

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
        if "attributes" not in data: # Auto-fix
            data["attributes"] = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
            save_npc_template(data)
        return data

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
        data["id"] = f"npc_{name.lower().replace(' ', '_')}"
        save_npc_template(data)
        return data
        
    except Exception as e: 
        print(f"❌ Erro NPC AI: {e}")
        # Fallback de segurança
        return {
            "name": name, "role": "Desconhecido", "id": "fallback", "persona": "Genérico",
            "initial_relationship": 5,
            "attributes": {"str":10, "dex":10, "con":10, "int":10, "wis":10, "cha":10},
            "combat_stats": {"hp": 10, "ac": 10, "attacks": []}
        }

# --- NÓ DE ATUAÇÃO (COM FILTRO DE IGNORÂNCIA) ---
def npc_actor_node(state: GameState):
    messages = state.get("messages", [])
    npc_name = state.get("active_npc_name")
    
    if not npc_name: return {"messages": [AIMessage(content="Ninguém responde.")]}
    
    # Busca dados (Prioridade: Estado -> DB -> Fallback)
    npcs_db = state.get("npcs", {})
    npc_data = npcs_db.get(npc_name)
    
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

    # O NPC NÃO é uma wikipédia: age por persona + memória própria (sem dump de lore global).
    last_msg = messages[-1].content if messages else ""

    # Memória vetorizada DESTE npc: recupera por relevância o que viveu com o jogador
    # (além das 3 últimas linhas). Inerte sem chave (get_embeddings -> None).
    game_id = state.get("game_id")
    npc_id = _npc_id(npc_data, npc_name)
    try:
        relevant_memory = query_npc_memory(game_id, npc_id, last_msg) if (RAG_AVAILABLE and game_id) else ""
    except Exception:
        relevant_memory = ""

    # Fações do mundo: o NPC PODE saber delas (e revelar ao jogador). O conhecimento do
    # jogador (faction_intel) só avança por aqui — fora daqui ele não é onisciente.
    factions = ensure_factions(state.get("factions"))
    faccoes_mundo = "\n".join(
        f"- id={f.get('id')} · {f.get('name')} ({f.get('region','')}) · plano: {f.get('goal','')}"
        for f in factions if not f.get("defeated")
    ) or "Nenhuma facção conhecida no mundo."

    llm = get_llm(temperature=0.8, tier=ModelTier.SMART)

    system_msg = SystemMessage(content=f"""
    <ROLE>
    Você é {npc_data.get('name')}.
    Ocupação: {npc_data.get('role')}.
    Persona: {npc_data.get('persona')}.
    Local: {npc_data.get('location')}.
    </ROLE>

    <MEMORIA>
    {npc_data.get('memory', [])[-3:]}
    </MEMORIA>

    <MEMORIA_RELEVANTE>
    {relevant_memory or "—"}
    </MEMORIA_RELEVANTE>

    <FACÇÕES_DO_MUNDO>
    {faccoes_mundo}
    Se — e SOMENTE se — seu personagem plausivelmente saber de uma destas facções (pela ocupação/local)
    E a conversa levar a isso, você pode contar ao jogador. Registre em 'faction_reveals' o faction_id
    EXATO e o nível: 'existencia' (só citou), 'objetivo' (contou o plano), 'progresso' (sabe quão perto está).
    Um camponês comum NÃO conhece os planos de cultos distantes. Na dúvida, deixe vazio ou solte só um rumor.
    </FACÇÕES_DO_MUNDO>

    <REGRAS DE ATUAÇÃO - CRÍTICO>
    1. NÃO SEJA UMA WIKIPÉDIA. Você é uma pessoa limitada pela sua ocupação e local.
    2. FILTRO DE CONHECIMENTO: Ignore fatos do Contexto Externo que seu personagem não saberia (ex: um soldado não sabe magia antiga). Se não souber, invente rumores ou seja cínico.
    3. Mantenha a persona (gírias, erros, arrogância) o tempo todo.
    4. Resposta curta e direta.
    """)

    try:
        actor = llm.with_structured_output(NPCResponse)
        res = actor.invoke([system_msg] + messages[-3:])
        
        # Atualiza memória e relação (com guardas contra chaves ausentes)
        turn = state.get('world', {}).get('turn_count', 0)
        npc_data['relationship'] = max(0, min(10, npc_data.get('relationship', 5) + res.relationship_change))
        npc_data.setdefault('memory', [])
        fato = f"Turno {turn}: {res.memory_update}"
        npc_data['memory'].append(fato)

        # Memória de longo prazo: vetoriza o fato no índice deste npc (inerte sem chave).
        if RAG_AVAILABLE and game_id and res.memory_update:
            try:
                add_npc_memory(game_id, npc_id, [fato])
            except Exception:
                pass

        # Atualiza o estado global
        new_npcs = npcs_db.copy()
        new_npcs[npc_name] = npc_data

        # Não-onisciência: o que o NPC contou vira conhecimento do jogador (Python grava).
        intel = ensure_faction_intel(state.get("faction_intel"))
        for rev in getattr(res, "faction_reveals", []) or []:
            intel = apply_faction_reveal(
                intel, factions, getattr(rev, "faction_id", ""), getattr(rev, "reveal_level", ""), turn
            )

        return {
            "messages": [AIMessage(content=f"**{npc_data['name']}:** \"{res.dialogue}\"\n*({res.action_description})*")],
            "npcs": new_npcs,
            "faction_intel": intel,
            "archive_due": True,  # conversa com NPC = evento relevante p/ o arquivista
        }
    except Exception as e:
        print(f"Erro NPC Actor: {e}")
        return {"messages": [AIMessage(content="...")]}