"""Typed structures describing the shared game state for the LangGraph workflow."""

import operator
from typing import Any, Annotated, Dict, List, Literal, Optional, TypedDict

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
    dot: int        # dano por turno (0 = buff/debuff sem dano direto)
    duration: int   # turnos restantes
    source: str     # quem/que habilidade aplicou
    # --- Fase 4.2: modificadores tipados (lidos por combat_mechanics.condition_modifiers)
    stat: Optional[str]     # "damage" | "ac" | "attack" | "save"
    delta: int              # soma no stat enquanto durar
    control: Optional[str]  # "stun" (perde turno) | "root" (não foge) | "fear" (-2 acerto)


class Armor(TypedDict, total=False):
    # spec conflito-05: armadura com Proteção + Integridade (fica Comprometida em 0).
    categoria: str          # "leve" | "media" | "pesada"
    protecao: int
    integridade_max: int
    integridade_atual: int
    penalidade_esquiva: int
    reducoes_max: int
    comprometida: bool


class Shield(TypedDict, total=False):
    categoria: str          # "broquel" | "comum" | "pesado"
    protecao: int
    integridade_max: int
    integridade_atual: int
    requisito_forca: int
    comprometida: bool


class Wound(TypedDict, total=False):
    # spec conflito-05: Ferimento localizado (vive em PlayerStats.ferimentos[cat]).
    categoria: str          # "leve" | "grave" | "critico"
    regiao: str
    suprimida: bool         # tratada, aguardando remoção no descanso longo


class EffectSpec(TypedDict, total=False):
    # spec conflito-03: catálogo FECHADO de efeitos mecânicos (services/conflict_scene
    # .EFFECT_KINDS). Compartilhado com conflito-10/11 — definido aqui, só referenciado lá.
    kind: str      # alter_terrain|block_route|unblock_route|damage|request_reaction|
                   # apply_condition|reposition|spawn_reinforcement|destroy_object|
                   # change_environment_condition
    params: Dict


class SceneObject(TypedDict, total=False):
    # spec conflito-03: objeto interativo da cena. O jogador vê label+cost das
    # interações, NUNCA o effect (oculto até uso, salvo investigação prévia).
    id: str
    name: str
    distance_state: str     # "proximo" | "distante" | "separado"
    zone_id: str
    interactions: List[Dict]  # {label, cost: "pre_acao"|"pos_acao"|"acao", effect: EffectSpec}
    secret: bool
    discovered: bool
    uses_remaining: Optional[int]
    destroyed: bool


class ConflictScene(TypedDict, total=False):
    # spec conflito-03: cena de conflito com posicionamento por zonas (não-grid).
    # Vive em GameState.combat["scene"]; convive com round/active/order/idle_turns
    # até o cutover (conflito-13) consolidar. `frozen` trava acréscimos por LLM.
    zones: List[Dict]              # {id, name, connections: List[zone_id]}
    positions: Dict[str, Dict]     # participant_id -> {zone_id, distance_state, postura, ocultacao,
                                   #   engaged_with, budget{pre_acao,acao,pos_acao}, guarding,
                                   #   hidden_from[obs], approx_from[obs]} (conflito-06)
    objects: List[SceneObject]
    frozen: bool
    reinforcement_triggers: List[Dict]  # gatilhos de reforço declarados ANTES do início


class Carta(TypedDict, total=False):
    # spec conflito-02: Carta substitui o formato de player_abilities.json.
    # efeito.kind usa o MESMO catálogo fechado da preparação de cena (conflito-03);
    # a RESOLUÇÃO em combate é escopo da conflito-04.
    id: str
    name: str
    tipo: str            # "ativa" | "passiva" | "utilitaria" | "reacao"
    classe: str
    subclasse: str
    patamar: str
    tier: int
    level_req: int
    apex: bool
    custo_entropia: int
    frequencia: str      # "livre"|"turno"|"cena"|"descanso_curto"|"descanso_longo"
    virtude_permitida: List[str]
    efeito: Dict
    ruptura: Optional[Dict]   # {"caminho_a": {...}, "caminho_b": {...}} (nível 4+)


class PlayerStats(TypedDict, total=False):
    name: str
    class_name: str
    race: str
    hp: int                         # alias legado derivado de vitalidade
    max_hp: int                     # alias legado derivado de max_vitalidade
    mana: int
    max_mana: int
    stamina: int
    max_stamina: int
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
    virtudes: Virtudes                 # mente/agilidade/forca/carisma/corpo (0-5)
    vitalidade: int                    # pool atual (substitui hp no motor novo)
    max_vitalidade: int                # derivado de Corpo (gamedata.VITALIDADE_POR_CORPO)
    vitalidade_base_bonus: int         # bônus da Postura; zero para inimigos/NPCs
    vitalidade_max_penalty: int        # perda permanente acumulada por Cicatrizes
    ferimento_espacos: Dict[str, int]  # capacidade {leve,grave,critico} derivada de Corpo (recalc no bump)
    ferimentos: Dict[str, List]        # Ferimentos ATIVOS por categoria (Wound) — conflito-05
    armor: Optional[Armor]             # spec conflito-05: armadura equipada (ou None)
    shield: Optional[Shield]           # spec conflito-05: escudo equipado (ou None)
    resistances: Dict[str, str]        # tipo_dano -> "resistencia|resistencia_maior|vulnerabilidade|..."
    immunities: List[str]              # tipos de dano imunes
    # Fase 4.3: inventário estruturado — {"id": str, "qty": int, "display_name"?: str}
    # (id resolve no ARTIFACTS_DB; item_desconhecido preserva nome de save antigo)
    inventory: List[Dict]
    # Fase 4.3: slots de equipamento — {"weapon"|"armor"|"accessory": item_id|None}
    # combate lê SÓ os slots (inventory.equip/unequip; backfill auto-equipa 1x)
    equipment: Dict[str, Optional[str]]
    # --- specs conflito-02/13: Cartas (Acervo/Preparação/Ruptura/Virtude) ---
    known_cards: List[str]             # Acervo: ids de Cartas conhecidas
    prepared_cards: List[str]          # subconjunto preparado (tamanho por nível)
    card_usage: Dict[str, Dict]        # id -> {used_this_turn, used_this_scene, used_since_short_rest, used_since_long_rest}
    virtue_cards: List[Dict]           # 2 permanentes: {card_id, virtude, estagio, mastery}
    subclass: str
    progression_grants: List[str]
    evolved_cards: Dict[str, str]      # id -> caminho ("A"|"B") já evoluído (permanente, único)
    # escolhas de level up pendentes — {"id", "level", "kind": virtude|carta}
    pending_choices: List[Dict]
    defense: int
    attack_bonus: int
    active_conditions: List[Condition]
    # --- Fase 2.5b: traits raciais (aplicados na criação; ver data/origins.json) ---
    racial_traits: List[str]           # nomes dos traits (narração/HUD)
    condition_resists: List[str]       # substrings de condições que a raça ignora
    racial_save_bonus: Dict[str, int]  # attr curto -> bônus em saving throws
    dead: bool
    estado_terminal: bool
    last_stand_pending: bool
    last_stand_resolved: bool


class EnemyStats(TypedDict, total=False):
    id: str
    name: str
    hp: int                         # alias legado derivado
    max_hp: int
    vitalidade: int
    max_vitalidade: int
    ferimento_espacos: Dict[str, int]
    ferimentos: Dict[str, List]
    stamina: int
    mana: int
    defense: int
    attack_mod: int
    attributes: Attributes
    # spec conflito-01 R7: campo existe no schema; preenchimento por criatura
    # (Vitalidade/Ferimentos) é escopo da conflito-05/15. attributes RESIDUAL no
    # inimigo até conflito-04/05 decidirem o destino (R8).
    virtudes: Optional[Dict[str, int]]
    abilities: List[str]
    status: str  # "ativo", "morto", "fugiu"
    active_conditions: List["Condition"]
    attacks: Optional[List[Dict]]
    # --- Fase 2.5b: comportamento de combate (ver data/bestiary.json) ---
    # {"profile": "tatico"|"feroz"|"covarde"|"implacavel", "flee_below": float, "pack_morale": bool}
    behavior: Optional[Dict]


class CompanionState(TypedDict, total=False):
    name: str
    hp: int                         # alias legado derivado
    max_hp: int
    vitalidade: int
    max_vitalidade: int
    ferimento_espacos: Dict[str, int]
    ferimentos: Dict[str, List]
    active: bool
    stats: Dict


class WorldClock(TypedDict):
    day: int
    period: str  # "Amanhecer" | "Manhã" | "Tarde" | "Anoitecer" | "Noite"


class WorldState(TypedDict, total=False):
    current_location: str
    current_location_id: str        # id no grafo data/world_map.json
    visited: List[str]              # ids de locais já revelados (fog of war)
    looted_locations: List[str]     # ids de locais cujo baú CURADO já foi saqueado (spec loot-exploracao, one-shot)
    world_clock: WorldClock         # dia + período (relógio do mundo)
    time_of_day: str
    turn_count: int
    weather: str
    quest_plan: List[str]
    quest_plan_origin: Optional[str]
    danger_level: int
    # --- Fase 4.4: economia — estoque persistente por mercador + último restock ---
    merchant_stocks: Dict[str, Dict[str, int]]   # merchant_id -> {item_id: qty}
    merchant_restock_day: Dict[str, int]         # merchant_id -> dia do último restock
    # --- Fase 6.4: encontros sistêmicos (flags one-shot, consumidas no uso) ---
    encounter_surprise: Optional[str]  # "player" (emboscou) | "enemy" (surpreendido)
    treasure_hint: bool                # pista de rastro: próximo TREASURE rola banda alta
    # --- Fase 6.5: clima (efeito é LEITURA via weather_effects, nunca condição) ---
    weather_state: str                 # id canônico do estado (weather.json da região)
    weather_global: Optional[Dict]     # fenômeno global ativo {id, periods_left}
    # --- Fase 2 / Etapa B: mundo que evolui (escrito por resolve_faction_completions) ---
    controlled: Dict[str, str]       # location_id -> faction_id (local dominado por fação)
    danger_overrides: Dict[str, int] # location_id -> perigo elevado por ascensão (teto 4)
    looming_threat: str              # ameaça invocada (entidade) pairando sobre o mundo
    last_encounter_turn: int         # turno do último encontro automático (cooldown)
    threat_alerts: List[Dict]        # Fase 2.5b: fugas viram alerta regional (ver world_utils.register_flee_alert)


class Faction(TypedDict, total=False):
    id: str
    name: str
    goal: str                 # objetivo de longo prazo da facção
    region: str               # região-base no grafo do mundo
    progress: int             # 0-100 rumo ao objetivo (avança em ticks de descanso/viagem)
    pace: int                 # quanto progride por período de tempo (determinístico)
    disposition: str          # "hostil" | "neutro" | "aliado" — postura geral no mundo
    reputation: int           # reputação do jogador com a facção (-100..100)
    completed: bool           # objetivo concluído (dispara evento de mundo)
    defeated: bool            # eliminada por outra facção (Fase 2 — sai de jogo)


class FactionIntel(TypedDict, total=False):
    """O que o JOGADOR sabe sobre uma facção (não-onisciência). Chave = faction_id."""
    known: bool               # existência revelada (só por NPC que sabe)
    knows_goal: bool          # objetivo/plano revelado
    progress_seen: int        # SNAPSHOT do progresso no momento em que soube (fica defasado)
    intel_turn: int           # turno em que o snapshot foi obtido (p/ marcar defasagem)


class BestiaryKnowledge(TypedDict, total=False):
    """O que o JOGADOR sabe sobre uma criatura do bestiário. Chave = id de data/bestiary.json."""
    seen: int               # avistada/citada em alerta ou hint de encontro (rumor)
    fought: int              # combates iniciados contra ela
    defeated: int             # instâncias mortas pelo player
    first_seen_turn: int
    last_update_turn: int


class CampaignBeat(TypedDict):
    description: str
    status: Literal["pending", "done"]


class CampaignPlan(TypedDict, total=False):
    location: str
    beats: List[CampaignBeat]
    climax: str
    current_step: int
    last_planned_turn: int
    arc_title: str         # Fase 3.1: título do arco atual — muda → capítulo novo na crônica


# --- Fase 3.3: quest log — side quests persistentes (main quest = view do CampaignPlan) ---

class Quest(TypedDict, total=False):
    id: str                  # uuid4 hex
    title: str
    description: str
    status: str              # "active" | "completed" | "failed"
    origin_name: str         # quem/o que originou (nome exibível)
    origin_entity_id: str    # id canônico se houver (habilita falha sistêmica); "" senão
    location_id: str         # alvo no mapa ("" se não aplicável)
    created_turn: int
    resolved_turn: int
    reward_hint: str         # texto livre ("o ferreiro prometeu 50 moedas")
    progress_log: List[Dict] # ledger: created | location_reached | investigation | completion_ready | completed
    completion_ready: bool   # objetivo verificável atingido; evento Python conclui no archivist
    reward_gold: int         # recompensa mecânica efetivamente entregue
    reward_delivered: bool


class ContinuityState(TypedDict, total=False):
    session_action_count: int  # ações jogadas, nunca retrocede em restore
    timeline_epoch: int        # incrementa a cada retorno de checkpoint
    last_checkpoint_turn: int
    death_history: List[Dict]


# --- Fase 3.1: crônica por capítulos (milestones determinísticos + prosa) ---

class ChronicleEntry(TypedDict, total=False):
    entry_id: str
    text: str
    turn: int
    kind: str        # "milestone" (determinístico, do event_log) | "prose" (menestrel LLM)
    event_id: str    # só milestones — auditoria (aponta para GameEvent.event_id)


class ChronicleChapter(TypedDict, total=False):
    chapter_id: str
    title: str
    started_turn: int
    location: str            # current_location no momento da abertura
    entries: List[ChronicleEntry]
    digest: Dict


# --- Fase 2.5: eventos estruturados + estado projetado do mundo ---
# Lore base (Codex/data/graph) é imutável; o que MUDA no mundo vive aqui.

class GameEvent(TypedDict, total=False):
    event_id: str      # uuid4 hex
    turn: int          # world.turn_count no momento do evento
    type: str          # "npc_killed" | "secret_revealed" | "location_control_changed" | ...
    actor_id: str      # quem causou ("player", npc id, faction id, "system")
    target_id: str     # entidade afetada (id canônico de data/graph/entities.json)
    payload: Dict      # dados específicos do tipo
    source: str        # "combat" | "storyteller" | "rule_engine" | "system" | "test"


class EntityState(TypedDict, total=False):
    alive: bool
    location_id: str
    stability: int         # fações: -100..100
    extra: Dict            # estado adicional por componente


class DynamicEdge(TypedDict, total=False):
    id: str
    source: str
    type: str
    target: str
    created_by_event: str  # event_id de origem (auditoria)


class DisabledEdge(TypedDict, total=False):
    edge_id: str           # id da edge base desativada
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
        "canonical_event", "player_observation", "npc_claim", "inference",
        "legacy_unverified",
    ]
    confidence: Literal["confirmed", "reported", "speculative"]
    source_id: Optional[str]
    source_turn: Optional[int]
    canonical_entity_ids: List[str]


class WorldProjection(TypedDict, total=False):
    entities: Dict[str, EntityState]
    dynamic_edges: List[DynamicEdge]
    disabled_edges: List[DisabledEdge]
    revealed_facts: Dict[str, RevealedFact]     # chave = event_id revelador
    location_summaries: Dict[str, str]          # loc_id -> resumo dinâmico curto


class GameState(TypedDict):
    # --- Identificação e Memória (NOVO) ---
    game_id: str  # ID único da sessão para isolar o RAG
    processed_action_ids: List[str]  # ledger limitado de idempotência SSE/POST
    visual_seen_entity_ids: List[str]  # Fase 8A: NPCs já apresentados
    visual_cue_ledger: List[Dict]  # Fase 8A: action_key -> cue|null (64)
    narrative_summary: str # Resumo de curto prazo (contexto comprimido)
    archivist_last_run: int # Controle de frequência do arquivista
    archive_due: bool       # flag transitória: evento relevante pede arquivamento (cadência)
    archived: bool         # Arquivamento é persistente, inclusive após passar pelo grafo.
    archived_reason: str
    game_over: bool         # Fase 4.6: player morreu — save vira memorial (sem chave no
                            # GameState o LangGraph DESCARTA o update; achado do smoke real)
    death_pending: bool     # spec checkpoints-morte: queda letal — aguardando a TELA DE
                            # MORTE (Continuar do checkpoint / Aceitar o fim). Transitório.
    continuity: ContinuityState
    action_guard_blocked: bool
    turn_prepared: bool
    last_action_outcome: Dict[str, Any]
    turn_baseline: Dict[str, Any]
    last_turn_outcome: Dict[str, Any]
    last_interaction_outcome: Dict[str, Any]
    # Laboratório isolado: {enabled, enemy_id, quantity}. Quando presente,
    # campanha, LLM/RAG, loot e archivist ficam fora do turno de combate.
    combat_simulation: Optional[Dict]
    chronicle: List[ChronicleChapter]  # Crônica por capítulos: milestones (event_log) + prosa de menestrel

    messages: Annotated[List[BaseMessage], operator.add]
    presentation_history: List[Dict[str, Any]]
    art_generation_ledger: List[Dict[str, Any]]
    art_arc_budgets: Dict[str, Dict[str, Any]]
    next: Optional[str]
    player: PlayerStats
    world: WorldState
    campaign_plan: Optional[CampaignPlan]
    needs_replan: bool
    enemies: List[EnemyStats]
    party: List[CompanionState]
    factions: List[Faction]  # Fase 2: fações com objetivos próprios (mundo vivo)
    faction_intel: Dict[str, Dict]  # Fase 2: o que o jogador SABE de cada facção (não-onisciência)
    bestiary_knowledge: Dict[str, BestiaryKnowledge]  # Fase 3.2: contadores por criatura (chave = id do bestiário)
    quests: List[Quest]  # Fase 3.3: side quests persistentes (main quest deriva de campaign_plan)
    npcs: Dict[str, Dict]
    active_npc_name: Optional[str]
    npc_fallback_hint: Optional[str]   # spec npc-fallback-sem-alvo (R2): rota NPC sem alvo → storyteller narra a ausência
    active_plan_step: Optional[str]
    router_confidence: Optional[float]
    last_routed_intent: Optional[str]
    
    # --- Campos de Transição ---
    combat_target: Optional[str]
    combat_origin_hint: Optional[str]  # causa transitória até combat.origin ser materializada
    loot_source: Optional[str]
    last_economy_action: Dict[str, Any]

    # --- Combate determinístico ---
    # {"round": int, "active": bool, "order": [{"id","name","side","init"}],
    #  "idle_turns": int}  — idle_turns (spec combate-lifecycle R3): turnos com
    #  combate ativo SEM rota de combate; o router incrementa, o combat_node zera,
    #  em >=3 o combate órfão expira. Sem migration (dict aberto, default 0).
    combat: Optional[Dict]

    # spec combate-lifecycle (R1): o router marca que a ação de VIAGEM durante o
    # combate deve virar tentativa de fuga rumo a este destino (não teleporta).
    combat_flee_attempt: Optional[bool]
    combat_flee_destination: Optional[str]

    # spec conflito-13 (cutover): declaração estruturada de turno do jogador/harness
    # (services/conflict_turn.TurnDeclaration serializada). Quando presente, o
    # combat_node NÃO faz o parse CLASSIFY — usada pelo playtest e pela UI (conflito-16).
    combat_declaration: Optional[Dict]
    player_reaction_card_id: Optional[str]  # conflito-16: escolha transitória da UI
    # spec conflito-12: resumo canônico do conflito resolvido — consumido por
    # loot/archivist para retomar a narrativa sem reverter fatos.
    conflict_summary: Optional[Dict]
    consumed_conflict_ids: List[str]  # ledger bounded de summaries já persistidos
    memory_fact_policy: Optional[str]  # política transitória ("canonical_only")
    memory_canonical_facts: List[str]  # allowlist persistida até commit RAG
    memory_facts: List[MemoryFact]      # ledger auditável já confirmado no RAG
    pending_memory_facts: List[MemoryFact]  # retry idempotente da sessão
    memory_rejections: List[Dict]       # recusas de proveniência/segredo (bounded)
    memory_promotions: List[Dict]       # promoções com fonte canônica (bounded)
    pending_npc_memory: List[Dict]      # fila bounded de retries add_npc_memory
    narrative_rejections: List[str]     # guardrails narrativos transitórios
    evidence_rejections: List[Dict[str, str]]  # bounded, no private text
    rejected_item_claims: List[str]     # itens recusados pelo motor (bounded, durável)
    rag_persistence_error: Optional[str]  # falha sanitizada de memória da sessão
    event_rejections: List[Dict]         # propostas recusadas + metadados sanitizados

    # --- Fase 2.5: mundo estruturado (LLM propõe, motor aplica) ---
    event_log: List[GameEvent]            # append-only; auditoria do que mudou
    world_projection: WorldProjection     # estado calculado a partir do event_log
    pending_world_events: List[Dict]      # propostas ainda não validadas (Fase 2.6)
