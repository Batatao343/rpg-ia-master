"""Narration agent that advances the story and campaign plan."""
from typing import Dict, List
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.npc import generate_new_npc
from agents.world_simulator import simulate_world
from llm_setup import get_llm
from rag import query_rag
from services import discovery as disc
from services import graph_resolver as gr
from services import quest_log
from services.context_builder import build_context_pack
from services.structured_outputs import ProposedQuest, ProposedWorldEvent
from state import GameState
from world_utils import (
    advance_factions,
    apply_reputation,
    apply_rest,
    apply_travel,
    check_encounter,
    clock_label,
    ensure_faction_intel,
    ensure_factions,
    ensure_world,
    find_travel_destination,
    is_rest,
    resolve_faction_completions,
)


class FactionImpact(BaseModel):
    faction_id: str = Field(description="id EXATO de uma fação listada em <FACÇÕES_CONHECIDAS>; vazio se nenhuma.")
    direction: str = Field(description="'ajudou' (jogador beneficiou a fação) ou 'prejudicou' (jogador a atrapalhou/traiu/atacou).")


class StoryUpdate(BaseModel):
    narrative: str = Field(description="O texto narrativo da resposta.")
    introduced_npcs: List[str] = Field(default_factory=list, description="Lista de nomes de NOVOS personagens.")
    faction_impacts: List[FactionImpact] = Field(
        default_factory=list,
        description=(
            "Fações afetadas pela AÇÃO do jogador NESTE turno. Vazio se a ação não ajuda "
            "nem prejudica claramente uma fação listada. Use o faction_id EXATO."
        ),
    )
    beat_completed: bool = Field(
        default=False,
        description=(
            "True SOMENTE se a ação deste turno cumpriu de forma clara o Objetivo Atual "
            "da cena (o beat ativo). Caso contrário False. Não marque True por progresso vago."
        ),
    )
    proposed_events: List[ProposedWorldEvent] = Field(
        default_factory=list,
        description=(
            "APENAS se a ação deste turno causou mudança PERSISTENTE no mundo "
            "(morte de personagem NOMEADO, segredo revelado, mudança de controle de local). "
            "Use ids EXATOS do bloco <ENTIDADES_CANONICAS>. Deixe vazio na dúvida. "
            "Para CONCLUIR uma quest listada em <QUESTS_ATIVAS>, proponha um evento "
            "type='quest_completed' com target_id=quest_id e payload={'quest_id': quest_id}."
        ),
    )
    proposed_quests: List[ProposedQuest] = Field(
        default_factory=list,
        description=(
            "APENAS se um personagem PRESENTE NA CENA ofereceu uma missão CONCRETA ao "
            "jogador NESTE turno. origin_name = quem pediu; origin_entity_id = id EXATO "
            "do bloco <ENTIDADES_CANONICAS> se houver, senão vazio; location_id só se o "
            "destino for claro. Deixe vazio na dúvida — não invente missões."
        ),
    )
    items_gained: List[str] = Field(
        default_factory=list,
        description=(
            "APENAS se a narrativa deu um item CONCRETO ao jogador NESTE turno "
            "(recebeu, pegou, ganhou). Nome do item conhecido — NÃO invente itens "
            "novos (criação de item é papel do baú/loja). Vazio na dúvida."
        ),
    )


def _scene_canonical_entities(state: GameState, factions: list, intel: dict, loc: str) -> str:
    """Ids+nomes canônicos (entities.json) das entidades da cena — o LLM só pode usar estes.

    Fações conhecidas já trazem id canônico; local e NPCs presentes casam por nome com o
    grafo (best-effort). Defensivo: qualquer falha vira lista vazia (o validator é o gate real).
    """
    lines: List[str] = []
    seen = set()
    for f in factions:
        fid = f.get("id")
        if fid and intel.get(fid, {}).get("known") and not f.get("defeated") \
                and fid not in seen and gr.get_entity(fid):
            lines.append(f"- id={fid} · {f.get('name')} · faction")
            seen.add(fid)
    try:
        entities = gr.load_entities()
    except Exception:
        entities = {}
    names_present = {n.lower() for n in state.get("npcs", {}).keys()}
    loc_l = (loc or "").strip().lower()
    for eid, ent in entities.items():
        if eid in seen:
            continue
        etype, ename = ent.get("type"), ent.get("name", "")
        nl = ename.lower()
        if etype == "location" and loc_l and (nl == loc_l or eid == loc_l):
            lines.append(f"- id={eid} · {ename} · location")
            seen.add(eid)
        elif etype == "npc" and nl in names_present:
            lines.append(f"- id={eid} · {ename} · npc")
            seen.add(eid)
    return "\n".join(lines) or "Nenhuma entidade canônica identificada na cena."


def _quests_ativas_block(quests: List[Dict]) -> str:
    """Fase 3.3: side quests ativas — o LLM só pode referenciar estes ids em quest_completed."""
    ativas = [q for q in (quests or []) if q.get("status") == "active"]
    if not ativas:
        return "Nenhuma missão pendente registrada."
    return "\n".join(f"- id={q.get('id')} · {q.get('title')} · origem: {q.get('origin_name', '?')}"
                     for q in ativas)


def _with_new_npc(npcs: Dict[str, Dict], new_name: str, loc: str, narrative_text: str) -> Dict[str, Dict]:
    existing_lower = {name.lower(): name for name in npcs.keys()}
    if new_name.lower() in existing_lower: return npcs
    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl: return npcs
    new_npcs = dict(npcs)
    new_npcs[new_name] = {
        "name": tpl["name"], "role": tpl["role"], "persona": tpl["persona"],
        "location": loc, "relationship": tpl.get("initial_relationship", 5),
        "memory": [], "last_interaction": "",
        "attributes": tpl.get("attributes", {}), "combat_stats": tpl.get("combat_stats", {})
    }
    return new_npcs

def storyteller_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"messages": [AIMessage(content="Comece a história.")]}
    
    last_user_input = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    world = ensure_world(state.get("world", {}))

    # --- Fase 0: viagem / descanso (determinístico) ---
    # --- Fase 2: o tempo que passa avança as fações off-screen (mundo vivo) ---
    travel_note = rest_note = faction_note = ""
    rested_player = None
    factions = ensure_factions(state.get("factions"))
    intel = ensure_faction_intel(state.get("faction_intel"))
    dest = find_travel_destination(world, last_user_input) if last_user_input else None
    if dest:
        world = apply_travel(world, dest)
        factions, faction_events = advance_factions(factions, 1)  # viagem = 1 período
        factions, world, faction_note = resolve_faction_completions(factions, world, faction_events, intel)
        travel_note = (
            f"O jogador VIAJOU para {dest['name']}. "
            f"Contexto do local: {dest.get('lore_seed', '')} Descreva a chegada e o que ele vê agora."
        )
    elif last_user_input and is_rest(last_user_input):
        rested_player, world = apply_rest(dict(state.get("player", {})), world)
        factions, faction_events = advance_factions(factions, 2)  # descanso = 2 períodos
        factions, world, faction_note = resolve_faction_completions(factions, world, faction_events, intel)
        rest_note = (
            f"O jogador DESCANSOU. O tempo avançou para {clock_label(world)} e ele recuperou parte das forças. "
            "Narre a passagem do tempo e o estado do mundo ao acordar."
        )
    # (Ação livre: o gating é feito pelo PRÓPRIO narrador no prompt — sem chamada extra ao Ruler.)

    # --- O tempo passou (viagem/descanso): ou cai em emboscada, ou o mundo "respira" ---
    world_note = ""
    if dest or rested_player is not None:
        turn = int(world.get("turn_count", 0))
        enc = check_encounter(world, factions, intel, turn)
        if enc:
            # Emboscada: curto-circuita para o combate (sem simular — poupa quota).
            world["last_encounter_turn"] = turn
            updates = {
                "messages": [SystemMessage(content=f"COMBAT START. {enc['flavor']}")],
                "world": world,
                "factions": factions,
                "combat_target": enc["hint"],
                "next": "combat_agent",
                "archive_due": True,  # emboscada = evento relevante
            }
            if rested_player is not None:
                updates["player"] = rested_player  # já curou no descanso antes da emboscada
            # Fase 3.2 (R3): criatura nomeada no hint ANTES do combate = rumor (seen, sem fought).
            enemy_id = enc.get("enemy_id")
            if enemy_id:
                updates["bestiary_knowledge"] = disc.record_rumor(
                    state.get("bestiary_knowledge", {}), enemy_id, turn
                )
            return updates
        # Sem emboscada: o mundo gera 1 evento off-screen narrado (e grava no RAG da sessão).
        try:
            world, world_note = simulate_world(state, world, factions, intel, 1 if dest else 2)
        except Exception:
            world_note = ""

    loc = world.get("current_location", "")
    existing_npcs = list(state.get("npcs", {}).keys())
    
    # --- Contexto Híbrido ---
    game_id = state.get("game_id")
    narrative_summary = state.get("narrative_summary", "")
    
    # --- Fase 2.8: contexto centralizado (estado dinâmico + lore + memória, com budget) ---
    # ESTADO ATUAL entra ANTES da lore base: a verdade viva vence o canônico.
    pack = build_context_pack(state, query=f"{loc} {last_user_input}",
                              purpose="story", game_id=game_id)
    lore_context = pack.lore_block or "Dark Fantasy Genérica."
    memoria_recente = pack.memory_block or narrative_summary

    campaign_plan = state.get("campaign_plan") or {}
    beats = [dict(beat) for beat in campaign_plan.get("beats", [])]
    current_step = campaign_plan.get("current_step", 0)
    active_step = beats[current_step].get("description") if current_step < len(beats) else "Clímax ou Ação Livre."

    llm = get_llm(temperature=0.7)
    
    # PROMPT ATUALIZADO
    eventos_turno = "\n".join(n for n in (travel_note, rest_note, faction_note, world_note) if n) or "Nenhum evento especial."

    # Fações que o JOGADOR conhece (não-onisciência): só estas podem ser citadas/afetadas.
    faccoes_conhecidas = "\n".join(
        f"- id={f.get('id')} · {f.get('name')} ({f.get('region','')}) · disposição={f.get('disposition','neutro')}"
        for f in factions
        if intel.get(f.get("id"), {}).get("known") and not f.get("defeated")
    ) or "Nenhuma fação conhecida pelo jogador ainda."

    # Fase 2.6: ids canônicos que o LLM pode usar em proposed_events (defesa em profundidade).
    entidades_canonicas = _scene_canonical_entities(state, factions, intel, loc)
    # Fase 3.3: quests ativas que o LLM pode concluir via proposed_events(quest_completed).
    quests_ativas = _quests_ativas_block(state.get("quests", []))

    sys = SystemMessage(content=f"""
    <PERSONA>
    Você é o Narrador (Mestre) de um RPG.
    Local Atual: {loc}.
    Momento: {clock_label(world)}.
    NPCs na cena: {existing_npcs}.
    Objetivo Atual: {active_step}
    </PERSONA>

    <EVENTOS_DESTE_TURNO>
    {eventos_turno}
    </EVENTOS_DESTE_TURNO>

    <FACÇÕES_CONHECIDAS>
    {faccoes_conhecidas}
    Se a ação do jogador NESTE turno claramente ajudar ou prejudicar uma destas fações,
    registre em 'faction_impacts' (faction_id EXATO + direction 'ajudou'/'prejudicou').
    Caso contrário, deixe 'faction_impacts' vazio. NÃO invente ids fora da lista.
    </FACÇÕES_CONHECIDAS>

    <ENTIDADES_CANONICAS>
    {entidades_canonicas}
    Se — e SÓ se — a ação deste turno causou mudança PERSISTENTE no mundo (morte de
    personagem NOMEADO, segredo revelado, mudança de controle de local), registre em
    'proposed_events' usando os ids EXATOS acima. Na dúvida, deixe vazio. NUNCA invente
    ids fora desta lista.
    </ENTIDADES_CANONICAS>

    <QUESTS_ATIVAS>
    {quests_ativas}
    Se um personagem PRESENTE NA CENA ofereceu uma missão concreta ao jogador NESTE
    turno, registre em 'proposed_quests' (origem = quem pediu; location_id só se o
    destino é claro). Se a ação deste turno CONCLUIU uma das quests listadas acima,
    proponha em 'proposed_events' um evento type='quest_completed' com
    target_id=quest_id e payload={{"quest_id": quest_id}} usando o id EXATO. Na
    dúvida, deixe vazio. NUNCA invente ids.
    </QUESTS_ATIVAS>

    {pack.world_state_block}
    (Se o ESTADO ATUAL DO MUNDO acima contradisser o lore/fatos passados abaixo, o ESTADO ATUAL VENCE.)

    <MEMORIA_RECENTE>
    Resumo dos fatos anteriores: {memoria_recente}
    </MEMORIA_RECENTE>

    <LORE_E_FATOS_PASSADOS>
    {lore_context}
    </LORE_E_FATOS_PASSADOS>

    <INSTRUÇÕES>
    - Responda em 2 a 3 parágrafos.
    - JULGUE a ação: se for implausível para a classe/ficha do personagem ({state.get('player', {}).get('class_name', '')})
      ou impossível no contexto, faça-a FALHAR de forma crível na narração (não conceda o impossível).
    - Termine com opções ou pergunta para ação.
    - Se introduzir NPC novo, adicione em 'introduced_npcs'.
    """)

    try:
        story_engine = llm.with_structured_output(StoryUpdate)
        update = story_engine.invoke([sys] + messages[-3:]) # Contexto reduzido

        narrative_text = update.narrative

        # --- Fase 2: a ação do jogador altera a reputação das fações (Python resolve) ---
        # A IA só identifica fação + direção; apply_reputation valida o id e fixa o delta.
        # Fase 3.4: cada mudança vira proposta reputation_changed (Python, não LLM) —
        # entra no event_log auditável pelo mesmo pipeline 2.6, alimenta a timeline.
        rep_events = []
        for imp in getattr(update, "faction_impacts", []) or []:
            fid = getattr(imp, "faction_id", "")
            direction = getattr(imp, "direction", "")
            factions, rep_ev = apply_reputation(factions, fid, direction)
            if rep_ev:
                rep_events.append({
                    "type": "reputation_changed", "actor_id": "player", "target_id": rep_ev["id"],
                    "payload": {"delta": rep_ev["delta"], "new_value": rep_ev["reputation"],
                               "reason": rep_ev["direction"]},
                    "source": "storyteller",
                })

        # --- Avanço de beat: o narrador sinaliza quando o objetivo da cena foi cumprido ---
        needs_replan = state.get("needs_replan", False)
        updated_plan = campaign_plan
        beat_done = bool(getattr(update, "beat_completed", False))
        # Fase 4.1: beat concluído = XP determinístico (o LLM só sinaliza o beat;
        # valor/level up são do motor). Level ups viram eventos source="progression".
        leveled_player = None
        level_up_events: list = []
        # Cena de abertura roda com turn_count==1 (campaign_manager incrementa antes):
        # narrador generoso marcando beat no prólogo não pode virar XP grátis na
        # criação (achado do smoke real 2026-07-05). XP de beat só do turno 2 em diante.
        if beat_done and int(world.get("turn_count", 0) or 0) > 1:
            from progression import grant_xp, XP_PER_BEAT
            base_p = rested_player if rested_player is not None else dict(state.get("player") or {})
            leveled_player, level_up_events = grant_xp(base_p, XP_PER_BEAT)
        if campaign_plan and beats and beat_done and current_step < len(beats):
            beats[current_step] = {**beats[current_step], "status": "done"}
            new_step = current_step + 1
            updated_plan = {**campaign_plan, "beats": beats, "current_step": new_step}
            # Esgotou os beats → próximo turno o campaign_manager replaneja (vê _should_replan).
            if new_step >= len(beats):
                needs_replan = True

        npcs = state.get("npcs", {})
        new_npcs = npcs
        for new_name in update.introduced_npcs:
            new_npcs = _with_new_npc(new_npcs, new_name, loc, narrative_text)

        updates = {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": new_npcs,
            "world": world,
            "factions": factions,
            "campaign_plan": updated_plan,
            "needs_replan": needs_replan,
        }
        if rested_player is not None:
            updates["player"] = rested_player
        if leveled_player is not None:  # Fase 4.1: XP do beat (inclui o descanso, se houve)
            updates["player"] = leveled_player

        # Fase 4.3 (R5): item narrado ENTRA no inventário — só se resolver no
        # ARTIFACTS_DB (storyteller não cria item; isso é papel do loot_node).
        gained = [g for g in (getattr(update, "items_gained", []) or []) if str(g).strip()]
        if gained:
            from inventory import add_item, is_unique, resolve_item_name
            from services.economy import claim_event, is_unique_available
            proj = state.get("world_projection") or {}
            cur_p = dict(updates.get("player") or state.get("player") or {})
            inv = list(cur_p.get("inventory") or [])
            changed = False
            for g in gained:
                iid = resolve_item_name(str(g))
                if not iid:
                    print(f"⚠️ [STORYTELLER] item narrado desconhecido ignorado: {g!r}")
                    continue
                # Fase 6.2: único já reclamado NUNCA re-entra pela narrativa
                if is_unique(iid) and not is_unique_available(iid, proj):
                    print(f"⚠️ [STORYTELLER] item ÚNICO já reclamado ignorado: {iid}")
                    continue
                inv = add_item(inv, iid, 1)
                changed = True
                if is_unique(iid):
                    rep_events.append(claim_event(iid, "player"))
            if changed:
                cur_p["inventory"] = inv
                updates["player"] = cur_p
        # Viagem/descanso/beat concluído = evento relevante → pede arquivamento.
        if dest or rested_player is not None or beat_done:
            updates["archive_due"] = True
        # Fase 2.6: enfileira propostas de evento estruturado (motor valida no archivist).
        # Fase 3.4: reputation_changed (Python) entra na mesma fila. 4.1: level_up idem.
        pending = ([e.model_dump() for e in getattr(update, "proposed_events", []) or []]
                   + rep_events + level_up_events)
        if pending:
            updates["pending_world_events"] = (state.get("pending_world_events", []) or []) + pending
            updates["archive_due"] = True  # mudança de mundo é evento relevante

        # Fase 3.3: side quests propostas nesta cena (validadas/criadas em Python).
        turn = int(world.get("turn_count", 0))
        new_quests, created = quest_log.register_proposed_quests(
            state.get("quests", []), getattr(update, "proposed_quests", []) or [], turn=turn
        )
        if created:
            updates["quests"] = new_quests
            updates["archive_due"] = True  # nova missão é evento relevante
        return updates

    except Exception as e:
        print(f"[STORYTELLER ERROR] {e}")
        return {"messages": [AIMessage(content="O destino é incerto... (Erro AI).")]}