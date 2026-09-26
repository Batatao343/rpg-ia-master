"""Narration agent that advances the story and campaign plan."""
import random
import re
from collections import Counter
from copy import deepcopy
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
    is_travel_intent,
    resolve_faction_completions,
)


class FactionImpact(BaseModel):
    faction_id: str = Field(description="id EXATO de uma fação listada em <FACÇÕES_CONHECIDAS>; vazio se nenhuma.")
    direction: str = Field(description="'ajudou' (jogador beneficiou a fação) ou 'prejudicou' (jogador a atrapalhou/traiu/atacou).")


class StoryUpdate(BaseModel):
    # default "" (não required): Gemini real às vezes omite o campo num schema
    # grande — melhor narrar via fallback do que perder o turno (smoke 2026-07-05)
    narrative: str = Field(default="", description="O texto narrativo da resposta. OBRIGATÓRIO: sempre preencha.")
    introduced_npcs: List[str] = Field(
        default_factory=list,
        description="Nomes de personagens que ENTRARAM na cena neste turno (novos ou conhecidos que reapareceram).")
    npcs_left_scene: List[str] = Field(
        default_factory=list,
        description="Nomes de personagens JÁ CONHECIDOS que SAÍRAM da cena neste turno (foram embora, morreram, sumiram). Vazio se ninguém saiu.")
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


_MONEY_CLAIM_RE = re.compile(r"\b(?:ouro|moedas?)\b", re.IGNORECASE)


def _is_monetary_claim(value: object) -> bool:
    """Dinheiro é economia, nunca um item a resolver pelo nome livre do LLM."""
    return bool(_MONEY_CLAIM_RE.search(str(value or "")))


def _inventory_counts(player: dict) -> Counter:
    counts: Counter = Counter()
    for entry in player.get("inventory") or []:
        if isinstance(entry, dict) and entry.get("id"):
            counts[str(entry["id"])] += int(entry.get("qty", 1) or 1)
    return counts


def _reward_confirmation(before: dict, after: dict) -> str:
    """Linha canônica derivada somente do delta mecânico confirmado."""
    rewards: List[str] = []
    gold_delta = int(after.get("gold", 0) or 0) - int(before.get("gold", 0) or 0)
    if gold_delta > 0:
        rewards.append(f"+{gold_delta} de ouro")
    before_items = _inventory_counts(before)
    after_items = _inventory_counts(after)
    if after_items:
        from inventory import item_display, make_entry
        for item_id, qty in (after_items - before_items).items():
            label = item_display(make_entry(item_id))
            rewards.append(f"{label}" + (f" ×{qty}" if qty > 1 else ""))
    return "Recompensa confirmada: " + ", ".join(rewards) + "." if rewards else ""


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


def _npc_fallback_clause(state: GameState) -> str:
    """spec npc-fallback-sem-alvo (R2): quando a rota NPC não achou interlocutor,
    o storyteller narra a AUSÊNCIA (sem inventar NPC em cena) e dá um gancho útil
    (onde há gente / o objetivo atual). Pura — testável sem LLM."""
    hint = state.get("npc_fallback_hint")
    if not hint:
        return ""
    from services.social_direction import build_social_direction
    direction = build_social_direction(state)
    return (f"\n    - SEM INTERLOCUTOR: o jogador tentou falar com alguém "
            f'("{str(hint)[:120]}"), mas NÃO há ninguém por perto para responder. '
            "Narre a solidão/silêncio SEM inventar um NPC novo em cena, e ofereça "
            f"esta direção ÚTIL e canônica: {direction}")


def _player_facing_note(note: str) -> str:
    """Converte notas de prompt em texto diegético; não vaza imperativos internos."""
    text = str(note or "").strip()
    if not text:
        return ""
    text = re.sub(r"^O jogador VIAJOU para ", "Após a viagem, você chega a ", text)
    text = re.sub(r"^O jogador ENTROU em ", "Você entra em ", text)
    text = re.sub(
        r"^O jogador ENCONTROU um baú/esconderijo em ([^:]+):\s*",
        r"Entre os vestígios de \1, você encontra um baú/esconderijo: ", text)
    text = re.sub(
        r"^Ao explorar ([^,]+), o jogador ENCONTROU:\s*",
        r"Ao explorar \1, você encontra ", text)
    text = re.sub(r"\s*Descreva\b[^.]*\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*Narre\b[^.]*\.?", "", text, flags=re.IGNORECASE)
    from services import prose_guard
    return prose_guard.sanitize_player_facing(text)


def _deterministic_story_fallback(notes, light: dict) -> str:
    """Fallback visível e contextual; nunca expõe erro de provider ao jogador."""
    parts = [_player_facing_note(note) for note in notes if str(note or "").strip()]
    parts = [part for part in parts if part]
    if light.get("dark"):
        parts.append(
            "Sem fonte de luz, a escuridão limita sua visão; sons e cheiros "
            "chegam antes das formas."
        )
    elif light.get("label") == "iluminado pela sua luz":
        parts.append(
            "A luz que você carrega abre um círculo trêmulo no breu e revela "
            "o espaço imediato."
        )
    return "\n".join(parts) or (
        "O momento passa em silêncio; o mundo aguarda seu próximo passo."
    )
def _with_new_npc(npcs: Dict[str, Dict], new_name: str, loc: str, narrative_text: str,
                  game_id: str = "", home_id: str = "", turn: int = 0) -> Dict[str, Dict]:
    from services import npc_layers
    from services.entity_identity import find_runtime_npc_key

    canonical = find_runtime_npc_key(npcs, new_name)
    if canonical is not None:
        # já conhecido: a cena o trouxe de volta (camada 3).
        # spec encontros-dedupe (exceção narrativa): re-introduzir um NPC conhecido
        # é uma decisão DELIBERADA do narrador/player (com o filtro R1 ele nem
        # aparece no contexto fora do seu local, então não há reuso passivo). Logo,
        # se ele foi trazido para OUTRO local (viajou junto, mandado em missão),
        # RELOCALIZA — o home_location_id passa a ser o local atual.
        new_npcs = dict(npcs)
        if isinstance(new_npcs.get(canonical), dict):
            atual = new_npcs[canonical]
            new_npcs[canonical] = {
                **atual, "in_scene": True, "last_seen_turn": turn,
                "home_location_id": home_id or atual.get("home_location_id", ""),
            }
        return new_npcs
    tpl = generate_new_npc(new_name, context=f"Local: {loc}. Cena: {narrative_text}")
    if not tpl: return npcs
    # O librarian/cache pode resolver uma referência técnica para uma ficha já
    # presente (ex.: npc_skriit_mil_olhos -> Skriit Mil-olhos). Revalida APÓS
    # a fábrica para não inserir o mesmo id sob uma segunda chave.
    canonical = find_runtime_npc_key(npcs, new_name, tpl)
    if canonical is not None:
        new_npcs = dict(npcs)
        atual = dict(new_npcs[canonical])
        new_npcs[canonical] = {
            **atual,
            "in_scene": True,
            "last_seen_turn": turn,
            "home_location_id": home_id or atual.get("home_location_id", ""),
        }
        return new_npcs
    new_npcs = dict(npcs)
    # A fábrica já devolve a ficha v4 materializada. Ela é a fonte da verdade:
    # recompor aqui apenas os campos antigos apagava Virtudes, Vitalidade,
    # Ferimentos e o perfil tático persistido.
    novo = dict(tpl)
    novo.setdefault("name", new_name)
    novo.setdefault("role", "Desconhecido")
    novo.setdefault("persona", "")
    novo["location"] = loc
    novo.setdefault("relationship", tpl.get("initial_relationship", 5))
    novo.setdefault("memory", [])
    novo.setdefault("last_interaction", "")
    novo.setdefault("attributes", {})
    novo.setdefault("combat_stats", {})
    # spec encontros-dedupe (R1/R2): vínculo de local + turnos p/ cooldown/invariante.
    novo.setdefault("created_turn", turn)
    novo["last_seen_turn"] = turn
    # spec npcs-3-camadas: quem a cena introduziu está EM cena e é conhecido.
    novo = npc_layers.ensure_npc_fields(novo, game_id, home_location_id=home_id,
                                        in_scene=True)
    new_npcs[str(novo.get("name") or new_name)] = novo
    return new_npcs

def storyteller_node(state: GameState):
    messages = state.get("messages", [])
    if not messages: return {"messages": [AIMessage(content="Comece a história.")]}
    
    last_user_input = messages[-1].content if isinstance(messages[-1], HumanMessage) else ""
    from services.actor_lifecycle import is_recovery_turn
    recovery_turn = is_recovery_turn(state)
    if recovery_turn:
        # Recovery is passage of time/treatment, never permission for another action.
        last_user_input = "Descanso e aguardo socorro."
    world = ensure_world(state.get("world", {}))

    # --- Fase 0: viagem / descanso (determinístico) ---
    # --- Fase 2: o tempo que passa avança as fações off-screen (mundo vivo) ---
    travel_note = rest_note = faction_note = ""
    rested_player = None
    factions = ensure_factions(state.get("factions"))
    intel = ensure_faction_intel(state.get("faction_intel"))
    travel_intent = bool(
        last_user_input and is_travel_intent(str(last_user_input))
    )
    dest = (
        find_travel_destination(world, last_user_input)
        if travel_intent else None
    )
    if travel_intent and not dest:
        try:
            from world_utils import invalid_travel_message
            refusal = invalid_travel_message(world, str(last_user_input))
        except (ImportError, AttributeError):
            refusal = ""
        if refusal:
            # Recusa canônica antes da LLM: destino impossível nunca aparece como
            # chegada na mensagem, no resumo nem na memória.
            return {
                "messages": [AIMessage(content=refusal)],
                "world": world,
                "archive_due": False,
            }
    travel_periods = 0
    discovery_events: list = []
    reward_player_before = deepcopy(state.get("player") or {})
    discovery_player = None
    if dest:
        from world_utils import travel_cost
        travel_periods = travel_cost(world, dest)  # custo ANTES de mover (usa origem)
        # spec loot-exploracao (R1): fog of war checado ANTES de apply_travel (que
        # carimba `visited`). Baú curado (R3) pode reconceder-se? Não — one-shot.
        first_visit = dest["id"] not in (world.get("visited") or [])
        world = apply_travel(world, dest)
        factions, faction_events = advance_factions(factions, travel_periods)
        factions, world, faction_note = resolve_faction_completions(factions, world, faction_events, intel)
        # spec loot-exploracao: achado ambiental (1ª visita) OU baú curado (sempre
        # que houver e não saqueado). Muta player.inventory/gold + world in-place
        # (propaga: viagem sem descanso não substitui o player no updates parcial).
        _pl = deepcopy(state.get("player"))
        if isinstance(_pl, dict) and (first_visit or (dest.get("treasure"))):
            from services import exploration
            _rng = exploration.arrival_rng(
                str(state.get("game_id", "")), dest["id"],
                int(world.get("turn_count", 0) or 0))
            disc_note, discovery_events = exploration.discover_on_arrival(
                _pl, world, dest, int(_pl.get("level", 1) or 1), _rng,
                projection=state.get("world_projection"))
            if disc_note:
                faction_note = (faction_note + " " + disc_note).strip()
            discovery_player = _pl
        if travel_periods == 0:
            travel_note = (
                f"O jogador ENTROU em {dest['name']} (mesma cidade — o tempo não passou). "
                f"Contexto do local: {dest.get('lore_seed', '')} Descreva o que ele vê ao entrar."
            )
        else:
            travel_note = (
                f"O jogador VIAJOU para {dest['name']}"
                + (f" (viagem longa: {travel_periods} períodos). " if travel_periods > 1 else ". ")
                + f"Contexto do local: {dest.get('lore_seed', '')} Descreva a chegada e o que ele vê agora."
            )
    elif last_user_input and is_rest(last_user_input):
        from world_utils import weather_effects
        rest_blocked = weather_effects(world).get("rest_block", False)  # Fase 6.5
        # spec refatoracao-sistema-classes (R6): aliado ativo mitiga a Insônia do Devoto.
        import party as _party_mod
        _rest_allies = _party_mod.active_allies(state)
        rested_player, world = apply_rest(dict(state.get("player", {})), world,
                                          allies=_rest_allies)
        factions, faction_events = advance_factions(factions, 2)  # descanso = 2 períodos
        factions, world, faction_note = resolve_faction_completions(factions, world, faction_events, intel)
        if rest_blocked:
            rest_note = (
                f"O jogador TENTOU descansar, mas o clima ({world.get('weather', 'o miasma')}) "
                f"NÃO permite descanso seguro ao relento — NADA foi recuperado e o tempo passou "
                f"({clock_label(world)}). Narre a noite péssima e a exaustão."
            )
        else:
            rest_note = (
                f"O jogador DESCANSOU. O tempo avançou para {clock_label(world)} e ele recuperou parte das forças. "
                "Narre a passagem do tempo e o estado do mundo ao acordar."
            )
    # Viagem fecha a cena anterior antes de qualquer encontro ou contexto. Isso
    # também protege retornos antecipados de combate contra NPCs teleportados.
    from services import npc_layers
    scene_npcs = (
        npc_layers.reset_scene(state.get("npcs", {}))
        if dest else state.get("npcs", {})
    )
    scene_state = {**state, "world": world, "npcs": scene_npcs}
    travel_needs_replan = bool(state.get("needs_replan"))
    if dest:
        from agents.campaign_manager import _same_region
        planned_location = str((state.get("campaign_plan") or {}).get("location") or "")
        if planned_location and not _same_region(
            planned_location, str(world.get("current_location") or ""),
        ):
            travel_needs_replan = True

    # (Ação livre: o gating é feito pelo PRÓPRIO narrador no prompt — sem chamada extra ao Ruler.)

    # --- O tempo passou (viagem/descanso): ou cai em encontro, ou o mundo "respira" ---
    world_note = ""
    extra_engine_events: list = []
    track_bk = None  # Fase 6.4: rastro atualiza o Codex do jogador
    # spec mapa-sublocais (R2): custo 0 (intra-cidade/interior) não rola encontro
    if (dest and travel_periods >= 1) or rested_player is not None:
        turn = int(world.get("turn_count", 0))
        # R5 (fix-playtest-achados): a FORÇA do encontro escala pelo nível (apex não).
        _plevel = int((state.get("player") or {}).get("level", 1) or 1)
        from world_utils import recovery_rest_safe
        from gamedata import get_location as _get_location
        danger_now = int(world.get("danger_level", 1) or 1)
        # spec letalidade-early-game-v2 (alavanca 1): um DESCANSO de early-game em
        # zona não-apex de perigo baixo recupera SEM sortear encontro — o laço de
        # recuperação que faltava (viagem não cura; descanso interrompido = morte).
        # Só vale pra REST (rested_player is not None), nunca pra viagem.
        _rest_recovers = (rested_player is not None
                          and recovery_rest_safe(_plevel, danger_now,
                                                 _get_location(world.get("current_location_id", "")) or {}))
        if _rest_recovers:
            enc = None
        else:
            # Fase 6.3: sorteio ponderado — pressão de caça/fação/migração
            enc = check_encounter(world, factions, intel, turn,
                                  bestiary_knowledge=state.get("bestiary_knowledge"),
                                  projection=state.get("world_projection"),
                                  player_level=_plevel)
        # spec encontros-dedupe (R3): não repete o MESMO template de encontro 2x
        # seguidas no mesmo local (o mundo não é um carrossel).
        if enc and enc.get("hint") and enc.get("hint") == world.get("last_encounter_id") \
                and world.get("last_encounter_loc") == world.get("current_location_id"):
            enc = None
        if enc:
            world["last_encounter_turn"] = turn
            world["last_encounter_id"] = enc.get("hint")
            world["last_encounter_loc"] = world.get("current_location_id")
            danger = int(world.get("danger_level", 1) or 1)
            base_p = (
                rested_player if rested_player is not None
                else dict(discovery_player or state.get("player") or {})
            )

            # Fase 6.4 (R1): percepção decide surpresa; (R2): nem todo perigo é combate.
            # Reforço/fação dominante SEMPRE é combate (eles vieram POR você).
            from world_utils import (detection_check, resolve_trap, resolve_track,
                                     roll_encounter_type, weather_effects, light_level)
            # Fase 6.5: neblina/vendaval atrapalham a percepção.
            # spec itens-vivos-e-luz (R3): escuridão sem luz também penaliza.
            _perc_mod = (weather_effects(world).get("perception_mod", 0)
                         + light_level(world, base_p).get("perception_mod", 0))
            det = detection_check(base_p, danger, perception_mod=_perc_mod)
            kind = ("combat" if enc.get("reason") in ("reinforcements", "controlled")
                    else roll_encounter_type(danger))

            if kind == "combat":
                from services.combat_origin import from_encounter
                # surpresa: percebeu -> herói embosca; falhou -> inimigo age antes
                world["encounter_surprise"] = "player" if det["perceived"] else "enemy"
                # R5: percebeu = tem AGÊNCIA — pode golpear OU recuar (a fuga já é
                # mecânica no combate: "fujo/corro/recuo"). Surpreendido = sem saída.
                sur_txt = ("Você os percebe ANTES — há tempo de golpear primeiro OU RECUAR "
                           "(diga que foge/corre/recua para escapar)."
                           if det["perceived"] else
                           "Eles saem do nada — você é pego de surpresa, sem chance de recuar.")
                updates = {
                    "messages": [SystemMessage(content=f"COMBAT START. {enc['flavor']} {sur_txt}")],
                    "world": world,
                    "factions": factions,
                    "combat_target": enc["hint"],
                    "combat_origin_hint": from_encounter(
                        enc, world, trigger=("rest" if rested_player is not None else "travel"),
                    ),
                    "next": "combat_agent",
                    "archive_due": True,  # emboscada = evento relevante
                    "npcs": scene_npcs,
                    "needs_replan": travel_needs_replan,
                }
                if rested_player is not None:
                    updates["player"] = rested_player  # já curou no descanso antes da emboscada
                elif discovery_player is not None:
                    updates["player"] = discovery_player
                # spec loot-exploracao: claim de único do baú curado não se perde
                # se um encontro disparar na mesma chegada.
                if discovery_events:
                    updates["pending_world_events"] = (
                        state.get("pending_world_events", []) or []) + discovery_events
                # Fase 3.2 (R3): criatura nomeada no hint ANTES do combate = rumor.
                enemy_id = enc.get("enemy_id")
                if enemy_id:
                    updates["bestiary_knowledge"] = disc.record_rumor(
                        state.get("bestiary_knowledge", {}), enemy_id, turn)
                return updates

            from gamedata import get_location
            loc_node = get_location(world.get("current_location_id", "")) or {}
            if kind == "trap":
                from party import active_allies
                helper = next(iter(active_allies(state)), None)
                new_p, trap_logs, info = resolve_trap(
                    base_p, loc_node, danger, helper=helper,
                )
                rested_player = new_p  # reusa o encanamento de player existente
                world_note = "ENCONTRO NA ESTRADA (armadilha — números JÁ resolvidos, narre-os):\n" \
                    + "\n".join(trap_logs)
                if info:
                    extra_engine_events += info.get("level_up_events", [])
            elif kind == "track":
                track_bk, note, hint = resolve_track(state.get("bestiary_knowledge", {}),
                                                     loc_node, danger, turn)
                if hint:
                    world["treasure_hint"] = True
                world_note = f"ENCONTRO NA ESTRADA (rastro): {note}"
            else:  # social
                world_note = (
                    "ENCONTRO NA ESTRADA (social): um grupo HOSTIL-MAS-NEGOCIÁVEL aborda o "
                    "jogador (ligado ao perigo local). Narre a abordagem tensa SEM iniciar "
                    "combate — eles querem algo (pedágio, informação, escolta). Se surgir um "
                    "porta-voz, registre-o em introduced_npcs.")
        # Sem emboscada: o mundo gera 1 evento off-screen narrado (e grava no RAG da sessão).
        try:
            world, world_note = simulate_world(state, world, factions, intel, 1 if dest else 2)
        except Exception:
            world_note = ""

    loc = world.get("current_location", "")
    # spec encontros-dedupe (R1): só NPCs vinculados ao local/em cena/party —
    # NPC gerado em outro lugar não é reciclado nesta cena.
    from services.npc_layers import npcs_for_context
    scene_state = {**scene_state, "world": world}
    existing_npcs = npcs_for_context(scene_state)
    
    # --- Contexto Híbrido ---
    game_id = state.get("game_id")
    # --- Fase 2.8: contexto centralizado (estado dinâmico + lore + memória, com budget) ---
    # ESTADO ATUAL entra ANTES da lore base: a verdade viva vence o canônico.
    pack = build_context_pack(scene_state, query=f"{loc} {last_user_input}",
                              purpose="story", game_id=game_id)
    lore_context = pack.lore_block or "Dark Fantasy Genérica."
    memoria_recente = pack.memory_block or "Sem memória recente dentro do budget deste turno."
    # spec arvores-habilidade-classes (§3.3): utilitárias conhecidas — gate
    # determinístico; a LLM só narra o que a ficha PERMITE.
    from services.context_builder import utility_context_block
    capacidades_block = utility_context_block(state.get("player", {}) or {})

    # spec itens-vivos-e-luz (R7): ambiente de luz na narração.
    from world_utils import light_level as _light_level
    _ll = _light_level(world, state.get("player", {}) or {})
    if _ll.get("dark"):
        luz_block = ("<AMBIENTE_DE_LUZ>\n    Está ESCURO e o herói NÃO tem fonte de luz. "
                     "Descreva a visão limitada — sombras, sons e cheiros antes de formas; "
                     "o perigo pode surgir de perto. (Percepção e mira sofrem.)\n    </AMBIENTE_DE_LUZ>")
    elif _ll.get("label") == "iluminado pela sua luz":
        luz_block = ("<AMBIENTE_DE_LUZ>\n    A luz que o herói carrega empurra a escuridão "
                     "num círculo trêmulo; além dele, o breu. Mencione a luz.\n    </AMBIENTE_DE_LUZ>")
    else:
        luz_block = ""
    from world_utils import weather_effects as _weather_effects
    _weather = _weather_effects(world)
    weather_note = ""
    clima_block = ""
    if world.get("weather_global"):
        weather_note = (
            f"Fenômeno global ativo: {_weather.get('label', 'clima anômalo')}. "
            "Ele domina o céu e afeta toda a cena."
        )
        clima_block = (
            "<CLIMA_GLOBAL>\n    " + weather_note
            + " Mencione sua presença e consequências sensoriais.\n    </CLIMA_GLOBAL>"
        )

    campaign_plan = state.get("campaign_plan") or {}
    beats = [dict(beat) for beat in campaign_plan.get("beats", [])]
    current_step = campaign_plan.get("current_step", 0)
    beat_eligible = (
        isinstance(current_step, int) and not isinstance(current_step, bool)
        and 0 <= current_step < len(beats)
        and beats[current_step].get("status", "pending") in {"pending", "active"}
    )
    active_step = beats[current_step].get("description") if beat_eligible else "Clímax ou Ação Livre."

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
    entidades_canonicas = _scene_canonical_entities(scene_state, factions, intel, loc)
    # Fase 3.3: quests ativas que o LLM pode concluir via proposed_events(quest_completed).
    quests_ativas = _quests_ativas_block(state.get("quests", []))

    # spec npc-fallback-sem-alvo (R2): rota NPC sem interlocutor delegou aqui.
    npc_fallback_clause = _npc_fallback_clause(scene_state)
    # spec polish-prosa: R1 (varie a abertura) + R3 (menu de opções concretas).
    from services import prose_guard
    _aberturas = prose_guard.ultimas_aberturas(messages)
    varie_clause = prose_guard.openings_clause(_aberturas)
    opcoes_clause = ("\n    - FECHE com 2 a 3 OPÇÕES concretas de ação, cada uma numa "
                     "linha iniciada por '— ', e termine com '— Ou outra ação.' "
                     "(dê rumo ao jogador; as opções mecânicas de combate vêm à parte).")
    _hero = state.get("player", {}) or {}
    hero_state_block = (
        "<ESTADO_DO_HEROI>\n"
        f"Nível: {int(_hero.get('level', 1) or 1)} · "
        f"Vitalidade: {int(_hero.get('vitalidade', _hero.get('hp', 0)) or 0)}/"
        f"{int(_hero.get('max_vitalidade', _hero.get('max_hp', 0)) or 0)} · "
        f"Ouro: {int(_hero.get('gold', 0) or 0)}\n"
        "Se mencionar o saldo do herói, use EXATAMENTE esse Ouro.\n"
        "</ESTADO_DO_HEROI>"
    )

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
    {luz_block}
    {clima_block}
    {hero_state_block}

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

    {capacidades_block}

    {pack.world_state_block}
    (Se o ESTADO ATUAL DO MUNDO acima contradisser o lore/fatos passados abaixo, o ESTADO ATUAL VENCE.)

    <MEMORIA_RECENTE>
    Resumo dos fatos anteriores: {memoria_recente}
    </MEMORIA_RECENTE>

    <LORE_PUBLICO_CANONICO>
    {lore_context}
    </LORE_PUBLICO_CANONICO>

    <INSTRUÇÕES>
    - Responda em 2 a 3 parágrafos.
    - JULGUE a ação: se for implausível para a classe/ficha do personagem ({state.get('player', {}).get('class_name', '')})
      ou impossível no contexto, faça-a FALHAR de forma crível na narração (não conceda o impossível).
    - Não afirme como cânone nome, item, facção, local ou evento ausente do ESTADO,
      da MEMÓRIA ou do LORE PÚBLICO acima. Quando faltar base, descreva incerteza
      ou admita que o personagem não sabe; não preencha a lacuna com fato novo.
    - Termine com opções ou pergunta para ação.
    - Se um personagem ENTRAR na cena (novo ou conhecido que reapareceu), adicione o nome em 'introduced_npcs'.
    - Se um personagem conhecido SAIR da cena (foi embora, sumiu), adicione o nome em 'npcs_left_scene'.{npc_fallback_clause}{varie_clause}{opcoes_clause}
    """)

    try:
        story_engine = llm.with_structured_output(StoryUpdate)
        update = story_engine.invoke([sys] + messages[-3:]) # Contexto reduzido

        # Guard crítico: FallbackLLM devolve AIMessage, não o schema solicitado.
        if not isinstance(update, StoryUpdate):
            update = StoryUpdate(narrative=_deterministic_story_fallback(
                (travel_note, rest_note, world_note, faction_note, weather_note), _ll,
            ))

        narrative_text = update.narrative
        # Pré-validação read-only das propostas da própria LLM. O processor no
        # archivist continua sendo o único escritor, mas a mensagem visível não
        # pode afirmar como fato uma mudança que ele rejeitará logo depois.
        from services.event_processor import prevalidate_event_batch
        llm_event_proposals = [
            event.model_dump() if hasattr(event, "model_dump") else dict(event)
            for event in (getattr(update, "proposed_events", []) or [])
        ]
        invalid_story_events = []
        preview_state = {
            **state,
            "world": world,
            "event_log": list(state.get("event_log") or []),
        }
        validations = prevalidate_event_batch(llm_event_proposals, preview_state)
        for proposal, validation in zip(llm_event_proposals, validations):
            if not validation.ok:
                invalid_story_events.append({
                    "type": str(proposal.get("type") or ""),
                    "target_id": str(proposal.get("target_id") or ""),
                    "reason": str(validation.reason or "")[:240],
                })
        # Política atômica/conservadora: uma proposta inválida põe em quarentena
        # TODO o payload livre da mesma resposta. Mantemos apenas as propostas
        # inválidas na fila para auditoria; propostas irmãs aparentemente válidas
        # não podem virar mudanças silenciosas depois que a narrativa foi descartada.
        quarantine_llm_payload = bool(invalid_story_events)
        pending_llm_events = (
            [
                {
                    "type": rejected["type"],
                    "target_id": rejected["target_id"],
                    "actor_id": "player",
                    "payload": {},
                    "source": "storyteller_prevalidation",
                    "_prevalidation_rejected": True,
                    "_prevalidation_reason": rejected["reason"],
                }
                for rejected in invalid_story_events
            ]
            if quarantine_llm_payload
            else llm_event_proposals
        )
        if not str(narrative_text).strip():
            # Fallback digno: o TURNO MECÂNICO sobrevive mesmo com LLM flaky —
            # as notas determinísticas (viagem/descanso/encontro) viram a narração.
            narrative_text = _deterministic_story_fallback(
                (travel_note, rest_note, world_note, faction_note, weather_note), _ll,
            )
        narrative_text = prose_guard.sanitize_player_facing(str(narrative_text))
        narrative_text = prose_guard.reconcile_player_gold_claims(
            narrative_text, int((state.get("player") or {}).get("gold", 0) or 0)
        )
        if invalid_story_events:
            # Não há fact-check semântico confiável frase a frase. Em vez de
            # deixar a alegação rejeitada sobreviver, usa somente consequências
            # determinísticas já aplicadas neste turno.
            safe_parts = [note for note in (travel_note, rest_note, faction_note) if note]
            narrative_text = _deterministic_story_fallback(safe_parts, _ll) if safe_parts else (
                "A tentativa altera apenas o momento imediato; nenhuma mudança "
                "permanente no mundo foi confirmada."
            )
            narrative_text += (
                "\n\n[SISTEMA] Uma mudança permanente proposta pela narração "
                "foi rejeitada pelo estado canônico."
            )

        narrative_text = prose_guard.vary_repeated_opening(
            str(narrative_text),
            _aberturas,
            salt=(
                f"{state.get('game_id', '')}:"
                f"{(world or {}).get('turn_count', 0)}:storyteller"
            ),
        )

        # spec polish-prosa (R4): telemetria de abertura repetida (não re-tenta).
        prose_guard.log_if_repeats(str(narrative_text),
                                   _aberturas[0] if _aberturas else "", where="storyteller")

        # --- Fase 2: a ação do jogador altera a reputação das fações (Python resolve) ---
        # A IA só identifica fação + direção; apply_reputation valida o id e fixa o delta.
        # Fase 3.4: cada mudança vira proposta reputation_changed (Python, não LLM) —
        # entra no event_log auditável pelo mesmo pipeline 2.6, alimenta a timeline.
        rep_events = []
        faction_impacts = (
            [] if quarantine_llm_payload
            else (getattr(update, "faction_impacts", []) or [])
        )
        for imp in faction_impacts:
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
        needs_replan = travel_needs_replan
        updated_plan = campaign_plan
        beat_done = (
            bool(getattr(update, "beat_completed", False))
            and not quarantine_llm_payload
            and beat_eligible
        )
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
        if beat_done:
            beats[current_step] = {**beats[current_step], "status": "done"}
            new_step = current_step + 1
            updated_plan = {**campaign_plan, "beats": beats, "current_step": new_step}
            # Esgotou os beats → próximo turno o campaign_manager replaneja (vê _should_replan).
            if new_step >= len(beats):
                needs_replan = True

        # spec npcs-3-camadas (R5): viagem zera a cena (ninguém teleporta junto);
        # introduced_npcs entram em cena; npcs_left_scene saem.
        new_npcs = scene_npcs
        home_id = world.get("current_location_id", "")
        _turn = int(world.get("turn_count", 0) or 0)
        introduced_npcs = (
            [] if quarantine_llm_payload else (update.introduced_npcs or [])
        )
        npcs_left_scene = (
            [] if quarantine_llm_payload
            else (getattr(update, "npcs_left_scene", []) or [])
        )
        for new_name in introduced_npcs:
            new_npcs = _with_new_npc(new_npcs, new_name, loc, narrative_text,
                                     game_id=str(game_id or ""), home_id=home_id,
                                     turn=_turn)
        for gone_name in npcs_left_scene:
            key = next((k for k in new_npcs if k.lower() == str(gone_name).lower()), None)
            if key and isinstance(new_npcs.get(key), dict):
                new_npcs = {**new_npcs, key: {**new_npcs[key], "in_scene": False}}

        updates = {
            "messages": [AIMessage(content=narrative_text)],
            "npcs": new_npcs,
            "world": world,
            "factions": factions,
            "campaign_plan": updated_plan,
            "needs_replan": needs_replan,
        }
        # Rumores/cores do simulador são percepção narrativa, não fatos globais.
        # A consequência mecânica aplicada já é persistida diretamente pelo
        # world_simulator; o archivist deve ignorar inferências livres deste texto.
        if world_note:
            updates["memory_fact_policy"] = "canonical_only"
        if rested_player is not None:
            updates["player"] = rested_player
        elif discovery_player is not None:
            updates["player"] = discovery_player
        if leveled_player is not None:  # Fase 4.1: XP do beat (inclui o descanso, se houve)
            updates["player"] = leveled_player

        # Fase 4.3 (R5): item narrado ENTRA no inventário — só se resolver no
        # ARTIFACTS_DB (storyteller não cria item; isso é papel do loot_node).
        gained = [
            g
            for g in (
                [] if quarantine_llm_payload
                else (getattr(update, "items_gained", []) or [])
            )
            if str(g).strip()
        ]
        rejected_claims: List[str] = []
        if gained:
            from inventory import add_item, get_qty, is_unique, resolve_item_name
            from services.economy import claim_event, is_unique_available
            proj = state.get("world_projection") or {}
            cur_p = dict(updates.get("player") or state.get("player") or {})
            inv = list(cur_p.get("inventory") or [])
            changed = False
            seen_unique: set[str] = set()
            for g in gained:
                if _is_monetary_claim(g):
                    # O valor válido já foi aplicado pela exploração/economia.
                    # Texto do provider nunca concede nem rejeita moeda.
                    continue
                iid = resolve_item_name(str(g))
                if not iid:
                    print(f"⚠️ [STORYTELLER] item narrado desconhecido ignorado: {g!r}")
                    rejected_claims.append(str(g))
                    continue
                # Fase 6.2: único já reclamado NUNCA re-entra pela narrativa
                unique = is_unique(iid)
                if unique and iid in seen_unique:
                    # Name/ID aliases in one payload represent one grant, not a
                    # second rejection that would erase the valid first grant.
                    continue
                if unique:
                    seen_unique.add(iid)
                if unique and (get_qty(inv, iid) > 0 or not is_unique_available(iid, proj)):
                    print(f"⚠️ [STORYTELLER] item ÚNICO já reclamado ignorado: {iid}")
                    rejected_claims.append(str(g))
                    continue
                inv = add_item(inv, iid, 1)
                changed = True
                if unique:
                    rep_events.append(claim_event(iid, "player"))
            if changed:
                cur_p["inventory"] = inv
                updates["player"] = cur_p
        if rejected_claims:
            clean = prose_guard.remove_rejected_claims(narrative_text, rejected_claims)
            clean = clean or "A busca não produz nenhum objeto utilizável."
            rejection_note = (
                "Nenhum outro objeto foi acrescentado aos seus pertences."
                if changed else
                "Ao conferir seus pertences, você percebe que nada novo foi obtido."
            )
            clean = (
                f"{clean}\n\n{rejection_note}"
            )
            updates["messages"] = [AIMessage(content=clean)]
            updates["narrative_rejections"] = [
                f"item_rejected:{name}" for name in dict.fromkeys(rejected_claims)]
            from persistence import normalize_rejected_item_claims
            updates["rejected_item_claims"] = normalize_rejected_item_claims([
                *list(state.get("rejected_item_claims") or []),
                *rejected_claims,
            ])
        reward_note = _reward_confirmation(
            reward_player_before,
            updates.get("player") or state.get("player") or {},
        )
        if reward_note:
            current_text = str(updates["messages"][0].content or "").rstrip()
            updates["messages"] = [AIMessage(content=f"{current_text}\n\n{reward_note}")]
        if invalid_story_events:
            updates["narrative_rejections"] = [
                *list(updates.get("narrative_rejections") or []),
                *[
                    f"event_rejected:{entry['type']}:{entry['target_id']}"
                    for entry in invalid_story_events
                ],
            ]
        # Viagem/descanso/beat concluído = evento relevante → pede arquivamento.
        if dest or rested_player is not None or beat_done:
            updates["archive_due"] = True
        if track_bk is not None:  # Fase 6.4: rastro alimenta o Codex (3.2)
            updates["bestiary_knowledge"] = track_bk
        # Fase 2.6: enfileira propostas de evento estruturado (motor valida no archivist).
        # Fase 3.4: reputation_changed (Python) entra na mesma fila. 4.1: level_up idem.
        # Fase 6.4: XP de esquiva de armadilha pode ter gerado level_up.
        pending = (
            pending_llm_events
            + rep_events
            + level_up_events
            + extra_engine_events
            + discovery_events
        )
        if pending:
            updates["pending_world_events"] = (state.get("pending_world_events", []) or []) + pending
            updates["archive_due"] = True  # mudança de mundo é evento relevante
        if rested_player is not None and rested_player.get("dead"):
            updates["death_pending"] = True
            updates["archive_due"] = True
            updates["pending_world_events"] = list(
                updates.get("pending_world_events")
                or state.get("pending_world_events", []) or []
            ) + [{
                "type": "player_downed",
                "actor_id": "player",
                "target_id": "player",
                "detail": "O herói tombou numa armadilha durante a viagem.",
                "payload": {
                    "location": world.get("current_location", ""),
                    "cause": "armadilha",
                },
                "source": "trap",
            }]

        # Fase 3.3: side quests propostas nesta cena (validadas/criadas em Python).
        turn = int(world.get("turn_count", 0))
        proposed_quests = (
            [] if quarantine_llm_payload
            else (getattr(update, "proposed_quests", []) or [])
        )
        new_quests, created = quest_log.register_proposed_quests(
            state.get("quests", []), proposed_quests, turn=turn
        )
        new_quests = quest_log.sync_location_progress(
            new_quests, str(world.get("current_location_id") or ""), turn=turn,
        )
        new_quests, ready_quest_ids = quest_log.sync_action_progress(
            new_quests,
            str(world.get("current_location_id") or ""),
            last_user_input,
            turn=turn,
        )
        if ready_quest_ids:
            quest_events = [{
                "type": "quest_completed",
                "actor_id": "player",
                "target_id": quest_id,
                "detail": "Objetivo concluído por investigação verificável.",
                "payload": {"quest_id": quest_id},
                "source": "system",
            } for quest_id in ready_quest_ids]
            updates["pending_world_events"] = list(
                updates.get("pending_world_events")
                or state.get("pending_world_events", [])
                or []
            ) + quest_events
        if created or new_quests != list(state.get("quests", []) or []):
            updates["quests"] = new_quests
            updates["archive_due"] = True  # nova missão é evento relevante
        return updates

    except Exception as e:
        print(f"[STORYTELLER ERROR] {e}")
        fallback = {"messages": [AIMessage(content=_deterministic_story_fallback(
            (travel_note, rest_note, world_note, faction_note, weather_note), _ll,
        ))]}
        if dest:
            # viagem mecânica sobrevive ao LLM flaky: mundo anda e a cena esvazia
            from services import npc_layers
            fallback["world"] = world
            fallback["needs_replan"] = travel_needs_replan
            fallback["npcs"] = npc_layers.reset_scene(state.get("npcs", {}))
        return fallback
