"""Typed structures describing the shared game state for the LangGraph workflow."""

import operator
from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict

from langchain_core.messages import BaseMessage


class Attributes(TypedDict):
    strength: int
    dexterity: int
    constitution: int
    intelligence: int
    wisdom: int
    charisma: int


class Virtudes(TypedDict):
    # spec conflito-01: 5 Virtudes (0-5) substituem os 6 atributos D&D.
    # Chaves curtas canônicas — sem aliases/normalização (attributes saiu do player).
    mente: int
    agilidade: int
    forca: int
    carisma: int
    corpo: int


class Condition(TypedDict, total=False):
    name: str
    dot: int  # dano por turno (0 = buff/debuff sem dano direto)
    duration: int  # turnos restantes
    source: str  # quem/que habilidade aplicou
    # --- Fase 4.2: modificadores tipados (lidos por combat_mechanics.condition_modifiers)
    stat: str | None  # "damage" | "ac" | "attack" | "save"
    delta: int  # soma no stat enquanto durar
    control: str | None  # "stun" (perde turno) | "root" (não foge) | "fear" (-2 acerto)


class Armor(TypedDict, total=False):
    # spec conflito-05: armadura com Proteção + Integridade (fica Comprometida em 0).
    categoria: str  # "leve" | "media" | "pesada"
    protecao: int
    integridade_max: int
    integridade_atual: int
    penalidade_esquiva: int
    reducoes_max: int
    comprometida: bool


class Shield(TypedDict, total=False):
    categoria: str  # "broquel" | "comum" | "pesado"
    protecao: int
    integridade_max: int
    integridade_atual: int
    requisito_forca: int
    comprometida: bool


class Wound(TypedDict, total=False):
    # spec conflito-05: Ferimento localizado (vive em PlayerStats.ferimentos[cat]).
    categoria: str  # "leve" | "grave" | "critico"
    regiao: str
    suprimida: bool  # tratada, aguardando remoção no descanso longo


class EffectSpec(TypedDict, total=False):
    # spec conflito-03: catálogo FECHADO de efeitos mecânicos (services/conflict_scene
    # .EFFECT_KINDS). Compartilhado com conflito-10/11 — definido aqui, só referenciado lá.
    kind: str  # alter_terrain|block_route|unblock_route|damage|request_reaction|
    # apply_condition|reposition|spawn_reinforcement|destroy_object|
    # change_environment_condition
    params: dict


class SceneObject(TypedDict, total=False):
    # spec conflito-03: objeto interativo da cena. O jogador vê label+cost das
    # interações, NUNCA o effect (oculto até uso, salvo investigação prévia).
    id: str
    name: str
    distance_state: str  # "proximo" | "distante" | "separado"
    zone_id: str
    interactions: list[dict]  # {label, cost: "pre_acao"|"pos_acao"|"acao", effect: EffectSpec}
    secret: bool
    discovered: bool
    uses_remaining: int | None
    destroyed: bool


class ConflictScene(TypedDict, total=False):
    # spec conflito-03: cena de conflito com posicionamento por zonas (não-grid).
    # Vive em GameState.combat["scene"]; convive com round/active/order/idle_turns
    # até o cutover (conflito-13) consolidar. `frozen` trava acréscimos por LLM.
    zones: list[dict]  # {id, name, connections: List[zone_id]}
    positions: dict[str, dict]  # participant_id -> {zone_id, distance_state, postura, ocultacao,
    #   engaged_with, budget{pre_acao,acao,pos_acao}, guarding,
    #   hidden_from[obs], approx_from[obs]} (conflito-06)
    objects: list[SceneObject]
    frozen: bool
    reinforcement_triggers: list[dict]  # gatilhos de reforço declarados ANTES do início


class Carta(TypedDict, total=False):
    # spec conflito-02: Carta substitui o formato de player_abilities.json.
    # efeito.kind usa o MESMO catálogo fechado da preparação de cena (conflito-03);
    # a RESOLUÇÃO em combate é escopo da conflito-04.
    id: str
    name: str
    tipo: str  # "ativa" | "passiva" | "utilitaria" | "reacao"
    classe: str
    subclasse: str
    patamar: str
    tier: int
    level_req: int
    apex: bool
    custo_entropia: int
    frequencia: str  # "livre"|"turno"|"cena"|"descanso_curto"|"descanso_longo"
    virtude_permitida: list[str]
    efeito: dict
    ruptura: dict | None  # {"caminho_a": {...}, "caminho_b": {...}} (nível 4+)


class PlayerStats(TypedDict, total=False):
    name: str
    class_name: str
    race: str
    race_id: str  # SPEC-298 R5: id de data/origins.json ("" = neutro)
    origin_region_id: str  # SPEC-298 R5: id da regiao de origem ("" = neutro)
    hp: int  # alias legado derivado de vitalidade
    max_hp: int  # alias legado derivado de max_vitalidade
    # spec refatoracao-sistema-classes: Entropia = pool ÚNICO das 5 classes novas
    # (substitui mana+stamina do jogador; inimigos seguem em mana/stamina).
    # Recompõe integral no descanso. Carga do Abismo = recurso de longo prazo
    # (não cai no descanso; consequência por patamar/classe).
    entropy: int
    max_entropy: int
    abyss_charge: int
    gold: int
    level: int
    xp: int
    alignment: str
    attributes: Attributes  # LEGADO — removido do jogador na Fase B da conflito-01
    # --- spec conflito-01: Virtudes + Vitalidade/Ferimentos (fundação de dados) ---
    virtudes: Virtudes  # mente/agilidade/forca/carisma/corpo (0-5)
    vitalidade: int  # pool atual (substitui hp no motor novo)
    max_vitalidade: int  # derivado de Corpo (gamedata.VITALIDADE_POR_CORPO)
    vitalidade_base_bonus: int  # bônus da Postura; zero para inimigos/NPCs
    vitalidade_max_penalty: int  # perda permanente acumulada por Cicatrizes
    ferimento_espacos: dict[
        str, int
    ]  # capacidade {leve,grave,critico} derivada de Corpo (recalc no bump)
    ferimentos: dict[str, list]  # Ferimentos ATIVOS por categoria (Wound) — conflito-05
    armor: Armor | None  # spec conflito-05: armadura equipada (ou None)
    shield: Shield | None  # spec conflito-05: escudo equipado (ou None)
    resistances: dict[str, str]  # tipo_dano -> "resistencia|resistencia_maior|vulnerabilidade|..."
    immunities: list[str]  # tipos de dano imunes
    # Fase 4.3: inventário estruturado — {"id": str, "qty": int, "display_name"?: str}
    # (id resolve no ARTIFACTS_DB; item_desconhecido preserva nome de save antigo)
    inventory: list[dict]
    # Fase 4.3: slots de equipamento — {"weapon"|"armor"|"accessory": item_id|None}
    # combate lê SÓ os slots (inventory.equip/unequip; backfill auto-equipa 1x)
    equipment: dict[str, str | None]
    # --- specs conflito-02/13: Cartas (Acervo/Preparação/Ruptura/Virtude) ---
    known_cards: list[str]  # Acervo: ids de Cartas conhecidas
    prepared_cards: list[str]  # subconjunto preparado (tamanho por nível)
    card_usage: dict[
        str, dict
    ]  # id -> {used_this_turn, used_this_scene, used_since_short_rest, used_since_long_rest}
    virtue_cards: list[dict]  # 2 permanentes: {card_id, virtude, estagio, mastery}
    subclass: str
    progression_grants: list[str]
    evolved_cards: dict[str, str]  # id -> caminho ("A"|"B") já evoluído (permanente, único)
    # escolhas de level up pendentes — {"id", "level", "kind": virtude|carta}
    pending_choices: list[dict]
    defense: int
    attack_bonus: int
    active_conditions: list[Condition]
    # --- Fase 2.5b: traits raciais (aplicados na criação; ver data/origins.json) ---
    racial_traits: list[str]  # nomes dos traits (narração/HUD)
    condition_resists: list[str]  # substrings de condições que a raça ignora
    racial_save_bonus: dict[str, int]  # attr curto -> bônus em saving throws
    dead: bool
    estado_terminal: bool
    last_stand_pending: bool
    last_stand_resolved: bool


class EnemyStats(TypedDict, total=False):
    id: str
    name: str
    hp: int  # alias legado derivado
    max_hp: int
    vitalidade: int
    max_vitalidade: int
    ferimento_espacos: dict[str, int]
    ferimentos: dict[str, list]
    stamina: int
    mana: int
    defense: int
    attack_mod: int
    attributes: Attributes
    # spec conflito-01 R7: campo existe no schema; preenchimento por criatura
    # (Vitalidade/Ferimentos) é escopo da conflito-05/15. attributes RESIDUAL no
    # inimigo até conflito-04/05 decidirem o destino (R8).
    virtudes: dict[str, int] | None
    abilities: list[str]
    status: str  # "ativo", "morto", "fugiu"
    active_conditions: list["Condition"]
    attacks: list[dict] | None
    # --- Fase 2.5b: comportamento de combate (ver data/bestiary.json) ---
    # {"profile": "tatico"|"feroz"|"covarde"|"implacavel", "flee_below": float, "pack_morale": bool}
    behavior: dict | None


class CompanionState(TypedDict, total=False):
    name: str
    hp: int  # alias legado derivado
    max_hp: int
    vitalidade: int
    max_vitalidade: int
    ferimento_espacos: dict[str, int]
    ferimentos: dict[str, list]
    active: bool
    stats: dict


class WorldClock(TypedDict):
    day: int
    period: str  # "Amanhecer" | "Manhã" | "Tarde" | "Anoitecer" | "Noite"


class WorldState(TypedDict, total=False):
    current_location: str
    current_location_id: str  # id no grafo data/world_map.json
    visited: list[str]  # ids de locais já revelados (fog of war)
    looted_locations: list[
        str
    ]  # ids de locais cujo baú CURADO já foi saqueado (spec loot-exploracao, one-shot)
    world_clock: WorldClock  # dia + período (relógio do mundo)
    time_of_day: str
    turn_count: int
    weather: str
    quest_plan: list[str]
    quest_plan_origin: str | None
    danger_level: int
    # --- Fase 4.4: economia — estoque persistente por mercador + último restock ---
    merchant_stocks: dict[str, dict[str, int]]  # merchant_id -> {item_id: qty}
    merchant_restock_day: dict[str, int]  # merchant_id -> dia do último restock
    # --- Fase 6.4: encontros sistêmicos (flags one-shot, consumidas no uso) ---
    encounter_surprise: str | None  # "player" (emboscou) | "enemy" (surpreendido)
    treasure_hint: bool  # pista de rastro: próximo TREASURE rola banda alta
    # --- Fase 6.5: clima (efeito é LEITURA via weather_effects, nunca condição) ---
    weather_state: str  # id canônico do estado (weather.json da região)
    weather_global: dict | None  # fenômeno global ativo {id, periods_left}
    # --- Fase 2 / Etapa B: mundo que evolui (escrito por resolve_faction_completions) ---
    controlled: dict[str, str]  # location_id -> faction_id (local dominado por fação)
    danger_overrides: dict[str, int]  # location_id -> perigo elevado por ascensão (teto 4)
    looming_threat: str  # ameaça invocada (entidade) pairando sobre o mundo
    looming_threat_faction: str  # SPEC-289: fação que invocou a ameaça (tema da criatura)
    last_encounter_turn: int  # turno do último encontro automático (cooldown)
    news: list[dict]  # SPEC-296: rumores percebidos ("Ouvi dizer"), FIFO 12
    threat_alerts: list[
        dict
    ]  # Fase 2.5b: fugas viram alerta regional (ver world_utils.register_flee_alert)
    shelter: dict | None  # SPEC-298 R24: {npc_id, location_id, until_clock} (favor esconder)


class FameEntry(TypedDict, total=False):
    """SPEC-298 R14: fama por local (so cresce com testemunha ou noticia entregue)."""

    renown: int  # 0..100
    infamy: int  # 0..100
    deeds: list[str]  # subject_ids ja contados aqui (teto 100, FIFO)


class ReputationPending(TypedDict):
    """SPEC-298 R12: delta de facção que ainda nao foi testemunhado pela facção."""

    subject_id: str
    faction_id: str
    delta: int
    created_day: int


class ReputationNotice(TypedDict, total=False):
    """SPEC-298 R26: aviso de mudança (template fixo, sem numero)."""

    kind: str  # npc | faction | fame | favor | social
    subject_id: str
    text: str
    turn: int


class NpcFavors(TypedDict, total=False):
    last_day: int
    debt: dict | None
    intercession: dict | None


class Faction(TypedDict, total=False):
    id: str
    name: str
    goal: str  # objetivo de longo prazo da facção
    region: str  # região-base no grafo do mundo
    progress: int  # 0-100 rumo ao objetivo (avança em ticks de descanso/viagem)
    pace: int  # quanto progride por período de tempo (determinístico)
    disposition: str  # "hostil" | "neutro" | "aliado" — postura geral no mundo
    reputation: int  # reputação do jogador com a facção (-100..100)
    completed: bool  # objetivo concluído (dispara evento de mundo)
    defeated: bool  # eliminada por outra facção (Fase 2 — sai de jogo)


class BestiaryKnowledge(TypedDict, total=False):
    """O que o JOGADOR sabe sobre uma criatura do bestiário. Chave = id de data/bestiary.json."""

    seen: int  # avistada/citada em alerta ou hint de encontro (rumor)
    fought: int  # combates iniciados contra ela
    defeated: int  # instâncias mortas pelo player
    first_seen_turn: int
    last_update_turn: int


class CampaignBeat(TypedDict):
    description: str
    status: Literal["pending", "done"]


class CampaignPlan(TypedDict, total=False):
    location: str
    beats: list[CampaignBeat]
    climax: str
    current_step: int
    last_planned_turn: int
    arc_title: str  # Fase 3.1: título do arco atual — muda → capítulo novo na crônica


# --- Fase 3.3: quest log — side quests persistentes (main quest = view do CampaignPlan) ---


class Quest(TypedDict, total=False):
    id: str  # uuid4 hex
    title: str
    description: str
    status: str  # "active" | "completed" | "failed"
    origin_name: str  # quem/o que originou (nome exibível)
    origin_entity_id: str  # id canônico se houver (habilita falha sistêmica); "" senão
    location_id: str  # alvo no mapa ("" se não aplicável)
    created_turn: int
    resolved_turn: int
    reward_hint: str  # texto livre ("o ferreiro prometeu 50 moedas")
    progress_log: list[
        dict
    ]  # ledger: created | location_reached | investigation | completion_ready | completed
    completion_ready: bool  # objetivo verificável atingido; evento Python conclui no archivist
    reward_gold: int  # recompensa mecânica efetivamente entregue
    reward_delivered: bool


class ContinuityState(TypedDict, total=False):
    session_action_count: int  # ações jogadas, nunca retrocede em restore
    timeline_epoch: int  # incrementa a cada retorno de checkpoint
    last_checkpoint_turn: int
    death_history: list[dict]


# --- Fase 3.1: crônica por capítulos (milestones determinísticos + prosa) ---


class ChronicleEntry(TypedDict, total=False):
    entry_id: str
    text: str
    turn: int
    kind: str  # "milestone" (determinístico, do event_log) | "prose" (menestrel LLM)
    event_id: str  # só milestones — auditoria (aponta para GameEvent.event_id)


class ChronicleChapter(TypedDict, total=False):
    chapter_id: str
    title: str
    started_turn: int
    location: str  # current_location no momento da abertura
    entries: list[ChronicleEntry]
    digest: dict


# --- Fase 2.5: eventos estruturados + estado projetado do mundo ---
# Lore base (Codex/data/graph) é imutável; o que MUDA no mundo vive aqui.


class GameEvent(TypedDict, total=False):
    event_id: str  # uuid4 hex
    turn: int  # world.turn_count no momento do evento
    type: str  # "npc_killed" | "secret_revealed" | "location_control_changed" | ...
    actor_id: str  # quem causou ("player", npc id, faction id, "system")
    target_id: str  # entidade afetada (id canônico de data/graph/entities.json)
    payload: dict  # dados específicos do tipo
    source: str  # "combat" | "storyteller" | "rule_engine" | "system" | "test"


class EntityState(TypedDict, total=False):
    alive: bool
    location_id: str
    stability: int  # fações: -100..100
    extra: dict  # estado adicional por componente


class DynamicEdge(TypedDict, total=False):
    id: str
    source: str
    type: str
    target: str
    created_by_event: str  # event_id de origem (auditoria)


class DisabledEdge(TypedDict, total=False):
    edge_id: str  # id da edge base desativada
    disabled_by_event: str


class RevealedFact(TypedDict, total=False):
    entity_id: str
    fact: str
    revealed_at_turn: int
    revealed_by_event: str


class MemoryFact(TypedDict, total=False):
    """Fato/relato persistido com autoridade derivada pelo motor."""

    memory_id: str
    text: str
    provenance: Literal[
        "canonical_event",
        "player_observation",
        "npc_claim",
        "inference",
        "legacy_unverified",
    ]
    confidence: Literal["confirmed", "reported", "speculative"]
    source_id: str | None
    source_turn: int | None
    canonical_entity_ids: list[str]
    vector_status: Literal["written", "pending", "failed"]  # SPEC-234


class KnowledgeLink(TypedDict, total=False):
    """SPEC-215: RELAÇÃO privada holder→assunto (nunca verdade nova, nunca na API)."""

    link_id: str  # sha256(holder|subject|relation|acquired_clock)[:16]
    holder_id: str  # "npc:<npc_id canônico>" | "loc:<location_id>"
    subject_kind: Literal["event", "memory_fact"]
    subject_id: str  # GameEvent.event_id | MemoryFact.memory_id
    relation: Literal["observed_by", "told_to", "believed_by"]
    source: str  # "world" | "player" | "npc:<id>" | "loc:<id>"
    channel: Literal["witness", "messenger", "local_rumor", "player"]
    hops: int  # 0 testemunha; <= MAX_HOPS
    acquired_clock: int  # day*5 + period_index
    acquired_turn: int
    location_id: str  # onde o holder soube (auditoria/invariante)
    origin_location_id: str  # onde o assunto aconteceu (mensageiro)
    origin_clock: int


class KnowledgeDelivery(TypedDict, total=False):
    """SPEC-215: entrega agendada de notícia (fila FIFO por due_clock, teto 200)."""

    delivery_id: str
    subject_kind: str
    subject_id: str
    subject_type: str
    from_location_id: str
    to_location_id: str
    hop: int
    due_clock: int
    created_turn: int
    origin_location_id: str
    origin_clock: int


class CrisisRecord(TypedDict, total=False):
    """SPEC-302 §3.3: crise do diretor de tensão (anunciada, ativa ou encerrada)."""

    crisis_id: str
    kind: str  # guerra | fome | praga | abismo | ascensao
    region_id: str
    location_id: str
    loc_state: str
    faction_id: str
    warned_day: int
    start_day: int | None
    escalation_day: int | None
    severity: int
    end_day: int | None
    resolution: str
    route: list[str]


class WorldSimState(TypedDict, total=False):
    """SPEC-302: estado PRIVADO do motor de mundo (dono: services.world_engine).
    Nunca sai pela API. Chave aditiva, sem bump de SCHEMA_VERSION."""

    version: int
    mode: str
    enabled_from_day: int
    last_ticked_day: int
    last_event_seq: int
    pressures: dict[str, dict[str, int]]
    bands: dict[str, dict[str, str]]
    phase: str
    phase_since_day: int
    calm_until_day: int
    recovery_until_day: int
    last_crisis_start_day: int
    region_last_crisis_end: dict[str, int]
    announce_block: dict[str, int]
    crises: list[CrisisRecord]
    faction_relations: dict[str, int]
    relation_bands: dict[str, str]
    faction_acc: dict[str, float]
    war_calm_days: dict[str, int]
    signals: list[dict]
    pending_digest: list[dict]
    tick_log: list[dict]
    shadow_location_states: dict[str, dict]
    shadow_blocked_routes: list[dict]


class WorldProjection(TypedDict, total=False):
    entities: dict[str, EntityState]
    dynamic_edges: list[DynamicEdge]
    disabled_edges: list[DisabledEdge]
    revealed_facts: dict[str, RevealedFact]  # chave = event_id revelador
    location_summaries: dict[str, str]  # loc_id -> resumo dinâmico curto
    # SPEC-302 R17: estado de local (cerco/escassez/...) — escrito SÓ por apply_event
    # (evento `location_state_changed`, source="engine"). Linha: LocationStateRow.
    location_states: dict[str, dict]


class GameState(TypedDict):
    # --- Identificação e Memória (NOVO) ---
    game_id: str  # ID único da sessão para isolar o RAG
    processed_action_ids: list[str]  # ledger limitado de idempotência SSE/POST
    visual_seen_entity_ids: list[str]  # Fase 8A: NPCs já apresentados
    pool_used: list[str]  # SPEC-297 R24: pool_entry_id já materializados neste jogo
    visual_cue_ledger: list[dict]  # Fase 8A: action_key -> cue|null (64)
    narrative_summary: str  # Resumo de curto prazo (contexto comprimido)
    archivist_last_run: int  # Controle de frequência do arquivista
    archive_due: bool  # flag transitória: evento relevante pede arquivamento (cadência)
    archived: bool  # Arquivamento é persistente, inclusive após passar pelo grafo.
    archived_reason: str
    game_over: bool  # Fase 4.6: player morreu — save vira memorial (sem chave no
    # GameState o LangGraph DESCARTA o update; achado do smoke real)
    death_pending: bool  # spec checkpoints-morte: queda letal — aguardando a TELA DE
    # MORTE (Continuar do checkpoint / Aceitar o fim). Transitório.
    continuity: ContinuityState
    action_guard_blocked: bool
    turn_prepared: bool
    last_action_outcome: dict[str, Any]
    turn_baseline: dict[str, Any]
    last_turn_outcome: dict[str, Any]
    last_interaction_outcome: dict[str, Any]
    # Laboratório isolado: {enabled, enemy_id, quantity}. Quando presente,
    # campanha, LLM/RAG, loot e archivist ficam fora do turno de combate.
    combat_simulation: dict | None
    chronicle: list[
        ChronicleChapter
    ]  # Crônica por capítulos: milestones (event_log) + prosa de menestrel

    messages: Annotated[list[BaseMessage], operator.add]
    presentation_history: list[dict[str, Any]]
    # SPEC-207: ring buffer (default 200) de refs de auditoria por turno — só ids,
    # visibilidade, delta mínimo, erros (enum fechado) e timing SPEC-200. Escrito
    # só por services.audit_trace.record_turn_trace na finalização do turno.
    audit_trace: list[dict[str, Any]]
    # SPEC-213: versão canônica × projeções derivadas (summary/memory/chronicle).
    # Dono: services.projections (stamp no commit do turno; apply com CAS de versão).
    projection_state: dict[str, Any]
    # SPEC-213: linha de base mínima (ids) da projeção adiada; None quando em dia.
    pending_derived: dict[str, Any] | None
    art_generation_ledger: list[dict[str, Any]]
    art_offers: list[dict[str, Any]]
    art_arc_budgets: dict[str, dict[str, Any]]
    next: str | None
    player: PlayerStats
    world: WorldState
    campaign_plan: CampaignPlan | None
    needs_replan: bool
    enemies: list[EnemyStats]
    party: list[CompanionState]
    factions: list[Faction]  # Fase 2: fações com objetivos próprios (mundo vivo)
    faction_intel: dict[str, dict]  # Fase 2: o que o jogador SABE de cada facção (não-onisciência)
    bestiary_knowledge: dict[
        str, BestiaryKnowledge
    ]  # Fase 3.2: contadores por criatura (chave = id do bestiário)
    quests: list[Quest]  # Fase 3.3: side quests persistentes (main quest deriva de campaign_plan)
    npcs: dict[str, dict]
    # SPEC-298: reputacao em 4 niveis (dono: services.reputation). Aditivo, sem bump.
    location_fame: dict[str, FameEntry]
    reputation_pending: list[ReputationPending]
    reputation_notices: list[ReputationNotice]
    social_intent: dict | None  # SPEC-298 R20: {approach, favor_kind, turn} (transitório)
    active_npc_name: str | None
    npc_fallback_hint: (
        str | None
    )  # TRANSITORIO (SPEC-230 R8: zerado pelo router a cada turno); spec npc-fallback-sem-alvo (R2): rota NPC sem alvo → storyteller narra a ausência
    # SPEC-202: quem respondeu o último turno — {kind, id, name, reason} públicos
    # + internos turn/state_key/last_npc (continuidade R7/R8). Escrito só no fim do
    # turno (turn_finalizer) ou na recusa determinística (action_guard). Persistido.
    last_speaker: dict[str, Any] | None
    interlocutor_reason: str | None  # TRANSITÓRIO (zerado pelo router a cada rota)
    mediated_subject_id: str | None  # TRANSITÓRIO: NPC de quem o narrador fala (R2/R7)
    active_plan_step: str | None
    router_confidence: float | None
    last_routed_intent: str | None

    # --- Campos de Transição ---
    combat_target: str | None
    route_source: (
        str | None
    )  # TRANSITORIO (SPEC-247): fonte da decisao de rota (combat_gate|interlocutor|recovery|story_regex|jev|classify|classify_fallback)
    route_fallback_reason: str | None  # TRANSITORIO (SPEC-247): motivo fechado do fallback
    combat_origin_hint: str | None  # causa transitória até combat.origin ser materializada
    # SPEC-203: referências one-shot PROPOSTAS ao spawn (zeradas pelo combat_node):
    # {enemy_id, reason, hint} do encontro sistêmico (storyteller) e "npc:<nome>"
    # quando o alvo do router casa com NPC em cena.
    combat_encounter_hint: dict[str, Any] | None
    combat_target_ref: str | None
    loot_source: str | None
    last_economy_action: dict[str, Any]

    # --- Combate determinístico ---
    # {"round": int, "active": bool, "order": [{"id","name","side","init"}],
    #  "idle_turns": int}  — idle_turns (spec combate-lifecycle R3): turnos com
    #  combate ativo SEM rota de combate; o router incrementa, o combat_node zera,
    #  em >=3 o combate órfão expira. Sem migration (dict aberto, default 0).
    # SPEC-203 (aditivo, sem bump de schema; normalizado no load):
    #  "phase": entering|active|resolving|ended, "outcome": None|victory|fled|
    #  surrendered_enemy|defeat|death|expired, "encounter": EncounterManifest
    #  congelado (services/encounter_manifest), "result": snapshot do desfecho
    #  (fonte do `combat_result` da API; xp_event_ref = receipt_id SPEC-199).
    combat: dict | None

    # spec combate-lifecycle (R1): o router marca que a ação de VIAGEM durante o
    # combate deve virar tentativa de fuga rumo a este destino (não teleporta).
    combat_flee_attempt: bool | None
    combat_flee_destination: str | None

    # spec conflito-13 (cutover): declaração estruturada de turno do jogador/harness
    # (services/conflict_turn.TurnDeclaration serializada). Quando presente, o
    # combat_node NÃO faz o parse CLASSIFY — usada pelo playtest e pela UI (conflito-16).
    combat_declaration: dict | None
    player_reaction_card_id: str | None  # conflito-16: escolha transitória da UI
    # spec conflito-12: resumo canônico do conflito resolvido — consumido por
    # loot/archivist para retomar a narrativa sem reverter fatos.
    conflict_summary: dict | None
    consumed_conflict_ids: list[str]  # ledger bounded de summaries já persistidos
    memory_fact_policy: str | None  # política transitória ("canonical_only")
    memory_canonical_facts: list[str]  # allowlist persistida até commit RAG
    memory_facts: list[MemoryFact]  # ledger auditável já confirmado no RAG
    pending_memory_facts: list[MemoryFact]  # retry idempotente da sessão
    memory_rejections: list[dict]  # recusas de proveniência/segredo (bounded)
    memory_promotions: list[dict]  # promoções com fonte canônica (bounded)
    pending_npc_memory: list[dict]  # fila bounded de retries add_npc_memory
    narrative_rejections: list[str]  # guardrails narrativos transitórios
    evidence_rejections: list[dict[str, str]]  # bounded, no private text
    rejected_item_claims: list[str]  # itens recusados pelo motor (bounded, durável)
    rag_persistence_error: str | None  # falha sanitizada de memória da sessão
    event_rejections: list[dict]  # propostas recusadas + metadados sanitizados

    # --- Fase 2.5: mundo estruturado (LLM propõe, motor aplica) ---
    event_log: list[GameEvent]  # append-only; auditoria do que mudou
    world_projection: WorldProjection  # estado calculado a partir do event_log
    pending_world_events: list[dict]  # propostas ainda não validadas (Fase 2.6)
    # --- SPEC-302: motor de mundo (dono: services.world_engine; PRIVADO) ---
    world_sim: WorldSimState
    world_sim_shadow: WorldSimState

    # --- SPEC-215: conhecimento por NPC (ledger PRIVADO; dono services.npc_knowledge) ---
    # Aditivo, sem bump de schema: save sem as chaves carrega vazio + legacy=True.
    knowledge_links: list[KnowledgeLink]  # teto 2000
    knowledge_queue: list[KnowledgeDelivery]  # teto 200
    location_heard: dict[str, list[str]]  # subject ids por local (teto 100/local)
    legacy_knowledge: bool
