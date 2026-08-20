"""playtest/invariants.py — invariantes de estado pós-turno (Fase 5.2).

As regras IMPLÍCITAS do motor viram funções puras `check_*(state, prev, turn)`
que devolvem `Violation`s. `check_all` roda todas; o harness 5.1 pluga isto no
fim de cada turno (audita a campanha inteira) e `assert_invariants` deixa usar
os mesmos checks em teste avulso.

Um check que crasha NUNCA derruba a auditoria (é engolido) — invariante é rede
de segurança, não fonte de novo crash. Severidade `error` reprova o estado;
`warning` sinaliza sem reprovar (R5 começa em warning — §7 da spec).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, List, Literal, Optional

Severity = Literal["error", "warning"]


@dataclass
class Violation:
    check_id: str
    severity: Severity
    turn: int
    message: str
    details: dict = field(default_factory=dict)


def _V(check_id, severity, turn, message, **details) -> Violation:
    return Violation(check_id=check_id, severity=severity, turn=turn,
                     message=message, details=details)


# --- R1 vitals --------------------------------------------------------------

def check_vitals(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    p = state.get("player", {}) or {}

    def bounds(entity, kind, name):
        # Vitalidade é o recurso canônico do conflito v4. HP permanece apenas
        # como alias de compatibilidade e é auditado, separadamente, por
        # check_vitality_consistency.
        for res, cap in (
            ("vitalidade", "max_vitalidade"),
            ("mana", "max_mana"),
            ("stamina", "max_stamina"),
        ):
            cur = entity.get(res)
            mx = entity.get(cap)
            if cur is None or mx is None:
                continue
            if cur < 0 or cur > mx:
                out.append(_V(f"vitals.{res}_bounds", "error", turn,
                              f"{name}: {res}={cur} fora de [0, {mx}]",
                              entity=name, res=res, value=cur, max=mx, kind=kind))

    bounds(p, "player", p.get("name", "herói"))
    for c in state.get("party", []) or []:
        if isinstance(c, dict) and c.get("active"):
            bounds(c, "companion", c.get("name", "aliado"))
    for e in state.get("enemies", []) or []:
        if isinstance(e, dict) and e.get("status") == "ativo":
            bounds(e, "enemy", e.get("name", "inimigo"))

    # conflito-13 (cutover v4): Vitalidade 0 NÃO é morte — no motor novo a queda vem
    # de Ferimentos (05/07); Vitalidade 0 é só "muito ferido, ainda de pé". A morte
    # REAL é a flag `dead` (o combat_node abre death_pending nesse caso). Só é
    # violação se o player está `dead` sem game_over E sem death_pending (morto e o
    # jogo seguiu). hp espelha Vitalidade — por isso hp=0 deixou de ser sinal de morte.
    if p.get("dead") and not state.get("game_over") and not state.get("death_pending"):
        out.append(_V("vitals.dead_no_game_over", "error", turn,
                      "player morto (dead) mas nem game_over nem death_pending setado", dead=True))

    # Ferimentos não podem exceder os espaços derivados de Corpo (integridade v4).
    fer = p.get("ferimentos") or {}
    espacos = p.get("ferimento_espacos") or {}
    for cat in ("leve", "grave", "critico"):
        cap = int(espacos.get(cat, 0) or 0)
        n = len(fer.get(cat, []) or [])
        if cap and n > cap:
            out.append(_V("vitals.ferimentos_overflow", "error", turn,
                          f"Ferimentos {cat}={n} excedem os espaços ({cap})",
                          categoria=cat, n=n, cap=cap))
    return out


def check_vitality_consistency(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Enquanto aliases HP existirem, eles devem espelhar a Vitalidade v4."""
    out: List[Violation] = []
    entities = [("player", state.get("player") or {})]
    entities += [
        (str(e.get("id") or e.get("name") or "enemy"), e)
        for e in (state.get("enemies") or [])
        if isinstance(e, dict)
    ]
    entities += [
        (str(a.get("id") or a.get("name") or "ally"), a)
        for a in (state.get("party") or [])
        if isinstance(a, dict)
    ]
    for entity_id, entity in entities:
        if "vitalidade" not in entity or "hp" not in entity:
            continue
        vitality = int(entity.get("vitalidade", 0) or 0)
        hp = int(entity.get("hp", 0) or 0)
        max_vitality = int(entity.get("max_vitalidade", vitality) or vitality)
        max_hp = int(entity.get("max_hp", hp) or hp)
        if hp != vitality or max_hp != max_vitality:
            out.append(_V(
                "vitality.consistency",
                "error",
                turn,
                f"{entity_id}: aliases HP {hp}/{max_hp} divergem de "
                f"Vitalidade {vitality}/{max_vitality}",
                entity=entity_id,
                hp=hp,
                max_hp=max_hp,
                vitalidade=vitality,
                max_vitalidade=max_vitality,
            ))
    return out


def check_wound_capacity(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Último Crítico cheio precisa estar ligado ao fluxo terminal/morte."""
    from services import death_flow

    entities = [("player", state.get("player") or {})]
    entities += [
        (str(actor.get("id") or actor.get("name") or "enemy"), actor)
        for actor in (state.get("enemies") or [])
        if isinstance(actor, dict)
    ]
    entities += [
        (str(actor.get("id") or actor.get("name") or "ally"), actor)
        for actor in (state.get("party") or [])
        if isinstance(actor, dict)
    ]
    out: List[Violation] = []
    for actor_id, actor in entities:
        if not death_flow.critical_spaces_full(actor):
            continue
        linked = bool(
            actor.get("dead") or actor.get("estado_terminal")
            or actor.get("last_stand_pending") or actor.get("last_stand_resolved")
            or actor.get("scar_pending")
        )
        if not linked:
            out.append(_V(
                "wound.capacity", "error", turn,
                f"{actor_id}: último Crítico cheio sem fluxo terminal ou morte",
                entity=actor_id,
            ))
    return out


# --- R2 economia ------------------------------------------------------------

def _unique_ids() -> set:
    from gamedata import ARTIFACTS_DB
    return {iid for iid, a in ARTIFACTS_DB.items() if isinstance(a, dict) and a.get("unique")}


def _inv_ids(entity: dict) -> List[dict]:
    return [e for e in (entity.get("inventory") or []) if isinstance(e, dict)]


def check_economy(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    p = state.get("player", {}) or {}

    if int(p.get("gold", 0) or 0) < 0:
        out.append(_V("economy.gold_negative", "error", turn,
                      f"ouro negativo: {p.get('gold')}", gold=p.get("gold")))

    for e in _inv_ids(p):
        if int(e.get("qty", 1) or 0) < 1:
            out.append(_V("economy.qty_invalid", "error", turn,
                          f"item {e.get('id')} com qty {e.get('qty')} < 1",
                          item=e.get("id"), qty=e.get("qty")))

    eq = p.get("equipment") or {}
    equipped = [v for v in eq.values() if v]
    if len(equipped) != len(set(equipped)):
        out.append(_V("economy.equip_dupe", "error", turn,
                      f"mesmo item em mais de um slot: {equipped}", equipped=equipped))

    # Item único: no máximo 1 lugar no mundo (inventários + estoques de mercador).
    uniques = _unique_ids()
    world = state.get("world", {}) or {}
    for uid in uniques:
        places = 0
        for e in _inv_ids(p):
            if e.get("id") == uid:
                places += 1
                if int(e.get("qty", 1) or 1) > 1:
                    places += 1  # unique não empilha
        for c in state.get("party", []) or []:
            if isinstance(c, dict) and any(x.get("id") == uid for x in _inv_ids(c)):
                places += 1
        for stock in (world.get("merchant_stocks") or {}).values():
            if isinstance(stock, dict) and int(stock.get(uid, 0) or 0) > 0:
                places += 1
        if places > 1:
            out.append(_V("economy.unique_dupe", "error", turn,
                          f"item único {uid} existe em {places} lugares", item=uid, places=places))
    return out


# --- R3 entidades -----------------------------------------------------------

def _killed_ids(state: dict) -> set:
    return {ev.get("target_id") for ev in (state.get("event_log") or [])
            if isinstance(ev, dict) and ev.get("type") == "npc_killed" and ev.get("target_id")}


def check_entities(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    killed = _killed_ids(state)
    if not killed:
        return out
    from services.npc_layers import is_in_scene

    for name, data in (state.get("npcs") or {}).items():
        if not isinstance(data, dict):
            continue
        ids = {data.get("id"), data.get("origin_id"), name}
        if ids & killed and is_in_scene(data):
            out.append(_V("entities.dead_npc_in_scene", "error", turn,
                          f"NPC morto '{name}' ainda está em cena", npc=name))

    for c in state.get("party", []) or []:
        if not isinstance(c, dict) or not c.get("active"):
            continue
        ids = {c.get("id"), c.get("origin_id"), c.get("name")}
        if ids & killed:
            out.append(_V("entities.dead_companion_active", "error", turn,
                          f"companion morto '{c.get('name')}' segue ativo na party", npc=c.get("name")))
    return out


# --- R4 mundo ---------------------------------------------------------------

def check_world(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    from gamedata import get_location
    from services.graph_resolver import get_current_controller

    world = state.get("world", {}) or {}
    projection = state.get("world_projection", {}) or {}

    cur = world.get("current_location_id", "")
    if cur and not get_location(cur):
        out.append(_V("world.location_unknown", "error", turn,
                      f"current_location_id '{cur}' não existe no grafo", loc=cur))

    for loc in world.get("visited", []) or []:
        if not get_location(loc):
            out.append(_V("world.visited_unknown", "error", turn,
                          f"local visitado '{loc}' não existe no grafo", loc=loc))

    defeated = {f.get("id") for f in (state.get("factions") or [])
                if isinstance(f, dict) and f.get("defeated")}
    if defeated:
        for loc in world.get("visited", []) or []:
            controller = get_current_controller(loc, projection, include_hidden=True)
            if controller in defeated:
                out.append(_V("world.defeated_controls", "error", turn,
                              f"fação derrotada '{controller}' ainda controla '{loc}'",
                              loc=loc, faction=controller))

    if prev:
        prev_day = ((prev.get("world") or {}).get("world_clock") or {}).get("day")
        cur_day = (world.get("world_clock") or {}).get("day")
        if isinstance(prev_day, int) and isinstance(cur_day, int) and cur_day < prev_day:
            out.append(_V("world.clock_regressed", "error", turn,
                          f"relógio voltou: dia {prev_day} → {cur_day}",
                          prev_day=prev_day, day=cur_day))
    return out


def check_summary_bounds(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    from services.memory_summary import NARRATIVE_SUMMARY_MAX_CHARS
    summary = str(state.get("narrative_summary") or "")
    if len(summary) <= NARRATIVE_SUMMARY_MAX_CHARS:
        return []
    return [_V(
        "memory.summary_bounds", "error", turn,
        f"narrative_summary tem {len(summary)} caracteres; teto é "
        f"{NARRATIVE_SUMMARY_MAX_CHARS}",
        chars=len(summary), max_chars=NARRATIVE_SUMMARY_MAX_CHARS,
    )]


def check_campaign_grounding(state: dict, prev: Optional[dict],
                             turn: int) -> List[Violation]:
    """Tolera o próprio turno de viagem; no turno seguinte o plano deve ancorar."""
    world = state.get("world") or {}
    plan = state.get("campaign_plan") or {}
    current = str(world.get("current_location") or "")
    planned = str(plan.get("location") or "")
    if not current or not planned or current == planned:
        return []
    previous_location = str(((prev or {}).get("world") or {}).get("current_location") or "")
    if previous_location and previous_location != current:
        return []
    try:
        from agents.campaign_manager import _same_region
        stale = not _same_region(planned, current)
    except Exception:
        stale = False
    if not stale:
        return []
    return [_V(
        "campaign.region_grounding", "error", turn,
        f"plano ancorado em {planned!r} enquanto a cena permanece em {current!r}",
        planned_location=planned, current_location=current,
    )]


def check_reward_feedback(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    if not prev:
        return []
    player = state.get("player") or {}
    previous = prev.get("player") or {}
    gold_gained = int(player.get("gold", 0) or 0) > int(previous.get("gold", 0) or 0)

    def inventory_total(actor: dict) -> int:
        return sum(int(entry.get("qty", 1) or 1)
                   for entry in (actor.get("inventory") or [])
                   if isinstance(entry, dict))

    item_gained = inventory_total(player) > inventory_total(previous)
    if not (gold_gained or item_gained):
        return []
    narrative = _last_narration(state)
    import re
    if not re.search(
        r"\b(?:nada novo (?:foi )?obtido|nenhum(?:a)? (?:recompensa|objeto|item).{0,30}(?:obtido|acrescentado))\b",
        narrative, re.IGNORECASE,
    ):
        return []
    return [_V(
        "narrative.reward_contradiction", "error", turn,
        "a narração negou uma recompensa confirmada pelo delta mecânico",
        gold_before=previous.get("gold"), gold_after=player.get("gold"),
        item_gained=item_gained,
    )]


# --- R5 conhecimento --------------------------------------------------------

# spec beats-visibilidade-ptbr (R1): as assinaturas migraram para o módulo
# compartilhado (consumido também pelo campaign_manager). Alias p/ compat.
from services.secret_signatures import SECRET_SIGNATURES, revealed_corpus

_SECRET_SIGNATURES = SECRET_SIGNATURES  # compat com quem importava daqui
_revealed_corpus = revealed_corpus


def check_knowledge(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    out: List[Violation] = []
    revealed = revealed_corpus(state)
    # spec beats-visibilidade-ptbr (R5): checa a narração E o texto dos beats do
    # plano (antes só narração — o vazamento do playtest veio de um BEAT).
    fontes = [("narração", _last_narration(state).lower())]
    for b in ((state.get("campaign_plan") or {}).get("beats") or []):
        if isinstance(b, dict) and b.get("description"):
            fontes.append(("beat", str(b["description"]).lower()))
    for origem, text in fontes:
        if not text:
            continue
        for secret_id, phrases in SECRET_SIGNATURES.items():
            for ph in phrases:
                if ph in text and ph not in revealed:
                    out.append(_V("knowledge.secret_leak", "warning", turn,
                                  f"{origem} vazou segredo '{secret_id}': “{ph}”",
                                  secret=secret_id, phrase=ph, origem=origem))
                    break
    return out


def _last_narration(state: dict) -> str:
    for msg in reversed(state.get("messages", []) or []):
        content = getattr(msg, "content", "")
        if content and getattr(msg, "type", "") != "human":
            return str(content)
    return ""


# --- R6 roundtrip (fora do loop por-turno: faz I/O de disco) ----------------

_ROUNDTRIP_FIELDS = ["player", "world", "party", "enemies", "factions",
                     "faction_intel", "bestiary_knowledge", "npcs", "quests",
                     "campaign_plan", "event_log", "world_projection", "game_over"]


def check_roundtrip(state: dict, prev: Optional[dict] = None, turn: int = 0) -> List[Violation]:
    """save → load → compara campos persistidos. NÃO entra em CHECKS (I/O)."""
    import json
    import persistence

    try:
        persistence.save_game_state(state)
        reloaded = persistence.load_game_state(persistence.save_path(state.get("game_id", "")))
    except Exception as e:
        return [_V("save.roundtrip", "error", turn, f"roundtrip falhou: {e!r}")]
    out: List[Violation] = []
    for k in _ROUNDTRIP_FIELDS:
        a = json.dumps(state.get(k), sort_keys=True, default=str, ensure_ascii=False)
        b = json.dumps((reloaded or {}).get(k), sort_keys=True, default=str, ensure_ascii=False)
        if a != b:
            out.append(_V("save.roundtrip", "warning", turn,
                          f"campo '{k}' difere após save→load", field=k))
    return out


# --- orquestração -----------------------------------------------------------

def check_lifecycle(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """R4 (fix-playtest-achados): save morto é terminal. Se o turno ANTERIOR já
    estava com game_over e mesmo assim o relógio avançou, um morto agiu — o gate
    do grafo (main.py) deveria ter barrado."""
    if not prev or not prev.get("game_over"):
        return []
    prev_turn = (prev.get("world") or {}).get("turn_count")
    cur_turn = (state.get("world") or {}).get("turn_count")
    if isinstance(prev_turn, int) and isinstance(cur_turn, int) and cur_turn > prev_turn:
        return [_V("lifecycle.acts_after_game_over", "error", turn,
                   f"turno processado após game_over (turn {prev_turn} → {cur_turn})",
                   prev_turn=prev_turn, turn_count=cur_turn)]
    return []


# spec combate-lifecycle (R4): combate ativo por muitos turnos sem receber rota
# de combate = "zumbi" (o bug do playtest longo: combat.active True por 59 turnos).
# `idle_turns` (mantido pelo router/combat_node) é o contador; R3 deveria expirar
# em 3, então idle >= 5 só sobra se R3 falhou — daí severidade `error`.
COMBAT_ZOMBIE_IDLE = 5


def check_combat_zombie(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    combat = state.get("combat") or {}
    if not combat.get("active"):
        return []
    idle = int(combat.get("idle_turns", 0) or 0)
    if idle >= COMBAT_ZOMBIE_IDLE:
        return [_V("combat.zombie", "error", turn,
                   f"combate ativo há {idle} turnos sem rota de combate "
                   f"(R3 deveria ter expirado em {COMBAT_ZOMBIE_IDLE})",
                   idle_turns=idle)]
    return []


_INVALID_SENTINELS = {"null", "none", "nil", "undefined", "n/a", "nan"}


def check_invalid_sentinels(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Strings-sentinela de structured output não podem virar entidades/IDs."""
    out: List[Violation] = []
    for key in (state.get("npcs") or {}):
        if str(key).strip().casefold() in _INVALID_SENTINELS:
            out.append(_V(
                "npc.invalid_sentinel",
                "error",
                turn,
                f"NPC inválido persistido com chave-sentinela {key!r}",
                field="npcs",
                value=key,
            ))
    for field_name in ("active_npc_name", "combat_target"):
        value = state.get(field_name)
        if isinstance(value, str) and value.strip().casefold() in _INVALID_SENTINELS:
            out.append(_V(
                "npc.invalid_sentinel",
                "error",
                turn,
                f"{field_name} contém sentinela textual {value!r}",
                field=field_name,
                value=value,
            ))
    return out


def check_rag_persistence(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """O archivist expõe falha persistente; o harness não pode silenciá-la."""
    error = state.get("rag_persistence_error")
    if not error:
        return []
    return [_V(
        "rag.persistence_error",
        "error",
        turn,
        f"persistência RAG falhou: {str(error)[:240]}",
        error=str(error)[:240],
    )]


def check_memory_provenance(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Memória confirmada precisa apontar para fonte que o motor consegue provar."""
    from services.memory_provenance import (
        normalize_memory_facts,
        source_is_applicable,
    )

    out: List[Violation] = []
    for record in normalize_memory_facts(state.get("memory_facts")):
        if record.get("confidence") != "confirmed":
            continue
        source_id = record.get("source_id")
        if source_is_applicable(source_id, state):
            continue
        out.append(_V(
            "memory.confirmed_without_source",
            "error",
            turn,
            f"memória confirmada {record.get('memory_id')!r} não tem fonte aplicável",
            memory_id=record.get("memory_id"),
            source_id=source_id,
            provenance=record.get("provenance"),
        ))
    return out


def check_summary_lifecycle(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Um resumo não consumido não pode atravessar silenciosamente outro turno."""
    if not prev:
        return []
    previous = prev.get("conflict_summary")
    current = state.get("conflict_summary")
    if not previous or not current or previous != current:
        return []
    prev_turn = int((prev.get("world") or {}).get("turn_count", 0) or 0)
    current_turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    if current_turn <= prev_turn or (state.get("combat") or {}).get("active"):
        return []
    return [_V(
        "summary.lifecycle",
        "error",
        turn,
        f"ConflictSummary atravessou o turno {prev_turn}→{current_turn} sem consumo",
        previous_turn=prev_turn,
        current_turn=current_turn,
    )]


def check_duplicate_consumed_summary(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Um ID confirmado no ledger não pode reaparecer como summary pendente."""
    summary = state.get("conflict_summary")
    if not isinstance(summary, dict) or not summary:
        return []
    from services import conflict_summary as summary_service
    conflict_id = summary_service.ensure_conflict_id(
        summary,
        turn=summary.get("conflict_turn"),
    )
    consumed = set(summary_service.normalize_consumed_conflict_ids(
        state.get("consumed_conflict_ids")
    ))
    if conflict_id not in consumed:
        return []
    return [_V(
        "summary.duplicate_consumption",
        "error",
        turn,
        f"ConflictSummary {conflict_id!r} reapareceu após consumo confirmado",
        conflict_id=conflict_id,
    )]


def _wounds_fingerprint(entity: dict) -> tuple:
    wounds = entity.get("ferimentos") or {}
    return tuple(
        (
            category,
            json.dumps(wounds.get(category, []) or [], sort_keys=True,
                       ensure_ascii=False, default=str),
        )
        for category in ("leve", "grave", "critico")
    )


def combat_progress_fingerprint(state: dict) -> Optional[tuple]:
    """Assinatura apenas de progresso mecânico; exclui round, texto e recursos."""
    combat = state.get("combat") or {}
    if not combat.get("active"):
        return None
    entities = [("player", state.get("player") or {})]
    entities += [
        (str(e.get("id") or e.get("name") or "?"), e)
        for e in (state.get("enemies") or [])
        if isinstance(e, dict)
    ]
    actor_bits = []
    for actor_id, entity in sorted(entities, key=lambda pair: pair[0]):
        actor_bits.append((
            actor_id,
            int(entity.get("vitalidade", entity.get("hp", 0)) or 0),
            str(entity.get("status") or ""),
            bool(entity.get("dead")),
            bool(entity.get("conscious", True)),
            _wounds_fingerprint(entity),
            json.dumps(entity.get("active_conditions", []) or [],
                       sort_keys=True, ensure_ascii=False, default=str),
        ))
    scene = combat.get("scene") or {}
    scene_bits = (
        json.dumps(scene.get("positions", {}) or {}, sort_keys=True,
                   ensure_ascii=False, default=str),
        json.dumps(scene.get("engagements", []) or [], sort_keys=True,
                   ensure_ascii=False, default=str),
        json.dumps(
            [
                {
                    "id": obj.get("id"),
                    "integrity": obj.get("integrity"),
                    "destroyed": obj.get("destroyed"),
                }
                for obj in (scene.get("objects") or [])
                if isinstance(obj, dict)
            ],
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ),
    )
    chase = combat.get("chase") or {}
    chase_bits = (
        str(chase.get("trilha") or ""),
        bool(chase.get("alcancado")),
        bool(chase.get("escapou")),
        str(chase.get("fugitive_id") or ""),
        tuple(sorted(str(value) for value in (chase.get("perseguidores") or []))),
    )
    return tuple(actor_bits), scene_bits, chase_bits


COMBAT_NO_PROGRESS_LIMIT = 5


def check_combat_no_progress(context: Optional[dict], turn: int) -> List[Violation]:
    streak = int((context or {}).get("combat_no_progress_streak", 0) or 0)
    if streak < COMBAT_NO_PROGRESS_LIMIT:
        return []
    return [_V(
        "combat.no_progress",
        "error",
        turn,
        f"conflito avançou {streak} rodadas sem mudança mecânica observável",
        streak=streak,
        threshold=COMBAT_NO_PROGRESS_LIMIT,
    )]


def check_action_declaration(
    decision: Optional[dict],
    resolved: Optional[dict],
    *,
    turn: int,
    combat_executed: bool,
) -> List[Violation]:
    """Compara a escolha única do perfil ao resultado canônico do combat_node."""
    decision = decision or {}
    if not combat_executed or decision.get("mode") not in ("declaration", "flee"):
        return []
    if not resolved:
        return [_V(
            "action.declaration_matches",
            "error",
            turn,
            f"decisão {decision.get('kind')!r} executou combate sem resultado canônico",
            expected_kind=str(decision.get("kind") or ""),
            resolved_kind="",
            mismatches={"resolved_action": ["present", "missing"]},
            decision=decision,
            resolved={},
        )]
    expected_kind = str(decision.get("kind") or "")
    resolved_kind = str(resolved.get("kind") or "")
    mismatches = {}
    if expected_kind != resolved_kind:
        mismatches["kind"] = [expected_kind, resolved_kind]
    for field_name in ("card_id", "item_id", "target_id"):
        expected = decision.get(field_name)
        actual = resolved.get(field_name)
        if expected is not None and expected != actual:
            mismatches[field_name] = [expected, actual]
    if expected_kind == "flee":
        attempted = resolved.get("attempted", True)
        if not attempted:
            mismatches["attempted"] = [True, attempted]
        expected_destination = decision.get("flee_destination_id")
        actual_destination = (
            resolved.get("flee_destination_id")
            or resolved.get("destination_id")
        )
        if expected_destination is not None and actual_destination is not None \
                and expected_destination != actual_destination:
            mismatches["flee_destination_id"] = [
                expected_destination, actual_destination,
            ]
    result = str(resolved.get("result") or "")
    if result == "invalid":
        mismatches["result"] = ["valid", "invalid"]
    elif result == "interrupted" and resolved.get("attempted", True):
        mismatches["attempted"] = [False, True]
    if not mismatches:
        return []
    return [_V(
        "action.declaration_matches",
        "error",
        turn,
        f"decisão {expected_kind!r} divergiu do efeito {resolved_kind!r}",
        expected_kind=expected_kind,
        resolved_kind=resolved_kind,
        mismatches=mismatches,
        decision=decision,
        resolved=resolved,
    )]


def check_contextual(
    state: dict, prev: Optional[dict], turn: int, context: Optional[dict],
) -> List[Violation]:
    context = context or {}
    out = check_combat_no_progress(context, turn)
    action = str(context.get("action") or "")
    if context.get("profile") == "normal" and re.search(
        r"\b(?:descreva|narre|beat|campaign_plan|objetivo principal:)\b",
        action,
        flags=re.IGNORECASE,
    ):
        out.append(_V(
            "profile.private_plan_leak", "error", turn,
            "perfil normal expôs metalinguagem/instrução privada na ação",
            action=action[:240],
        ))
    out += check_action_declaration(
        context.get("decision"),
        context.get("resolved_action"),
        turn=turn,
        combat_executed=bool(context.get("combat_executed")),
    )
    economy_action = context.get("economy_action") or {}
    if economy_action:
        gold_before = int(economy_action.get("gold_before", 0) or 0)
        gold_after = int(economy_action.get("gold_after", 0) or 0)
        gold_delta = int(economy_action.get("gold_delta", 0) or 0)
        if economy_action.get("ok") and gold_after - gold_before != gold_delta:
            out.append(_V(
                "economy.transaction_conservation", "error", turn,
                "delta de ouro da transação diverge do ledger Python",
                outcome=economy_action,
            ))
        for field_name in ("stock_before", "stock_after"):
            for quote in economy_action.get(field_name) or []:
                if int(quote.get("stock", 0) or 0) < 0:
                    out.append(_V(
                        "economy.stock_bounds", "error", turn,
                        "estoque negativo no ledger de mercado",
                        field=field_name, quote=quote,
                    ))
        before_qty: dict[str, int] = {}
        after_qty: dict[str, int] = {}
        for item in economy_action.get("inventory_before") or []:
            if isinstance(item, dict):
                item_id = str(item.get("id") or "")
                before_qty[item_id] = before_qty.get(item_id, 0) + int(
                    item.get("qty", 1) or 0
                )
        for item in economy_action.get("inventory_after") or []:
            if isinstance(item, dict):
                item_id = str(item.get("id") or "")
                after_qty[item_id] = after_qty.get(item_id, 0) + int(
                    item.get("qty", 1) or 0
                )
        if economy_action.get("ok") and economy_action.get("item_id"):
            item_id = str(economy_action["item_id"])
            qty = int(economy_action.get("qty", 1) or 1)
            mode = str(economy_action.get("mode") or "")
            delta_qty = after_qty.get(item_id, 0) - before_qty.get(item_id, 0)
            expected = qty if mode in ("buy", "craft") else -qty
            if delta_qty != expected:
                out.append(_V(
                    "economy.transaction_conservation", "error", turn,
                    "delta de item da transação diverge do ledger Python",
                    item_id=item_id, expected=expected, actual=delta_qty,
                    outcome=economy_action,
                ))
    net_worth = context.get("net_worth_after")
    if net_worth is not None and not isinstance(net_worth, int):
        out.append(_V(
            "economy.net_worth_finite", "error", turn,
            "net worth não é inteiro finito", value=net_worth,
        ))
    decision = context.get("decision") or {}
    resolved = context.get("resolved_action") or {}
    chase_state = (state.get("combat") or {}).get("chase") or {}
    if (decision.get("kind") == "flee"
            and resolved.get("result") == "flee_failed"
            and chase_state.get("trilha") in ("afastado", "quase_livre")
            and not chase_state.get("alcancado")):
        out.append(_V(
            "combat.flee_progress_mislabeled", "error", turn,
            "progresso válido de perseguição foi classificado como falha",
            chase_track=chase_state.get("trilha"), result=resolved.get("result"),
        ))
    latency_ms = int(context.get("latency_ms", 0) or 0)
    if context.get("real_llm") and latency_ms > 45_000:
        severity: Severity = "error" if latency_ms > 90_000 else "warning"
        out.append(_V(
            "performance.turn_latency", severity, turn,
            f"turno real levou {latency_ms / 1000:.1f}s",
            latency_ms=latency_ms, warning_ms=45_000, error_ms=90_000,
        ))
    rag_errors = [
        event for event in (context.get("rag_events") or [])
        if not bool(event.get("success", True))
    ]
    for event in rag_errors:
        out.append(_V(
            "rag.persistence_error",
            "error",
            turn,
            f"operação RAG {event.get('operation', '?')} falhou: "
            f"{str(event.get('error') or '')[:200]}",
            operation=event.get("operation"),
            error=str(event.get("error") or "")[:200],
        ))
    if context.get("combat_ended"):
        summary_present = bool(state.get("conflict_summary"))
        rag_error = state.get("rag_persistence_error")
        current_turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
        archived = any(
            isinstance(entry, dict)
            and entry.get("kind") == "conflict"
            and int(entry.get("turn", -1) or -1) == current_turn
            for chapter in (state.get("chronicle") or [])
            if isinstance(chapter, dict)
            for entry in (chapter.get("entries") or [])
        )
        if summary_present and not rag_error:
            out.append(_V(
                "summary.lifecycle",
                "error",
                turn,
                "conflito encerrou, mas o ConflictSummary ficou pendente após o archivist",
                world_turn=current_turn,
                conflict_id=str(
                    (state.get("conflict_summary") or {}).get("conflict_id") or ""
                ),
            ))
        elif not summary_present and not archived:
            out.append(_V(
                "summary.lifecycle",
                "error",
                turn,
                "conflito encerrou sem ConflictSummary presente ou arquivado",
                world_turn=current_turn,
            ))
    return out



def check_recycled_npc(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """spec encontros-dedupe (R4) + npc-in-scene-viagem (R3): NPC GERADO (tem
    `created_turn`) que VAZA para o contexto do narrador fora do local onde nasceu
    = reciclagem/flag zumbi (o 'Sobrevivente moribundo' em 3 locais; a flag
    in_scene que sobrevivia à viagem).

    Mede USO OBSERVÁVEL, não a flag crua: só reporta quando o nome remoto aparece
    na última narração ou entre aliados transitórios do combate. Uma flag residual
    filtrada pelas views não produz falso positivo."""
    out: List[Violation] = []
    loc = (state.get("world") or {}).get("current_location_id", "") or ""
    if not loc:
        return out
    active_npc = str(state.get("active_npc_name") or "").casefold()
    combat_names = {
        str(ally.get("name") or "").casefold()
        for ally in ((state.get("combat") or {}).get("scene_allies") or [])
        if isinstance(ally, dict)
    }
    party_names = {c.get("name") for c in (state.get("party") or [])
                   if isinstance(c, dict)}
    for name, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        home = npc.get("home_location_id") or ""
        # Vínculo legítimo (home == loc) ou membro de party NÃO é vazamento.
        actually_used = name.casefold() == active_npc or name.casefold() in combat_names
        if (npc.get("created_turn") is not None and actually_used
                and name not in party_names and home and home != loc):
            out.append(_V("narrative.recycled_npc", "warning", turn,
                          f"NPC gerado '{name}' no contexto fora do local de origem "
                          f"(origem={home}, atual={loc})", npc=name, home=home, loc=loc))
    return out


def check_zero_vitality_outside_terminal(
    state: dict, prev: Optional[dict], turn: int,
) -> List[Violation]:
    """Vitalidade 0 só é jogável dentro do conflito ou do fluxo terminal."""
    player = state.get("player") or {}
    vitality = int(player.get("vitalidade", player.get("hp", 0)) or 0)
    if vitality != 0:
        return []
    if (state.get("combat") or {}).get("active"):
        return []
    if state.get("death_pending") or state.get("game_over"):
        return []
    return [_V(
        "player.zero_vitality_outside_terminal", "error", turn,
        "protagonista com Vitalidade 0 saiu do combate sem fluxo terminal",
    )]


def check_repeated_opening(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """spec polish-prosa (R5): 3 narrações consecutivas com a MESMA abertura de 6
    palavras = prosa engessada. Warning (telemetria — não reprova). Sob MockLLM a
    narração é fixa, então o runner filtra este check em modo mock (§7 da spec)."""
    from services.prose_guard import opening
    narrs: List[str] = []
    for m in reversed(state.get("messages", []) or []):
        content = getattr(m, "content", "")
        if content and getattr(m, "type", "") != "human":
            narrs.append(str(content))
            if len(narrs) >= 3:
                break
    if len(narrs) < 3:
        return []
    ops = [opening(n) for n in narrs]
    if ops[0] and ops[0] == ops[1] == ops[2]:
        return [_V("narrative.repeated_opening", "warning", turn,
                   f"3 narrações seguidas abrindo com “{ops[0]}…”", abertura=ops[0])]
    return []


def check_meta_leak(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """spec polish-prosa-v2: marcador do motor na última narração é regressão."""
    from services.prose_guard import contains_engine_marker
    for message in reversed(state.get("messages", []) or []):
        content = getattr(message, "content", "")
        if not content or getattr(message, "type", "") == "human":
            continue
        if contains_engine_marker(str(content)):
            return [_V(
                "narrative.meta_leak",
                "error",
                turn,
                "Narração visível contém marcador interno do motor.",
                sample=str(content)[:180],
            )]
        break
    return []


def check_phantom_ally(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """spec aliados-em-combate (R5): nome de aliado CITADO na narração de combate
    sem combatente correspondente do lado herói = aliado fantasma (a lacuna que
    originou o achado — o narrador inventava aliado sem lastro de estado). Só
    checa nomes de aliados CONHECIDOS (party + amigo em cena), não palavra
    qualquer → baixo falso-positivo. Warning."""
    if not (state.get("combat") or {}).get("active"):
        return []
    narr = ""
    for m in reversed(state.get("messages", []) or []):
        c = getattr(m, "content", "")
        if c and getattr(m, "type", "") != "human":
            narr = str(c)
            break
    if not narr:
        return []
    low = narr.lower()
    try:
        import party as party_mod
        present = {str(a.get("name", "")).lower()
                   for a in party_mod.active_allies(state) + party_mod.scene_allies(state)}
    except Exception:
        present = set()
    # candidatos = companheiros de party + amigos em cena (nomes conhecidos)
    candidatos = set()
    for c in (state.get("party") or []):
        if isinstance(c, dict) and c.get("name"):
            candidatos.add(str(c["name"]))
    for name, npc in (state.get("npcs") or {}).items():
        if isinstance(npc, dict) and npc.get("in_scene") \
                and int(npc.get("relationship", 5) or 5) >= 6:
            candidatos.add(str(npc.get("name", name)))
    out: List[Violation] = []
    for nome in candidatos:
        if len(nome) >= 3 and nome.lower() in low and nome.lower() not in present:
            out.append(_V("combat.phantom_ally", "warning", turn,
                          f"aliado '{nome}' citado na narração de combate sem "
                          f"combatente do lado herói", ally=nome))
    return out


def check_effect_catalog(state: dict, prev: Optional[dict], turn: int) -> List[Violation]:
    """spec conflito-13 (R5): nenhum efeito FORA do catálogo fechado (03/10) escapa
    para produção. Varre a cena de combate ativa (objetos + eventos do Abismo); um
    `effect.kind` inventado pela LLM que passou os validadores é um vazamento grave."""
    from services.conflict_scene import EFFECT_KINDS
    out: List[Violation] = []
    scene = (state.get("combat") or {}).get("scene") or {}
    for o in scene.get("objects", []) or []:
        for it in (o.get("interactions") or []):
            eff = it.get("effect") or {}
            if eff and str(eff.get("kind")) not in EFFECT_KINDS:
                out.append(_V("combat.effect_catalog", "error", turn,
                              f"efeito fora do catálogo em objeto '{o.get('id')}': "
                              f"{eff.get('kind')!r}", kind=eff.get("kind")))
    for ev in (scene.get("abyss_events") or []):
        eff = ev.get("effect") or {}
        if eff and str(eff.get("kind")) not in EFFECT_KINDS:
            out.append(_V("combat.effect_catalog", "error", turn,
                          f"evento do Abismo '{ev.get('id')}' fora do catálogo: "
                          f"{eff.get('kind')!r}", kind=eff.get("kind")))
    return out


def check_reproducibility(seed: int = 7, rounds: int = 6) -> bool:
    """spec conflito-13 (R5) / doc 03 Cenário 53: mesma seed + mesmo estado inicial →
    MESMO resultado NO CONFLITO. Verifica a reprodutibilidade do MOTOR (não da
    campanha inteira, que é confundida por caches globais legítimos de conteúdo
    gerado): roda a MESMA sequência de rodadas 2× e compara os logs. True se igual.

    Determinismo do motor = seed do RNG local + `random` global (o dano usa
    `combat_mechanics.roll_dice_numeric`, que lê o `random` global)."""
    import random as _random
    from services import conflict_orchestrator as orch
    from services import conflict_scene as cs
    from services.conflict_turn import TurnDeclaration, TurnStep

    def _one_run() -> list:
        _random.seed(seed)
        player = orch.ensure_combat_sheet(
            {"id": "player", "name": "Herói", "is_player": True, "class_name": "Sangromante",
             "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
             "attack_formula": "2d6"}, is_player=True)
        enemy = orch.ensure_combat_sheet(
            {"id": "e1", "name": "Bandido", "type": "padrao",
             "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1}})
        scene = cs.new_scene()
        cs.place(scene, "player")
        cs.place(scene, "e1")
        cs.freeze(scene)
        actors = {"player": player, "e1": enemy}
        sides = {"hero": ["player"], "enemy": ["e1"]}
        decl = TurnDeclaration(actor_id="player", acao=TurnStep(kind="attack", target_id="e1"))
        logs: list = []
        rng = _random.Random(seed)
        for _ in range(rounds):
            out = orch.run_round(scene, actors, sides, {"player": player},
                                 declarations={"player": decl}, rng=rng)
            logs += out["logs"]
            if out["ended"]:
                break
        return logs

    return _one_run() == _one_run()


Check = Callable[[dict, Optional[dict], int], List[Violation]]

CHECKS: List[Check] = [
    check_vitals, check_vitality_consistency, check_wound_capacity,
    check_economy, check_entities, check_world, check_summary_bounds,
    check_campaign_grounding, check_reward_feedback, check_knowledge,
    check_lifecycle, check_combat_zombie, check_effect_catalog,
    check_invalid_sentinels, check_rag_persistence, check_summary_lifecycle,
    check_memory_provenance,
    check_duplicate_consumed_summary,
    check_recycled_npc, check_zero_vitality_outside_terminal,
    check_repeated_opening, check_meta_leak,
    check_phantom_ally,
]


def check_all(state: dict, prev_state: Optional[dict] = None,
              turn: int = 0, context: Optional[dict] = None) -> List[Violation]:
    out: List[Violation] = []
    for fn in CHECKS:
        try:
            out.extend(fn(state, prev_state, turn) or [])
        except Exception as exc:
            # O check não derruba a campanha, mas também não pode produzir verde.
            out.append(_V(
                "invariant.crash",
                "error",
                turn,
                f"{fn.__name__} falhou com {type(exc).__name__}: {str(exc)[:180]}",
                check=fn.__name__,
                exception_type=type(exc).__name__,
                error=str(exc)[:180],
            ))
    try:
        out.extend(check_contextual(state, prev_state, turn, context) or [])
    except Exception as exc:
        out.append(_V(
            "invariant.crash",
            "error",
            turn,
            f"check_contextual falhou com {type(exc).__name__}: {str(exc)[:180]}",
            check="check_contextual",
            exception_type=type(exc).__name__,
            error=str(exc)[:180],
        ))
    return out


def assert_invariants(state: dict) -> None:
    """Uso em testes: levanta AssertionError legível com TODAS as violações."""
    violations = check_all(state)
    if violations:
        linhas = "\n".join(f"  [{v.severity}] {v.check_id}: {v.message}" for v in violations)
        raise AssertionError(f"{len(violations)} invariante(s) violado(s):\n{linhas}")
