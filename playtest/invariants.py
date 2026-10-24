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
from typing import List, Literal, Optional
from collections.abc import Callable

Severity = Literal["error", "warning"]


@dataclass
class Violation:
    check_id: str
    severity: Severity
    turn: int
    message: str
    details: dict = field(default_factory=dict)


def _V(check_id, severity, turn, message, **details) -> Violation:
    return Violation(
        check_id=check_id, severity=severity, turn=turn, message=message, details=details
    )


# --- R1 vitals --------------------------------------------------------------


def check_vitals(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    out: list[Violation] = []
    p = state.get("player", {}) or {}

    def bounds(entity, kind, name):
        # Vitalidade é o recurso canônico do conflito v4. HP permanece apenas
        # como alias de compatibilidade e é auditado, separadamente, por
        # check_vitality_consistency.
        for res, cap in (("vitalidade", "max_vitalidade"),):
            cur = entity.get(res)
            mx = entity.get(cap)
            if cur is None or mx is None:
                continue
            if cur < 0 or cur > mx:
                out.append(
                    _V(
                        f"vitals.{res}_bounds",
                        "error",
                        turn,
                        f"{name}: {res}={cur} fora de [0, {mx}]",
                        entity=name,
                        res=res,
                        value=cur,
                        max=mx,
                        kind=kind,
                    )
                )

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
        out.append(
            _V(
                "vitals.dead_no_game_over",
                "error",
                turn,
                "player morto (dead) mas nem game_over nem death_pending setado",
                dead=True,
            )
        )

    # Ferimentos não podem exceder os espaços derivados de Corpo (integridade v4).
    fer = p.get("ferimentos") or {}
    espacos = p.get("ferimento_espacos") or {}
    for cat in ("leve", "grave", "critico"):
        cap = int(espacos.get(cat, 0) or 0)
        n = len(fer.get(cat, []) or [])
        if cap and n > cap:
            out.append(
                _V(
                    "vitals.ferimentos_overflow",
                    "error",
                    turn,
                    f"Ferimentos {cat}={n} excedem os espaços ({cap})",
                    categoria=cat,
                    n=n,
                    cap=cap,
                )
            )
    return out


def check_vitality_consistency(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """Enquanto aliases HP existirem, eles devem espelhar a Vitalidade v4."""
    out: list[Violation] = []
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
            out.append(
                _V(
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
                )
            )
    return out


def check_wound_capacity(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
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
    out: list[Violation] = []
    for actor_id, actor in entities:
        if not death_flow.critical_spaces_full(actor):
            continue
        linked = bool(
            actor.get("dead")
            or actor.get("estado_terminal")
            or actor.get("last_stand_pending")
            or actor.get("last_stand_resolved")
            or actor.get("scar_pending")
        )
        if not linked:
            out.append(
                _V(
                    "wound.capacity",
                    "error",
                    turn,
                    f"{actor_id}: último Crítico cheio sem fluxo terminal ou morte",
                    entity=actor_id,
                )
            )
    return out


# --- R2 economia ------------------------------------------------------------


def _unique_ids() -> set:
    from gamedata import ARTIFACTS_DB

    return {iid for iid, a in ARTIFACTS_DB.items() if isinstance(a, dict) and a.get("unique")}


def _inv_ids(entity: dict) -> list[dict]:
    return [e for e in (entity.get("inventory") or []) if isinstance(e, dict)]


def check_economy(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    out: list[Violation] = []
    p = state.get("player", {}) or {}

    if int(p.get("gold", 0) or 0) < 0:
        out.append(
            _V(
                "economy.gold_negative",
                "error",
                turn,
                f"ouro negativo: {p.get('gold')}",
                gold=p.get("gold"),
            )
        )

    for e in _inv_ids(p):
        if int(e.get("qty", 1) or 0) < 1:
            out.append(
                _V(
                    "economy.qty_invalid",
                    "error",
                    turn,
                    f"item {e.get('id')} com qty {e.get('qty')} < 1",
                    item=e.get("id"),
                    qty=e.get("qty"),
                )
            )

    eq = p.get("equipment") or {}
    equipped = [v for v in eq.values() if v]
    if len(equipped) != len(set(equipped)):
        out.append(
            _V(
                "economy.equip_dupe",
                "error",
                turn,
                f"mesmo item em mais de um slot: {equipped}",
                equipped=equipped,
            )
        )

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
            out.append(
                _V(
                    "economy.unique_dupe",
                    "error",
                    turn,
                    f"item único {uid} existe em {places} lugares",
                    item=uid,
                    places=places,
                )
            )
    return out


# --- R3 entidades -----------------------------------------------------------


def _killed_ids(state: dict) -> set:
    return {
        ev.get("target_id")
        for ev in (state.get("event_log") or [])
        if isinstance(ev, dict) and ev.get("type") == "npc_killed" and ev.get("target_id")
    }


def check_entities(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    out: list[Violation] = []
    from services.entity_identity import runtime_npc_aliases

    seen_identities: dict[str, str] = {}
    for key, data in (state.get("npcs") or {}).items():
        if not isinstance(data, dict):
            continue
        aliases = runtime_npc_aliases(str(key), data)
        duplicate_alias = next(
            (alias for alias in sorted(aliases) if alias in seen_identities),
            None,
        )
        if duplicate_alias is not None:
            out.append(
                _V(
                    "entity.npc_duplicate_identity",
                    "error",
                    turn,
                    f"NPC {data.get('name') or key!r} existe sob duas chaves",
                    identity=duplicate_alias,
                    first_key=seen_identities[duplicate_alias],
                    duplicate_key=str(key),
                )
            )
        else:
            for alias in aliases:
                seen_identities[alias] = str(key)
    killed = _killed_ids(state)
    if not killed:
        return out
    from services.npc_layers import is_in_scene

    for name, data in (state.get("npcs") or {}).items():
        if not isinstance(data, dict):
            continue
        ids = {data.get("id"), data.get("origin_id"), name}
        if ids & killed and is_in_scene(data):
            out.append(
                _V(
                    "entities.dead_npc_in_scene",
                    "error",
                    turn,
                    f"NPC morto '{name}' ainda está em cena",
                    npc=name,
                )
            )

    for c in state.get("party", []) or []:
        if not isinstance(c, dict) or not c.get("active"):
            continue
        ids = {c.get("id"), c.get("origin_id"), c.get("name")}
        if ids & killed:
            out.append(
                _V(
                    "entities.dead_companion_active",
                    "error",
                    turn,
                    f"companion morto '{c.get('name')}' segue ativo na party",
                    npc=c.get("name"),
                )
            )
    return out


# --- R4 mundo ---------------------------------------------------------------


def check_world(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    out: list[Violation] = []
    from gamedata import get_location
    from services.graph_resolver import get_current_controller

    world = state.get("world", {}) or {}
    projection = state.get("world_projection", {}) or {}

    cur = world.get("current_location_id", "")
    if cur and not get_location(cur):
        out.append(
            _V(
                "world.location_unknown",
                "error",
                turn,
                f"current_location_id '{cur}' não existe no grafo",
                loc=cur,
            )
        )

    # SPEC-233 R1: danger_level (campo de leitura) == perigo efetivo do local atual.
    if cur and get_location(cur) and world.get("danger_level") is not None:
        from world_utils import effective_danger

        if int(world["danger_level"]) != effective_danger(world):
            out.append(
                _V(
                    "world.danger_mismatch",
                    "warning",
                    turn,
                    f"danger_level {world['danger_level']} != efetivo "
                    f"{effective_danger(world)} em '{cur}'",
                    loc=cur,
                )
            )

    for loc in world.get("visited", []) or []:
        if not get_location(loc):
            out.append(
                _V(
                    "world.visited_unknown",
                    "error",
                    turn,
                    f"local visitado '{loc}' não existe no grafo",
                    loc=loc,
                )
            )

    defeated = {
        f.get("id")
        for f in (state.get("factions") or [])
        if isinstance(f, dict) and f.get("defeated")
    }
    if defeated:
        for loc in world.get("visited", []) or []:
            controller = get_current_controller(loc, projection, include_hidden=True)
            if controller in defeated:
                out.append(
                    _V(
                        "world.defeated_controls",
                        "error",
                        turn,
                        f"fação derrotada '{controller}' ainda controla '{loc}'",
                        loc=loc,
                        faction=controller,
                    )
                )

    if prev:
        prev_day = ((prev.get("world") or {}).get("world_clock") or {}).get("day")
        cur_day = (world.get("world_clock") or {}).get("day")
        if isinstance(prev_day, int) and isinstance(cur_day, int) and cur_day < prev_day:
            out.append(
                _V(
                    "world.clock_regressed",
                    "error",
                    turn,
                    f"relógio voltou: dia {prev_day} → {cur_day}",
                    prev_day=prev_day,
                    day=cur_day,
                )
            )
    return out


def check_summary_bounds(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    from services.memory_summary import NARRATIVE_SUMMARY_MAX_CHARS

    summary = str(state.get("narrative_summary") or "")
    if len(summary) <= NARRATIVE_SUMMARY_MAX_CHARS:
        return []
    return [
        _V(
            "memory.summary_bounds",
            "error",
            turn,
            f"narrative_summary tem {len(summary)} caracteres; teto é "
            f"{NARRATIVE_SUMMARY_MAX_CHARS}",
            chars=len(summary),
            max_chars=NARRATIVE_SUMMARY_MAX_CHARS,
        )
    ]


def check_campaign_grounding(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """Tolera o próprio turno de viagem; no turno seguinte o plano deve ancorar."""
    world = state.get("world") or {}
    plan = state.get("campaign_plan") or {}
    current = str(world.get("current_location") or "")
    planned = str(plan.get("location") or "")
    if not current or not planned or current == planned:
        return []
    previous_location = str(((prev or {}).get("world") or {}).get("current_location") or "")
    if previous_location and previous_location != current and state.get("needs_replan"):
        return []
    try:
        from agents.campaign_manager import _same_region

        stale = not _same_region(planned, current)
    except Exception:
        stale = False
    if not stale:
        return []
    if state.get("needs_replan"):
        combat_active = bool((state.get("combat") or {}).get("active"))
        previous_combat_active = bool(((prev or {}).get("combat") or {}).get("active"))
        # campaign_manager intentionally defers SMART planning while combat owns
        # the route. The exact turn that closes combat cannot replan retroactively;
        # the next turn must consume needs_replan before normal narration.
        if combat_active or previous_combat_active:
            return []
    return [
        _V(
            "campaign.region_grounding",
            "error",
            turn,
            f"plano ancorado em {planned!r} enquanto a cena permanece em {current!r}",
            planned_location=planned,
            current_location=current,
        )
    ]


def check_reward_feedback(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    if not prev:
        return []
    player = state.get("player") or {}
    previous = prev.get("player") or {}
    gold_gained = int(player.get("gold", 0) or 0) > int(previous.get("gold", 0) or 0)

    def inventory_total(actor: dict) -> int:
        return sum(
            int(entry.get("qty", 1) or 1)
            for entry in (actor.get("inventory") or [])
            if isinstance(entry, dict)
        )

    item_gained = inventory_total(player) > inventory_total(previous)
    if not (gold_gained or item_gained):
        return []
    from services.turn_outcome import player_facing_message

    narrative = player_facing_message(state)
    import re

    if not re.search(
        r"\b(?:nada novo (?:foi )?obtido|nenhum(?:a)? (?:recompensa|objeto|item).{0,30}(?:obtido|acrescentado))\b",
        narrative,
        re.IGNORECASE,
    ):
        return []
    return [
        _V(
            "narrative.reward_contradiction",
            "error",
            turn,
            "a narração negou uma recompensa confirmada pelo delta mecânico",
            gold_before=previous.get("gold"),
            gold_after=player.get("gold"),
            item_gained=item_gained,
        )
    ]


# --- R5 conhecimento --------------------------------------------------------

# spec beats-visibilidade-ptbr (R1): as assinaturas migraram para o módulo
# compartilhado (consumido também pelo campaign_manager). Alias p/ compat.
from services.secret_signatures import SECRET_SIGNATURES, revealed_corpus

_SECRET_SIGNATURES = SECRET_SIGNATURES  # compat com quem importava daqui
_revealed_corpus = revealed_corpus


def check_knowledge(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    out: list[Violation] = []
    revealed = revealed_corpus(state)
    # spec beats-visibilidade-ptbr (R5): checa a narração E o texto dos beats do
    # plano (antes só narração — o vazamento do playtest veio de um BEAT).
    fontes = [("narração", _last_narration(state).lower())]
    for b in (state.get("campaign_plan") or {}).get("beats") or []:
        if isinstance(b, dict) and b.get("description"):
            fontes.append(("beat", str(b["description"]).lower()))
    for origem, text in fontes:
        if not text:
            continue
        for secret_id, phrases in SECRET_SIGNATURES.items():
            for ph in phrases:
                if ph in text and ph not in revealed:
                    out.append(
                        _V(
                            "knowledge.secret_leak",
                            "warning",
                            turn,
                            f"{origem} vazou segredo '{secret_id}': “{ph}”",
                            secret=secret_id,
                            phrase=ph,
                            origem=origem,
                        )
                    )
                    break
    return out


def _last_narration(state: dict) -> str:
    for msg in reversed(state.get("messages", []) or []):
        content = getattr(msg, "content", "")
        if content and getattr(msg, "type", "") != "human":
            return str(content)
    return ""


# --- R6 roundtrip (fora do loop por-turno: faz I/O de disco) ----------------

_ROUNDTRIP_FIELDS = [
    "player",
    "world",
    "party",
    "enemies",
    "factions",
    "faction_intel",
    "bestiary_knowledge",
    "npcs",
    "quests",
    "campaign_plan",
    "event_log",
    "world_projection",
    "game_over",
]


def check_roundtrip(state: dict, prev: dict | None = None, turn: int = 0) -> list[Violation]:
    """save → load → compara campos persistidos. NÃO entra em CHECKS (I/O)."""
    import json

    import persistence

    try:
        persistence.save_game_state(state)
        reloaded = persistence.load_game_state(persistence.save_path(state.get("game_id", "")))
    except Exception as e:
        return [_V("save.roundtrip", "error", turn, f"roundtrip falhou: {e!r}")]
    out: list[Violation] = []
    for k in _ROUNDTRIP_FIELDS:
        a = json.dumps(state.get(k), sort_keys=True, default=str, ensure_ascii=False)
        b = json.dumps((reloaded or {}).get(k), sort_keys=True, default=str, ensure_ascii=False)
        if a != b:
            out.append(
                _V("save.roundtrip", "warning", turn, f"campo '{k}' difere após save→load", field=k)
            )
    return out


# --- orquestração -----------------------------------------------------------


def check_lifecycle(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """R4 (fix-playtest-achados): save morto é terminal. Se o turno ANTERIOR já
    estava com game_over e mesmo assim o relógio avançou, um morto agiu — o gate
    do grafo (main.py) deveria ter barrado."""
    if not prev or not prev.get("game_over"):
        return []
    prev_turn = (prev.get("world") or {}).get("turn_count")
    cur_turn = (state.get("world") or {}).get("turn_count")
    if isinstance(prev_turn, int) and isinstance(cur_turn, int) and cur_turn > prev_turn:
        return [
            _V(
                "lifecycle.acts_after_game_over",
                "error",
                turn,
                f"turno processado após game_over (turn {prev_turn} → {cur_turn})",
                prev_turn=prev_turn,
                turn_count=cur_turn,
            )
        ]
    return []


# spec combate-lifecycle (R4): combate ativo por muitos turnos sem receber rota
# de combate = "zumbi" (o bug do playtest longo: combat.active True por 59 turnos).
# `idle_turns` (mantido pelo router/combat_node) é o contador; R3 deveria expirar
# em 3, então idle >= 5 só sobra se R3 falhou — daí severidade `error`.
COMBAT_ZOMBIE_IDLE = 5


def check_combat_zombie(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    combat = state.get("combat") or {}
    if not combat.get("active"):
        return []
    idle = int(combat.get("idle_turns", 0) or 0)
    if idle >= COMBAT_ZOMBIE_IDLE:
        return [
            _V(
                "combat.zombie",
                "error",
                turn,
                f"combate ativo há {idle} turnos sem rota de combate "
                f"(R3 deveria ter expirado em {COMBAT_ZOMBIE_IDLE})",
                idle_turns=idle,
            )
        ]
    return []


def check_encounter_identity(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-203: elenco da rodada == manifesto (salvo eventos) e participantes
    congelados não mudam de espécie/bestiário/facção/papel."""
    from services import encounter_manifest as em

    combat = state.get("combat") or {}
    manifest = combat.get("encounter")
    if not combat.get("active") or not em.is_valid_manifest(manifest):
        return []
    out: list[Violation] = []
    violations = em.validate_roster(manifest, state.get("enemies") or [])
    if violations:
        out.append(
            _V(
                "encounter.identity_drift",
                "error",
                turn,
                f"elenco fora do manifesto: {violations}",
                field="enemies",
            )
        )
    prev_manifest = ((prev or {}).get("combat") or {}).get("encounter")
    if em.is_valid_manifest(prev_manifest) and prev_manifest.get("encounter_id") == manifest.get(
        "encounter_id"
    ):
        try:
            em.assert_immutable(prev_manifest, manifest)
        except ValueError as exc:
            out.append(
                _V("encounter.identity_drift", "error", turn, str(exc), field="combat.encounter")
            )
    return out


def check_encounter_phase(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-203: combate inativo não pode ficar preso em fase não terminal."""
    combat = state.get("combat") or {}
    phase = combat.get("phase")
    if phase and not combat.get("active") and phase != "ended":
        return [
            _V(
                "encounter.phase_stuck",
                "error",
                turn,
                f"combate inativo com fase {phase!r}",
                field="combat.phase",
            )
        ]
    return []


_INVALID_SENTINELS = {"null", "none", "nil", "undefined", "n/a", "nan"}


def check_invalid_sentinels(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """Strings-sentinela de structured output não podem virar entidades/IDs."""
    out: list[Violation] = []
    for key in state.get("npcs") or {}:
        if str(key).strip().casefold() in _INVALID_SENTINELS:
            out.append(
                _V(
                    "npc.invalid_sentinel",
                    "error",
                    turn,
                    f"NPC inválido persistido com chave-sentinela {key!r}",
                    field="npcs",
                    value=key,
                )
            )
    for field_name in ("active_npc_name", "combat_target"):
        value = state.get(field_name)
        if isinstance(value, str) and value.strip().casefold() in _INVALID_SENTINELS:
            out.append(
                _V(
                    "npc.invalid_sentinel",
                    "error",
                    turn,
                    f"{field_name} contém sentinela textual {value!r}",
                    field=field_name,
                    value=value,
                )
            )
    return out


def check_rag_persistence(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """O archivist expõe falha persistente; o harness não pode silenciá-la."""
    error = state.get("rag_persistence_error")
    if not error:
        return []
    return [
        _V(
            "rag.persistence_error",
            "error",
            turn,
            f"persistência RAG falhou: {str(error)[:240]}",
            error=str(error)[:240],
        )
    ]


def check_summary_frozen(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """SPEC-234: o resumo de curto prazo nunca congela por falha do indice.

    O arquivista roda a cada <=10 turnos (ou por evento); `archivist_last_run`
    atrasado alem da folga indica o loop de retry vetorial que antes travava tudo.
    """
    current = int((state.get("world") or {}).get("turn_count", 0) or 0)
    last = int(state.get("archivist_last_run", 0) or 0)
    if current >= 14 and current - last > 13:
        return [
            _V(
                "memory.summary_frozen",
                "error",
                turn,
                f"resumo narrativo congelado: arquivista parado no turno {last} (atual {current}).",
                archivist_last_run=last,
                turn_count=current,
            )
        ]
    return []


def check_memory_provenance(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """Memória confirmada precisa apontar para fonte que o motor consegue provar."""
    from services.memory_provenance import (
        canonical_location_contradiction,
        inventory_possession_contradiction,
        normalize_memory_facts,
        npc_identity_contradiction,
        source_is_applicable,
    )

    out: list[Violation] = []
    previous_ids = {
        record["memory_id"] for record in normalize_memory_facts((prev or {}).get("memory_facts"))
    }
    for record in normalize_memory_facts(state.get("memory_facts")):
        contradiction = canonical_location_contradiction(record.get("text", ""))
        if contradiction and record["memory_id"] not in previous_ids:
            out.append(
                _V(
                    "memory.location_grounding",
                    "error",
                    turn,
                    f"memória atribui {contradiction['location_name']!r} à região "
                    f"{contradiction['claimed_region']!r}; esperado "
                    f"{contradiction['expected_region']!r}",
                    memory_id=record.get("memory_id"),
                    **contradiction,
                )
            )
        inventory_contradiction = inventory_possession_contradiction(
            record.get("text", ""),
            state,
        )
        if inventory_contradiction and record["memory_id"] not in previous_ids:
            out.append(
                _V(
                    "memory.inventory_grounding",
                    "error",
                    turn,
                    f"memória atribui ao jogador item ausente "
                    f"{inventory_contradiction['item_name']!r}",
                    memory_id=record.get("memory_id"),
                    **inventory_contradiction,
                )
            )
        npc_contradiction = npc_identity_contradiction(
            record.get("text", ""),
            state,
        )
        if npc_contradiction and record["memory_id"] not in previous_ids:
            out.append(
                _V(
                    "memory.npc_identity_grounding",
                    "error",
                    turn,
                    f"memória contradiz identidade de "
                    f"{npc_contradiction['npc_name']!r}: "
                    f"{npc_contradiction['claimed']!r} vs "
                    f"{npc_contradiction['expected']!r}",
                    memory_id=record.get("memory_id"),
                    **npc_contradiction,
                )
            )
        if record.get("confidence") != "confirmed":
            continue
        source_id = record.get("source_id")
        if source_is_applicable(source_id, state):
            continue
        out.append(
            _V(
                "memory.confirmed_without_source",
                "error",
                turn,
                f"memória confirmada {record.get('memory_id')!r} não tem fonte aplicável",
                memory_id=record.get("memory_id"),
                source_id=source_id,
                provenance=record.get("provenance"),
            )
        )
    return out


def check_summary_lifecycle(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
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
    return [
        _V(
            "summary.lifecycle",
            "error",
            turn,
            f"ConflictSummary atravessou o turno {prev_turn}→{current_turn} sem consumo",
            previous_turn=prev_turn,
            current_turn=current_turn,
        )
    ]


def check_duplicate_consumed_summary(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """Um ID confirmado no ledger não pode reaparecer como summary pendente."""
    summary = state.get("conflict_summary")
    if not isinstance(summary, dict) or not summary:
        return []
    from services import conflict_summary as summary_service

    conflict_id = summary_service.ensure_conflict_id(
        summary,
        turn=summary.get("conflict_turn"),
    )
    consumed = set(
        summary_service.normalize_consumed_conflict_ids(state.get("consumed_conflict_ids"))
    )
    if conflict_id not in consumed:
        return []
    return [
        _V(
            "summary.duplicate_consumption",
            "error",
            turn,
            f"ConflictSummary {conflict_id!r} reapareceu após consumo confirmado",
            conflict_id=conflict_id,
        )
    ]


def _wounds_fingerprint(entity: dict) -> tuple:
    wounds = entity.get("ferimentos") or {}
    return tuple(
        (
            category,
            json.dumps(
                wounds.get(category, []) or [], sort_keys=True, ensure_ascii=False, default=str
            ),
        )
        for category in ("leve", "grave", "critico")
    )


def combat_progress_fingerprint(state: dict) -> tuple | None:
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
        actor_bits.append(
            (
                actor_id,
                int(entity.get("vitalidade", entity.get("hp", 0)) or 0),
                str(entity.get("status") or ""),
                bool(entity.get("dead")),
                bool(entity.get("conscious", True)),
                _wounds_fingerprint(entity),
                json.dumps(
                    entity.get("active_conditions", []) or [],
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ),
            )
        )
    scene = combat.get("scene") or {}
    scene_bits = (
        json.dumps(
            scene.get("positions", {}) or {}, sort_keys=True, ensure_ascii=False, default=str
        ),
        json.dumps(
            scene.get("engagements", []) or [], sort_keys=True, ensure_ascii=False, default=str
        ),
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


def check_combat_no_progress(context: dict | None, turn: int) -> list[Violation]:
    streak = int((context or {}).get("combat_no_progress_streak", 0) or 0)
    if streak < COMBAT_NO_PROGRESS_LIMIT:
        return []
    return [
        _V(
            "combat.no_progress",
            "error",
            turn,
            f"conflito avançou {streak} rodadas sem mudança mecânica observável",
            streak=streak,
            threshold=COMBAT_NO_PROGRESS_LIMIT,
        )
    ]


def check_action_declaration(
    decision: dict | None,
    resolved: dict | None,
    *,
    turn: int,
    combat_executed: bool,
) -> list[Violation]:
    """Compara a escolha única do perfil ao resultado canônico do combat_node."""
    decision = decision or {}
    if not combat_executed or decision.get("mode") not in ("declaration", "flee"):
        return []
    if not resolved:
        return [
            _V(
                "action.declaration_matches",
                "error",
                turn,
                f"decisão {decision.get('kind')!r} executou combate sem resultado canônico",
                expected_kind=str(decision.get("kind") or ""),
                resolved_kind="",
                mismatches={"resolved_action": ["present", "missing"]},
                decision=decision,
                resolved={},
            )
        ]
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
        actual_destination = resolved.get("flee_destination_id") or resolved.get("destination_id")
        if (
            expected_destination is not None
            and actual_destination is not None
            and expected_destination != actual_destination
        ):
            mismatches["flee_destination_id"] = [
                expected_destination,
                actual_destination,
            ]
    result = str(resolved.get("result") or "")
    if result == "invalid":
        mismatches["result"] = ["valid", "invalid"]
    elif result == "interrupted" and resolved.get("attempted", True):
        mismatches["attempted"] = [False, True]
    if not mismatches:
        return []
    return [
        _V(
            "action.declaration_matches",
            "error",
            turn,
            f"decisão {expected_kind!r} divergiu do efeito {resolved_kind!r}",
            expected_kind=expected_kind,
            resolved_kind=resolved_kind,
            mismatches=mismatches,
            decision=decision,
            resolved=resolved,
        )
    ]


def check_contextual(
    state: dict,
    prev: dict | None,
    turn: int,
    context: dict | None,
) -> list[Violation]:
    context = context or {}
    out = check_combat_no_progress(context, turn)
    action = str(context.get("action") or "")
    if context.get("profile") == "normal" and re.search(
        r"\b(?:descreva|narre|beat|campaign_plan|objetivo principal:)\b",
        action,
        flags=re.IGNORECASE,
    ):
        out.append(
            _V(
                "profile.private_plan_leak",
                "error",
                turn,
                "perfil normal expôs metalinguagem/instrução privada na ação",
                action=action[:240],
            )
        )
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
            out.append(
                _V(
                    "economy.transaction_conservation",
                    "error",
                    turn,
                    "delta de ouro da transação diverge do ledger Python",
                    outcome=economy_action,
                )
            )
        for field_name in ("stock_before", "stock_after"):
            for quote in economy_action.get(field_name) or []:
                if int(quote.get("stock", 0) or 0) < 0:
                    out.append(
                        _V(
                            "economy.stock_bounds",
                            "error",
                            turn,
                            "estoque negativo no ledger de mercado",
                            field=field_name,
                            quote=quote,
                        )
                    )
        before_qty: dict[str, int] = {}
        after_qty: dict[str, int] = {}
        for item in economy_action.get("inventory_before") or []:
            if isinstance(item, dict):
                item_id = str(item.get("id") or "")
                before_qty[item_id] = before_qty.get(item_id, 0) + int(item.get("qty", 1) or 0)
        for item in economy_action.get("inventory_after") or []:
            if isinstance(item, dict):
                item_id = str(item.get("id") or "")
                after_qty[item_id] = after_qty.get(item_id, 0) + int(item.get("qty", 1) or 0)
        if economy_action.get("ok") and economy_action.get("item_id"):
            item_id = str(economy_action["item_id"])
            qty = int(economy_action.get("qty", 1) or 1)
            mode = str(economy_action.get("mode") or "")
            delta_qty = after_qty.get(item_id, 0) - before_qty.get(item_id, 0)
            expected = qty if mode in ("buy", "craft") else -qty
            if delta_qty != expected:
                out.append(
                    _V(
                        "economy.transaction_conservation",
                        "error",
                        turn,
                        "delta de item da transação diverge do ledger Python",
                        item_id=item_id,
                        expected=expected,
                        actual=delta_qty,
                        outcome=economy_action,
                    )
                )
    net_worth = context.get("net_worth_after")
    if net_worth is not None and not isinstance(net_worth, int):
        out.append(
            _V(
                "economy.net_worth_finite",
                "error",
                turn,
                "net worth não é inteiro finito",
                value=net_worth,
            )
        )
    decision = context.get("decision") or {}
    resolved = context.get("resolved_action") or {}
    chase_state = (state.get("combat") or {}).get("chase") or {}
    if (
        decision.get("kind") == "flee"
        and resolved.get("result") == "flee_failed"
        and chase_state.get("trilha") in ("afastado", "quase_livre")
        and not chase_state.get("alcancado")
    ):
        out.append(
            _V(
                "combat.flee_progress_mislabeled",
                "error",
                turn,
                "progresso válido de perseguição foi classificado como falha",
                chase_track=chase_state.get("trilha"),
                result=resolved.get("result"),
            )
        )
    latency_ms = int(context.get("latency_ms", 0) or 0)
    if context.get("real_llm") and latency_ms > 45_000:
        severity: Severity = "error" if latency_ms > 90_000 else "warning"
        out.append(
            _V(
                "performance.turn_latency",
                severity,
                turn,
                f"turno real levou {latency_ms / 1000:.1f}s",
                latency_ms=latency_ms,
                warning_ms=45_000,
                error_ms=90_000,
            )
        )
    rag_errors = [
        event for event in (context.get("rag_events") or []) if not bool(event.get("success", True))
    ]
    for event in rag_errors:
        out.append(
            _V(
                "rag.persistence_error",
                "error",
                turn,
                f"operação RAG {event.get('operation', '?')} falhou: "
                f"{str(event.get('error') or '')[:200]}",
                operation=event.get("operation"),
                error=str(event.get("error") or "")[:200],
            )
        )
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
            out.append(
                _V(
                    "summary.lifecycle",
                    "error",
                    turn,
                    "conflito encerrou, mas o ConflictSummary ficou pendente após o archivist",
                    world_turn=current_turn,
                    conflict_id=str((state.get("conflict_summary") or {}).get("conflict_id") or ""),
                )
            )
        elif not summary_present and not archived:
            out.append(
                _V(
                    "summary.lifecycle",
                    "error",
                    turn,
                    "conflito encerrou sem ConflictSummary presente ou arquivado",
                    world_turn=current_turn,
                )
            )
    return out


def check_recycled_npc(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """spec encontros-dedupe (R4) + npc-in-scene-viagem (R3): NPC GERADO (tem
    `created_turn`) que VAZA para o contexto do narrador fora do local onde nasceu
    = reciclagem/flag zumbi (o 'Sobrevivente moribundo' em 3 locais; a flag
    in_scene que sobrevivia à viagem).

    Mede USO OBSERVÁVEL, não a flag crua: só reporta quando o nome remoto aparece
    na última narração ou entre aliados transitórios do combate. Uma flag residual
    filtrada pelas views não produz falso positivo."""
    out: list[Violation] = []
    loc = (state.get("world") or {}).get("current_location_id", "") or ""
    if not loc:
        return out
    active_npc = str(state.get("active_npc_name") or "").casefold()
    combat_names = {
        str(ally.get("name") or "").casefold()
        for ally in ((state.get("combat") or {}).get("scene_allies") or [])
        if isinstance(ally, dict)
    }
    party_names = {c.get("name") for c in (state.get("party") or []) if isinstance(c, dict)}
    for name, npc in (state.get("npcs") or {}).items():
        if not isinstance(npc, dict):
            continue
        home = npc.get("home_location_id") or ""
        # Vínculo legítimo (home == loc) ou membro de party NÃO é vazamento.
        actually_used = name.casefold() == active_npc or name.casefold() in combat_names
        if (
            npc.get("created_turn") is not None
            and actually_used
            and name not in party_names
            and home
            and home != loc
        ):
            out.append(
                _V(
                    "narrative.recycled_npc",
                    "warning",
                    turn,
                    f"NPC gerado '{name}' no contexto fora do local de origem "
                    f"(origem={home}, atual={loc})",
                    npc=name,
                    home=home,
                    loc=loc,
                )
            )
    return out


def check_actor_lifecycle(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """Life phase coherence; zero Vitality by itself is explicitly valid."""
    player = state.get("player") or {}
    if player.get("dead") and player.get("conscious", True) and not state.get("death_pending"):
        return [
            _V(
                "player.lifecycle_incoherent",
                "error",
                turn,
                "protagonista morto permanece marcado como consciente",
            )
        ]
    if player.get("incapacitated") and player.get("conscious", True):
        return [
            _V(
                "player.lifecycle_incoherent",
                "error",
                turn,
                "protagonista incapacitado permanece marcado como consciente",
            )
        ]
    from services.actor_lifecycle import transition_readiness

    readiness = transition_readiness(state)
    if (
        not readiness["ready"]
        and readiness["phase"] in {"last_stand", "terminal"}
        and not (state.get("combat") or {}).get("active")
    ):
        previous_readiness = transition_readiness(prev or {})
        if previous_readiness.get("code") != readiness["code"]:
            return [
                _V(
                    "transition.unresolved_at_boundary",
                    "error",
                    turn,
                    "transição crítica saiu de seu produtor sem resolvedor",
                    phase=readiness["phase"],
                    code=readiness["code"],
                )
            ]
        return []
    if not prev:
        return []
    previous = prev.get("player") or {}
    was_blocked = not previous.get("conscious", True) or previous.get("incapacitated")
    action = state.get("last_action_outcome") or {}
    # Independent observation of location: trusting allowed=False here alone
    # would reproduce the product guard's own blind spot for mixed actions.
    if (
        was_blocked
        and not (prev.get("combat") or {}).get("active")
        and not prev.get("death_pending")
        and not state.get("death_pending")
        and (
            (prev.get("continuity") or {}).get("timeline_epoch", 0)
            == (state.get("continuity") or {}).get("timeline_epoch", 0)
        )
    ):
        if (state.get("world") or {}).get("current_location_id") != (prev.get("world") or {}).get(
            "current_location_id"
        ):
            return [
                _V(
                    "player.action_while_incapacitated",
                    "error",
                    turn,
                    "recuperação de ator incapacitado alterou localização",
                )
            ]
    if was_blocked and action.get("allowed") is False:
        prev_world, world = prev.get("world") or {}, state.get("world") or {}
        if world.get("turn_count") != prev_world.get("turn_count") or world.get(
            "current_location_id"
        ) != prev_world.get("current_location_id"):
            return [
                _V(
                    "player.action_while_incapacitated",
                    "error",
                    turn,
                    "ação bloqueada alterou turno ou localização",
                )
            ]
    return []


def check_repeated_opening(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """spec polish-prosa (R5): 3 narrações consecutivas com a MESMA abertura de 6
    palavras = prosa engessada. Warning (telemetria — não reprova). Sob MockLLM a
    narração é fixa, então o runner filtra este check em modo mock (§7 da spec)."""
    from services.prose_guard import is_deterministic_interaction_message, semantic_opening

    narrs: list[str] = []
    for m in reversed(state.get("messages", []) or []):
        content = getattr(m, "content", "")
        if content and getattr(m, "type", "") != "human":
            narrs.append(str(content))
            if len(narrs) >= 4:
                break
    if len(narrs) < 3:
        return []
    if any(is_deterministic_interaction_message(n) for n in narrs[:3]):
        return []
    ops = [semantic_opening(n) for n in narrs]
    if ops[0] and ops[0] == ops[1] == ops[2] and (len(ops) < 4 or ops[3] != ops[0]):
        return [
            _V(
                "narrative.repeated_opening",
                "warning",
                turn,
                f"3 narrações seguidas abrindo com “{ops[0]}…”",
                abertura=ops[0],
            )
        ]
    return []


def check_interaction_no_progress(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    outcome = state.get("last_interaction_outcome") or {}
    if outcome.get("turn") is not None and outcome["turn"] != (state.get("world") or {}).get(
        "turn_count"
    ):
        return []
    repeat_count = int(outcome.get("repeat_count", 0) or 0)
    if outcome.get("progressed") or repeat_count < 3:
        return []
    if repeat_count != 3 and repeat_count & (repeat_count - 1):
        return []
    return [
        _V(
            "interaction.no_progress",
            "warning",
            turn,
            f"interação repetida {repeat_count} vezes sem progresso",
            code=outcome.get("code"),
            subject_id=outcome.get("subject_id"),
            repeat_count=repeat_count,
        )
    ]


def check_meta_leak(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """spec polish-prosa-v2: marcador do motor na última narração é regressão."""
    from services.prose_guard import contains_engine_marker

    for message in reversed(state.get("messages", []) or []):
        content = getattr(message, "content", "")
        if not content or getattr(message, "type", "") == "human":
            continue
        if contains_engine_marker(str(content)):
            return [
                _V(
                    "narrative.meta_leak",
                    "error",
                    turn,
                    "Narração visível contém marcador interno do motor.",
                    sample=str(content)[:180],
                )
            ]
        break
    return []


def _unproven_anchor(ev: dict, state: dict, prev: dict, turn: int) -> list[Violation]:
    """`npc_killed`/`secret_revealed` de fonte LLM: reaplica o gate de prova do
    motor no estado do turno (combate do turno / âncora na cena). A prova vale
    se o estado anterior OU o atual a sustentam (o archivist pode já ter limpo
    o `conflict_summary` ou a cena ao fim do turno)."""
    from pydantic import ValidationError

    from services.structured_outputs import ProposedWorldEvent
    from services.world_validators import _proof_gate

    try:
        proposal = ProposedWorldEvent(
            type=ev.get("type"),
            actor_id=str(ev.get("actor_id") or "player"),
            target_id=str(ev.get("target_id") or ""),
            payload=dict(ev.get("payload") or {}),
        )
    except ValidationError:
        return []
    ev_turn = int(ev.get("turn", 0) or 0)
    reasons = []
    for snapshot in (prev, state):
        snap = {**snapshot, "world": {**(snapshot.get("world") or {}), "turn_count": ev_turn}}
        result = _proof_gate(proposal, snap, snapshot.get("world_projection") or {})
        if result.ok:
            return []
        reasons.append(result.reason)
    return [
        _V(
            "narrative.unproven_event",
            "error",
            turn,
            f"{ev.get('type')} aplicado sem prova: {reasons[-1]}",
            event_type=str(ev.get("type")),
            target_id=str(ev.get("target_id")),
        )
    ]


def check_unproven_event(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-223 R8: evento de mundo vindo do LLM aplicado SEM prova é regressão.

    Só eventos NOVOS (ausentes no estado anterior) de fonte não-motor contam.
    `quest_completed` é reavaliado contra a quest do estado ANTERIOR; morte e
    segredo de fonte LLM exigem a âncora gravada (combate do turno / cena)."""
    from services.quest_log import has_completion_proof
    from services.world_validators import ENGINE_SOURCES

    if prev is None:
        return []
    seen = {e.get("event_id") for e in (prev.get("event_log") or []) if isinstance(e, dict)}
    prev_quests = {q.get("id"): q for q in (prev.get("quests") or []) if isinstance(q, dict)}
    out: list[Violation] = []
    for ev in state.get("event_log") or []:
        if not isinstance(ev, dict) or ev.get("event_id") in seen:
            continue
        if str(ev.get("source") or "") in ENGINE_SOURCES:
            continue
        if ev.get("type") in ("npc_killed", "secret_revealed"):
            out.extend(_unproven_anchor(ev, state, prev, turn))
            continue
        if ev.get("type") != "quest_completed":
            continue
        qid = (ev.get("payload") or {}).get("quest_id")
        quest = prev_quests.get(qid)
        proof_state = {
            **prev,
            "world": {**(prev.get("world") or {}), "turn_count": int(ev.get("turn", 0) or 0)},
        }
        ok, why = has_completion_proof(quest, proof_state) if quest else (False, "quest ausente")
        if not ok:
            out.append(
                _V(
                    "narrative.unproven_event",
                    "error",
                    turn,
                    f"quest_completed aplicado sem prova: {why}",
                    event_type="quest_completed",
                    target_id=str(ev.get("target_id")),
                )
            )
    return out


def check_phantom_ally(state: dict, prev: dict | None, turn: int) -> list[Violation]:
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

        present = {
            str(a.get("name", "")).lower()
            for a in party_mod.active_allies(state) + party_mod.scene_allies(state)
        }
    except Exception:
        present = set()
    # candidatos = companheiros de party + amigos em cena (nomes conhecidos)
    candidatos = set()
    for c in state.get("party") or []:
        if isinstance(c, dict) and c.get("name"):
            candidatos.add(str(c["name"]))
    for name, npc in (state.get("npcs") or {}).items():
        if (
            isinstance(npc, dict)
            and npc.get("in_scene")
            and int(npc.get("relationship", 5) or 5) >= 6
        ):
            candidatos.add(str(npc.get("name", name)))
    out: list[Violation] = []
    for nome in candidatos:
        if len(nome) >= 3 and nome.lower() in low and nome.lower() not in present:
            out.append(
                _V(
                    "combat.phantom_ally",
                    "warning",
                    turn,
                    f"aliado '{nome}' citado na narração de combate sem combatente do lado herói",
                    ally=nome,
                )
            )
    return out


def check_effect_catalog(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """spec conflito-13 (R5): nenhum efeito FORA do catálogo fechado (03/10) escapa
    para produção. Varre a cena de combate ativa (objetos + eventos do Abismo); um
    `effect.kind` inventado pela LLM que passou os validadores é um vazamento grave."""
    from services.conflict_scene import EFFECT_KINDS

    out: list[Violation] = []
    scene = (state.get("combat") or {}).get("scene") or {}
    for o in scene.get("objects", []) or []:
        for it in o.get("interactions") or []:
            eff = it.get("effect") or {}
            if eff and str(eff.get("kind")) not in EFFECT_KINDS:
                out.append(
                    _V(
                        "combat.effect_catalog",
                        "error",
                        turn,
                        f"efeito fora do catálogo em objeto '{o.get('id')}': {eff.get('kind')!r}",
                        kind=eff.get("kind"),
                    )
                )
    for ev in scene.get("abyss_events") or []:
        eff = ev.get("effect") or {}
        if eff and str(eff.get("kind")) not in EFFECT_KINDS:
            out.append(
                _V(
                    "combat.effect_catalog",
                    "error",
                    turn,
                    f"evento do Abismo '{ev.get('id')}' fora do catálogo: {eff.get('kind')!r}",
                    kind=eff.get("kind"),
                )
            )
    return out


def check_false_player_death(
    state: dict,
    prev: dict | None,
    turn: int,
) -> list[Violation]:
    """A recoverable down may never be memorialized as a confirmed death."""
    player_name = str((state.get("player") or {}).get("name") or "").strip()
    previous_facts = {
        str(row.get("memory_id") or "")
        for row in ((prev or {}).get("memory_facts") or [])
        if isinstance(row, dict)
    }
    from services.turn_outcome import player_facing_message

    texts = [player_facing_message(state), str(state.get("narrative_summary") or "")]
    texts.extend(
        str(row.get("text") or "")
        for row in (state.get("memory_facts") or [])
        if isinstance(row, dict) and str(row.get("memory_id") or "") not in previous_facts
    )
    from services.memory_provenance import false_player_death_claim

    offending = next((text for text in texts if false_player_death_claim(text, state)), "")
    if not offending:
        return []
    return [
        _V(
            "narrative.false_player_death",
            "error",
            turn,
            "morte do protagonista afirmada sem evidência terminal",
            source_excerpt=offending[:180],
            player=player_name,
        )
    ]


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
            {
                "id": "player",
                "name": "Herói",
                "is_player": True,
                "class_name": "Sangromante",
                "virtudes": {"forca": 4, "agilidade": 3, "corpo": 3, "mente": 1, "carisma": 1},
                "attack_formula": "2d6",
            },
            is_player=True,
        )
        enemy = orch.ensure_combat_sheet(
            {
                "id": "e1",
                "name": "Bandido",
                "type": "padrao",
                "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
            }
        )
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
            out = orch.run_round(
                scene, actors, sides, {"player": player}, declarations={"player": decl}, rng=rng
            )
            logs += out["logs"]
            if out["ended"]:
                break
        return logs

    return _one_run() == _one_run()


def check_projection_ahead(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-213 R6: derivado nunca à frente do canônico; e alerta de falhas seguidas."""
    raw = state.get("projection_state")
    if not isinstance(raw, dict):
        return []
    out: list[Violation] = []
    canonical = int(raw.get("canonical_version", 0) or 0)
    for name in ("summary", "memory", "chronicle"):
        entry = raw.get(name) or {}
        projected = int(entry.get("projected_version", 0) or 0)
        if projected > canonical:
            out.append(
                _V(
                    "projection.ahead_of_canonical",
                    "error",
                    turn,
                    f"{name}: projected_version {projected} > canonical {canonical}",
                    projection=name,
                )
            )
        if entry.get("status") == "failed" and int(entry.get("attempts", 0) or 0) >= 3:
            out.append(
                _V(
                    "projection.failed_streak",
                    "warning",
                    turn,
                    f"{name}: projeção falhou {entry.get('attempts')}x seguidas",
                    projection=name,
                )
            )
    return out


def check_npc_knowledge(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-215: `knowledge.teleport` (notícia chegou antes da distância
    permitir) e `knowledge.rumor_promoted` (rumor/mentira virou fato)."""
    links = state.get("knowledge_links") or []
    if not links:
        return []
    from services.world_distance import travel_periods

    out: list[Violation] = []
    for lk in links:
        if not isinstance(lk, dict):
            continue
        origin, here = lk.get("origin_location_id"), lk.get("location_id")
        o_clock, acquired = lk.get("origin_clock"), lk.get("acquired_clock")
        if origin and here and isinstance(o_clock, int) and isinstance(acquired, int):
            dist = travel_periods(str(origin), str(here))
            if dist is not None and acquired < o_clock + dist:
                out.append(
                    _V(
                        "knowledge.teleport",
                        "error",
                        turn,
                        f"{lk.get('holder_id')} soube de {lk.get('subject_id')} em "
                        f"{here} no clock {acquired} < {o_clock}+{dist}",
                        holder=lk.get("holder_id"),
                        subject=lk.get("subject_id"),
                    )
                )
    rumor_ids = {
        lk.get("subject_id")
        for lk in links
        if isinstance(lk, dict) and lk.get("subject_kind") == "memory_fact"
    }
    if rumor_ids:
        event_ids = {
            ev.get("event_id") for ev in state.get("event_log") or [] if isinstance(ev, dict)
        }
        revealed = set((state.get("world_projection") or {}).get("revealed_facts") or {})
        for mf in state.get("memory_facts") or []:
            if not isinstance(mf, dict) or mf.get("memory_id") not in rumor_ids:
                continue
            mid = mf.get("memory_id")
            promoted = (
                mf.get("provenance") in ("npc_claim", "inference")
                and mf.get("confidence") == "confirmed"
            )
            if promoted or mid in event_ids or mid in revealed:
                out.append(
                    _V(
                        "knowledge.rumor_promoted",
                        "error",
                        turn,
                        f"rumor {mid} promovido a fato",
                        subject=mid,
                    )
                )
    return out


Check = Callable[[dict, dict | None, int], list[Violation]]


def check_reputation(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-298 §3.6: faixas, `reputation_changed` no mesmo turno e avisos só de fação conhecida."""
    out: list[Violation] = []
    for name, npc in (state.get("npcs") or {}).items():
        rel = npc.get("relationship") if isinstance(npc, dict) else None
        if isinstance(rel, (int, float)) and not 0 <= rel <= 10:
            out.append(_V("reputation.npc_range", "error", turn, f"{name}: relação fora de 0..10"))
    prev_reps = {
        f.get("id"): f.get("reputation", 0)
        for f in ((prev or {}).get("factions") or [])
        if isinstance(f, dict)
    }
    log = state.get("event_log") or []
    for f in state.get("factions") or []:
        if not isinstance(f, dict):
            continue
        rep = f.get("reputation", 0)
        if isinstance(rep, (int, float)) and not -100 <= rep <= 100:
            out.append(
                _V("reputation.faction_range", "error", turn, f"{f.get('id')}: fora de -100..100")
            )
        if prev is not None and f.get("id") in prev_reps and prev_reps[f["id"]] != rep:
            changed = any(
                isinstance(e, dict)
                and e.get("type") == "reputation_changed"
                and e.get("target_id") == f.get("id")
                and e.get("turn") == (state.get("world") or {}).get("turn_count")
                for e in log
            )
            if not changed:
                out.append(
                    _V(
                        "reputation.change_without_event",
                        "error",
                        turn,
                        f"{f.get('id')}: reputação mudou sem reputation_changed no turno",
                    )
                )
    for loc, entry in (state.get("location_fame") or {}).items():
        for key in ("renown", "infamy"):
            val = (entry or {}).get(key, 0)
            if not 0 <= val <= 100:
                out.append(
                    _V("reputation.fame_range", "error", turn, f"{loc}.{key} fora de 0..100")
                )
    intel = state.get("faction_intel") or {}
    for n in state.get("reputation_notices") or []:
        if n.get("kind") == "faction" and not (intel.get(n.get("subject_id")) or {}).get("known"):
            out.append(
                _V(
                    "reputation.notice_unknown_faction",
                    "error",
                    turn,
                    "aviso de fação desconhecida",
                )
            )
    return out


def check_world_engine(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-302 R32: teto de crises, aviso previo, faixa das pressoes, tick unico por dia."""
    sim = (state or {}).get("world_sim") or {}
    if not sim:
        return []
    from services import world_pressures as wp

    dc = wp.director_constants()
    out: list[Violation] = []
    crises = sim.get("crises") or []
    active = [c for c in crises if c.get("start_day") is not None and c.get("end_day") is None]
    if len(active) > int(dc["MAX_ACTIVE_CRISES"]):
        out.append(
            _V(
                "world.crisis_cap_exceeded",
                "error",
                turn,
                f"{len(active)} crises ativas",
                active=len(active),
            )
        )
    for c in crises:
        if c.get("start_day") is not None and int(c["start_day"]) - int(
            c.get("warned_day", 0)
        ) < int(dc["MIN_WARNING_DAYS"]):
            out.append(
                _V(
                    "world.crisis_without_warning",
                    "error",
                    turn,
                    f"crise {c.get('kind')} em {c.get('region_id')} sem aviso de {dc['MIN_WARNING_DAYS']} dias",
                    crisis_id=c.get("crisis_id"),
                )
            )
    for region, row in (sim.get("pressures") or {}).items():
        for kind, value in row.items():
            if not isinstance(value, int) or not 0 <= value <= 100:
                out.append(
                    _V("world.pressure_out_of_range", "error", turn, f"{region}.{kind}={value}")
                )
    days = [e.get("day") for e in sim.get("tick_log") or [] if not e.get("capped")]
    if len(days) != len(set(days)):
        out.append(_V("world.day_ticked_twice", "error", turn, "dia simulado mais de uma vez"))
    return out


def check_faction_membership(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-301: vínculo com fações (limite, fações fechadas, patente monótona, influência)."""
    out: list[Violation] = []
    records = state.get("faction_membership") or {}
    if not isinstance(records, dict):
        return [_V("faction.membership_shape", "error", turn, "faction_membership não é dict")]
    from services import faction_membership as fm

    catalog = fm.load_catalog()
    open_rows = {
        fid: r
        for fid, r in records.items()
        if isinstance(r, dict) and r.get("status") in fm.OPEN_STATUSES
    }
    if len(open_rows) > fm.MAX_MEMBERSHIPS:
        out.append(
            _V(
                "faction.membership_count_le_2",
                "error",
                turn,
                f"{len(open_rows)} vínculos abertos (máx. {fm.MAX_MEMBERSHIPS})",
            )
        )
    for fid in records:
        if (catalog.get(fid) or {}).get("accepts") not in ("sim", "condicional"):
            out.append(
                _V(
                    "faction.no_membership_in_closed",
                    "error",
                    turn,
                    f"{fid}: vínculo em fação que não aceita membros",
                )
            )
    prev_rows = (prev or {}).get("faction_membership") or {}
    for fid, row in records.items():
        before = prev_rows.get(fid) or {}
        if (
            before
            and row.get("status") in fm.ACTIVE_STATUSES
            and before.get("status") in fm.ACTIVE_STATUSES
            and row.get("joined_day") == before.get("joined_day")
            and int(row.get("rank_index", 0) or 0) < int(before.get("rank_index", 0) or 0)
        ):
            out.append(
                _V(
                    "faction.rank_monotonic_unless_expelled",
                    "error",
                    turn,
                    f"{fid}: patente caiu sem expulsão/traição",
                )
            )
    for f in state.get("factions") or []:
        if not isinstance(f, dict):
            continue
        infl = f.get("influence", 0)
        if isinstance(infl, (int, float)) and abs(infl) > 9:
            out.append(
                _V("faction.influence_bounded", "error", turn, f"{f.get('id')}: influência {infl}")
            )
        # Transição, não estado: com o motor 302 `on` o tick pode deixar a fação em 100
        # aguardando o aviso da ascensão. Erro = chegou a 100 num turno SEM virada de dia.
        before = next(
            (p for p in (prev or {}).get("factions") or [] if p.get("id") == f.get("id")), None
        )
        day = ((state.get("world") or {}).get("world_clock") or {}).get("day")
        day_before = (((prev or {}).get("world") or {}).get("world_clock") or {}).get("day")
        if (
            before is not None
            and isinstance(f.get("progress"), (int, float))
            and f["progress"] >= 100 > (before.get("progress") or 0)
            and not f.get("completed")
            and not f.get("defeated")
            and day == day_before
        ):
            out.append(
                _V(
                    "faction.progress_le_99_outside_tick",
                    "error",
                    turn,
                    f"{f.get('id')}: progresso chegou a 100 sem virada de dia (missão não ascende)",
                )
            )
    return out


def check_companions(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-300 R30: aprovação em 0..100; partida/traição só com aviso prévio; morte off-screen
    só com telegrama >= 1 dia; uma missão pessoal por companheiro; `loyal` nunca trai."""
    out: list[Violation] = []
    souls = state.get("companion_souls") or {}
    quests = [q for q in (state.get("quests") or []) if isinstance(q, dict)]
    for cid, soul in souls.items():
        if not isinstance(soul, dict):
            continue
        approval = soul.get("approval")
        if not isinstance(approval, int) or isinstance(approval, bool) or not 0 <= approval <= 100:
            out.append(
                _V("companion.approval_range", "error", turn, f"{cid}: aprovação fora de 0..100")
            )
        if soul.get("departed") in ("left", "betrayed") and soul.get("warned_turn") is None:
            out.append(
                _V("companion.left_without_warning", "error", turn, f"{cid}: partiu sem aviso")
            )
        if soul.get("loyal") and soul.get("departed") == "betrayed":
            out.append(_V("companion.loyal_betrayed", "error", turn, f"{cid}: leal não trai"))
        if sum(1 for q in quests if q.get("personal_of") == cid) > 1:
            out.append(
                _V("companion.many_personal_quests", "error", turn, f"{cid}: >1 missão pessoal")
            )
    for ev in state.get("event_log") or []:
        if not isinstance(ev, dict) or ev.get("type") != "companion_fate":
            continue
        payload = ev.get("payload") or {}
        soul = souls.get(ev.get("target_id")) or {}
        days = [t.get("day") for t in soul.get("telegraphs") or [] if isinstance(t, dict)]
        day = payload.get("day")
        if not days or not isinstance(day, int) or day - min(days) < 1:
            out.append(
                _V(
                    "companion.fate_without_telegraph",
                    "error",
                    turn,
                    f"{ev.get('target_id')}: destino off-screen sem telegrama de >= 1 dia",
                )
            )
    return out


_LAW_LEAK_KEYS = ("law_state", "heat", "bounty", "wanted")


def check_law(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-299 §3.8: ``law.no_leak`` (a API nunca expõe a lei), ``law.report_needs_witness``
    (todo relato vem de quem testemunhou) e ``law.heat_bounds`` (0..100)."""
    law_state = state.get("law_state")
    if not isinstance(law_state, dict) or not law_state:
        return []
    out: list[Violation] = []
    crimes = {c.get("crime_id"): c for c in law_state.get("crimes") or [] if isinstance(c, dict)}
    for rep in law_state.get("reports") or []:
        crime = crimes.get(rep.get("crime_id")) if isinstance(rep, dict) else None
        if crime is None or rep.get("reporter") not in (crime.get("witnesses") or []):
            out.append(
                _V(
                    "law.report_needs_witness",
                    "error",
                    turn,
                    "relato sem testemunha correspondente no crime",
                    report=str((rep or {}).get("report_id")),
                )
            )
    for jid, w in (law_state.get("wanted") or {}).items():
        heat = (w or {}).get("heat", 0)
        if not isinstance(heat, int) or not 0 <= heat <= 100:
            out.append(_V("law.heat_bounds", "error", turn, f"{jid}: heat fora de 0..100"))
    try:
        import api

        dumped = api.format_response(state).model_dump()
        leaked = [k for k in _LAW_LEAK_KEYS if k in dumped]
        if leaked:
            out.append(_V("law.no_leak", "error", turn, f"GameResponse vazou {leaked}"))
    except Exception:  # silent-ok: invariante é rede de segurança, nunca fonte de crash
        pass
    return out


def check_world_quests(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-305 R6/R9/R16/R2 (R27): quests de mundo — so do que foi percebido, teto de 3,
    nunca falham antes do prazo e o prazo nunca encurta."""
    quests = [q for q in (state or {}).get("quests") or [] if q.get("world_kind")]
    if not quests:
        return []
    out: list[Violation] = []
    active = [q for q in quests if q.get("status") == "active"]
    if len(active) > 3:
        out.append(
            _V(
                "quest.world_cap_exceeded",
                "error",
                turn,
                f"{len(active)} quests de mundo ativas (teto 3)",
                active=len(active),
            )
        )
    sim = (state or {}).get("world_sim") or {}
    ledger = set(sim.get("perceived_ids") or [])
    heard_any = {i for ids in ((state or {}).get("location_heard") or {}).values() for i in ids}
    logged = {str(e.get("event_id")) for e in (state or {}).get("event_log") or []}
    prev_by_id = {q.get("id"): q for q in (prev or {}).get("quests") or [] if q.get("world_kind")}
    for q in quests:
        via = q.get("heard_via") or {}
        ref = str(via.get("event_id") or "")
        channel = str(via.get("channel") or "")
        if channel in ("npc", "rumor"):
            heard = ref in heard_any
        else:
            heard = ref in ledger or (
                q.get("world_kind") in ("reabrir_rota", "recuperar_objeto") and ref in logged
            )
        if not (channel and ref and heard):
            out.append(
                _V(
                    "quest.world_unheard",
                    "error",
                    turn,
                    "quest de mundo sem percepção registrada",
                    kind=q.get("world_kind"),
                    channel=channel,
                )
            )
        if (
            q.get("status") == "failed"
            and q.get("fail_reason") == "prazo"
            and q.get("world_kind") != "resgate"
            and int(q.get("resolved_day", 0) or 0) < int(q.get("deadline_day", 0) or 0)
        ):
            out.append(
                _V(
                    "quest.failed_before_deadline",
                    "error",
                    turn,
                    "quest de mundo falhou antes do prazo",
                    kind=q.get("world_kind"),
                )
            )
        before = prev_by_id.get(q.get("id"))
        if before and int(q.get("deadline_day", 0) or 0) < int(before.get("deadline_day", 0) or 0):
            out.append(
                _V(
                    "quest.deadline_shortened",
                    "error",
                    turn,
                    "prazo de quest de mundo encurtou",
                    kind=q.get("world_kind"),
                )
            )
    return out


def check_calendar(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-303 R27: festa nunca por cima de crise; estação nunca anda para trás; parâmetros
    do calendário congelados."""
    sim = (state or {}).get("world_sim") or {}
    cal = sim.get("calendar")
    if not isinstance(cal, dict):
        return []
    from services import world_calendar as wcal

    out: list[Violation] = []
    prev_sim = (prev or {}).get("world_sim") or {}
    prev_cal = prev_sim.get("calendar")
    if isinstance(prev_cal, dict) and prev_cal != cal:
        # SPEC-307 R24: exatamente uma mudanca v1 -> v2 (migracao) e legitima.
        migrated = prev_cal.get("version") == 1 and cal.get("migrated_from") == 1
        if not migrated:
            out.append(_V("calendar.params_changed", "error", turn, "world_sim.calendar mudou"))
    rows = ((state.get("world_projection") or {}).get("location_states")) or {}
    prev_rows = (((prev or {}).get("world_projection") or {}).get("location_states")) or {}
    for lid, row in rows.items():
        was = (prev_rows.get(lid) or {}).get("state")
        if (row or {}).get("state") == "festa" and was and was != "festa":
            out.append(_V("calendar.festa_over_crisis", "error", turn, f"{lid}: festa sobre {was}"))
    cur_season = ((state.get("world") or {}).get("season") or {}).get("id")
    prev_season = (((prev or {}).get("world") or {}).get("season") or {}).get("id")
    if cur_season in wcal.SEASONS and prev_season in wcal.SEASONS:
        dd = int(((state.get("world") or {}).get("world_clock") or {}).get("day", 1) or 1) - int(
            (((prev or {}).get("world") or {}).get("world_clock") or {}).get("day", 1) or 1
        )
        step = (wcal.SEASONS.index(cur_season) - wcal.SEASONS.index(prev_season)) % 4
        min_season = int(cal.get("month_days") or cal.get("season_days") or 14)  # R24: v2 = 20
        if (dd == 0 and step != 0) or (0 <= dd < min_season and step == 3):
            out.append(
                _V(
                    "calendar.season_regressed",
                    "error",
                    turn,
                    f"{prev_season} -> {cur_season} em {dd} dia(s)",
                )
            )
    out.extend(_check_date(state, prev, turn))
    return out


def _check_date(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-307 R24: data nunca anda para tras; vista `world["date"]` fresca apos o tick."""
    w = (state or {}).get("world") or {}
    view = w.get("date")
    if not isinstance(view, dict):
        return []
    out: list[Violation] = []
    day = int((w.get("world_clock") or {}).get("day", 1) or 1)
    pw = (prev or {}).get("world") or {}
    pview = pw.get("date")
    pday = int((pw.get("world_clock") or {}).get("day", 1) or 1)
    if isinstance(pview, dict) and day > pday:
        from services import world_calendar as wcal

        order = [m["id"] for m in wcal.months()]

        def _key(v: dict) -> tuple[int, int, int]:
            mid = v.get("month_id")
            return (
                int(v.get("year", 0) or 0),
                order.index(mid) if mid in order else -1,
                int(v.get("day_of_month", 0) or 0),
            )

        if _key(view) < _key(pview):
            out.append(
                _V(
                    "calendar.date_regressed",
                    "error",
                    turn,
                    f"{pview.get('label')} -> {view.get('label')}",
                )
            )
    sim_day = int(((state or {}).get("world_sim") or {}).get("last_ticked_day", 0) or 0)
    if sim_day >= day and view.get("day") != day:
        out.append(
            _V(
                "calendar.date_stale",
                "warning",
                turn,
                f"world.date.day={view.get('day')} != world_clock.day={day}",
            )
        )
    return out


def check_npc_world(state: dict, prev: dict | None, turn: int) -> list[Violation]:
    """SPEC-304 R30: elenco, telegrama, percepcao, presenca, lideres e vazamento de crenca."""
    sim = (state or {}).get("npc_sim") or {}
    if not sim:
        return []
    from services import npc_perils, npc_world
    from services.npc_layers import npc_alive

    out: list[Violation] = []
    cap = int(npc_perils.const("ROSTER_CAP"))
    if len(sim.get("roster") or []) > cap:
        out.append(
            _V("npc.roster_cap_exceeded", "error", turn, f"{len(sim['roster'])} > {cap} no elenco")
        )
    world = (state or {}).get("world") or {}
    here = str(world.get("current_location_id") or "")
    day = int(((world.get("world_clock")) or {}).get("day", 1) or 1)
    known_ids = {
        str(e.get("event_id"))
        for e in [
            *((state or {}).get("event_log") or []),
            *((state or {}).get("pending_world_events") or []),
        ]
        if isinstance(e, dict)
    }
    fates = ("morto", "ferido", "capturado", "escapou")
    for p in sim.get("perils") or []:
        res = str(p.get("resolution") or "")
        if res not in fates:
            continue
        gap = int(p.get("resolved_day", 0) or 0) - int(p.get("opened_day", 0) or 0)
        if (
            not p.get("warning_event_id")
            or gap < int(npc_perils.const("TELEGRAPH_MIN_DAYS"))
            or p["warning_event_id"] not in known_ids
        ):
            out.append(
                _V(
                    "npc.fate_without_warning",
                    "error",
                    turn,
                    f"destino {res} sem telegrama >= {npc_perils.const('TELEGRAPH_MIN_DAYS')} dias",
                    peril_id=p.get("peril_id"),
                )
            )
        if res == "morto" and p.get("major") and not npc_perils.perceived(p, day):
            out.append(
                _V(
                    "npc.major_death_unperceived",
                    "error",
                    turn,
                    "morte de perigo maior sem telegrama percebido",
                    peril_id=p.get("peril_id"),
                )
            )
        if int(p.get("resolved_day", -1) or -1) == day and npc_perils.at_player(
            here, str(p.get("location_id") or "")
        ):
            out.append(
                _V(
                    "npc.fate_while_player_present",
                    "error",
                    turn,
                    "destino aplicado no local do jogador",
                    peril_id=p.get("peril_id"),
                )
            )
    for key, row in ((state or {}).get("npcs") or {}).items():
        if isinstance(row, dict) and row.get("in_scene") and not npc_alive(row):
            out.append(_V("npc.dead_in_scene", "error", turn, f"{key} morto em cena"))
    aff = ((state or {}).get("world_projection") or {}).get("npc_affiliations") or {}
    for ref in aff:
        if npc_world.is_leader(ref):
            out.append(_V("npc.leader_defected", "error", turn, f"lider {ref} trocou de lado"))
    try:
        import api

        shown = {v["name"]: v["status"] for v in api._npcs_block(state.get("npcs") or {}, state)}
    except Exception as exc:  # silent-ok: sem API (ambiente reduzido) o check de vazamento pula
        from observability.telemetry import log_fallback

        log_fallback("playtest", "belief_leak_api_unavailable", exc)
        shown = {}
    for key, row in ((state or {}).get("npcs") or {}).items():
        if not isinstance(row, dict):
            continue
        ov = npc_world.belief_view(state, str(key))
        name = row.get("name", key)
        if ov is not None and name in shown and shown[name] != ov["status"]:
            out.append(
                _V(
                    "npc.belief_leak",
                    "error",
                    turn,
                    f"API mostra status diferente da crenca de {key}",
                )
            )
    return out


CHECKS: list[Check] = [
    check_companions,
    check_law,
    check_reputation,
    check_faction_membership,
    check_vitals,
    check_vitality_consistency,
    check_wound_capacity,
    check_economy,
    check_entities,
    check_world,
    check_summary_bounds,
    check_campaign_grounding,
    check_reward_feedback,
    check_knowledge,
    check_lifecycle,
    check_combat_zombie,
    check_effect_catalog,
    check_invalid_sentinels,
    check_rag_persistence,
    check_summary_lifecycle,
    check_memory_provenance,
    check_summary_frozen,
    check_duplicate_consumed_summary,
    check_recycled_npc,
    check_actor_lifecycle,
    check_repeated_opening,
    check_interaction_no_progress,
    check_meta_leak,
    check_phantom_ally,
    check_false_player_death,
    check_encounter_identity,
    check_encounter_phase,
    check_unproven_event,
    check_projection_ahead,
    check_npc_knowledge,
    check_world_engine,
    check_world_quests,
    check_calendar,
    check_npc_world,
]


def check_all(
    state: dict, prev_state: dict | None = None, turn: int = 0, context: dict | None = None
) -> list[Violation]:
    out: list[Violation] = []
    for fn in CHECKS:
        try:
            out.extend(fn(state, prev_state, turn) or [])
        except Exception as exc:
            # O check não derruba a campanha, mas também não pode produzir verde.
            out.append(
                _V(
                    "invariant.crash",
                    "error",
                    turn,
                    f"{fn.__name__} falhou com {type(exc).__name__}: {str(exc)[:180]}",
                    check=fn.__name__,
                    exception_type=type(exc).__name__,
                    error=str(exc)[:180],
                )
            )
    try:
        out.extend(check_contextual(state, prev_state, turn, context) or [])
    except Exception as exc:
        out.append(
            _V(
                "invariant.crash",
                "error",
                turn,
                f"check_contextual falhou com {type(exc).__name__}: {str(exc)[:180]}",
                check="check_contextual",
                exception_type=type(exc).__name__,
                error=str(exc)[:180],
            )
        )
    return out


def assert_invariants(state: dict) -> None:
    """Uso em testes: levanta AssertionError legível com TODAS as violações."""
    violations = check_all(state)
    if violations:
        linhas = "\n".join(f"  [{v.severity}] {v.check_id}: {v.message}" for v in violations)
        raise AssertionError(f"{len(violations)} invariante(s) violado(s):\n{linhas}")
