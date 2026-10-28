"""
agents/router.py
Roteador de Intenções.
Agora com detecção explícita de início de combate para acionar o Spawner.
"""

import re
from contextvars import ContextVar
from enum import Enum
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END
from pydantic import BaseModel, Field, field_validator

from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services.input_normalization import optional_entity_ref
from services.prompt_guard import PLAYER_INPUT_RULE
from state import GameState


class RouteType(str, Enum):
    STORY = "storyteller"
    COMBAT = "combat_agent"
    NPC = "npc_actor"
    LOOT = "loot"
    NONE = "none"


# spec combate-lifecycle (R3): combate ATIVO que não recebe rota de combate por
# N turnos seguidos é "órfão" — expira sozinho (rede de segurança; com R1+R2 quase
# nunca dispara).
COMBAT_IDLE_EXPIRE = 3

_EXPLICIT_STORY_RE = re.compile(
    r"\b(?:descanso|descansamos|durmo|dormimos|acampo|acampamos|viajo|viajamos|(?:quero|vou|vamos|preciso|posso)\s+(?:descansar|dormir|acampar|viajar)|vou\s+para|sigo\s+para)\b",
    re.IGNORECASE,
)
_EXPLICIT_HOSTILITY_RE = re.compile(
    r"\b(?:atac\w*|golpe\w*|apunhal\w*|dispar\w*|saco\s+(?:a|minha|o|meu)?\s*"
    r"(?:arma|espada|arco)|inicio\s+(?:um\s+)?combate|enfrent\w*)\b",
    re.IGNORECASE,
)

# SPEC-317 R2: verbos que tiram um turno do "vocativo puro" (saque/comercio/coacao/favor/divida).
# Casados contra o texto DOBRADO (sem acento, minusculo): qualquer um manda o turno ao CLASSIFY.
_NON_PLAIN_TALK_RE = re.compile(
    r"\b(?:saque\w*|peg[oa]\w*|vasculh\w*|roub\w*|abr[oi]\w*|compr\w*|vend\w*|troc\w*|cri[ao]r?|"
    r"forj\w*|ameac\w*|intimid\w*|mat[aeo]\w*|esfaque\w*|cort[aeo]\w*|soc[oa]\w*|"
    r"desafi\w*|chut\w*|empurr\w*|estrangul\w*|enforc\w*|agarr\w*|segur[oa]\w*|"
    r"entreg\w*|esconda\w*|escond\w*|emprest\w*|interced\w*|divida|pag[oa]\w*|suborn\w*|"
    r"ment[ie]\w*|mintu\w*|minto|sond\w*|verdade|pression\w*|exij\w*|exig\w*|"
    r"obrig\w*|chantag\w*|blef\w*|favor|peco|pedir|imploro|suplico)\b",
    re.IGNORECASE,
)


def _last_human_text(messages) -> str:
    """Texto da última fala do jogador (para detectar viagem no gate de combate)."""
    for m in reversed(messages or []):
        if getattr(m, "type", "") == "human":
            return str(getattr(m, "content", "") or "")
    return ""


def _base_route_payload(route: RouteType, world: dict) -> dict:
    """Resposta completa: reducer não pode preservar transitórios antigos."""
    return {
        "next": route.value,
        "world": world,
        "combat_target": None,
        "active_npc_name": None,
        "loot_source": None,
        "combat_origin_hint": None,
        "npc_fallback_hint": None,  # SPEC-230 R8: transitório
        # SPEC-202: transitórios do interlocutor (zerados a cada rota).
        "interlocutor_reason": None,
        "mediated_subject_id": None,
        "combat_target_ref": None,  # SPEC-203: one-shot
        "combat_encounter_hint": None,  # SPEC-203: one-shot
    }


_LAST_DECISION: ContextVar[dict | None] = ContextVar("router_last_decision", default=None)


def reset_last_decision() -> None:
    _LAST_DECISION.set(None)


def last_decision() -> dict:
    """``{route_source, route_fallback_reason}`` da ultima decisao deste contexto."""
    return dict(_LAST_DECISION.get() or {})


def _target_kind(payload: dict) -> str:
    if payload.get("active_npc_name") or str(payload.get("combat_target_ref") or "").startswith(
        "npc:"
    ):
        return "npc"
    return "enemy" if payload.get("combat_target") else "none"


def _tag(payload: dict, source: str, fallback_reason: str | None = None) -> dict:
    """SPEC-247 R1: fonte da decisao de rota + motivo de fallback (codigos fechados).

    NAO muda o payload (o contrato ``off`` do SPEC-217 e byte-identico): guarda a decisao num
    contextvar que ``route_intent_node`` copia ao estado (vai ao ``rpg.turn``) e emite
    ``router.decision``. So o caminho que DECIDE a rota chama isto — o observador do shadow nao."""
    _LAST_DECISION.set({"route_source": source, "route_fallback_reason": fallback_reason})
    try:
        from services.jev_rollout import rollout_mode

        _log_event(
            "router",
            "decision",
            route=payload.get("next"),
            source=source,
            fallback_reason=fallback_reason,
            jev_mode=rollout_mode(),
            target_kind=_target_kind(payload),
        )
    except Exception:  # silent-ok: o log da decisao nunca derruba o turno
        pass
    return payload


def _interlocutor_payload(resolution, world: dict) -> dict:
    """SPEC-202: payload de rota a partir de uma InterlocutorResolution."""
    route = RouteType(resolution.route)
    payload = _base_route_payload(route, world)
    payload["interlocutor_reason"] = resolution.reason
    payload["mediated_subject_id"] = resolution.mediated_subject_id
    if route == RouteType.NPC:
        payload["active_npc_name"] = resolution.npc_state_key
    if resolution.fallback_hint:
        payload["npc_fallback_hint"] = resolution.fallback_hint
    return payload


def _law_gate(state: GameState, world: dict, messages) -> dict | None:
    """SPEC-299 R19: com confronto da lei aberto (`law_state.confrontation`) o router NÃO
    classifica: resolve por léxico determinístico (pagar/render-se/subornar/fugir/atacar/falar).
    Sem confronto ou `RPG_LAW != on` devolve None e o router segue idêntico."""
    from services import law

    if law.mode() != "on":
        return None
    resolver = law.resolve_choice
    if not (state.get("law_state") or {}).get("confrontation"):
        # D2: "peço o registro (licença) do meu Éter" — gesto diegético de licença.
        resolver = law.resolve_license_request
    try:
        choice = resolver(state, _last_human_text(messages))
    except Exception as exc:  # silent-ok: a lei nunca derruba o turno; segue o roteamento normal
        _log_event("law", "gate_failed", level="warning", error=type(exc).__name__)
        return None
    if not choice:
        return None
    route = RouteType(choice.pop("next"))
    payload = _base_route_payload(route, world)
    payload.update(choice)
    payload["next"] = route.value
    if route == RouteType.STORY:
        # P1-1: o turno foi resolvido pela lei; o storyteller NÃO reaplica viagem/descanso.
        payload["law_gate_consumed"] = True
    return _tag(payload, "law_gate")


def _combat_gate(state: GameState, world: dict, combat: dict):
    """Gate determinístico quando `combat.active` (spec combate-lifecycle):
    - R2: força `combat_agent` (bloqueia npc/loot; conversa segue pro combate que narra).
    - R1: ação de VIAGEM não teleporta — vira tentativa de fuga (flag + destino).
    - R3: combate órfão (idle_turns >= N) expira, limpando TUDO (R5)."""
    from world_utils import find_travel_destination

    idle = int(combat.get("idle_turns", 0)) + 1
    if idle >= COMBAT_IDLE_EXPIRE:
        _log_event("router", "orphan_combat_expired", level="info")
        cleared = {
            "active": False,
            "round": combat.get("round", 1),
            "order": combat.get("order", []),
            "idle_turns": 0,
        }
        # SPEC-203 R5/R7: expiração vira outcome explícito, com desfecho na UI.
        from services import encounter_manifest as em

        manifest = combat.get("encounter")
        if em.is_valid_manifest(manifest):
            cleared["encounter"] = manifest
            cleared["instance_id"] = combat.get("instance_id")
        cleared["phase"] = combat.get("phase") or "active"
        cleared = em.end_combat(cleared, "expired")
        if em.is_valid_manifest(manifest):
            cleared["result"] = em.build_result(
                manifest, "expired", int(combat.get("round", 1) or 1)
            )
        return _tag(
            {
                "next": RouteType.STORY.value,
                "combat": cleared,
                "enemies": [],
                "combat_target": None,
                "messages": [
                    SystemMessage(
                        content="SYSTEM: COMBAT EXPIRED — "
                        "os inimigos perdem seu rastro e o combate termina."
                    )
                ],
            },
            "combat_gate",
            "orphan_expired",
        )

    combat["idle_turns"] = idle
    payload = {
        "next": RouteType.COMBAT.value,
        "world": world,
        "combat": combat,
        "interlocutor_reason": None,
        "mediated_subject_id": None,
    }
    intent = _last_human_text(state.get("messages", []))
    # Uma borda estruturada (API/harness) já resolveu o id exato do destino.
    # O parser textual é apenas fallback: nomes de interiores contêm o nome da
    # região e podem ser reduzidos indevidamente ao nó-pai se reprocessados.
    explicit_dest_id = state.get("combat_flee_destination")
    has_structured_action = state.get("combat_declaration") is not None
    dest = (
        find_travel_destination(world, intent)
        if intent and not explicit_dest_id and not has_structured_action
        else None
    )
    if state.get("combat_flee_attempt") and explicit_dest_id:
        payload["combat_flee_attempt"] = True
        payload["combat_flee_destination"] = explicit_dest_id
    elif dest is not None:
        payload["combat_flee_attempt"] = True
        payload["combat_flee_destination"] = dest["id"]
        _log_event("router", "travel_in_combat_flee", level="info")
    return _tag(payload, "combat_gate")


_SOCIAL_APPROACHES = ("conversar", "intimidar", "sondar", "pedir_favor", "pagar_divida")
_FAVOR_KINDS = ("esconder", "emprestar", "interceder")


class RouterDecision(BaseModel):
    route: RouteType
    loot_context: Literal["TREASURE", "SHOP", "CRAFT"] | None = Field(
        description="Se for LOOT: 'TREASURE', 'SHOP' ou 'CRAFT'."
    )
    target: str | None = Field(
        description="Se for COMBAT, quem é o inimigo? Ex: 'Goblin', 'Guarda', 'O Vulto'."
    )
    reasoning: str
    confidence: float
    # SPEC-298 R20: abordagem social (só rota NPC). Inválido -> conversar / None.
    social_approach: (
        Literal["conversar", "intimidar", "sondar", "pedir_favor", "pagar_divida"] | None
    ) = Field(default=None, description="Só rota NPC: como o jogador aborda o NPC.")
    favor_kind: Literal["esconder", "emprestar", "interceder"] | None = Field(
        default=None, description="Só quando social_approach=pedir_favor."
    )

    @field_validator("social_approach", mode="before")
    @classmethod
    def _normalize_social_approach(cls, value):
        if value is None:
            return None
        return value if value in _SOCIAL_APPROACHES else "conversar"

    @field_validator("favor_kind", mode="before")
    @classmethod
    def _normalize_favor_kind(cls, value):
        return value if value in _FAVOR_KINDS else None

    @field_validator("loot_context", mode="before")
    @classmethod
    def _normalize_loot_context(cls, value):
        normalized = optional_entity_ref(value)
        return normalized.upper() if normalized is not None else None

    @field_validator("target", mode="before")
    @classmethod
    def _normalize_target(cls, value):
        return optional_entity_ref(value)


_NEGATION_BEFORE_RE = re.compile(r"\b(?:nao|nunca|jamais)\b(?:\s+\w+){0,2}\s*$")
# contexto que não é combate ("numa partida de dados", "para arrombá-la"): na dúvida, STORY
_NON_COMBAT_CONTEXT_RE = re.compile(
    r"\b(?:numa?|em\s+uma?)\s+(?:partida|jogo|disputa|aposta|competicao|concurso|queda\s+de\s+braco)\b"
    r"|\bde\s+dados\b|\bpara\s+(?:arromb|abrir|quebr|derrub|acend|cort|desbloque)\w*"
)


def _fold_text(text: str) -> str:
    """Minusculo sem acento (mesmo comprimento para texto latino precomposto)."""
    import unicodedata

    base = unicodedata.normalize("NFKD", str(text or "").casefold())
    return "".join(ch for ch in base if not unicodedata.combining(ch))


def _last_ai_text(messages) -> str:
    for m in reversed(messages or []):
        if getattr(m, "type", "") == "ai":
            return str(getattr(m, "content", "") or "")
    return ""


_HOSTILE_1P_RE = re.compile(
    r"\b(?:ataco|golpeio|apunhalo|esfaqueio|enfrento|atiro\s+(?:em|contra)|"
    r"disparo\s+(?:em|contra)|invisto\s+(?:contra|sobre))\s+(?P<obj>[^.,;!?]+)"
)
_OBJ_CUT_RE = re.compile(r"\b(?:e|com|que|para|pra|ate|enquanto|pois|mas)\b")
_POSSESSIVE_RE = re.compile(r"^(?:o\s+|a\s+)?(?:meu|minha|meus|minhas|seu|sua|nosso|nossa)\b")
_CREATURE_WORDS = ("criatura", "inimigo", "vulto", "monstro", "besta", "figura", "hostil")
_THREAT_WORDS_RE = re.compile(r"\b(?:ameac\w*|hostil\w*|ataq\w*|emboscad\w*|sac[ao]u?|rosn\w*)\b")


def _hostility_target(state, folded: str, obj: str) -> str | None:
    """Alvo presente na cena para o objeto do verbo hostil, ou ``None`` (na dúvida, STORY).

    Presente = NPC em cena citado, criatura do bestiário/da lista de inimigos citada, ou
    substantivo que a última narração da IA (com ameaça) acabou de apresentar. Genérico
    ("a criatura hostil") só vale com ameaça + criatura na última narração."""
    from services import encounter_manifest as em
    from services import npc_layers

    obj = _OBJ_CUT_RE.split(obj.strip())[0].strip()
    if not obj or _POSSESSIVE_RE.match(obj):
        return None
    core = em.hint_core(obj)
    tokens = set(em.name_tokens(core))
    ai = _fold_text(_last_ai_text(state.get("messages") or []))
    threat = bool(_THREAT_WORDS_RE.search(ai))
    if not tokens:  # alvo genérico
        if threat and any(w in ai for w in _CREATURE_WORDS):
            return "Inimigos"
        return None
    npcs = state.get("npcs") or {}
    for name in npc_layers.npcs_in_scene(state):
        if name in npcs and _fold_text(name) in obj:
            return core
    wanted = tokens
    for _bid, entry in em._bestiary().items():
        names = set(em.name_tokens(entry.get("name", "") or _bid))
        if names and names <= wanted:
            return core
    for enemy in state.get("enemies") or []:
        names = set(em.name_tokens(str(enemy.get("name") or "")))
        if names and names <= wanted:
            return core
    manifest = (state.get("combat") or {}).get("encounter")
    if em.is_valid_manifest(manifest):  # criaturas do manifesto do encontro
        for part in manifest.get("participants") or []:
            names = set(em.name_tokens(str(part.get("species_label") or part.get("name") or "")))
            if names and names <= wanted:
                return core
    return None


def _hostility_fallback(state, last_human: str, world: dict, _resumed, resume_explore: bool):
    """SPEC-346 R26: CLASSIFY esgotado + verbo hostil em 1ª pessoa no presente + alvo presente.

    Devolve ``None`` (segue STORY) sem verbo, com negação, particípio/narração ("fui atacado"),
    objeto que não é entidade da cena ("a mesa", "meu medo", "a subida") ou na dúvida."""
    folded = _fold_text(last_human)
    if _NON_COMBAT_CONTEXT_RE.search(folded):
        return None
    chosen = None
    for m in _HOSTILE_1P_RE.finditer(folded):
        if _NEGATION_BEFORE_RE.search(folded[: m.start()]):
            continue
        try:
            chosen = _hostility_target(state, folded, m.group("obj"))
        except Exception as exc:  # silent-ok: sem alvo o fluxo segue STORY
            _log_event(
                "router", "hostility_signal_failed", level="warning", error=type(exc).__name__
            )
            return None
        if chosen:
            break
    if not chosen:
        return None
    decision = RouterDecision(
        route=RouteType.COMBAT,
        loot_context=None,
        target=chosen,
        reasoning="hostility_fallback",
        confidence=0.5,
    )
    payload = _finalize(state, last_human, world, decision, _resumed, resume_explore)
    payload["interlocutor_reason"] = "classify_fallback"
    return payload


def dm_router_node(state: GameState):
    messages = state.get("messages", [])
    if not messages:
        return {"next": RouteType.STORY.value}

    last_msg = messages[-1]
    # Evita loop se a IA acabou de falar (exceto tool calls)
    if isinstance(last_msg, AIMessage) and not getattr(last_msg, "tool_calls", None):
        return {"next": END}

    world = state.get("world", {})
    loc = world.get("current_location", "Desconhecido")

    # spec combate-lifecycle: com combate ATIVO, o router não decide livremente —
    # gate determinístico (força combate, converte viagem em fuga, expira órfão).
    combat = dict(state.get("combat") or {})
    if combat.get("active"):
        return _combat_gate(state, world, combat)

    from services.actor_lifecycle import is_recovery_turn

    if is_recovery_turn(state):
        return _tag(_base_route_payload(RouteType.STORY, world), "recovery")

    law_payload = _law_gate(state, world, messages)
    if law_payload is not None:
        return law_payload

    # Descanso e viagem explícitos fora de combate são mecânicas de STORY.
    # Fechar essa borda evita que contexto hostil antigo reabra um conflito no
    # turno imediatamente posterior a uma fuga.
    last_human = _last_human_text(messages)

    # SPEC-203 R6: o 1º turno após um encontro encerrado (≠ morte) NÃO reabre
    # combate por contexto residual — só hostilidade explícita reabre. A intenção
    # NPC/LOOT/STORY do jogador continua sendo respeitada (revisão Astra: forçar
    # STORY sequestrava "falo com o prisioneiro rendido").
    resume_explore = bool(
        combat.get("phase") == "ended"
        and combat.get("result")
        and not combat.get("explore_resumed")
        and combat.get("outcome") != "death"
    )

    def _resumed(payload: dict) -> dict:
        if resume_explore:
            payload["combat"] = {**combat, "explore_resumed": True}
        return payload

    # SPEC-229 R4: hostilidade explícita tem precedência; formas verbais fechadas.
    if _EXPLICIT_STORY_RE.search(last_human) and not _EXPLICIT_HOSTILITY_RE.search(last_human):
        return _tag(_resumed(_base_route_payload(RouteType.STORY, world)), "story_regex")

    # SPEC-202 R2/R3: meta-pergunta ao narrador e descrição de cena são decididas
    # em Python, SEM chamar o CLASSIFY (zero invoke).
    from services import interlocutor

    pre = interlocutor.pre_classify(state, last_human)
    if pre is not None:
        return _tag(_resumed(_interlocutor_payload(pre, world)), "interlocutor")

    # SPEC-317 R2: vocativo inequivoco a NPC presente -> rota NPC sem CLASSIFY. Roda DEPOIS do
    # Jev primary (que, coberto, decide); em shadow so observa e compara com a decisao real.
    det_mode = _deterministic_npc_mode()
    det_pre = _deterministic_npc(state, last_human) if det_mode != "off" else None

    # SPEC-217 R14 (rollout SPEC-180): the Jev runs only AFTER every Python gate.
    # ``off`` (default) returns None with no side effect. Primary decides when the
    # frozen J2 policy covers the turn; shadow only observes the CLASSIFY result.
    from services import jev_rollout

    pending = jev_rollout.begin(state, last_human)
    if pending is not None and pending.mode == "primary":
        routing = pending.primary_routing()
        if routing is not None:
            jev_payload = _finalize(
                state, last_human, world, _jev_decision(state, routing), _resumed, resume_explore
            )
            _log_deterministic_shadow(det_mode, det_pre, jev_payload, "jev")
            return _tag(jev_payload, "jev")

    if det_pre is not None and det_mode == "on":
        _log_event("router", "deterministic_npc", route="npc_actor")
        return _tag(_resumed(_interlocutor_payload(det_pre, world)), "deterministic_npc")

    payload = _classify(state, messages, last_human, world, loc, _resumed, resume_explore)
    _log_deterministic_shadow(det_mode, det_pre, payload, "classify")
    if pending is not None and pending.mode == "shadow":
        pending.observe(
            payload,
            lambda routing: _finalize(
                state, last_human, world, _jev_decision(state, routing), _resumed, resume_explore
            ),
            state,
        )
    return payload


def likely_non_story(state: GameState, text: str) -> bool:
    """Heuristica pura (sem LLM) p/ o prefetch: o turno provavelmente NAO e STORY."""
    from services import interlocutor

    folded = interlocutor._norm(text)
    if _EXPLICIT_HOSTILITY_RE.search(folded) or _NON_PLAIN_TALK_RE.search(folded):
        return True
    if (state.get("combat") or {}).get("active"):
        return True
    return interlocutor.addressed_in_scene(state, text) is not None


def _log_deterministic_shadow(mode: str, det_pre, payload: dict, source: str) -> None:
    """Shadow do R2: ``agree`` exige rota, NPC E ausencia de abordagem social (SPEC-298 R20),
    porque o caminho ``on`` sempre devolve ``conversar``."""
    if det_pre is None or mode != "shadow":
        return
    _log_event(
        "router",
        "deterministic_shadow",
        agree=bool(
            payload.get("next") == RouteType.NPC.value
            and payload.get("active_npc_name") == det_pre.npc_state_key
            and payload.get("social_intent") is None
        ),
        decided_by=source,
    )


def _deterministic_npc_mode() -> str:
    """``RPG_ROUTER_DETERMINISTIC_NPC``: off | shadow (default) | on (SPEC-317 R2)."""
    import os

    value = os.environ.get("RPG_ROUTER_DETERMINISTIC_NPC", "shadow").strip().lower()
    return value if value in ("off", "shadow", "on") else "shadow"


def _deterministic_npc(state: GameState, last_human: str):
    """NPC resolution when the player plainly addresses a NPC present in the scene.

    Only a direct vocative qualifies (``direct_address``), with no hostility, loot,
    coercion or favour lexicon; anything else returns None and goes to CLASSIFY."""
    from services import interlocutor

    folded = interlocutor._norm(last_human)
    if (
        _EXPLICIT_HOSTILITY_RE.search(last_human)
        or _EXPLICIT_HOSTILITY_RE.search(folded)
        or _NON_PLAIN_TALK_RE.search(folded)
    ):
        return None
    try:
        addressed = interlocutor.addressed_in_scene(state, last_human)
    except Exception as exc:  # silent-ok: o atalho nunca derruba o turno; segue ao CLASSIFY
        _log_event("router", "deterministic_npc_failed", level="warning", error=type(exc).__name__)
        return None
    if addressed is None or addressed[1] != "direct_address":
        return None
    return interlocutor.deterministic_npc_resolution(addressed[0])


_THREAT_NARRATED_RE = re.compile(
    r"\b(?:ameac\w*|hostil\w*|armad[oa]s?|ataq\w*|emboscad\w*|perig\w*|sac[ao]u?|rosn\w*)\b"
)


def _window_trim_enabled() -> bool:
    """``RPG_ROUTER_WINDOW_TRIM=on|off`` (default off ate o evals compare do router, SPEC-317 R4)."""
    import os

    return os.environ.get("RPG_ROUTER_WINDOW_TRIM", "off").strip().lower() == "on"


def _router_window(messages) -> list:
    """SPEC-317 R4: ultima fala do jogador + cauda (400 chars) da narracao anterior
    + fala anterior do jogador, em ordem cronologica."""
    msgs = list(messages or [])
    humans = [i for i, m in enumerate(msgs) if getattr(m, "type", "") == "human"]
    if not humans or not _window_trim_enabled():
        return msgs[-3:]
    last_i = humans[-1]
    out: list = []
    prev_human_i = humans[-2] if len(humans) > 1 else None
    if prev_human_i is not None:
        out.append(msgs[prev_human_i])
    for i in range(last_i - 1, -1, -1):
        m = msgs[i]
        if getattr(m, "type", "") == "ai" and str(getattr(m, "content", "") or "").strip():
            text = str(m.content)
            # a cabeca descartada nunca pode conter uma ameaca narrada (regra COMBAT do prompt)
            head = text[:-400]
            from services.interlocutor import _norm

            keep_all = len(text) <= 400 or bool(
                _EXPLICIT_HOSTILITY_RE.search(head) or _THREAT_NARRATED_RE.search(_norm(head))
            )
            out.append(m if keep_all else AIMessage(content=text[-400:]))
            break
    out.append(msgs[last_i])
    return out


def _jev_decision(state: GameState, routing) -> RouterDecision:
    """A covered Jev decision as a RouterDecision (scene ID -> router target name)."""
    from services.jev_rollout import target_name_for_id

    return RouterDecision(
        route=RouteType(routing.route),
        loot_context=routing.loot_source,
        target=target_name_for_id(state, routing.target_id),
        reasoning="jev",
        confidence=routing.confidence,
    )


def _classify(
    state: GameState, messages, last_human: str, world: dict, loc, _resumed, resume_explore: bool
) -> dict:
    """The CLASSIFY path (behaviour unchanged by SPEC-217)."""
    from services import interlocutor

    scene_names = (
        ", ".join(
            interlocutor.canonical_npc_name(state, key) for key in interlocutor.scene_keys(state)
        )
        or "ninguém"
    )

    from services.prompt_layout import compose as compose_prompt

    # SPEC-317 R9: regras estaticas primeiro quando RPG_PROMPT_STATIC_FIRST=on.
    _router_intro = """
    Roteador de RPG. Classifique a intenção da ÚLTIMA mensagem do jogador.
    
    """
    _router_state = f"""Local Atual: {loc}
    NPCs presentes na cena: {scene_names}

    """
    _router_rules = f"""REGRAS:
    - COMBAT: Jogador ataca, saca armas ou reage a uma ameaça narrada. IMPORTANTE: Identifique o 'target' (inimigo).
    - NPC: Conversa social, diplomacia DIRIGIDA a um personagem presente. 'target' = nome EXATO de um NPC presente (ou vazio).
    - Se a rota for NPC, preencha 'social_approach': conversar (padrão) | intimidar (ameaça/coação) | sondar (ler intenções, "ele mente?") | pedir_favor (esconder/emprestar/interceder -> 'favor_kind') | pagar_divida.
    - Pergunta ao narrador/mestre SOBRE alguém (o que sente, se mente, quem é) = STORY, não NPC.
    - LOOT: "Vasculhar corpo", "Pegar item", "Abrir baú" (TREASURE) ou "Comprar/Vender/Criar" (SHOP/CRAFT).
    - STORY: Movimentação, exploração, observar cenário.
    - {PLAYER_INPUT_RULE}
    """
    system_instruction = compose_prompt(
        [(_router_intro, True), (_router_state, False), (_router_rules, True)]
    )

    llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)

    try:
        from services.prompt_guard import guard_messages

        router_llm = llm.with_structured_output(RouterDecision)
        decision = router_llm.invoke(
            [SystemMessage(content=system_instruction)] + guard_messages(_router_window(messages))
        )
    except Exception as e:
        _log_event("router", "failed", level="error", error=type(e).__name__)
        hostile = _hostility_fallback(state, last_human, world, _resumed, resume_explore)
        if hostile is not None:
            return _tag(hostile, "hostility_fallback", "invoke_exception")
        return _tag(
            _resumed(
                {
                    **_base_route_payload(RouteType.STORY, world),
                    "interlocutor_reason": "classify_fallback",
                }
            ),
            "classify_fallback",
            "invoke_exception",
        )

    # Sem API key (FallbackLLM) o invoke devolve um AIMessage, não um
    # RouterDecision. Nesse caso seguimos para o storyteller (modo degradado).
    if not isinstance(decision, RouterDecision):
        hostile = _hostility_fallback(state, last_human, world, _resumed, resume_explore)
        if hostile is not None:
            return _tag(hostile, "hostility_fallback", "not_router_decision")
        return _tag(
            _resumed(
                {
                    **_base_route_payload(RouteType.STORY, world),
                    "interlocutor_reason": "classify_fallback",
                }
            ),
            "classify_fallback",
            "not_router_decision",
        )
    return _tag(_finalize(state, last_human, world, decision, _resumed, resume_explore), "classify")


def _finalize(
    state: GameState,
    last_human: str,
    world: dict,
    decision: RouterDecision,
    _resumed,
    resume_explore: bool,
) -> dict:
    """Router payload from a RouterDecision (CLASSIFY, or a covered Jev decision)."""
    from services import interlocutor

    # RouteType.NONE ("nenhuma intenção clara": input sem ação, lixo ou injeção)
    # NÃO é um nó do grafo — o mapping condicional de main.py só conhece
    # storyteller/combat/npc/loot/END. O LLM real ESCOLHE NONE para a entrada do
    # troll (emoji, SQL, "ignore as instruções") e o router devolvia next="none"
    # → KeyError('none') no grafo. O MockLLM nunca escolhe NONE, então o bug só
    # aparecia no LLM real (achado do playtest da Fase 5). Normaliza para STORY:
    # o narrador descreve o ambiente em vez de derrubar o turno.
    if decision.route == RouteType.NONE:
        decision.route = RouteType.STORY
    # SPEC-203 R6: pós-desfecho, COMBAT sem hostilidade explícita vira exploração.
    if (
        resume_explore
        and decision.route == RouteType.COMBAT
        and not _EXPLICIT_HOSTILITY_RE.search(last_human)
    ):
        decision.route = RouteType.STORY

    # SPEC-202 R3–R8: o alvo do CLASSIFY só vira interlocutor se resolver para
    # uma ficha existente em cena; o alvo cru NUNCA é propagado (R5).
    if decision.route in (RouteType.NPC, RouteType.STORY):
        resolution = interlocutor.post_classify(
            state, last_human, decision.route.value, decision.target
        )
        payload = _interlocutor_payload(resolution, world)
        # SPEC-298 R20: a abordagem só vale na rota NPC; carrega o turno p/ não vazar.
        intent = None
        if decision.route == RouteType.NPC and decision.social_approach not in (None, "conversar"):
            from services.reputation import normalize_social_intent

            intent = {
                **normalize_social_intent(decision.social_approach, decision.favor_kind),
                "turn": int((world or {}).get("turn_count", 0) or 0),
            }
        if intent is not None:  # sem abordagem: payload byte a byte igual ao anterior
            payload["social_intent"] = intent
        return _resumed(payload)

    response_payload = _base_route_payload(decision.route, world)
    response_payload["interlocutor_reason"] = "classify_story"

    if decision.route == RouteType.LOOT:
        response_payload["loot_source"] = decision.loot_context or "TREASURE"

    # GATILHO DE COMBATE:
    # Se for combate, adicionamos uma flag no histórico (temporária) para o Combat Agent saber que é o turno 1
    if decision.route == RouteType.COMBAT:
        target = decision.target or "Inimigos"
        response_payload["combat_target"] = target
        # SPEC-203 R3(b): alvo que casa com NPC em cena vira referência canônica.
        from services import npc_layers

        folded_target = target.casefold()
        for npc_name in npc_layers.npcs_in_scene(state):
            if npc_name in (state.get("npcs") or {}) and (
                npc_name.casefold() in folded_target or folded_target in npc_name.casefold()
            ):
                response_payload["combat_target_ref"] = f"npc:{npc_name}"
                break
        response_payload["combat_origin_hint"] = (
            "player_provoked" if _EXPLICIT_HOSTILITY_RE.search(last_human) else "regional_danger"
        )
        if "messages" not in response_payload:
            response_payload["messages"] = []
        response_payload["messages"].append(
            SystemMessage(content=f"SYSTEM: COMBAT START. TARGET_HINT: {target}")
        )

    return _resumed(response_payload)
