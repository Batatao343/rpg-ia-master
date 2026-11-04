"""
agents/combat.py — Agente de Combate (conflito v2, pós-cutover conflito-13).

Arquitetura NOVA: a IA só PREPARA a cena (uma vez, antes) e NARRA (depois). A
resolução do conflito é 100% Python/determinística no motor novo
(`services/conflict_orchestrator.run_round`, que compõe as specs 03-12). ZERO LLM
durante a resolução — só a identificação da fala do jogador → `TurnDeclaration`
(tier CLASSIFY) e a narração final (tier FAST).

Fluxo de 1 chamada = 1 RODADA:
  (1º turno) preparar cena jogável → congelar → posicionar
  → identificar a ação do jogador (fala livre → TurnDeclaration)
  → run_round (iniciativa/ataques/dano→Ferimento/Reações/Terminal/Abismo)
  → espelhar Vitalidade→hp (HUD/checkpoints) → narrar → summary→loot na vitória.
"""

import random
import re
import zlib
from dataclasses import dataclass
from typing import Any, Dict, List, NamedTuple, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field

import combat_mechanics as cm
import gamedata
from agents.bestiary import generate_new_enemy
from llm_setup import ModelTier, get_llm
from observability.telemetry import log_event as _log_event
from services import card_rewards, card_status, death_flow
from services import conflict_orchestrator as orch
from services import conflict_scene as cs
from services import conflict_summary as summ
from services import discovery as disc
from services import encounter_preparation as prep
from services import enemy_intent as _enemy_intent
from services import fauna_saber as _fauna_saber
from services import generic_spawn as _gs
from services import graph_resolver as gr
from services import off_text as _off_text
from services import scene_cards as _scene_cards
from services.conflict_turn import _SUPPORT_EFFECTS, TurnDeclaration, TurnStep
from services.context_builder import build_context_pack
from services.prompt_guard import PLAYER_INPUT_RULE, guard_messages, wrap_player_input
from state import GameState

_PLAYER_ID = "player"


class FleeDecision(NamedTuple):
    """Resultado único de perseguição, compatível com o unpack legado."""

    escaped: bool
    logs: list[str]
    chase: dict

    @property
    def eligible(self) -> bool:
        return self.chase.get("eligible") is True and not self.chase.get("blocked_reason")


def _downed_identity_tokens(player: dict) -> list[str]:
    """All stable identities understood by ConflictSummary for the protagonist."""
    return list(
        dict.fromkeys(
            value
            for value in (
                _PLAYER_ID,
                str(player.get("id") or ""),
                str(player.get("name") or ""),
            )
            if value
        )
    )


_MAX_SCANNER_TYPES = 8
_MAX_SCANNER_PER_TYPE = 12
_MAX_SCANNER_TOTAL = 24


# --- Schema de identificação de inimigos na cena (IA só identifica) ---
class EnemyIdentification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Nome singular do inimigo. Ex: 'Goblin'.")
    count: int = Field(
        ge=1,
        le=_MAX_SCANNER_PER_TYPE,
        description="Quantidade destes inimigos na cena.",
    )


class EncounterScanner(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected_enemies: list[EnemyIdentification] = Field(max_length=_MAX_SCANNER_TYPES)
    flavor_text: str = Field(description="Descrição curta da entrada dos inimigos em combate.")


# ==========================================================================
# Eventos canônicos de morte de inimigo (mantidos do motor antigo)
# ==========================================================================
def _canonical_enemy_id(enemy: dict) -> str | None:
    raw = (enemy.get("id") or "").strip()
    if not raw:
        return None
    base = re.sub(r"_\d+$", "", raw)
    for cand in (base, raw):
        ent = gr.get_entity(cand)
        if ent and ent.get("type") == "npc":
            return cand
    return None


def _kill_events(dead: list[dict]) -> list[dict]:
    kills = []
    for e in dead:
        cid = _canonical_enemy_id(e)
        if cid:
            kills.append(
                {
                    "type": "npc_killed",
                    "actor_id": "player",
                    "target_id": cid,
                    "detail": f"{e.get('name', 'inimigo')} morto em combate",
                    "payload": {},
                    "source": "combat",
                }
            )
    return kills


def _mark_nonlethal(decl: TurnDeclaration, intent: str) -> None:
    """SPEC-325 R9: golpe do jogador declarado não-letal (texto ou chip) vira
    `params["nao_letal"]`. O orquestrador decide o efeito conforme a flag
    (`shadow` só registra, `on` incapacita). Inimigo nunca declara não-letal."""
    from services import combat_flags
    from services.combat_intents import nonlethal_declared

    if combat_flags.mode("nonlethal") == "off":
        return
    steps = [decl.acao] if decl.acao is not None else []
    steps += [s for s in (decl.jogadas or []) if all(s is not t for t in steps)]  # SPEC-342 R1.3
    declared = nonlethal_declared(intent)
    for step in steps:
        if step.kind not in ("attack", "card"):
            continue
        if step.params.get("nao_letal") or declared:
            step.params["nao_letal"] = True


def _reveal_resistances(attacks: list[dict], enemies: list[dict], sides: dict) -> None:
    """SPEC-325 R8: imunidade/resistência/vulnerabilidade só é revelada depois de
    agir num golpe do herói/aliado contra inimigo (regra de ouro). `shadow` só
    registra. No perfil `legacy` persiste no bestiário (fail-closed como
    `_sync_enemy_knowledge`)."""
    import os

    from services import bestiary_knowledge as bk
    from services import combat_flags

    mode = combat_flags.mode("reveal_resist")
    if mode == "off":
        return
    friendly = set(sides.get("hero", [])) | set(sides.get("ally", []))
    by_id = {str(e.get("id") or e.get("name")): e for e in enemies if isinstance(e, dict)}
    shared = os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() == "legacy"
    for atk in attacks:
        hit = atk.get("resistance_hit")
        enemy = by_id.get(str(atk.get("target_id") or ""))
        if not hit or enemy is None or atk.get("actor_id") not in friendly:
            continue
        entry = f"{hit['type']}:{hit['effect']}"
        if entry in (enemy.get("revealed_resistances") or []):
            continue
        if mode == "shadow":
            _log_event("combat", "reveal_resist_shadow", effect=str(hit["effect"]))
            continue
        try:
            if shared:
                bk.reveal_resistance(enemy, entry)
            else:
                enemy.setdefault("revealed_resistances", []).append(entry)
        except Exception:  # revelação é cosmética: nunca derruba o turno
            _log_event("combat", "enemy_knowledge_failed", level="warning")
        else:
            _log_event("combat", "reveal_resist", effect=str(hit["effect"]))


def _chase_is_live(chase: object) -> bool:
    """Perseguição em andamento (não terminal, elegível) — base das escolhas da Fase B."""
    from services import chase as chase_mod

    return (
        isinstance(chase, dict)
        and chase.get("eligible") is not False
        and not chase.get("blocked_reason")
        and not chase.get("alcancado")
        and not chase.get("escapou")
        and chase.get("trilha") in chase_mod.TRACK[:-1]
    )


def _chase_attack_gate(combat_meta: dict, decl: TurnDeclaration) -> str:
    """SPEC-325 R11: ataque do jogador com perseguição ativa. À distância segue; corpo a
    corpo em `pressionado` fecha a trilha (combate normal); em `afastado`/`quase_livre` é
    RECUSADO (devolve o motivo, sem gastar a rodada). `shadow` só registra."""
    from services import cards, combat_flags
    from services import chase as chase_mod
    from services import conflict_turn as ct

    mode = combat_flags.mode("chase_attack")
    step = decl.acao
    chase = combat_meta.get("chase")
    if mode == "off" or step is None or step.kind not in ("attack", "card"):
        return ""
    if not _chase_is_live(chase):
        return ""
    card = cards.get_card(step.card_id or "") if step.card_id else None
    melee = ct._is_melee(card, step)
    verdict = chase_mod.chase_attack(dict(chase), melee=melee)
    if mode == "shadow":
        _log_event(
            "combat",
            "chase_attack_shadow",
            mode=str(verdict["mode"]),
            allowed=bool(verdict["allowed"]),
        )
        return ""
    if not verdict["allowed"]:
        _log_event("combat", "chase_attack_refused", level="info")
        return (
            "Corpo a corpo é impossível enquanto os inimigos estão a distância: "
            "reduza a distância antes ou ataque de longe."
        )
    if verdict["ends_chase"]:
        combat_meta.pop("chase", None)
        _log_event("combat", "chase_attack_reengage", level="info")
    return ""


def _visible_scene_objects(scene: dict | None) -> list[dict]:
    """Objetos que o herói enxerga (sem `effect`; secreto só depois de descoberto)."""
    return cs.visible_objects(scene or {}) if scene else []


def _object_declaration(scene: dict, intent: str) -> TurnDeclaration | None:
    """SPEC-325 R14: nome canônico do objeto + rótulo da interação no texto (chip) vira
    `TurnStep(kind="object")` sem LLM. `shadow` só registra; `off` não faz nada."""
    from services import combat_flags
    from services.combat_intents import object_step

    mode = combat_flags.mode("objects")
    if mode == "off":
        return None
    hit = object_step(intent, _visible_scene_objects(scene))
    if hit is None:
        return None
    if mode == "shadow":
        _log_event("combat", "objects_shadow", action="declare")
        return None
    return TurnDeclaration(
        actor_id=_PLAYER_ID,
        acao=TurnStep(kind="object", object_id=hit[0], interaction=hit[1]),
    )


def _valid_object_use(scene: dict | None, object_id: str | None, label: str | None) -> bool:
    for obj in _visible_scene_objects(scene):
        if obj.get("id") == object_id:
            return any(it.get("label") == label for it in obj.get("interactions") or [])
    return False


def _effect_is_offensive(effect: dict) -> bool:
    """Dano, ou condição nociva (dano contínuo, controle ou redutor), no catálogo fechado."""
    kind = str(effect.get("kind") or "")
    if kind == "damage":
        return True
    if kind != "apply_condition":
        return False
    params = effect.get("params") or {}
    cond = cm.parse_condition(str(params.get("condition", "abissal")), source="objeto")
    return bool(cond.get("dot") or cond.get("control") or int(cond.get("delta", 0) or 0) < 0)


def _guard_object_step(decl: TurnDeclaration, scene: dict, active: list[dict], sides: dict) -> str:
    """SPEC-325 R14 (só com a flag `on`): objeto inválido vira ataque básico no 1º inimigo;
    efeito ofensivo com alvo do próprio lado é RECUSADO sem gastar a rodada. A recusa nunca
    descreve o efeito (regra de ouro: o efeito do objeto fica oculto até o uso)."""
    from services import combat_flags

    step = decl.acao
    if step is None or step.kind != "object" or combat_flags.mode("objects") != "on":
        return ""
    if not _valid_object_use(scene, step.object_id, step.interaction):
        _log_event("combat", "object_invalid_fallback", level="info")
        decl.acao = TurnStep(kind="attack", target_id=(active[0]["id"] if active else None))
        return ""
    obj = next((o for o in scene.get("objects") or [] if o.get("id") == step.object_id), {})
    it = next((i for i in obj.get("interactions") or [] if i.get("label") == step.interaction), {})
    effect = it.get("effect") or {}
    target = (effect.get("params") or {}).get("target")
    friendly = set(sides.get("hero", [])) | set(sides.get("ally", []))
    if _effect_is_offensive(effect) and target in friendly:
        _log_event("combat", "object_refused", level="info")
        return f"Não dá para usar '{step.interaction}' assim agora; escolha outra ação."
    _log_event("combat", "object_used", level="info")
    return ""


def _player_text_without_order(
    intent: str, enemies: list[dict], actors_by_id: dict, sides: dict
) -> tuple[str, bool]:
    """SPEC-325 C-P2-1 (só com `RPG_COMPANION_ORDERS=on`): a oração da ordem a aliado sai do
    texto antes do parser do jogador, para o CLASSIFY não a ler como ação do herói. Devolve
    `(texto restante, True se só havia a ordem)`."""
    from services import combat_flags
    from services.combat_intents import split_order

    if combat_flags.mode("companion_orders") != "on" or not intent:
        return intent, False
    names = {
        str(i): str((actors_by_id.get(i) or {}).get("name") or "")
        for i in sides.get("ally", [])
        if actors_by_id.get(i)
    }
    order, rest = split_order(intent, names, enemies)
    if order is None:
        return intent, False
    return rest, not rest.strip()


def _companion_orders(
    state: dict,
    intent: str,
    party: list[dict],
    enemies: list[dict],
    scene: dict,
    actors_by_id: dict,
    sides: dict,
) -> tuple[dict, list[str]]:
    """SPEC-325 R15: "<aliado>, <verbo> [alvo]" vira `TurnDeclaration` do aliado. As
    Restrições da alma (tabela fixa, D9) podem recusar: o aliado age pelo perfil e a recusa
    vai para o log/narração. Aliado sem comando (medo, confusão...) ignora a ordem.
    `shadow` só registra. Devolve `(declarações por ator, linhas de log)`."""
    from services import combat_flags, companion_orders, tactical_profile
    from services import companion_soul as cs_
    from services.combat_intents import companion_order

    mode = combat_flags.mode("companion_orders")
    if mode == "off" or not intent:
        return {}, []
    names = {
        str(i): str((actors_by_id.get(i) or {}).get("name") or "")
        for i in sides.get("ally", [])
        if actors_by_id.get(i)
    }
    order = companion_order(intent, names, enemies)
    if order is None:
        return {}, []
    if mode == "shadow":
        _log_event("combat", "companion_orders_shadow", verb=str(order["verb"]))
        return {}, []
    ally = actors_by_id[order["ally_id"]]
    name = str(ally.get("name") or order["ally_id"])
    if tactical_profile.loses_command(ally):
        _log_event("combat", "companion_order_ignored", level="info")
        return {}, [f"{name} está fora de si e ignora a ordem."]
    entry = next((m for m in party if str(m.get("id") or m.get("name")) == order["ally_id"]), None)
    soul = (
        (state.get("companion_souls") or {}).get(cs_.comp_id(entry)) if entry is not None else None
    )
    verdict = companion_orders.validate_order(ally, soul, order)
    if not verdict["accepted"]:
        _log_event("combat", "companion_order_refused", level="info", verb=str(order["verb"]))
        return {}, [f"{name} recusa a ordem: {verdict['reason']}."]
    decl = companion_orders.ally_declaration(order, ally, scene, actors_by_id, sides)
    if decl is None:
        return {}, [f"{name} não consegue cumprir a ordem agora."]
    _log_event("combat", "companion_order", level="info", verb=str(order["verb"]))
    return {order["ally_id"]: decl}, []


def _plan_reinforcements(
    scene: dict, enemies: list[dict], state: dict, player: dict, allies: list[dict], level: int
) -> None:
    """SPEC-325 R16: todo `lider_matilha` registra 1 gatilho ANTES de congelar a cena (Python,
    nunca LLM). `shadow` só registra; `off` não faz nada."""
    from services import combat_flags
    from services import reinforcements as rf

    mode = combat_flags.mode("reinforcements")
    if mode == "off" or not any(rf.is_leader(e) for e in enemies):
        return
    import encounter_budget as eb

    world = state.get("world") or {}
    budget = eb.encounter_budget(
        int(player.get("level", 1) or 1), int(world.get("danger_level", 1) or 1), len(allies)
    )
    triggers = rf.plan_triggers(enemies, budget, encounter_level=level)
    if mode == "shadow":
        _log_event("combat", "reinforcements_shadow", phase="plan", leaders=len(triggers))
        return
    for trigger in triggers:
        cs.add_reinforcement_trigger(scene, trigger)


def _advance_reinforcements(
    scene: dict,
    enemies: list[dict],
    actors_by_id: dict,
    sides: dict,
    combat_meta: dict,
    logs: list[str],
) -> None:
    """SPEC-325 R16: aviso na rodada em que o líder cai a 50 %, chegada de 1 reforço `distante`
    na seguinte (se o líder ainda age). Id único `<base>_r<N>`; entra no manifesto como `joined`."""
    from services import combat_flags
    from services import encounter_manifest as em
    from services import reinforcements as rf

    mode = combat_flags.mode("reinforcements")
    if mode == "off" or not scene:
        return
    round_ = int(combat_meta.get("round", 0) or 0)
    res = rf.advance(scene, enemies, actors_by_id, sides, combat_meta, round_, mode=mode)
    logs += res["logs"]
    for enemy in res["spawned"]:
        _mirror_vitals(enemy)
        _sync_enemy_knowledge([enemy])
        if em.is_valid_manifest(combat_meta.get("encounter")):
            zone = ((scene.get("positions") or {}).get(enemy["id"]) or {}).get("zone_id") or "z0"
            combat_meta["encounter"] = em.add_joined(
                combat_meta["encounter"], enemy, "reinforcement", round_, zone
            )


def _soul_traits(state: dict, member: dict) -> list[str]:
    from services import companion_soul as cs_

    _key, row = cs_.npc_row(state, member)
    return [
        str(t) for t in [*(row.get("hidden_traits") or []), *(row.get("revealed_traits") or [])]
    ]


def _chase_party_choices(
    state: dict,
    combat_meta: dict,
    party: list[dict],
    allies: list[dict],
    ally_ids: list,
    actors_by_id: dict,
    sides: dict,
    player: dict,
    intent: str,
    active: list[dict],
) -> dict:
    """SPEC-325 R12/R13: "deixo <nome>" (companheiro formal que tirou Complicação na rodada
    anterior) e aceite do sacrifício oferecido. O destino é sorteado por seed e SELADO em
    `party[i]["pending_fate"]` (nada aplicado agora; `companion_soul.apply_turn` consome
    depois de >= 1 dia). O narrador só recebe "ficou para trás". `shadow` só registra."""
    from services import chase as chase_mod
    from services import combat_flags, combat_intents

    res: dict = {"flee": False, "logs": [], "events": [], "sacrificed": None, "abandoned": []}
    mode = combat_flags.abandon_mode()
    prev = combat_meta.get("chase")
    if mode == "off" or not _chase_is_live(prev):
        return res
    if not _can_attempt_flee(player) or cm.has_control(player, "root"):
        return res
    formal = {
        chase_mod._ally_key(m): str(m.get("name") or "")
        for m in party
        if m.get("active") and not m.get("transient") and not m.get("pending_fate")
    }
    if mode == "shadow":
        if combat_intents.abandon_target(intent, formal):
            _log_event("combat", "chase_abandon_shadow")
        return res

    target = combat_intents.abandon_target(intent, chase_mod.abandon_candidates(prev, party))
    offer = str(prev.get("sacrifice_offer") or "")
    sacrificed = None
    if not target and offer and combat_intents.accepts_sacrifice(intent):
        entry = next((m for m in party if chase_mod._ally_key(m) == offer), None)
        if entry is not None and entry.get("active") and not entry.get("pending_fate"):
            from services import companion_soul as cs_

            probe = dict(entry)
            if "se_sacrifica_pelo_grupo" in _soul_traits(state, entry):
                probe["se_sacrifica_pelo_grupo"] = True
            soul = (state.get("companion_souls") or {}).get(cs_.comp_id(entry))
            if chase_mod.offer_sacrifice(probe, True, soul)["sacrificed"]:
                sacrificed = offer
    key = target or sacrificed
    if not key:
        return res
    entry = next(m for m in party if chase_mod._ally_key(m) == key)
    world = state.get("world") or {}
    day = int(((world.get("world_clock") or {}).get("day", 1)) or 1)
    location_id = str(world.get("current_location_id") or "")
    chase_mod.seal_fate(
        entry,
        instance_id=str(combat_meta.get("instance_id") or "game"),
        round_=int(combat_meta.get("round", 0) or 0) + 1,
        pursuers=len(active),
        day=day,
        location_id=location_id,
        outcomes=chase_mod.SACRIFICE_OUTCOMES if sacrificed else None,
    )
    # sai da cena: fora do pool de Sorte desta rodada e da própria rodada de combate
    allies[:] = [a for a in allies if chase_mod._ally_key(a) != key]
    ally_ids[:] = [i for i in ally_ids if str(i) != key]
    actors_by_id.pop(key, None)
    sides["ally"] = [i for i in sides.get("ally", []) if str(i) != key]
    player["_party_active"] = bool(allies)
    name = str(entry.get("name") or key)
    res["flee"] = True
    res["abandoned"].append(key)
    if sacrificed:
        res["sacrificed"] = sacrificed
        res["logs"].append(f"{name} fica para trás para segurar os perseguidores.")
        import hashlib

        # Decisão do coordenador (B-P2-6): evento + marco de crônica percebidos, sem o destino e
        # sem efeito extra de reputação (a SPEC-300 pode etiquetar pelo catálogo de tags).
        res["events"].append(
            {
                "event_id": "sacrifice-"
                + hashlib.sha1(entry["pending_fate"]["seed"].encode()).hexdigest()[:16],
                "turn": int(world.get("turn_count", 0) or 0),
                "type": "companion_sacrificed",
                "actor_id": "player",
                "target_id": key,
                "payload": {"name": name, "location_id": location_id, "day": day},
                "source": "combat",
            }
        )
        _log_event("combat", "chase_sacrifice", level="info")
    else:
        res["logs"].append(f"{name} ficou para trás.")
        combat_meta["chase"] = {**prev, "abandoned": [*(prev.get("abandoned") or []), key]}
        import hashlib

        res["events"].append(
            {
                # id estável por (instância, aliado, rodada), sem expor a seed do destino
                "event_id": "abandon-"
                + hashlib.sha1(entry["pending_fate"]["seed"].encode()).hexdigest()[:16],
                "turn": int(world.get("turn_count", 0) or 0),
                "type": "companion_abandoned",
                "actor_id": "player",
                "target_id": key,
                "payload": {"name": name, "location_id": location_id, "day": day},
                "source": "combat",
            }
        )
        _log_event("combat", "chase_abandon", level="info")
    return res


def _publish_sacrifice_offer(
    state: dict, party: list[dict], chase_state: dict, *, hero_fled: bool, logs: list[str]
) -> None:
    """SPEC-325 R13: com a trilha em `pressionado` e um companheiro elegível (D3), publica a
    oferta UMA vez por perseguição. Recusar/ignorar não tem penalidade (a oferta só expira)."""
    from services import chase as chase_mod
    from services import combat_flags

    mode = combat_flags.abandon_mode()
    if mode == "off":
        return
    if mode == "on" and "sacrifice_offer" in chase_state:
        chase_state["sacrifice_offer"] = None  # consumida: aceita, recusada ou ignorada
    if hero_fled or chase_state.get("trilha") != "pressionado":
        return
    if mode == "on" and chase_state.get("sacrifice_offered"):
        return
    key = chase_mod.eligible_for_sacrifice(
        party,
        state.get("companion_souls") or {},
        traits_of=lambda m: _soul_traits(state, m),
    )
    if not key:
        return
    if mode == "shadow":
        _log_event("combat", "chase_sacrifice_shadow")
        return
    chase_state["sacrifice_offer"] = key
    chase_state["sacrifice_offered"] = True
    name = next((str(m.get("name") or key) for m in party if chase_mod._ally_key(m) == key), key)
    logs.append(f"{name} se oferece para ficar e segurar os perseguidores.")
    _log_event("combat", "chase_sacrifice_offered", level="info")


def _last_human_text(messages: list) -> str:
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return str(m.content)
    return ""


# ==========================================================================
# Preparação da cena (ANTES do conflito — LLM identifica; guard obrigatório)
# ==========================================================================
def _bounded_enemy_groups(scan: EncounterScanner) -> list[tuple[str, int]]:
    """Normaliza/deduplica o scanner inteiro antes de chamar qualquer factory."""
    grouped: dict[str, dict] = {}
    for ident in (scan.detected_enemies or [])[:_MAX_SCANNER_TYPES]:
        raw_name = ident.get("name") if isinstance(ident, dict) else getattr(ident, "name", "")
        name = " ".join(str(raw_name or "Inimigo").split()) or "Inimigo"
        key = name.casefold()
        raw_count = ident.get("count", 1) if isinstance(ident, dict) else getattr(ident, "count", 1)
        try:
            count = max(1, int(raw_count or 1))
        except (TypeError, ValueError):
            count = 1
        entry = grouped.setdefault(key, {"name": name, "count": 0})
        entry["count"] = min(
            _MAX_SCANNER_PER_TYPE,
            int(entry["count"]) + min(count, _MAX_SCANNER_PER_TYPE),
        )

    remaining = _MAX_SCANNER_TOTAL
    bounded: list[tuple[str, int]] = []
    for entry in grouped.values():
        if remaining <= 0:
            break
        count = min(int(entry["count"]), remaining)
        if count:
            bounded.append((str(entry["name"]), count))
            remaining -= count
    return bounded


def _display_enemy_name(hint: str) -> str:
    """SPEC-346 R24: nucleo da dica com so a inicial maiuscula e no maximo 3 palavras."""
    from services import encounter_manifest as em

    words = (em.hint_core(hint) or "inimigo").split()[:3]
    return " ".join(words).capitalize()


def _name_without_generic_head(name: str, messages: list) -> str:
    """SPEC-363 R30: nenhum inimigo nasce "Criatura da Fogueira": vale a espécie citada na
    narração (bestiário); sem ela, o núcleo da dica (a cabeça sem o complemento)."""
    from services import encounter_manifest as em

    if not em.has_generic_head(name):
        return name
    bid = _bestiary_name_from_narration(messages)
    species = str((em._bestiary().get(bid) or {}).get("name") or "") if bid else ""
    return species or _display_enemy_name(name)


def _bestiary_name_from_narration(messages: list) -> str | None:
    """SPEC-346 R25: id do bestiario cujo nome (todos os tokens) aparece na ultima narracao da IA.

    Deterministico: o nome mais especifico (mais tokens) vence; empate -> menor id."""
    from services import encounter_manifest as em

    text = ""
    for m in reversed(messages or []):
        if getattr(m, "type", "") == "ai":
            text = str(getattr(m, "content", "") or "")
            break
    wanted = set(em.name_tokens(text))
    best: tuple[int, str] | None = None
    for bid, entry in em._bestiary().items():
        tokens = set(em.name_tokens(entry.get("name", "") or bid))
        if tokens and tokens <= wanted:
            cand = (-len(tokens), str(bid))
            if best is None or cand < best:
                best = cand
    return best[1] if best else None


def _grounded_template(
    name: str, context: str, encounter_level: int, state: dict | None = None
) -> dict:
    """Factory do bestiário com trava de identidade (SPEC-203 R3/H3): se o
    dedupe/gerador devolver OUTRA espécie, descarta e materializa o nome pedido."""
    from services import encounter_manifest as em

    pool_kwargs: dict = {}
    from services.shared_pool import enabled as _pool_enabled

    if _pool_enabled() and (state or {}).get("game_id"):
        # SPEC-297 R9: nome vindo da dica/scanner (texto do jogador) nunca promove (D1).
        pool_kwargs = {
            "game_id": str(state.get("game_id")),
            "location_id": str((state.get("world") or {}).get("current_location_id", "")),
            "name_origin": "player",
        }
    from services import creature_gen as _cg

    gen_on = _cg.mode() == "on"
    if gen_on:  # SPEC-361 R30: o gerador lê a trama e o teto do estado
        pool_kwargs["state"] = state
        pool_kwargs.pop("name_origin", None)  # R22: a origem do nome é decidida na geração
    template = generate_new_enemy(
        name, context=context, encounter_level=encounter_level, **pool_kwargs
    )
    if em.shares_identity(name, str(template.get("name") or "")) or em.shares_identity(
        name, str(template.get("id") or "")
    ):
        return template
    if gen_on:
        from services.prompt_guard import sanitize_entity_name

        # SPEC-361 R18: nova/variante/fallback do gerador marcam o nome pedido; o nome que o
        # LLM escreveu ("Coro de Quitina" para "lacaio mente-colmeia") não é troca de espécie.
        if (template.get("geracao") or {}).get("nome") == (
            sanitize_entity_name(name) or "Criatura"
        ):
            return template
    if _gs.is_contentless_name(name):
        _log_event("combat", "spawn_generic_name", level="warning")
    else:
        _log_event("combat", "spawn_identity_mismatch", level="warning")
    from agents.bestiary import _slug, materialize_enemy_concept

    # SPEC-346 R24: o nome materializado e o nucleo da dica (<= 3 palavras), nunca a frase.
    display = _display_enemy_name(name)
    return materialize_enemy_concept(
        {
            "name": display,
            "id": f"fallback_{_slug(display)}",
            "description": "Criatura materializada pela trava de identidade.",
            "categoria": template.get("categoria") or "padrao",
            "arquetipo": template.get("arquetipo") or "bruto",
        },
        encounter_level=encounter_level,
    )


def _instances(
    template: dict, count: int, next_by_template: dict[str, int], deck_seed: int | None = None
) -> list[dict]:
    out = []
    base_id = str(template.get("id") or "enemy")
    for _ in range(count):
        number = next_by_template.get(base_id, 0) + 1
        next_by_template[base_id] = number
        inst = dict(template)
        inst["id"] = f"{base_id}_{number}"
        inst.setdefault("archetype_id", base_id)  # SPEC-272: chave do bestiário
        if deck_seed is not None:
            inst["deck_seed"] = deck_seed  # SPEC-332 R3 (só com RPG_ENEMY_DECKS != off)
        inst["name"] = f"{template['name']} {number}" if count > 1 else template["name"]
        out.append(orch.ensure_combat_sheet(inst))
    return out


def _sync_enemy_knowledge(enemies: list[dict], *, load_persisted: bool = False) -> None:
    """SPEC-272 (liga SPEC-069 R8): Carta que o inimigo já usou fica revelada no
    painel de combate; no início do encontro, o que o bestiário já sabe do arquétipo
    começa revelado. Persistir/ler o overlay compartilhado só no perfil `legacy` —
    mesmo fail-closed de `dossiers._revealed_for` (escopo não é por dono/jogo)."""
    import os

    from services import bestiary_knowledge as bk

    shared = os.getenv("RPG_RUNTIME_PROFILE", "legacy").strip().lower() == "legacy"
    for enemy in enemies:
        if not isinstance(enemy, dict):
            continue
        try:
            # Revisão SPEC-272: reforço do orçamento (`fill_encounter`) e saves
            # antigos não passam por `_instances`; sem isso a chave do overlay
            # viraria o id da instância (`goblin_3`), poluindo o bestiário.
            if not enemy.get("archetype_id") and enemy.get("id"):
                from services.encounter_manifest import _base_id

                enemy["archetype_id"] = _base_id(enemy["id"])
            if load_persisted and shared:
                bk.apply_persisted_knowledge(enemy)
            for card_id in list(enemy.get("enemy_card_usage") or {}):
                if bk.is_card_revealed(enemy, card_id):
                    continue
                if shared:
                    bk.reveal_card(enemy, card_id)
                else:
                    enemy.setdefault("revealed_cards", []).append(card_id)
        except Exception:  # revelação é cosmética: nunca derruba o turno
            _log_event("combat", "enemy_knowledge_failed", level="warning")


def _spawn_v4_enemies(
    messages: list, target_hint: str, state: dict | None, meta: dict | None = None
) -> tuple:
    """Monta o elenco do encontro e converte CADA um em ficha v4.

    SPEC-203 R3 — ordem determinística: (a) `enemy_id` do encontro sistêmico;
    (b) NPC em cena; (c) alvo/ameaça já resolvida (nome exato do bestiário);
    (d) só então o `EncounterScanner` (LLM CLASSIFY), com saída validada contra a
    dica. `meta` (out-param) recebe source/target_ref/joined_ids/cut_ids."""
    from services import encounter_manifest as em

    meta = meta if meta is not None else {}
    _log_event("combat", "preparing_encounter", level="info")
    enemies: list[dict] = []
    flavor = "Algo hostil emerge."
    world = (state or {}).get("world") or {}
    encounter_level = prep.compute_encounter_level(
        location_danger=int(world.get("danger_level", 1) or 1),
        region_danger=int(world.get("danger_level", 1) or 1),
        event_type=str(world.get("encounter_type", "comum")),
        importance="comum",
    )
    mechanical_context = (
        f"{target_hint}; local={world.get('current_location', 'desconhecido')}; "
        f"nível_do_encontro={encounter_level}"
    )
    next_instance_by_template: dict[str, int] = {}
    import zlib as _zlib

    from services import enemy_decks as _edk_spawn

    _deck_seed = (
        _zlib.crc32(
            f"{(state or {}).get('game_id') or 'game'}|{world.get('turn_count', 0)}|{target_hint}".encode()
        )
        if _edk_spawn.mode() != "off"
        else None
    )
    protected: set = set()
    canonical = em.resolve_canonical_source(
        state or {}, target_hint, (state or {}).get("combat_encounter_hint")
    )
    if canonical and canonical["kind"] == "bestiary":
        from agents.bestiary import template_by_id

        for bid, count in canonical["groups"]:
            template = template_by_id(bid, encounter_level=encounter_level)
            if template:
                enemies += _instances(template, count, next_instance_by_template, _deck_seed)
                protected.add(bid)
        if enemies:
            meta.update(source=canonical["source"], target_ref=canonical["target_ref"])
            flavor = f"{enemies[0].get('name', 'Algo')} avança contra você."
    elif canonical and canonical["kind"] == "npc":
        npc = dict(((state or {}).get("npcs") or {}).get(canonical["npc_name"]) or {})
        sheet = prep.build_npc_combat_sheet({**npc, "name": canonical["npc_name"]})
        enemies = [orch.ensure_combat_sheet(sheet)]
        protected.add(str(sheet.get("id")))
        meta.update(source="npc_in_scene", target_ref=canonical["target_ref"])
        flavor = f"{canonical['npc_name']} se volta contra você."

    if not enemies:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        sys_prompt = (
            f"Analise a narrativa recente. O combate começou. Identifique QUAIS "
            f"inimigos estão presentes e QUANTOS. Use a dica: '{target_hint}'. "
            f"Ex.: 'Três orcs surgem' -> [{{name:'Orc', count:3}}]. " + PLAYER_INPUT_RULE
        )
        try:
            scan = llm.with_structured_output(EncounterScanner).invoke(
                [SystemMessage(content=sys_prompt)] + guard_messages(messages[-2:])
            )
            if isinstance(scan, EncounterScanner):
                flavor = scan.flavor_text or flavor
                # Primeiro fecha tipos/contagens; somente depois toca bestiário/factory.
                groups = _bounded_enemy_groups(scan)
                if not em.is_generic_hint(target_hint):
                    # R3(d): saída do scanner precisa casar com a dica (fauna da
                    # prosa não entra). Nada casou → a própria dica vira o grupo.
                    grounded = [(n, c) for n, c in groups if em.shares_identity(target_hint, n)]
                    if len(grounded) != len(groups):
                        _log_event("combat", "spawn_scanner_discarded", level="warning")
                    groups = grounded or [
                        (_display_enemy_name(target_hint), em.hint_count(target_hint))
                    ]
                meta["requested_total"] = sum(int(c) for _n, c in groups)  # SPEC-346 R29
                regional = False
                for name, count in groups:
                    name = _name_without_generic_head(name, messages)  # SPEC-363 R30
                    template = _gs.regional_template(  # SPEC-387 R10: nome vazio -> fauna da região
                        name, state, target_hint, encounter_level
                    )
                    regional = regional or template is not None
                    template = template or _grounded_template(
                        name, mechanical_context, encounter_level, state
                    )
                    from services.creature_variants import contagem_min as _cmin

                    if _cmin(template) > count:  # SPEC-361 R7: piso do grupo da variante
                        count = _cmin(template)
                        protected.add(str(template.get("id")))
                    enemies += _instances(template, count, next_instance_by_template, _deck_seed)
                if enemies:
                    meta.update(source="regional_generic" if regional else "scanner")
                    meta["target_ref"] = str(target_hint or "")
                    if regional:
                        flavor = f"{enemies[0].get('name', 'Algo')} avança contra você."
        except Exception as e:
            _log_event("combat", "spawn_failed", level="warning", error=type(e).__name__)

    if not enemies:
        # SPEC-346 R25: scanner indisponivel -> especie citada na ultima narracao.
        bid = _bestiary_name_from_narration(messages)
        if bid:
            from agents.bestiary import template_by_id

            template = template_by_id(bid, encounter_level=encounter_level)
            if template:
                count = 1 if em.is_generic_hint(target_hint) else em.hint_count(target_hint)
                enemies = _instances(template, count, next_instance_by_template, _deck_seed)
                protected.add(bid)
                meta.update(source="narration_bestiary", target_ref=bid)
                _log_event("combat", "spawn_from_narration", level="info")

    if not enemies:
        enemies = [
            orch.ensure_combat_sheet(
                {
                    "id": "sombrio_1",
                    "name": "Inimigo Sombrio",
                    "type": "padrao",
                    "virtudes": {"forca": 2, "agilidade": 2, "corpo": 2, "mente": 1, "carisma": 1},
                }
            )
        ]
        meta.update(source="fallback", target_ref=str(target_hint or ""))
        _log_event("combat", "spawn_fallback", level="warning")

    # Orçamento determinístico do encontro (mesma lógica da Fase 4.6, escala nova).
    if state is not None:
        enemies, flavor = _apply_encounter_budget(
            enemies, state, flavor, protected=protected or None, report=meta
        )
    return enemies, flavor


def _apply_encounter_budget(
    enemies: list[dict],
    state: dict,
    flavor: str,
    *,
    protected: set | None = None,
    report: dict | None = None,
) -> tuple:
    """SPEC-203 R4: clamp/fill seguem a regra numérica, mas o alvo canônico não
    perde vaga por variedade e todo corte/reforço é reportado (ids) para virar
    evento de composição no manifesto."""
    report = report if report is not None else {}
    try:
        import encounter_budget as eb
        import party as party_mod
        from gamedata import get_location
        from services import encounter_manifest as em
        from services import fauna_tramas

        if protected is None:
            bid = em.resolve_bestiary_name(str(state.get("combat_target") or ""))
            protected = {bid} if bid else set()
        world = state.get("world") or {}
        danger = int(world.pop("encounter_eff_danger", None) or world.get("danger_level", 1) or 1)
        level = int((state.get("player") or {}).get("level", 1) or 1)
        enemy_refs = [
            str(value)
            for enemy in enemies
            for value in (enemy.get("id"), enemy.get("name"))
            if value
        ]
        n_allies = len(party_mod.active_allies(state)) + len(
            party_mod.scene_allies(state, excluded=enemy_refs)
        )
        budget = eb.encounter_budget(level, danger, n_allies)
        before_ids = [str(e.get("id")) for e in enemies]
        enemies, cut = eb.clamp_encounter(enemies, budget, player_level=level, protected=protected)
        kept_ids = {str(e.get("id")) for e in enemies}
        loc = get_location(world.get("current_location_id", "")) or {}
        enemies, fill = eb.fill_encounter(
            enemies,
            budget,
            loc,
            danger,
            turn=int(world.get("turn_count", 0) or 0),
            make_instance=lambda t, i: orch.ensure_combat_sheet(
                {**t, "id": f"{t.get('id', 'enemy')}_{i}"}
            ),
            trama_stages=fauna_tramas.stages_for(state, world),  # SPEC-372
        )
        report["cut_ids"] = [i for i in before_ids if i not in kept_ids]
        report["joined_ids"] = [
            str(e.get("id")) for e in enemies if str(e.get("id")) not in kept_ids
        ]
        extra = " ".join(cut + fill)
        if extra:
            flavor = f"{flavor} {extra}".strip()
    except Exception as e:
        _log_event("combat", "budget_failed", level="warning", error=type(e).__name__)
    return enemies, flavor


def _early_game_reaction_initiator(
    state: dict, player: dict, initiator: str | None, *, combat_round: int | None = None
) -> str | None:
    """Garante uma primeira decisão a herói novo e saudável fora de apex.

    [BALANCEAR] A baseline real encontrou mortes de nível 1–2 em emboscadas antes
    de qualquer janela de fuga/cura. Não reduz dano nem budget: quando o herói
    entra com Vitalidade cheia, somente a iniciativa do primeiro round é sua.
    Depois de agir (ou em apex), a iniciativa e a letalidade normais prevalecem.
    """
    level = int(player.get("level", 1) or 1)
    vitality = int(player.get("vitalidade", player.get("hp", 0)) or 0)
    maximum = int(player.get("max_vitalidade", player.get("max_hp", 0)) or 0)
    # SPEC-232 R9: `combat_round` é a rodada CORRENTE (pós-incremento, 1 = primeira).
    # Antes lia o estado pré-incremento com `<= 1` e valia por duas rodadas.
    if combat_round is None:
        combat_round = int((state.get("combat") or {}).get("round", 0) or 0)
    world = state.get("world") or {}
    loc = gamedata.get_location(world.get("current_location_id", "")) or {}
    tags = {str(tag).casefold() for tag in (loc.get("tags") or [])}
    if (
        level <= 2
        and maximum > 0
        and vitality >= maximum
        and combat_round == 1
        and "apex" not in tags
    ):
        return "heroes"
    return initiator


_PREPARED_CATEGORIES = {"elite", "chefe", "nomeado", "boss"}


def _wants_prepared_scene(player: dict, enemies: list[dict]) -> bool:
    """D-A: Carga ≥ leve OU inimigo de categoria ≥ Elite."""
    try:
        if cm.abyss_tier(player) != "nenhum":
            return True
    except Exception:
        pass
    return any(
        str(e.get("categoria") or e.get("type") or "").strip().lower() in _PREPARED_CATEGORIES
        for e in enemies or []
    )


def _prepare_scene(state: dict, enemies: list[dict], player: dict, allies: list[dict]) -> dict:
    """Monta a cena JOGÁVEL em Python com zonas mínimas e seguras. O Nível do
    Encontro é perigo ABSOLUTO (11 R6), nunca depende da party."""
    world = state.get("world") or {}
    loc = world.get("current_location", "Campo")
    encounter_level = prep.compute_encounter_level(
        location_danger=int(world.get("danger_level", 1) or 1),
        region_danger=int(world.get("danger_level", 1) or 1),
        event_type=str(world.get("encounter_type", "comum")),
        importance="comum",
    )
    ctx = {
        "location": loc,
        "enemies": enemies,
        "npcs": [],
        "allies": [str(a.get("id") or a.get("name")) for a in allies],  # SPEC-331 (proteger)
        "encounter_level": encounter_level,
        "narrative": "",
    }
    # SPEC-232 R10 (D-A, default do dono): a preparação por LLM (objetos, eventos
    # do Abismo, reforços, condições de fim) só roda quando importa — Carga do
    # Abismo ≥ patamar leve ou algum inimigo Elite/Chefe/Nomeado. Custo: 1 invoke
    # FAST nesses encontros; nos demais, geometria mínima em Python (sem invoke).
    if _wants_prepared_scene(player, enemies):
        try:
            # SPEC-317 R8: o contexto so serve ao prompt de preparacao (e so o estado do mundo).
            ctx["narrative"] = build_context_pack(
                state,
                query=str(loc),
                purpose="combat_narration",
                token_budget=600,
                include_lore=False,
            ).world_state_block
            saber_linha = _fauna_saber.prep_line(state, enemies)  # SPEC-371 R11 (flag on)
            if saber_linha:
                ctx["saber_linha"] = saber_linha
            llm = get_llm(temperature=0.4, tier=ModelTier.FAST)
            scene = prep.prepare_encounter(ctx, llm)  # guard + fallback internos
        except Exception as e:
            _log_event("combat", "prep_failed", level="warning", error=type(e).__name__)
            scene = prep.fallback_safe_scene(ctx)
    else:
        scene = prep.fallback_safe_scene(ctx)
    if not scene.get("zones"):
        scene["zones"] = [{"id": "z0", "name": loc, "connections": []}]
    scene["positions"] = {}
    zone_id = scene["zones"][0]["id"]
    cs.place(scene, _PLAYER_ID, zone_id=zone_id, distance_state="proximo")
    for a in allies:
        cs.place(scene, a.get("id") or a.get("name"), zone_id=zone_id, distance_state="proximo")
    for e in enemies:
        cs.place(scene, e["id"], zone_id=zone_id, distance_state="proximo")
    _plan_reinforcements(scene, enemies, state, player, allies, encounter_level)  # SPEC-325 R16
    cs.freeze(scene)
    scene["encounter_level"] = encounter_level
    return scene


# ==========================================================================
# Identificação da ação do jogador (fala livre → TurnDeclaration, CLASSIFY)
# ==========================================================================
def _prepared_cards_catalog(player: dict, piles: dict | None = None) -> str:
    from services import cards

    linhas = []
    if piles is not None:  # SPEC-328 R15: o catálogo do prompt é a MÃO, com o Fôlego
        seen: set[str] = set()
        for cid in piles.get("mao") or []:
            c = cards.get_card(cid)
            if not c or cid in seen:
                continue
            seen.add(cid)
            linhas.append(
                f"- {cid}: {c.get('name', cid)} | tipo {c.get('tipo')} | "
                f"Fôlego {cards.custo_folego(c)} | Entropia {c.get('custo_entropia', 0)} | "
                f"{c.get('descricao', '')[:50]}"
            )
        header = f"Fôlego disponível: {int(piles.get('folego', 0) or 0)}.\n    "
        return header + ("\n".join(linhas) or "- (mão vazia; use ataque básico)")
    for cid in player.get("prepared_cards") or []:
        c = cards.get_card(cid)
        if not c:
            continue
        linhas.append(
            f"- {cid}: {c.get('name', cid)} | tipo {c.get('tipo')} | "
            f"custo {c.get('custo_entropia', 0)} Entropia | {c.get('descricao', '')[:50]}"
        )
    return "\n".join(linhas) or "- (nenhuma carta preparada; use ataque básico)"


def _deck_mode_now() -> str:
    from services import card_piles

    return card_piles.mode()


def _normalize_extra_play(step: TurnStep, active: list[dict], ally_ids: list[str]) -> None:
    """SPEC-328 R13: alvo das jogadas 2..n com as mesmas regras da 1ª."""
    from services import cards

    active_ids = [e["id"] for e in active]
    if step.kind == "attack" and step.target_id not in set(active_ids):
        step.target_id = active_ids[0] if active_ids else None
    elif step.kind == "card":
        step.target_id = _card_target_for(
            cards.get_card(step.card_id or "") or {},
            step.target_id,
            active_ids=active_ids,
            friendly_ids=[_PLAYER_ID] + [aid for aid in ally_ids if aid],
        )


def _usable_items_catalog(player: dict) -> str:
    from gamedata import ARTIFACTS_DB
    from inventory import item_display

    lines = []
    for entry in player.get("inventory") or []:
        if not isinstance(entry, dict):
            continue
        item = ARTIFACTS_DB.get(entry.get("id", "")) or {}
        if str(item.get("type", "")).lower() not in ("consumable", "potion"):
            continue
        lines.append(f"- {entry.get('id')}: {item_display(entry)} (x{entry.get('qty', 1)})")
    return "\n".join(lines) or "- (nenhum consumível)"


def _default_card_target(card: dict, enemy_id: str | None) -> str:
    """Cartas benéficas sem alvo explícito afetam o próprio jogador. Evita que
    chips como Cura/Proteção herdem mecanicamente o primeiro inimigo."""
    kind = str((card.get("efeito") or {}).get("kind") or "")
    # SPEC-232 R9: fonte única = efeitos de suporte do motor (inclui a Purga
    # `reduzir_carga_aliado`, antes ausente e gasta num inimigo).
    return _PLAYER_ID if kind in _SUPPORT_EFFECTS else (enemy_id or _PLAYER_ID)


def _card_target_for(
    card: dict, declared: str | None, *, active_ids: list[str], friendly_ids: list[str]
) -> str:
    """SPEC-232 R5: alvo de Carta validado na borda do nó. Ofensiva só mira um
    inimigo ATIVO (nunca o jogador nem um morto); suporte só mira o próprio lado.
    Inválido → alvo default da Carta."""
    kind = str((card.get("efeito") or {}).get("kind") or "")
    allowed = friendly_ids if kind in _SUPPORT_EFFECTS else active_ids
    if declared in set(allowed):
        return str(declared)
    return _default_card_target(card, active_ids[0] if active_ids else None)


def _parse_turn_declaration(
    player: dict, enemies: list[dict], intent: str, scene: dict, piles: dict | None = None
) -> TurnDeclaration:
    """A IA IDENTIFICA a fala do jogador → `TurnDeclaration` estruturada (só
    identifica, não resolve). Guard de fallback: ataque básico no 1º inimigo.
    O harness passa a declaração pronta e não chega aqui."""
    from pydantic import BaseModel, Field

    alvos = ", ".join(f"{e['id']}={e.get('name', e['id'])}" for e in enemies) or "—"
    fallback = TurnDeclaration(
        actor_id=_PLAYER_ID,
        acao=TurnStep(kind="attack", target_id=(enemies[0]["id"] if enemies else None)),
    )
    if not intent:
        return fallback

    # Chips do HUD carregam nomes canônicos: resolvemos localmente, sem gastar
    # CLASSIFY e sem permitir id alucinado.
    from services import cards

    folded_intent = intent.casefold()
    target_id = enemies[0]["id"] if enemies else None
    if piles is not None:  # SPEC-328 R15: várias cartas pelo nome, na ordem em que aparecem
        cands = []
        for cid in dict.fromkeys(list(piles.get("mao") or []) + list(player.get("deck") or [])):
            card = cards.get_card(cid)
            name = str((card or {}).get("name", "")).casefold()
            pos = folded_intent.find(name) if name else -1
            if pos >= 0:
                cands.append((pos, pos + len(name), cid, card))
        named = []  # P2-1: o nome mais longo vence; nomes contidos em outro não duplicam
        taken: list[tuple[int, int]] = []
        for pos, end, cid, card in sorted(cands, key=lambda c: (-(c[1] - c[0]), c[0])):
            if any(pos < e and end > s for s, e in taken):
                continue
            taken.append((pos, end))
            named.append((pos, cid, card))
        if named:
            steps = [
                TurnStep(kind="card", card_id=cid, target_id=_default_card_target(card, target_id))
                for _pos, cid, card in sorted(named, key=lambda n: n[0])
            ]
            return TurnDeclaration(actor_id=_PLAYER_ID, acao=steps[0], jogadas=steps)
    for cid in player.get("prepared_cards") or []:
        card = cards.get_card(cid)
        if card and str(card.get("name", "")).casefold() in folded_intent:
            return TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(
                    kind="card", card_id=cid, target_id=_default_card_target(card, target_id)
                ),
            )
    from gamedata import ARTIFACTS_DB
    from inventory import item_display

    for entry in player.get("inventory") or []:
        if not isinstance(entry, dict):
            continue
        item = ARTIFACTS_DB.get(entry.get("id", "")) or {}
        name = item_display(entry)
        if (
            str(item.get("type", "")).lower() in ("consumable", "potion")
            and name.casefold() in folded_intent
        ):
            return TurnDeclaration(
                actor_id=_PLAYER_ID,
                acao=TurnStep(kind="item", item_id=entry.get("id"), target_id=target_id),
            )

    object_decl = _object_declaration(scene, intent)
    if object_decl is not None:  # SPEC-325 R14: chip/nome canônico, sem CLASSIFY
        return object_decl

    class PlayerMove(BaseModel):
        kind: str = Field(description="attack | card | item | maneuver | move | pass")
        card_id: str = Field(default="", description="id EXATO da Carta preparada, se kind=card.")
        item_id: str = Field(default="", description="id EXATO do consumível, se kind=item.")
        target_id: str = Field(default="", description="id do inimigo alvo (da lista).")
        maneuver: str = Field(
            default="",
            description="engajar|desengajar|guardar|esconder|procurar, se kind=maneuver.",
        )
        direction: str = Field(default="", description="aproximar|afastar, se kind=move.")

    # SPEC-325 R14 (só `on` e com objeto visível): o schema/prompt ganham `object` — id e
    # rótulo EXATOS vindos de `visible_objects` (sem `effect`); fora disso, tudo igual a `off`.
    from services import combat_flags as _cf

    visible_objs = _visible_scene_objects(scene) if _cf.mode("objects") == "on" else []
    move_model = PlayerMove
    if piles is not None:  # SPEC-328 P1-1: o campo só existe no schema com baralho ativo

        class PlayerMoveDeck(PlayerMove):
            extra_card_ids: list[str] = Field(
                default_factory=list,
                description="ids EXATOS de Cartas da mão jogadas DEPOIS da primeira, na ordem.",
            )

        move_model = PlayerMoveDeck
    object_rule = ""
    if visible_objs:

        class PlayerMoveObject(move_model):
            object_id: str = Field(default="", description="id EXATO do objeto, se kind=object.")
            interaction: str = Field(
                default="", description="rótulo EXATO da interação, se kind=object."
            )

        move_model = PlayerMoveObject
        listing = "; ".join(
            f"{o['id']}={o.get('name')} ["
            + ", ".join(str(i.get("label")) for i in o.get("interactions") or [])
            + "]"
            for o in visible_objs
        )
        object_rule = (
            f"\n    Objetos da cena (use id e rótulo EXATOS): {listing}"
            "\n    - Usar um objeto da cena -> kind=object + object_id + interaction."
        )

    sys = SystemMessage(
        content=f"""
    Você IDENTIFICA a ação de combate do jogador (não resolva mecânica).
    Traduza a fala numa ação estruturada do conflito de Valoria.

    Cartas preparadas (use o id EXATO em card_id):
    {_prepared_cards_catalog(player, piles)}

    Consumíveis presentes (use o id EXATO em item_id):
    {_usable_items_catalog(player)}

    Inimigos presentes (use o id em target_id): {alvos}

    Regras:
    - Ataque com arma comum -> kind=attack, target_id do alvo.
    - Usar uma Carta -> kind=card, card_id da Carta, target_id se ofensiva.
    - Beber/usar consumível -> kind=item, item_id do inventário, target_id se hostil.
    - Manobra tática (guardar/esconder/engajar/desengajar/procurar) -> kind=maneuver.
    - Mover (aproximar/afastar) -> kind=move + direction.
    - Sem alvo claro -> kind=attack no primeiro inimigo.{object_rule}
    {PLAYER_INPUT_RULE}
    """
    )
    try:
        llm = get_llm(temperature=0.0, tier=ModelTier.CLASSIFY)
        res = llm.with_structured_output(move_model).invoke(
            [sys, HumanMessage(content=wrap_player_input(intent))]
        )
        if isinstance(res, PlayerMove):
            kind = (res.kind or "attack").lower()
            tid = res.target_id or (enemies[0]["id"] if enemies else None)
            if kind == "object":  # só chega aqui com `on`; id/rótulo inválido -> ataque básico
                oid = str(getattr(res, "object_id", "") or "")
                label = str(getattr(res, "interaction", "") or "")
                if _valid_object_use(scene, oid, label):
                    return TurnDeclaration(
                        actor_id=_PLAYER_ID,
                        acao=TurnStep(kind="object", object_id=oid, interaction=label),
                    )
                _log_event("combat", "object_invalid_fallback", level="info")
            if kind == "card" and (
                res.card_id in (player.get("prepared_cards") or [])
                or _scene_cards.in_hand(piles, res.card_id)  # SPEC-331 P1-1
            ):
                card = cards.get_card(res.card_id) or {}
                first = TurnStep(
                    kind="card", card_id=res.card_id, target_id=_default_card_target(card, tid)
                )
                if piles is not None:  # SPEC-328 R15: lista validada contra o Acervo/baralho
                    extras = [
                        TurnStep(
                            kind="card",
                            card_id=x,
                            target_id=_default_card_target(cards.get_card(x) or {}, tid),
                        )
                        for x in (getattr(res, "extra_card_ids", None) or [])
                        if x in (player.get("prepared_cards") or [])
                        or _scene_cards.in_hand(piles, x)
                    ]
                    if extras:
                        return TurnDeclaration(
                            actor_id=_PLAYER_ID, acao=first, jogadas=[first, *extras]
                        )
                return TurnDeclaration(actor_id=_PLAYER_ID, acao=first)
            if kind == "item" and res.item_id:
                return TurnDeclaration(
                    actor_id=_PLAYER_ID,
                    acao=TurnStep(kind="item", item_id=res.item_id, target_id=tid),
                )
            if kind == "maneuver" and res.maneuver:
                return TurnDeclaration(
                    actor_id=_PLAYER_ID,
                    acao=TurnStep(kind="maneuver", maneuver=res.maneuver, target_id=tid),
                )
            if kind == "move" and res.direction:
                return TurnDeclaration(
                    actor_id=_PLAYER_ID, acao=TurnStep(kind="move", direction=res.direction)
                )
            if kind == "pass":
                return TurnDeclaration(actor_id=_PLAYER_ID, acao=TurnStep(kind="pass"))
            return TurnDeclaration(actor_id=_PLAYER_ID, acao=TurnStep(kind="attack", target_id=tid))
    except Exception as e:
        _log_event("combat", "parse_failed", level="warning", error=type(e).__name__)
    return fallback


# ==========================================================================
# Alias Vitalidade→hp (compatibilidade pública)
# ==========================================================================
def _mirror_vitals(actor: dict) -> None:
    """Sincroniza apenas os aliases de borda e o status textual."""
    import gamedata

    gamedata.sync_legacy_hp_aliases(actor)
    if actor.get("dead"):
        actor["status"] = "morto"
    elif actor.get("fled"):
        actor["status"] = "fugiu"
    elif actor.get("surrendered"):
        actor["status"] = "rendido"
    elif actor.get("incapacitated") and actor.get("nonlethal_by"):
        actor["status"] = "incapacitado"  # SPEC-325 R9: golpe não-letal, não é derrota
    else:
        actor.setdefault("status", "ativo")


def _canonical_player_action(
    declaration: TurnDeclaration | None,
    out: dict,
    *,
    attempted: bool = True,
    flee_requested: bool = False,
    hero_fled: bool = False,
    flee_destination_id: str | None = None,
    chase_state: dict | None = None,
) -> dict:
    """Contrato mecânico consumido pelo harness; não depende da prosa do LLM."""
    step = declaration.acao if declaration is not None else None
    if flee_requested:
        kind = "flee"
        if hero_fled:
            result = "fled"
        elif (chase_state or {}).get("eligible") is False:
            result = "flee_blocked"
        elif chase_state and not chase_state.get("alcancado"):
            result = "flee_progress"
        else:
            result = "flee_failed"
    else:
        raw_kind = str((step.kind if step else "pass") or "pass").lower()
        if raw_kind == "object":  # SPEC-325 C-P2-4: com a flag `off` segue o contrato anterior
            from services import combat_flags

            if combat_flags.mode("objects") == "off":
                raw_kind = "pass"
        kind = (
            raw_kind
            if raw_kind
            in {
                "attack",
                "card",
                "item",
                "maneuver",
                "move",
                "pass",
                "flee",
                "object",
            }
            else "pass"
        )
        player_attack = next(
            (
                attack
                for attack in (out.get("attacks") or [])
                if attack.get("actor_id") == _PLAYER_ID
            ),
            None,
        )
        if kind in ("attack", "card") and player_attack is not None:
            result = "hit" if player_attack.get("acerto") else "miss"
        elif kind == "pass":
            result = "pass"
        elif not attempted:
            result = "interrupted"
        else:
            result = "ok"
    params = (step.params if step is not None else {}) or {}
    player_attack = next(
        (attack for attack in (out.get("attacks") or []) if attack.get("actor_id") == _PLAYER_ID),
        {},
    )
    action = {
        "kind": kind,
        "card_id": step.card_id if step is not None else None,
        "item_id": step.item_id if step is not None else None,
        "target_id": step.target_id if step is not None else None,
        "maneuver": step.maneuver if step is not None else None,
        "direction": step.direction if step is not None else None,
        "region": player_attack.get("regiao") or params.get("regiao"),
        "result": result,
        "attempted": bool(attempted),
        "flee_destination_id": flee_destination_id,
        "chase_track": (chase_state or {}).get("trilha") if flee_requested else None,
    }
    if declaration is not None and len(declaration.jogadas) > 1:  # SPEC-328 P2-5 (aditivo)
        action["plays"] = [
            {"kind": s.kind, "card_id": s.card_id, "target_id": s.target_id}
            for s in declaration.jogadas
        ]
    if flee_requested and (chase_state or {}).get("approach"):
        action["chase_approach"] = chase_state["approach"]  # SPEC-325 R10 (só com a flag `on`)
    return action


MAX_CONSECUTIVE_FLEE_ATTEMPTS = 6


def _flee_verdict(chase_state: dict | None, previous: str, hero_fled: bool) -> str:
    """SPEC-363 R22: escapou | avancou | perdeu_terreno | alcancado | falhou."""
    state = chase_state or {}
    if hero_fled or state.get("escapou"):
        return "escapou"
    if state.get("alcancado"):
        return "alcancado"
    if (state.get("_last") or {}).get("sucesso"):
        return "avancou"
    from services import chase as _chase

    track = _chase.TRACK
    now = str(state.get("trilha") or previous)
    if previous in track and now in track and track.index(now) < track.index(previous):
        return "perdeu_terreno"
    return "perdeu_terreno" if (state.get("_last") or {}).get("total") is not None else "falhou"


def _flee_roll_payload(chase_state: dict | None, prev_track: str, hero_fled: bool) -> dict | None:
    """SPEC-353 R39b / SPEC-364 R1: payload `out["fuga"]`. O "de" vem de dentro da
    perseguição (`_last.de`, depois de retomar/reiniciar); `prev_track` só p/ save antigo."""
    last = (chase_state or {}).get("_last") or {}
    de = str(last.get("de") or prev_track)
    if last.get("sacrificio"):  # sacrifício aceito: escapa sem teste
        return {
            "total": None,
            "dificuldade": None,
            "sucesso": True,
            "veredito": "escapou",
            "de": de,
            "para": "escapou",
            "sacrificio": True,
        }
    if last.get("total") is None:
        return None
    return {
        "total": last.get("total"),
        "dificuldade": last.get("difficulty"),
        "sucesso": bool(last.get("sucesso")),
        # SPEC-363 R22: o veredito vem da perseguição, não do "sucesso" do dado
        "veredito": _flee_verdict(chase_state, de, hero_fled),
        "de": de,
        "para": (chase_state or {}).get("trilha"),
    }


def _enforce_flee_attempt_limit(chase_state: dict, *, attempts: int) -> tuple[bool, dict]:
    """Fecha perseguições que oscilaram demais sem retirar letalidade do combate.

    O limite é local à instância e só é aplicado pelo chamador quando existe
    um destino de fuga válido. Até lá, cada rodada continua usando os testes
    normais da trilha.
    """
    chase = dict(chase_state or {})
    if chase.get("eligible") is False or chase.get("blocked_reason"):
        return False, chase
    if int(attempts or 0) < MAX_CONSECUTIVE_FLEE_ATTEMPTS:
        return bool(chase.get("escapou")), chase
    chase.update({"trilha": "escapou", "escapou": True, "alcancado": False})
    return True, chase


def _is_valid_flee_destination(state: dict, destination_id: str | None) -> bool:
    if not destination_id:
        return False
    current_id = str((state.get("world") or {}).get("current_location_id") or "")
    try:
        return any(
            str(location.get("id") or "") == str(destination_id)
            for location in gamedata.get_connections(current_id)
            if isinstance(location, dict)
        )
    except Exception:
        return False


# ==========================================================================
# Narração (depois da resolução — LLM FAST, guard)
# ==========================================================================
def _killer_identity(
    active: list, out: dict | None = None, pool: list | None = None
) -> tuple[str, str]:
    """SPEC-288: (espécie canônica, id do bestiário) do inimigo que deu o golpe final.

    SPEC-363 R14: com `out["final_blows"]`, vale o autor do golpe que derrubou o herói."""
    from services import encounter_manifest as em

    enemy = None
    for blow in reversed((out or {}).get("final_blows") or []):
        if str(blow.get("target_id")) != "player":
            continue
        kind = blow.get("kind")
        if kind == "dano_continuo":
            from services import card_effects as _fx

            raw = str(blow.get("condition") or "")
            return (_fx.condition_label(raw) if raw else "dano contínuo"), ""
        if kind == "auto_dano":
            return "o preço da própria Carta", ""
        by = str(blow.get("by_actor_id") or "")
        enemy = next(
            (e for e in [*(active or []), *(pool or [])] if e and str(e.get("id")) == by), None
        )
        break
    if enemy is None:
        enemy = next((e for e in active or [] if e), None)
    if not enemy:
        return "", ""
    base = em._base_id(enemy.get("id", ""))
    known = base in (gamedata.BESTIARY or {})
    return em.species_label_for(enemy), (base if known else str(enemy.get("bestiary_id") or ""))


def _normalize_status_logs(lines: list[str], player: dict) -> list[str]:
    """SPEC-363 R26: linhas de condição na voz do jogador ("Você ganha a condição Cego."), uma vez."""
    from services import round_log

    hero = str((player or {}).get("name") or "")
    out: list[str] = []
    for line in lines or []:
        text = round_log._voce(str(line), hero)
        if text and text not in out:
            out.append(text)
    return out


def _diante_de(killer: str) -> str:
    return "diante d" + killer if killer.startswith("o ") else f"diante de {killer}"


def _narrate_fall(player: dict, logs: list[str], killer: str = "") -> str:
    """SPEC-346 R16: texto determinístico da queda (sem bullets de log cru) + a Roda do Abismo."""
    from services import round_log

    quem = f" {_diante_de(killer)}" if killer else ""
    return f"Você tomba{quem}. {round_log.WHEEL_TEXT}"


def _faction_withhold_clause(manifest, factions, intel) -> str:
    """SPEC-292 (P2-3): fações dos combatentes que o jogador AINDA não conhece ficam
    sem nome na narração (descreve-se por aparência/armas). Vazio se nada a esconder."""
    from world_utils import unknown_faction_names

    ids = [p.get("faction_id") for p in (manifest or {}).get("participants") or []]
    names = unknown_faction_names(ids, factions, intel)
    if not names:
        return ""
    clause = (
        "O herói NÃO conhece as facções: "
        + "; ".join(names)
        + ". NÃO cite esses nomes nem o nome de organização dos inimigos — descreva-os "
        "por aparência, armas e comportamento."
    )
    # Revisão SPEC-292: o NOME da criatura carrega o radical da fação ("Iniciado da
    # Chama Azul"); sem esta exceção ao elenco o fallback (Groq) repetiu o nome inteiro.
    hidden = _concealed_species(manifest, factions, intel)
    if hidden:
        clause += (
            " Prevalece sobre o elenco canônico: chame "
            + "; ".join(f"'{full}' apenas de '{short}'" for full, short in hidden)
            + " — NUNCA pelo nome completo."
        )
    return clause


def _concealed_species(manifest, factions, intel) -> list[tuple[str, str]]:
    """(nome canônico, rótulo curto) das espécies cujo nome expõe fação desconhecida."""
    # SPEC-293 R7: mesmo rótulo de exibição do HUD/Bestiário (services.faction_display).
    from services.faction_display import display_label

    out: list[tuple[str, str]] = []
    for p in (manifest or {}).get("participants") or []:
        full = str(p.get("species_label") or "")
        short = display_label(full, str(p.get("faction_id") or ""), factions, intel)
        if full and short != full and full not in dict(out):
            out.append((full, short))
    return out


def _flee_alert_world(world: dict, enemies: list[dict], outcome: str) -> dict | None:
    """SPEC-296 R2: devolve o world com 1 alerta de fuga (1º inimigo `fled`), ou None.
    Fuga do herói, morte, derrota e rendição não registram (review P2-3: reforço
    não chega em cima do herói caído)."""
    if outcome in ("fled", "death", "defeat", "surrendered_enemy"):
        return None
    fugitive = next((e for e in enemies if e.get("fled") or e.get("status") == "fugiu"), None)
    if fugitive is None:
        return None
    from world_utils import register_flee_alert

    species, bestiary_id = _killer_identity([fugitive])
    hint = species or str(fugitive.get("name") or "o fugitivo")
    return register_flee_alert(
        world,
        hint,
        faction_id=(fugitive.get("faction_id") or fugitive.get("faction") or None),
        turn=int((world or {}).get("turn_count", 0) or 0),
        enemy_id=bestiary_id,
    )


def _perceived_for_combat(state: dict) -> str:
    """SPEC-309 R19: `<MUNDO_PERCEBIDO>` na narracao do combate (so ambiente; nunca quebra)."""
    from services.perceived_world import perceived_world_block

    block = perceived_world_block(state, audience="combat")
    return f"\n{block}" if block else ""


def _ambient_for_combat(world: dict, player: dict) -> str:
    """SPEC-296 R5: `<AMBIENTE>` (sem saídas) na narração do combate; nunca quebra o turno."""
    try:
        from services.ambient import ambient_block

        return ambient_block(world, player, audience="combat")
    except Exception as exc:  # noqa: BLE001 - ambientação é opcional
        from observability.telemetry import log_fallback

        log_fallback("combat_agent", "ambient_block_failed", exc)
        return ""


def _narrate(
    player: dict,
    enemies: list[dict],
    logs: list[str],
    spawned_flavor: str | None,
    intent: str,
    victory: bool,
    world_ctx: str,
    aberturas: list[str] | None = None,
    manifest: dict | None = None,
    withhold: str = "",
    fecho_override: str | None = None,
    fallback_text: str | None = None,
    off_ctx: dict | None = None,
) -> str:
    from services import prose_guard, round_log

    canonical = sorted(
        {
            p.get("species_label", "")
            for p in (manifest or {}).get("participants") or []
            if p.get("species_label")
        }
    )
    elenco = (
        (
            "Elenco canônico (espécies EXATAS; não renomeie nem troque por fauna): "
            + ", ".join(canonical)
        )
        if canonical
        else ""
    )
    log_str = "\n".join(l for l in logs if l) or "Nada acontece."
    alive = [
        f"{e['name']} (Vit {e.get('vitalidade', 0)}/{e.get('max_vitalidade', 0)})"
        for e in enemies
        if e.get("status") == "ativo"
    ]
    varie = prose_guard.openings_clause(aberturas or [])
    fecho = (
        "O combate foi VENCIDO — encerre com o respiro da vitória."
        if victory
        else "Termine com tensão e uma deixa para a próxima ação do jogador."
    )
    if fecho_override:  # SPEC-346 R16: queda do herói não é "tensão para a próxima ação"
        fecho = fecho_override
    sys = SystemMessage(
        content=f"""
    <role>Narrador de Combate — Dark Fantasy</role>
    Descreva o round em 1-2 parágrafos, com base APENAS no log mecânico. Não invente
    dano nem resultado fora do log. Trate o jogador por "você"; nunca use o nome próprio do
    herói. Visceral, conciso. Ferimentos são localizados e
    permanentes; Vitalidade é fôlego/vigor. Use o CONTEXTO só para ambientar.

    {("ENTRADA: " + spawned_flavor) if spawned_flavor else ""}
    Ação do jogador: {wrap_player_input(intent)}
    {world_ctx}
    {PLAYER_INPUT_RULE}
    <log_mecanico>
    {log_str}
    </log_mecanico>
    Herói: {player.get("name")} Vit {player.get("vitalidade")}/{player.get("max_vitalidade")}
    Inimigos ativos: {", ".join(alive) if alive else "nenhum"}
    {elenco}
    {withhold}
    {fecho}{varie}
    """
    )
    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        from services.narrative_sink import narrate_text

        # SPEC-319: tokens ao vivo so com sink (stream SSE); senao e o invoke de sempre.
        res = narrate_text(
            llm, [sys, HumanMessage(content=wrap_player_input(intent or "Continue o combate."))]
        )
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        if text.strip():
            # SPEC-203 R9: prosa que troca a espécie do elenco é neutralizada
            # (cai no texto determinístico); o estado nunca é reescrito.
            drift = prose_guard.species_drift(text, manifest) if manifest else []
            if round_log.names_hero(text, str(player.get("name") or "")):  # SPEC-387 R33
                _log_event("combat", "narration_hero_name", level="info")
            elif not drift:
                return text
            if drift:
                prose_guard.log_species_drift(drift, where="combate")
    except Exception as e:
        _log_event("combat", "narrate_failed", level="warning", error=type(e).__name__)
    if fallback_text is not None:  # SPEC-346 R15/R16: legível, sem bullets de log cru
        return fallback_text
    return _off_text.for_round(logs, player, spawned_flavor, victory, off_ctx)


# ==========================================================================
# SPEC-346 — tabuleiro sem LLM por rodada: entrada, recusa de texto livre e desfecho narrado
# ==========================================================================
BOARD_FREETEXT_REFUSAL = (
    "No tabuleiro, escolha suas Cartas na mão — ou use o botão Fugir. "
    "O texto livre espera o fim do conflito."
)


def _fast_text(
    system: SystemMessage,
    human: str,
    *,
    manifest: dict | None = None,
    where: str,
    on_fail=None,
    stream: bool = True,
    budget_s: float | None = None,
    on_budget=None,
) -> str | None:
    """Uma chamada FAST de prosa com o guard de FallbackLLM. ``None`` = use o texto
    determinístico (LLM indisponível, erro, resposta vazia ou espécie trocada).

    SPEC-353 R39c: ``budget_s`` dá um prazo à chamada; estourou → ``None`` (``on_budget(ms)``) e a
    thread que ainda corre é abandonada (o resultado dela é descartado)."""
    if budget_s is None:
        return _fast_text_call(
            system, human, manifest=manifest, where=where, on_fail=on_fail, stream=stream
        )
    import concurrent.futures
    import contextvars
    import time

    ctx = contextvars.copy_context()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    t0 = time.monotonic()
    fut = pool.submit(
        ctx.run,
        lambda: _fast_text_call(
            system, human, manifest=manifest, where=where, on_fail=on_fail, stream=stream
        ),
    )
    try:
        return fut.result(timeout=budget_s)
    except concurrent.futures.TimeoutError:
        if on_budget is not None:
            on_budget(int((time.monotonic() - t0) * 1000))
        return None
    finally:
        pool.shutdown(wait=False)


def _fast_text_call(
    system: SystemMessage,
    human: str,
    *,
    manifest: dict | None = None,
    where: str,
    on_fail=None,
    stream: bool = True,
) -> str | None:
    from services import prose_guard

    try:
        llm = get_llm(temperature=0.6, tier=ModelTier.FAST)
        if getattr(llm, "is_fallback", False):
            raise RuntimeError("fallback")
        from services.narrative_sink import narrate_text

        res = narrate_text(llm, [system, HumanMessage(content=human)], stream=stream)
        text = getattr(res, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in text)
        text = str(text).strip()
        if not text:
            return None
        drift = prose_guard.species_drift(text, manifest) if manifest else []
        if drift:
            prose_guard.log_species_drift(drift, where=where)
            return None
        return text
    except Exception as e:
        _log_event(
            "combat", "fast_text_failed", level="warning", where=where, error=type(e).__name__
        )
        if on_fail is not None:
            on_fail(type(e).__name__)
        return None


VIGILIA_CARD_ID = "dev_zel_vigilia"


def _has_vigilia(player: dict | None) -> bool:
    """Decisão do coordenador: "Vigília Ciumenta" no baralho/preparadas anula a emboscada.
    SPEC-355 R17: vale para QUALQUER Carta de Iniciativa (`buff_iniciativa`) do baralho/preparadas."""
    from services import card_effects as fx
    from services import cards

    p = player or {}
    for cid in list(p.get("deck") or []) + list(p.get("prepared_cards") or []):
        if cid == VIGILIA_CARD_ID:
            return True
        card = cards.get_card(str(cid))
        if card and any(e.get("kind") == "buff_iniciativa" for e in fx.normalize(card)):
            return True
    return False


def _opening_initiator(
    world: dict, origin: str, player: dict | None = None
) -> tuple[str | None, str]:
    """D4 (SPEC-346): quem age primeiro na rodada 1, pelo contexto da cena.

    Emboscada contra o jogador -> inimigos; o jogador iniciou o ataque (ou emboscou) -> jogador;
    sem sinal claro -> ``None`` (regra de iniciativa atual do motor)."""
    surprise = (world or {}).get("encounter_surprise")
    if surprise == "enemy":
        if _has_vigilia(player):  # surpresa anulada: cai na regra de iniciativa atual
            return None, "ambush_negated_vigilia"
        return "enemy", "ambush"
    if surprise == "player":
        return "heroes", "player_ambush"
    if origin == "player_provoked":
        return "heroes", "player_attack"
    return None, "neutral"


def _species_count_clause(enemies: list[dict], *, more_requested: bool) -> str:
    """R29: o narrador sabe exatamente quantos lutam."""
    from services import encounter_manifest as em

    counts: dict[str, int] = {}
    for e in enemies:
        label = em.species_label_for(e) or str(e.get("name") or "inimigo")
        counts[label] = counts.get(label, 0) + 1
    listed = ", ".join(f"{n} {label}" for label, n in counts.items()) or "nenhum"
    clause = f"Lutam contra você exatamente: {listed}."
    if more_requested:
        clause += " Os demais recuam e não entram na luta."
    return clause


def _narrate_entrance(
    player: dict,
    enemies: list[dict],
    spawned_flavor: str | None,
    intent: str,
    world_ctx: str,
    *,
    manifest: dict | None,
    withhold: str,
    aberturas: list[str] | None,
    more_requested: bool,
) -> str:
    """R1: a história abre o tabuleiro. Uma narração de entrada, sem resolver rodada."""
    from services import prose_guard

    deterministic = spawned_flavor or "Os inimigos avançam. O tabuleiro está aberto."
    system = SystemMessage(
        content=f"""
    <role>Narrador de Combate — Dark Fantasy</role>
    Narre em 1 parágrafo curto COMO O CONFRONTO COMEÇA. Ainda não há golpes resolvidos:
    não descreva dano, ferimento nem desfecho. Termine com os inimigos prontos, em tensão.
    {("ENTRADA: " + spawned_flavor) if spawned_flavor else ""}
    {_species_count_clause(enemies, more_requested=more_requested)}
    Ação do jogador: {wrap_player_input(intent)}
    {world_ctx}
    {PLAYER_INPUT_RULE}
    {withhold}{prose_guard.openings_clause(aberturas or [])}
    """
    )
    text = _fast_text(
        system,
        wrap_player_input(intent or "O confronto começa."),
        manifest=manifest,
        where="combate",
        on_fail=lambda err: _log_event("combat", "narrate_failed", level="warning", error=err),
    )
    if text:
        drift = prose_guard.count_drift(text, manifest)  # SPEC-353 R17
        if drift:
            _log_event(
                "combat",
                "entrance_count_reconciled",
                level="info",
                species=",".join(str(d["species"]) for d in drift),
            )
            text = text.rstrip() + " " + prose_guard.reconcile_count_sentence(drift)
    return text or deterministic


_OUTCOME_FECHO = {
    "victory": "O combate foi VENCIDO — encerre com o respiro da vitória.",
    "surrendered_enemy": "Os inimigos se renderam — encerre com o respiro da trégua.",
    "fled": "O herói ESCAPOU — descreva a fuga e o rastro que se perde.",
    "death": (
        "O herói TOMBA neste golpe — narre a queda, SEM declarar a morte definitiva "
        "(a Roda do Abismo decide depois)."
    ),
    "defeat": "O herói foi derrotado e perde os sentidos — narre a queda sem declarar a morte.",
    "incapacitated": "O herói perde os sentidos — narre a queda sem declarar a morte.",
    "expired": "Os inimigos perdem o rastro e o confronto se desfaz.",
}


def _fecho(label: str, last_out: dict | None) -> str:
    """Instrução de fecho do resumo; `objective_failed` (SPEC-387 R20) leva o motivo do motor."""
    if label == "objective_failed":
        from services import round_log

        why = round_log.objective_reason(last_out)
        return (
            f"O objetivo se perdeu{': ' + why if why else ''}. O herói segue de pé; "
            "não narre queda nem desmaio."
        )
    return _OUTCOME_FECHO.get(label, _OUTCOME_FECHO["victory"])


_OUTCOME_BUDGET_S = 6.0  # SPEC-353 D7/R39c: orçamento só do resumo final (sem env/flag)


def _narrate_outcome(
    outcome: str,
    conflict_sum: dict,
    player: dict,
    enemies: list[dict],
    last_out: dict,
    intent: str,
    world_ctx: str,
    *,
    manifest: dict | None,
    withhold: str = "",
    names: dict[str, str] | None = None,
    source_sink: dict | None = None,
) -> str:
    """R11-R15: a ÚNICA chamada de IA do combate `on`. Fatos em linguagem, sem números;
    pós-filtro de números; não contradiz o motor; fallback determinístico legível."""
    from services import prose_guard, round_log

    label = "incapacitated" if (player.get("post_combat_state") == "inconsciente") else outcome
    if (  # SPEC-387 R20: objetivo falho com o herói de pé não é "derrota"/desmaio
        label == "defeat"
        and ((last_out or {}).get("objetivo") or {}).get("resultado") == "falhou"
        and player.get("conscious", True)
    ):
        label = "objective_failed"
    facts = round_log.outcome_facts(
        label,
        conflict_sum,
        player,
        enemies,
        last_out,
        decisive_cards=round_log.decisive_cards(last_out),
        names=names,
    )
    auth = round_log.authorship(
        last_out, round_log._fact_names(player, enemies, names), player, conflict_sum
    )
    if source_sink is not None:
        source_sink.pop("last_outcome_source", None)  # nunca herda o valor de um conflito anterior

    def _src(value: str) -> None:  # SPEC-363 R13: por que o texto final é o que é
        if source_sink is not None:
            source_sink["last_outcome_source"] = value

    system = SystemMessage(
        content=f"""
    <role>Narrador de Combate — Dark Fantasy</role>
    Narre o FIM deste conflito em 1 parágrafo curto (3 a 5 frases), em segunda pessoa, usando
    APENAS os fatos abaixo. Trate o jogador por "você" (nunca tu/teu/tua). NÃO escreva números, dados, pontos de vida nem aritmética. Não invente
    mortes, golpes nem resultados fora dos fatos. Cada ação tem um autor: nunca atribua a Carta
    ou o golpe de um combatente a outro, nem diga que um golpe acertou (ou errou) contra os fatos.
    Quem caiu antes do fim já estava caído: conte no passado (já tinha tombado), nunca como se tombasse agora.
    Glossário: Vitalidade = vigor e resistência do corpo; Fôlego = energia para jogar Cartas
    (nunca é dano). Ferimentos são localizados e permanentes.
    <fatos>
    {chr(10).join(facts)}
    </fatos>
    Ação do jogador: {wrap_player_input(intent)}
    {world_ctx}
    {PLAYER_INPUT_RULE}
    {withhold}
    {_fecho(label, last_out)}
    """
    )
    text = _fast_text(
        system,
        wrap_player_input(intent or "O conflito termina."),
        manifest=manifest,
        where="combate",
        on_fail=lambda err: (
            _src("fallback_llm_error"),
            _log_event(
                "combat", "outcome_narration_failed", level="warning", error=err, outcome=label
            ),
        ),
        stream=False,  # o texto final = registro + resumo: o ao vivo não seria prefixo
        budget_s=_OUTCOME_BUDGET_S,  # SPEC-353 R39c: estourou → fallback determinístico
        on_budget=lambda ms: (
            _src("fallback_budget"),
            _log_event(
                "combat", "outcome_narration_budget_exceeded", level="warning", elapsed_ms=ms
            ),
        ),
    )
    if source_sink is not None and not text and "last_outcome_source" not in source_sink:
        _src("fallback_llm_error")
    if text:
        text, removed = prose_guard.strip_mechanic_numbers(text)
        if removed:
            _log_event("combat", "narration_numbers_stripped", level="info", count=removed)
        if not text:  # o filtro esvaziou a prosa: o fallback é por causa dela
            _src("fallback_narrative")
        verdict = summ.validate_narrative_text(conflict_sum, text) if text else {"ok": False}
        if text and verdict["ok"]:
            codes = summ.validate_attribution(text, auth)  # SPEC-353 R8
            codes = codes or prose_guard.wounds_bad(label, text, player)  # SPEC-393 R3
            if not codes:
                _src("llm")
                return text
            _src("fallback_attribution")
            _log_event(
                "combat", "outcome_attribution_rejected", level="info", codes=",".join(codes)
            )
        elif text:  # SPEC-363 R13: a rejeição da prosa também deixa rastro
            _src("fallback_narrative")
            _log_event(
                "combat",
                "outcome_narrative_rejected",
                level="info",
                codes=",".join(verdict.get("codes") or ["narrative"]),
            )
    return round_log.deterministic_outcome_text(
        label, conflict_sum, player, last_out=last_out, names=names
    )


# ==========================================================================
# SPEC-203 — desfecho do encontro
# ==========================================================================
def _encounter_outcome(
    *,
    player: dict,
    enemies: list[dict],
    hero_fled: bool,
    player_dead: bool,
    objective_result: str | None = None,
) -> str:
    if player_dead:
        return "death"
    if hero_fled:
        return "fled"
    if objective_result == "cumprido":  # SPEC-331 R5: desfecho próprio do Objetivo
        return "victory"
    if objective_result == "falhou":
        return "defeat"
    remaining = [
        e
        for e in enemies
        if e.get("status") == "ativo" and not e.get("dead") and not e.get("incapacitated")
    ]
    if remaining or not player.get("conscious", True):
        return "defeat"
    dead = [e for e in enemies if e.get("dead") or e.get("status") == "morto"]
    surrendered = [e for e in enemies if e.get("surrendered") or e.get("status") == "rendido"]
    if surrendered and not dead:
        return "surrendered_enemy"
    return "victory"


def _finish_encounter(combat_meta: dict, enemies: list[dict], outcome: str, *, loot: bool) -> dict:
    """Leva o encontro a `ended` e grava o snapshot do desfecho (R7)."""
    from services import encounter_manifest as em

    meta = dict(combat_meta)
    round_ = int(meta.get("round", 0) or 0)
    manifest = meta.get("encounter")
    if em.is_valid_manifest(manifest):
        manifest = em.sync_statuses(manifest, enemies, round_)
        meta["encounter"] = manifest
    meta = em.end_combat(meta, outcome)
    if em.is_valid_manifest(manifest):
        meta["result"] = em.build_result(
            manifest, outcome, round_, loot=loot and outcome == "victory"
        )
    meta["active"] = False
    return meta


# ==========================================================================
# NÓ PRINCIPAL
# ==========================================================================
def combat_node(state: GameState):
    """SPEC-251: abre o trace mecânico do turno e emite combat.mechanics/summary."""
    from services import creature_gen as _cg
    from services import mechanics_trace as _mt

    token = _cg.CONTADOR_ATUALIZADO.set(None)
    try:
        with _mt.scope():
            result = _combat_node(state)
            _mt.emit_turn_logs()
        contador = _cg.CONTADOR_ATUALIZADO.get()
        if contador is not None and isinstance(result, dict):
            # SPEC-361 R4: o spawn gerou criatura NOVA; o contador do jogo vai para o estado.
            world = dict(result.get("world") or state.get("world") or {})
            world["creature_gen"] = {"novas": int(contador[0]), "ultimo_turno": int(contador[1])}
            result["world"] = world
    finally:
        _cg.CONTADOR_ATUALIZADO.reset(token)
    return result


@dataclass
class _CombatTurn:
    """Estado mutavel de um turno do combate (SPEC-382): o que antes eram locais compartilhados entre
    as fases de `_combat_node`. Mesmas referencias, nunca copias."""

    aberturas: Any = None
    active: Any = None
    actors_by_id: Any = None
    allies: Any = None
    ally_ids: Any = None
    bestiary_knowledge: Any = None
    bk_changed: Any = None
    board_on: Any = None
    chase_refusal: Any = None
    chase_state: Any = None
    choices: Any = None
    combat_meta: Any = None
    combat_over: Any = None
    combat_target: Any = None
    conflict_sum: Any = None
    dead: Any = None
    dead_before: Any = None
    decl: Any = None
    declaration: Any = None
    downed: Any = None
    enemies: Any = None
    enemy_refs: Any = None
    fauna_sim: Any = None
    flee_dest_id: Any = None
    flee_lines: Any = None
    flee_requested: Any = None
    flee_roll: Any = None
    hero_fled: Any = None
    initiator: Any = None
    intent: Any = None
    is_simulation: Any = None
    is_start: Any = None
    kill_xp: Any = None
    last_player_action: Any = None
    level_up_events: Any = None
    loc: Any = None
    logs: Any = None
    logs_pre_flee: Any = None
    messages: Any = None
    narrative: Any = None
    newly_dead: Any = None
    order_decls: Any = None
    order_logs: Any = None
    out: Any = None
    outcome_now: Any = None
    party: Any = None
    player: Any = None
    player_dead: Any = None
    prior_flee_attempts: Any = None
    resolved_decl: Any = None
    result: Any = None
    rng: Any = None
    round_state: Any = None
    scene: Any = None
    scene_tr: Any = None
    sides: Any = None
    spawn_meta: Any = None
    spawned_flavor: Any = None
    state: Any = None
    status_logs: Any = None
    turn: Any = None
    victory: Any = None
    weather_logs: Any = None
    world: Any = None
    world_out: Any = None
    wounds_before: Any = None


def _combat_node(state: GameState):
    from services import prose_guard

    t = _CombatTurn(state=state)
    t.messages = t.state.get("messages", [])
    if not t.messages:
        return {"next": "dm_router"}

    t.player = dict(t.state["player"])
    if _deck_mode_now() == "off" and "prepared_cards_pre_deck" in t.player:
        from services import card_piles as _cp

        _cp.deactivate_deck(t.player)  # SPEC-328 P1-3: flag voltou a `off` → Preparação de antes
    orch.ensure_combat_sheet(t.player, is_player=True)
    t.enemies = [orch.ensure_combat_sheet(dict(e)) for e in (t.state.get("enemies") or [])]
    t.combat_meta = dict(t.state.get("combat") or {})
    t.combat_target = t.state.get("combat_target", "Inimigos")
    t.turn = int(t.state.get("world", {}).get("turn_count", 0) or 0)
    t.bestiary_knowledge = dict(t.state.get("bestiary_knowledge") or {})
    t.bk_changed = False
    t.is_simulation = bool((t.state.get("combat_simulation") or {}).get("enabled"))
    t.wounds_before: dict[str, int] = {}  # SPEC-333 R7: Ferimentos antes da rodada
    t.status_logs: list[str] = []  # SPEC-333: por que o jogador perdeu Fôlego/ficou Cego
    # SPEC-226 R1: mortos que já constavam no estado de entrada não rendem de novo.
    t.dead_before = {
        str(e.get("id") or e.get("name"))
        for e in (t.state.get("enemies") or [])
        if e.get("dead") or e.get("status") == "morto" or e.get("xp_awarded")
    }

    _early = _combat_unconscious_refusal(t)
    if _early is not None:
        return _early

    last_msg = t.messages[-1]
    t.is_start = isinstance(last_msg, SystemMessage) and "COMBAT START" in str(last_msg.content)
    t.scene = t.combat_meta.get("scene")
    t.spawned_flavor = None

    _early = _combat_freetext_refusal(t)
    if _early is not None:
        return _early

    # ---- Preparação (1x): identifica inimigos + monta cena jogável + congela ----
    # Um encontro pode chegar aqui já com `enemies` preenchido (router, save v4,
    # testes/e2e). Nesse caso preservamos os combatentes e apenas construímos a
    # cena ausente; só pedimos spawn quando não há inimigo ativo.
    from services import encounter_manifest as em

    t.spawn_meta: dict = {}
    # SPEC-346 R1: com o Baralho `on` a história ABRE o tabuleiro: entrada narrada, mão
    # distribuída, nenhuma rodada resolvida.
    opening_board = bool(t.is_start and _deck_mode_now() == "on" and not t.is_simulation)
    if t.is_start or not t.scene:
        _combat_open_scene(t)
    else:
        # R2: leitura por rodada — manifesto é a verdade; nunca reclassifica.
        if not em.is_valid_manifest(t.combat_meta.get("encounter")):
            t.combat_meta["encounter"] = em.manifest_from_legacy(
                t.enemies, t.combat_meta, game_id=str(t.state.get("game_id") or "game")
            )
        if t.combat_meta.get("phase") not in ("active",):
            t.combat_meta["phase"], t.combat_meta["outcome"] = "active", None
        t.combat_meta["encounter"], t.enemies, _violations = em.reconcile_roster(
            t.combat_meta["encounter"], t.enemies, int(t.combat_meta.get("round", 0) or 0)
        )

    t.active = [e for e in t.enemies if e.get("status") == "ativo" and not e.get("dead")]
    if not t.active:
        return _combat_no_active_result(t)

    _combat_assemble_sides(t)
    if opening_board:
        return _board_opening_result(
            t.state,
            t.messages,
            player=t.player,
            enemies=t.enemies,
            allies=t.allies,
            party=t.party,
            scene=t.scene,
            combat_meta=t.combat_meta,
            combat_target=t.combat_target,
            actors_by_id=t.actors_by_id,
            sides=t.sides,
            spawn_meta=t.spawn_meta,
            spawned_flavor=t.spawned_flavor,
            status_logs=t.status_logs,
            intent=t.intent,
            bestiary_knowledge=t.bestiary_knowledge,
            bk_changed=t.bk_changed,
        )
    t.declaration = t.state.get("combat_declaration")  # harness passa estruturado
    if t.declaration is not None and not isinstance(t.declaration, TurnDeclaration):
        t.declaration = TurnDeclaration(**t.declaration)

    _combat_flee_request(t)

    _combat_environment(t)
    _combat_attempt_flee(t)
    if not t.hero_fled:
        _combat_declare_turn(t)
        _combat_prepare_round(t)
        _combat_run_round(t)
    else:
        t.out = {
            "deaths": [],
            "ended": True,
            "player_dead": False,
            "scars_pending": [],
            "reason": "fuga",
            "recidiva_event": None,
            "attacks": [],
            "reactions": [],
            "resolved_turns": [_PLAYER_ID],
        }

    _combat_aftermath(t)

    _combat_outcome_summary(t)
    _combat_narrate(t)

    _combat_close_round_meta(t)
    _combat_close_round_log(t)
    _combat_close_encounter(t)
    _combat_result_base(t)

    _combat_result_quests(t)

    _combat_result_events(t)

    return t.result


def _combat_no_active_result(t: _CombatTurn) -> dict:
    """Sem inimigo ativo: encerra o encontro com vitória silenciosa."""
    import party as party_mod

    t.party = party_mod.backfill_party(t.state.get("party") or [])
    t.enemy_refs = [
        str(value) for enemy in t.enemies for value in (enemy.get("id"), enemy.get("name")) if value
    ]
    t.scene_tr = t.combat_meta.get("scene_allies") or party_mod.scene_allies(
        t.state, excluded=t.enemy_refs
    )
    t.allies = [
        orch.ensure_combat_sheet(dict(a), is_ally=True) for a in t.party if a.get("active")
    ] + [orch.ensure_combat_sheet(dict(a), is_ally=True) for a in t.scene_tr]
    # Saves legados podem ter somente o status textual. O summary precisa das
    # flags canônicas usadas por build_summary.
    for participant in t.enemies + t.allies:
        status = str(participant.get("status") or "").lower()
        if status == "morto":
            participant["dead"] = True
            participant["conscious"] = False
        elif status == "fugiu":
            participant["fled"] = True
        elif status == "rendido":
            participant["surrendered"] = True
    t.conflict_sum = summ.build_summary(
        [t.player] + t.enemies + t.allies,
        scene=t.scene,
        extras={"turn": t.turn, "conflict_id": t.combat_meta.get("instance_id")},
    )
    t.combat_meta["last_player_action"] = _canonical_player_action(None, {}, attempted=False)
    early_outcome = _encounter_outcome(
        player=t.player, enemies=t.enemies, hero_fled=False, player_dead=False
    )
    t.combat_meta = _finish_encounter(
        t.combat_meta, t.enemies, early_outcome, loot=not t.is_simulation
    )
    return {
        "messages": [AIMessage(content="O silêncio retorna ao campo. Vitória.")],
        "next": "loot",
        "combat_target": None,
        "enemies": [],
        "conflict_summary": t.conflict_sum,
        "combat": {
            **t.combat_meta,
            "active": False,
            "round": t.combat_meta.get("round", 0),
            "scene": None,
        },
        "archive_due": True,
    }


def _combat_assemble_sides(t: _CombatTurn) -> None:
    """Lados, atores por id e intenção do jogador."""
    # ---- Montagem dos lados + declaração do jogador ----
    import party as party_mod

    t.party = party_mod.backfill_party(t.state.get("party") or [])
    t.enemy_refs = [
        str(value) for enemy in t.enemies for value in (enemy.get("id"), enemy.get("name")) if value
    ]
    t.scene_tr = t.combat_meta.get("scene_allies") or party_mod.scene_allies(
        t.state, excluded=t.enemy_refs
    )
    t.allies = [
        orch.ensure_combat_sheet(dict(a), is_ally=True) for a in t.party if a.get("active")
    ] + [
        orch.ensure_combat_sheet(dict(a), is_ally=True)
        for a in t.scene_tr
        if not (a.get("dead") or a.get("status") == "morto")
    ]
    t.player["_party_active"] = bool(t.allies)
    t.ally_ids = [a.get("id") or a.get("name") for a in t.allies]

    t.actors_by_id: dict[str, dict] = {_PLAYER_ID: t.player}
    for e in t.enemies:
        t.actors_by_id[e["id"]] = e
    for a in t.allies:
        t.actors_by_id[a.get("id") or a.get("name")] = a
    t.sides = {"hero": [_PLAYER_ID], "ally": t.ally_ids, "enemy": [e["id"] for e in t.active]}

    t.intent = _last_human_text(t.messages)


def _combat_narrate(t: _CombatTurn) -> None:
    """Narração da rodada: tabuleiro, queda, simulação ou LLM."""
    from services import prose_guard

    t.narrative = ""
    if t.board_on:
        pass  # compõe o REGISTRO depois que `status_logs` fecha (SPEC-346 R4/R5)
    elif t.player_dead and not t.is_simulation:
        # SPEC-346 R16: a queda é narrada pelo `_narrate` (fecho de queda) e fecha com a Roda.
        from services import round_log

        killer = _killer_identity(t.active, t.out, t.enemies)[0]
        world_pack = build_context_pack(
            t.state,
            query=f"{t.loc} {t.intent}",
            purpose="combat_narration",
            token_budget=1200,
            include_lore=False,
        )
        t.narrative = _narrate(
            t.player,
            t.enemies,
            t.logs,
            t.spawned_flavor,
            t.intent,
            False,
            world_pack.world_state_block
            + "\n"
            + _ambient_for_combat(t.state.get("world") or {}, t.player)
            + _perceived_for_combat(t.state),
            t.aberturas,
            manifest=t.combat_meta.get("encounter"),
            withhold=_faction_withhold_clause(
                t.combat_meta.get("encounter"),
                t.state.get("factions"),
                t.state.get("faction_intel"),
            ),
            fecho_override=_OUTCOME_FECHO["death"],
            fallback_text=_narrate_fall(t.player, t.logs, killer),
        )
        if round_log.WHEEL_TEXT not in t.narrative:
            t.narrative = t.narrative.rstrip() + "\n\n" + round_log.WHEEL_TEXT
    elif t.player_dead:
        t.narrative = _narrate_fall(
            t.player, t.logs, _killer_identity(t.active, t.out, t.enemies)[0]
        )
    elif t.is_simulation:
        suffix = "\n\nVitória no laboratório." if t.victory else "\n\nEscolha a próxima ação."
        t.narrative = "⚔️ " + "\n".join(f"• {line}" for line in t.logs if line) + suffix
    else:
        world_pack = build_context_pack(
            t.state,
            query=f"{t.loc} {t.intent}",
            purpose="combat_narration",
            token_budget=1200,
            include_lore=False,  # SPEC-317 R8: so world_state_block e usado
        )
        t.narrative = _narrate(
            t.player,
            t.enemies,
            t.logs,
            t.spawned_flavor,
            t.intent,
            t.victory,
            world_pack.world_state_block
            + "\n"
            + _ambient_for_combat(t.state.get("world") or {}, t.player)
            + _perceived_for_combat(t.state),
            t.aberturas,
            manifest=t.combat_meta.get("encounter"),
            withhold=_faction_withhold_clause(
                t.combat_meta.get("encounter"),
                t.state.get("factions"),
                t.state.get("faction_intel"),
            ),
            off_ctx=_off_text.context_from(t.out, t.actors_by_id),  # Sol R3-P1-1
        )
    if t.combat_over and not t.board_on:
        t.narrative = summ.narrative_or_fallback(t.conflict_sum, t.narrative, player_facing=True)
        if t.player_dead:  # SPEC-346 R11: a Roda do Abismo fecha a queda, mesmo no fallback
            from services import round_log

            if round_log.WHEEL_TEXT not in t.narrative:
                t.narrative = t.narrative.rstrip() + "\n\n" + round_log.WHEEL_TEXT
    if not t.board_on:
        t.narrative = prose_guard.sanitize_meta_preamble(t.narrative)
        prose_guard.log_if_repeats(
            t.narrative, t.aberturas[0] if t.aberturas else "", where="combate"
        )


def _combat_close_round_meta(t: _CombatTurn) -> None:
    """Presságio seguinte, pilhas do baralho e snapshot de aliados."""
    # ---- Montagem do resultado (contrato preservado) ----
    # SPEC-231 R4: o snapshot de aliados transitórios carrega as fichas PÓS-rodada.
    if t.scene_tr:
        live_tr = {str(a.get("id") or a.get("name")): a for a in t.allies if a.get("transient")}
        t.scene_tr = [live_tr.get(str(a.get("id") or a.get("name")), a) for a in t.scene_tr]
        t.combat_meta["scene_allies"] = t.scene_tr
    t.combat_meta["active"] = not t.combat_over
    # SPEC-329 R1: congela o Presságio da PRÓXIMA rodada (a UI o mostra antes da jogada).
    refused = bool(t.out.get("action_refused"))  # SPEC-328 R-2: recusa não rerrola o Presságio
    if not refused:
        t.combat_meta.pop("pressagios", None)
        t.combat_meta.pop("pressagios_publicos", None)
    if _enemy_intent.active() and not t.combat_over and not t.is_simulation and not refused:
        try:
            from services import enemy_decks as _enemy_decks

            _exec_round = cs.tactical_round(t.scene) + 1  # rodada em que estas intenções valem
            _next_round = _enemy_intent.forecast_round(
                t.scene,
                t.actors_by_id,
                t.sides,
                t.rng,
                scene_state=({"_rodada_decisao": _exec_round} if _enemy_decks.active() else None),
            )
            t.combat_meta["pressagios"] = _next_round
            t.combat_meta["pressagios_publicos"] = _enemy_intent.public_round(
                _next_round, t.actors_by_id, _exec_round
            )
            if _enemy_decks.active():  # SPEC-355 R3: a promessa pública fica na cena
                for _row in t.combat_meta["pressagios_publicos"]:
                    if _row.get("prenuncio") and _row.get("actor_id") in t.actors_by_id:
                        _enemy_decks.record_promise(
                            t.scene, t.actors_by_id[_row["actor_id"]], _exec_round
                        )
        except Exception:  # cosmético: nunca derruba o turno
            _log_event("combat", "pressagio_forecast_failed", level="warning")
    if _scene_cards.active():  # SPEC-331 R3: o que dispara na PRÓXIMA rodada
        if t.combat_over:
            t.combat_meta.pop("pressagios_cena", None)
        elif not refused:
            t.combat_meta["pressagios_cena"] = _scene_cards.forecast(
                t.scene, cs.tactical_round(t.scene) + 1
            )
    if isinstance(t.combat_meta.get("pilhas"), dict):  # SPEC-328: pilhas vivem só no conflito
        if t.combat_over:
            t.combat_meta.pop("pilhas", None)
        elif not t.out.get("action_refused") and _deck_mode_now() != "off":
            from services import card_piles

            t.status_logs += card_status.on_round_end(
                t.combat_meta["pilhas"], t.player, t.wounds_before
            )
            drawn_now: list[str] = []
            card_piles.begin_round(
                t.combat_meta["pilhas"], drawn_out=drawn_now
            )  # mão da PRÓXIMA rodada
            if card_status.active():
                t.status_logs += card_status.on_hand_drawn(
                    t.combat_meta["pilhas"], t.player, drawn_now
                )
            _scene_cards.sync_hand(t.scene, t.combat_meta["pilhas"], _PLAYER_ID)  # SPEC-331 R6


def _combat_close_round_log(t: _CombatTurn) -> None:
    """Iniciativa, fontes de condição, mech_log e registro do tabuleiro."""
    t.combat_meta["initiative"] = list(t.out.get("initiative") or [])
    t.combat_meta["last_player_action"] = t.last_player_action
    t.combat_meta["last_reactions"] = list(t.out.get("reactions") or [])
    from services import combat_preview as _preview

    if t.flee_roll:
        t.out["fuga"] = t.flee_roll
    avisados = set(
        t.combat_meta.get("sem_vitalidade_avisados") or []
    )  # SPEC-353 R27: 1× por inimigo
    t.out["sem_vitalidade"] = [
        x for x in t.out.get("sem_vitalidade") or [] if x["actor_id"] not in avisados
    ]
    t.combat_meta["sem_vitalidade_avisados"] = sorted(
        avisados | {x["actor_id"] for x in t.out["sem_vitalidade"]}
    )
    fontes = t.combat_meta.setdefault("fontes_condicao", {})  # SPEC-353 R51
    for novo in t.out.get("condicoes_novas") or []:
        if not novo.get("source_id"):
            fontes.get(novo["victim_id"], {}).pop(novo["condition"], None)  # fonte desconhecida
            continue
        fontes.setdefault(novo["victim_id"], {})[novo["condition"]] = novo["source_id"]
    _preview.store_mech_log(
        t.combat_meta,
        t.out,
        [t.player, *t.enemies, *t.allies],
        {str(e.get("id") or e.get("name")) for e in t.enemies},
    )  # SPEC-334 R6 (só deck on)
    t.status_logs = _normalize_status_logs(t.status_logs, t.player)  # SPEC-363 R26
    if t.status_logs:  # SPEC-333: o jogador sabe por que a carta de status pesou
        t.combat_meta["last_mech_log"] = (
            list(t.combat_meta.get("last_mech_log") or []) + t.status_logs
        )
        # SPEC-346 R5: as linhas de status vão ao REGISTRO/mech_log, nunca coladas à prosa.
    if t.board_on:
        t.narrative = _compose_board_narrative(
            t.state,
            t.out,
            t.actors_by_id,
            t.status_logs,
            extra_lines=t.weather_logs + t.order_logs + t.flee_lines,
            combat_over=t.combat_over,
            outcome=t.outcome_now,
            conflict_sum=t.conflict_sum,
            player=t.player,
            enemies=t.enemies,
            player_dead=t.player_dead,
            intent=t.intent,
            manifest=t.combat_meta.get("encounter"),
            source_sink=t.combat_meta,
        )


def _combat_close_encounter(t: _CombatTurn) -> None:
    """Fim do encontro (espólio, desfecho) ou confirmação da entrada."""
    from services import encounter_manifest as em

    t.combat_meta["last_tactics"] = list(t.out.get("tactics") or [])
    if t.combat_over:
        from services import cards

        cards.reset_card_usage({"player": t.player}, "cena")
        card_status.cleanup(t.player)  # SPEC-333: Cartas temporarias saem com o conflito
        if (
            (t.victory or t.scene.get("objetivo_resultado") == "cumprido")
            and not (t.player_dead or t.is_simulation)
            # objetivo cumprido vale mesmo saindo da cena (ex.: alcancar_zona); fuga comum não
            and not (t.hero_fled and t.scene.get("objetivo_resultado") != "cumprido")
            and card_rewards.mode() != "off"
        ):
            # SPEC-333 R1/R3: espolio so em vitoria real ou objetivo cumprido (SPEC-331).
            card_rewards.grant_after_conflict(
                t.state,
                t.player,
                conflict_id=str(t.combat_meta.get("instance_id") or ""),
                seed=zlib.crc32(f"{t.combat_meta.get('instance_id')}:espolio".encode()),
                defeated=t.dead + t.downed,
                objective_result=t.scene.get("objetivo_resultado"),
                turn=t.turn,
            )
        t.combat_meta["scene"] = None
        t.combat_meta.pop("scene_allies", None)
        # SPEC-203 R5/R7: resolving → ended + snapshot do desfecho.
        _outcome = t.outcome_now
        t.combat_meta = _finish_encounter(
            t.combat_meta,
            t.enemies,
            _outcome,
            loot=bool(t.victory) and not t.is_simulation,
        )
        # SPEC-296 R2: inimigo que fugiu pode voltar com reforços (1 alerta/encontro).
        if not t.is_simulation:
            _alerted = _flee_alert_world(t.world_out or t.world, t.enemies, _outcome)
            if _alerted is not None:
                t.world_out = _alerted
    else:
        # Narração de entrada enviada → encontro confirmado (entering→active).
        if t.combat_meta.get("phase") == "entering":
            t.combat_meta = em.safe_transition(t.combat_meta, "active")
        if em.is_valid_manifest(t.combat_meta.get("encounter")):
            t.combat_meta["encounter"] = em.sync_statuses(
                t.combat_meta["encounter"], t.enemies, int(t.combat_meta.get("round", 0) or 0)
            )


def _combat_result_base(t: _CombatTurn) -> None:
    """Dict de retorno do turno e campos opcionais."""
    t.result = {
        "messages": [AIMessage(content=t.narrative)],
        "player": t.player,
        "enemies": [] if t.combat_over else t.enemies,
        "combat": t.combat_meta,
        "combat_target": None if t.combat_over else t.combat_target,
        "next": "loot" if t.victory and not t.is_simulation else None,
        "archive_due": t.combat_over and not t.is_simulation,
        "party": _merge_formal_party(t.party, t.allies),
        "combat_declaration": None,  # consumida (não vaza para o próximo turno)
        "combat_origin_hint": None,
        "combat_encounter_hint": None,  # SPEC-203: one-shot consumido
        "combat_target_ref": None,
    }
    if t.conflict_sum is not None:
        t.result["conflict_summary"] = t.conflict_sum
    if t.choices["events"]:
        # SPEC-325 R12: `companion_abandoned` (sem o destino: ele fica selado na party).
        t.result["event_log"] = list(t.state.get("event_log") or []) + t.choices["events"]
        from services import chronicle as _chron

        _chronicle = list(t.state.get("chronicle") or [])
        for _ev in t.choices["events"]:
            _text = _chron.render_milestone(_ev, t.state.get("world_projection") or {})
            if _text:
                _chronicle = _chron.append_entry(
                    _chronicle,
                    text=_text,
                    turn=int(_ev.get("turn", 0) or 0),
                    kind="milestone",
                    event_id=_ev["event_id"],
                )
        if _chronicle != list(t.state.get("chronicle") or []):
            t.result["chronicle"] = _chronicle
    if t.world_out is not None:
        t.result["world"] = t.world_out
    if t.bk_changed:
        t.result["bestiary_knowledge"] = t.bestiary_knowledge
    if t.fauna_sim is not None:
        t.result["world_sim"] = t.fauna_sim
    if t.kill_xp:
        from services.turn_outcome import record_gain

        _bl = record_gain(t.state.get("turn_baseline"), "xp", t.kill_xp, "combat")
        if _bl is not t.state.get("turn_baseline"):
            t.result["turn_baseline"] = _bl


def _combat_result_quests(t: _CombatTurn) -> None:
    """Progresso de quests de mundo e de caça pela vitória."""
    # SPEC-305 R11: vitoria no alvo de quest de mundo (cerco/ocupacao/ascensao/objeto) = 1
    # evidencia `combat_won` por combate.
    if (
        t.victory
        and not t.is_simulation
        and any(q.get("world_kind") for q in t.state.get("quests") or [])
    ):
        from services import quest_log as _quest_log

        _wstate = t.state.get("world") or {}
        _synced = _quest_log.sync_combat_progress(
            t.state.get("quests") or [],
            str(_wstate.get("current_location_id") or ""),
            turn=int(_wstate.get("turn_count", 0) or 0),
        )
        if _synced != list(t.state.get("quests") or []):
            t.result["quests"] = _synced

    # SPEC-313 R20: a morte da criatura-ancora numa quest `cacar_criatura` e a unica prova da
    # caca (inimigo que fugiu e combate simulado nao contam).
    if (
        t.victory
        and not t.is_simulation
        and any(q.get("world_kind") == "cacar_criatura" for q in t.state.get("quests") or [])
    ):
        from services import quest_log as _quest_log
        from services import world_pressures as _wp
        from services.discovery import normalize_bestiary_id as _normalize_bestiary_id

        _w = t.state.get("world") or {}
        _hunted = _quest_log.sync_hunt_progress(
            t.result.get("quests", t.state.get("quests") or []),
            [_normalize_bestiary_id(e) for e in t.dead + t.downed],
            _wp.region_of(str(_w.get("current_location_id") or "")),
            turn=int(_w.get("turn_count", 0) or 0),
        )
        if _hunted != list(t.result.get("quests", t.state.get("quests") or [])):
            t.result["quests"] = _hunted


def _combat_result_events(t: _CombatTurn) -> None:
    """Reflexo dos aliados, eventos de mundo (kills, queda), fuga com viagem."""
    # ---- Reflexo dos aliados transitórios no NPC de origem ----
    if t.scene_tr:
        t.result["npcs"] = _reflect_scene_allies(t.state, t.scene_tr, t.allies, t.combat_over)

    # ---- Eventos de mundo (kills canônicas + level up + morte do jogador) ----
    engine_events = [] if t.is_simulation else _kill_events(t.newly_dead) + t.level_up_events
    if t.out.get("recidiva_event"):
        engine_events.append(t.out["recidiva_event"])

    death_events = []
    if t.player_dead:
        stabilization = next(
            (
                entry
                for entry in reversed(t.out.get("stabilizations") or [])
                if entry.get("actor_id") == _PLAYER_ID
            ),
            {},
        )
        t.combat_meta["death_context"] = {
            "last_action": t.last_player_action,
            "entered_terminal": bool(
                _PLAYER_ID in (t.out.get("terminal") or [])
                or _PLAYER_ID in (t.out.get("last_stands") or [])
            ),
            "stabilization": stabilization.get("cause") or stabilization.get("log", ""),
            "stabilization_attempts": int(
                stabilization.get("attempts", t.player.get("stabilization_attempts", 0)) or 0
            ),
            "killer": _killer_identity(t.active, t.out, t.enemies)[0],
        }
        t.result["death_pending"] = True
        t.result["combat"] = {**t.combat_meta, "active": False, "scene": None}
        t.result["enemies"] = []
        t.result["combat_target"] = None
        t.result["next"] = None
        t.result["archive_due"] = not t.is_simulation
        killer, killer_id = _killer_identity(t.active, t.out, t.enemies)
        death_events.append(
            {
                "type": "player_downed",
                "actor_id": "player",
                "target_id": "player",
                "detail": f"{t.player.get('name', 'O herói')} tombou em combate"
                + (f" {_diante_de(killer)}" if killer else ""),
                "payload": {
                    "killer": killer,
                    "killer_id": killer_id,
                    "location": t.loc,
                    "boss_present": any(
                        str(e.get("categoria", "")).lower() in ("chefe", "nomeado")
                        for e in t.enemies
                    ),
                },
                "source": "combat",
            }
        )
    if not t.is_simulation:
        engine_events += death_events
    if engine_events:
        t.result["pending_world_events"] = (
            t.state.get("pending_world_events", []) or []
        ) + engine_events

    # ---- Fuga bem-sucedida → viagem no mesmo turno + reset de cena ----
    if t.hero_fled and t.flee_dest_id:
        _apply_flee_travel(t.state, t.result, t.flee_dest_id, t.player, t.logs)
    if t.state.get("combat_flee_attempt"):
        t.result["combat_flee_attempt"] = False
        t.result["combat_flee_destination"] = None
    t.result["player_reaction_card_id"] = None


def _combat_unconscious_refusal(t: _CombatTurn) -> dict | None:
    """Inconsciente não inicia outro conflito."""
    if not t.player.get("conscious", True) and not t.combat_meta.get("active"):
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Você está inconsciente e não pode iniciar outro conflito. "
                        "É preciso descansar ou receber tratamento primeiro."
                    )
                )
            ],
            "player": t.player,
            "enemies": [],
            "combat": {**t.combat_meta, "active": False, "scene": None},
            "combat_target": None,
            "next": None,
            "archive_due": False,
            "combat_declaration": None,
        }
    return None


def _combat_freetext_refusal(t: _CombatTurn) -> dict | None:
    """Com o tabuleiro aberto não existe texto livre."""
    # ---- SPEC-346 R3/D5: com o tabuleiro aberto (`on`) NÃO existe texto livre, nem fuga por texto ----
    if (
        not t.is_start
        and t.scene
        and t.combat_meta.get("active")
        and not t.is_simulation
        and _deck_mode_now() == "on"
        and t.state.get("combat_declaration") is None
    ):
        _log_event("combat", "freetext_refused", level="info")
        return {
            "messages": [AIMessage(content=BOARD_FREETEXT_REFUSAL)],
            "combat": {**dict(t.state.get("combat") or {}), "idle_turns": 0},
            "next": None,
            "archive_due": False,
            "combat_declaration": None,
            "combat_flee_attempt": False,
            "combat_flee_destination": None,
        }
    return None


def _combat_open_scene(t: _CombatTurn) -> None:
    """Preparação (1x): spawn, cena, manifesto, pilhas e Presságio de cena."""
    import party as party_mod
    from services import encounter_manifest as em

    t.party = party_mod.backfill_party(t.state.get("party") or [])
    if not [e for e in t.enemies if e.get("status") == "ativo" and not e.get("dead")]:
        t.enemies, t.spawned_flavor = _spawn_v4_enemies(
            t.messages, t.combat_target, t.state, t.spawn_meta
        )
    t.enemy_refs = [
        str(value) for enemy in t.enemies for value in (enemy.get("id"), enemy.get("name")) if value
    ]
    if t.combat_target:
        t.enemy_refs.append(str(t.combat_target))
    t.allies = [
        orch.ensure_combat_sheet(dict(a), is_ally=True) for a in t.party if a.get("active")
    ] + [
        orch.ensure_combat_sheet(dict(a), is_ally=True)
        for a in party_mod.scene_allies(t.state, excluded=t.enemy_refs)
    ]
    # SPEC-353 R22: o aliado de cena tem nome já na rodada 0; R54: conflito novo limpa o registro
    opening_allies = party_mod.scene_allies(t.state, excluded=t.enemy_refs)
    t.scene = _prepare_scene(t.state, t.enemies, t.player, t.allies)
    _sync_enemy_knowledge(t.enemies, load_persisted=True)
    t.bestiary_knowledge = disc.record_encounter(t.bestiary_knowledge, t.enemies, t.turn)
    t.bk_changed = True
    for _enemy in t.enemies:  # SPEC-371 R8: o saber do herói entra no ator (flag on)
        _fauna_saber.stamp_actor(_enemy, t.bestiary_knowledge)
    from services.combat_origin import materialize

    continuity = t.state.get("continuity") or {}
    conflict_instance_id = ":".join(
        (
            str(t.state.get("game_id") or "game"),
            str(int(continuity.get("timeline_epoch", 0) or 0)),
            str(int(continuity.get("session_action_count", t.turn) or t.turn)),
        )
    )
    t.combat_meta = {
        "round": 0,
        "active": True,
        "scene": t.scene,
        "idle_turns": 0,
        "origin": materialize(t.combat_meta, t.state.get("combat_origin_hint")),
        "instance_id": conflict_instance_id,
        "encounter_level": t.scene.get("encounter_level", 1),
        # SPEC-353 R22: nome do aliado de cena já na rodada 0. R54/R51: o dict novo também
        # zera last_round_board/last_mech_log/fontes_condicao do conflito anterior.
        "scene_allies": opening_allies,
    }
    # SPEC-328 R5/R16: Baralho de Conflito (semente derivada do conflito → replay).
    from services import card_piles

    if card_piles.mode() == "on":
        card_piles.activate_deck(t.player)  # P1-3: guarda a Preparação original p/ rollback
    if card_piles.mode() != "off":
        t.combat_meta["pilhas"] = card_piles.start_piles(
            t.player, zlib.crc32(conflict_instance_id.encode("utf-8"))
        )
        _scene_cards.sync_hand(t.scene, t.combat_meta["pilhas"], _PLAYER_ID)  # SPEC-331 R6
        t.status_logs += card_status.on_start(t.combat_meta["pilhas"], t.player)  # SPEC-333 R9
    if card_rewards.mode() == "on":
        card_rewards.expire_pending(t.player)  # SPEC-333 R3: espolio nao decidido expira
    if _scene_cards.active():  # SPEC-331 R3: presságio de cena da rodada 1
        t.combat_meta["pressagios_cena"] = _scene_cards.forecast(t.scene, 1)
    # SPEC-203 R1/R5: manifesto congelado no spawn → fase `entering`.
    t.combat_meta = em.safe_transition(t.combat_meta, "entering")
    t.combat_meta["encounter"] = em.build_manifest(
        t.enemies,
        source=(
            t.spawn_meta.get("source") or ("simulation" if t.is_simulation else "legacy_migrated")
        ),
        origin=t.combat_meta["origin"],
        encounter_id=conflict_instance_id,
        target_ref=t.spawn_meta.get("target_ref") or str(t.combat_target or ""),
        scene=t.scene,
        joined_ids=t.spawn_meta.get("joined_ids") or (),
        cut_ids=t.spawn_meta.get("cut_ids") or (),
    )
    _log_event("combat", "started", level="info", enemies=len(t.enemies))


def _combat_flee_request(t: _CombatTurn) -> None:
    """Pedido de fuga e escolhas do grupo na perseguição."""
    # ---- Fuga: chase determinístico (conflito-09) ----
    t.flee_dest_id = None
    from services.chase import FLEE_RE

    # SPEC-325 C-P2-1: "Brunna, recuar." é ordem ao aliado, nunca a fuga do herói.
    flee_text, _order_only = _player_text_without_order(
        t.intent, t.enemies, t.actors_by_id, t.sides
    )
    t.flee_requested = bool(FLEE_RE.search(flee_text.lower()))
    if t.flee_requested:
        from services.intent_guard import log_intent_guard

        log_intent_guard("flee_regex", "FLEE_RE", t.intent)
    if (
        t.declaration is not None
        and t.declaration.acao is not None
        and t.declaration.acao.kind == "flee"
    ):
        t.flee_requested = True
        t.flee_dest_id = t.declaration.acao.params.get("destination_id")
    if t.state.get("combat_flee_attempt"):
        t.flee_requested = True
        t.flee_dest_id = t.state.get("combat_flee_destination")

    # SPEC-325 R12/R13: abandono/sacrifício durante a perseguição (`off`/sem fuga = nada muda).
    t.choices = _chase_party_choices(
        t.state,
        t.combat_meta,
        t.party,
        t.allies,
        t.ally_ids,
        t.actors_by_id,
        t.sides,
        t.player,
        t.intent,
        t.active,
    )
    if t.choices["flee"]:
        t.flee_requested = True
        t.logs_pre_flee = list(t.choices["logs"])
    else:
        t.logs_pre_flee = []

    t.prior_flee_attempts = t.combat_meta.get("flee_attempts")
    if t.flee_requested:
        t.combat_meta["flee_attempts"] = int(t.combat_meta.get("flee_attempts", 0) or 0) + 1
    else:
        # O teto mede tentativas consecutivas dentro deste conflito.
        t.combat_meta.pop("flee_attempts", None)


def _combat_environment(t: _CombatTurn) -> None:
    """Rodada, clima, luz, iniciativa e surpresa."""
    t.combat_meta["round"] = int(t.combat_meta.get("round", 0)) + 1
    t.combat_meta["active"] = True
    t.combat_meta["idle_turns"] = 0
    t.combat_meta["scene_allies"] = t.scene_tr
    # RNG = módulo global (semeado pelo harness/persistência) → reprodutível por seed.
    t.rng = random

    t.hero_fled = False
    t.logs: list[str] = []
    t.flee_lines: list[str] = []  # SPEC-346: linhas humanas da fuga para o registro
    t.flee_roll: dict | None = None  # SPEC-353 R39b: dado da fuga desta rodada, para o mech_log
    t.order_logs: list[str] = []
    t.weather_logs: list[str] = []
    t.world_out = None
    t.world = t.state.get("world") or {}
    from world_utils import DARK_COMBAT_PENALTY, light_level, weather_effects

    weather_fx = weather_effects(t.world)
    light_fx = light_level(t.world, t.player)
    weather_attack = int(weather_fx.get("combat_attack_mod", 0) or 0)
    hero_light_attack = int(light_fx.get("combat_mod", 0) or 0)
    enemy_light_attack = DARK_COMBAT_PENALTY if light_fx.get("natural_dark") else 0
    t.player["_env_attack_mod"] = weather_attack + hero_light_attack
    for ally in t.allies:
        ally["_env_attack_mod"] = weather_attack + hero_light_attack
    for enemy in t.active:
        enemy["_env_attack_mod"] = weather_attack + enemy_light_attack
    surprise = t.world.get("encounter_surprise")
    t.initiator = "heroes" if surprise == "player" else ("enemy" if surprise == "enemy" else None)
    if int(t.combat_meta.get("round", 0) or 0) == 1 and "initiator_reason" in t.combat_meta:
        # SPEC-346 D4: a abertura já decidiu pela cena (inclusive "anulada pela vigília" = None);
        # a surpresa crua do mundo não vale de novo.
        t.initiator = t.combat_meta.get("initiator")
    t.initiator = _early_game_reaction_initiator(
        t.state, t.player, t.initiator, combat_round=int(t.combat_meta.get("round", 1) or 1)
    )
    locked = (
        t.combat_meta.get("initiator") if int(t.combat_meta.get("round", 0) or 0) == 1 else None
    )
    if locked in ("enemy", "heroes"):  # SPEC-346 D4: a cena decidiu quem age primeiro
        t.initiator = locked
    if "encounter_surprise" in t.world:
        t.world_out = dict(t.world)
        t.world_out.pop("encounter_surprise", None)
    t.weather_logs = _apply_weather_hazard(t.player, t.world, rng=t.rng)
    _register_environmental_damage_terminal(t.player, t.weather_logs)
    if isinstance(t.combat_meta.get("pilhas"), dict):  # SPEC-331 P1-1: cartas de objeto no turno
        _scene_cards.sync_hand(t.scene, t.combat_meta["pilhas"], _PLAYER_ID)


def _combat_attempt_flee(t: _CombatTurn) -> None:
    """Tentativa de fuga do herói (chase determinístico)."""
    t.resolved_decl: TurnDeclaration | None = t.declaration
    flee_allowed = _can_attempt_flee(t.player)
    if t.flee_requested and flee_allowed:
        _prev_track = str((t.combat_meta.get("chase") or {}).get("trilha") or "pressionado")
        t.hero_fled, flee_logs, t.chase_state = _attempt_flee(
            t.scene,
            t.player,
            t.active,
            t.sides,
            t.rng,
            existing_chase=t.combat_meta.get("chase"),
            intent=t.intent,
            force_escape=bool(t.choices["sacrificed"]),
        )
        if not t.hero_fled and _is_valid_flee_destination(t.state, t.flee_dest_id):
            t.hero_fled, t.chase_state = _enforce_flee_attempt_limit(
                t.chase_state,
                attempts=int(t.combat_meta.get("flee_attempts", 0) or 0),
            )
            if t.hero_fled:
                flee_logs.append("Após uma perseguição prolongada, os inimigos perdem o rastro.")
        _publish_sacrifice_offer(
            t.state, t.party, t.chase_state, hero_fled=t.hero_fled, logs=flee_logs
        )
        t.combat_meta["chase"] = t.chase_state
        t.flee_roll = _flee_roll_payload(t.chase_state, _prev_track, t.hero_fled) or t.flee_roll
        t.logs += t.weather_logs + t.logs_pre_flee + flee_logs
        t.flee_lines = list(t.logs_pre_flee) + list(flee_logs)
    elif t.flee_requested:
        t.chase_state = {
            **dict(t.combat_meta.get("chase") or {}),
            "eligible": False,
            "blocked_reason": "lifecycle",
        }
        t.combat_meta["chase"] = t.chase_state
        t.logs += t.weather_logs + [
            "Sua condição atual impede iniciar a fuga; a rodada resolve sua recuperação."
        ]


def _combat_declare_turn(t: _CombatTurn) -> None:
    """Declaração do herói (fuga falha, estruturada, ordem ou parse)."""
    if t.flee_requested:
        # A tentativa falhou, mas consumiu a Ação do protagonista. Inimigos
        # ainda resolvem a rodada; não há parse secundário nem ataque oculto.
        t.decl = TurnDeclaration(
            actor_id=_PLAYER_ID,
            acao=TurnStep(kind="pass"),
        )
    else:
        if t.declaration is not None and t.declaration.acao is not None:
            t.decl = t.declaration
        else:
            parse_text, order_only = _player_text_without_order(
                t.intent, t.enemies, t.actors_by_id, t.sides
            )
            if order_only:  # só a ordem: o herói ataca o 1º inimigo, sem gastar CLASSIFY
                t.decl = TurnDeclaration(
                    actor_id=_PLAYER_ID,
                    acao=TurnStep(kind="attack", target_id=t.active[0]["id"]),
                )
            else:
                t.decl = _parse_turn_declaration(
                    t.player,
                    t.active,
                    parse_text,
                    t.scene,
                    piles=t.combat_meta.get("pilhas") if _deck_mode_now() == "on" else None,
                )
    _mark_nonlethal(t.decl, t.intent)
    t.resolved_decl = t.decl


def _combat_prepare_round(t: _CombatTurn) -> None:
    """Recusas, ordens de companheiros, alvos e pilhas da rodada."""
    t.chase_refusal = _chase_attack_gate(t.combat_meta, t.decl)  # SPEC-325 R11
    if not t.chase_refusal:  # SPEC-325 R14: objeto inválido/ofensivo contra os seus
        t.chase_refusal = _guard_object_step(t.decl, t.scene, t.active, t.sides)
    t.order_decls, t.order_logs = _companion_orders(
        t.state, t.intent, t.party, t.enemies, t.scene, t.actors_by_id, t.sides
    )  # SPEC-325 R15
    # alvo inválido (inimigo já caiu / declaração pré-computada) → 1º inimigo ativo
    if (
        t.decl.acao
        and t.decl.acao.kind == "attack"
        and t.decl.acao.target_id not in {e["id"] for e in t.active}
    ):
        from services import mechanics_trace as _mt

        _mt.record_step(
            "target_redirect",
            actor=_PLAYER_ID,
            target=t.active[0]["id"],
            reason="target_not_active",
        )
        t.decl.acao.target_id = t.active[0]["id"]
    elif t.decl.acao and t.decl.acao.kind == "card":
        from services import cards

        declared_card = cards.get_card(t.decl.acao.card_id or "") or {}
        t.decl.acao.target_id = _card_target_for(
            declared_card,
            t.decl.acao.target_id,
            active_ids=[e["id"] for e in t.active],
            friendly_ids=[_PLAYER_ID] + [aid for aid in t.ally_ids if aid],
        )
    for extra_step in t.decl.jogadas[1:]:  # SPEC-328 R13: mesmas regras de alvo p/ a lista
        _normalize_extra_play(extra_step, t.active, t.ally_ids)
    t.round_state = {
        "player": t.player,
        "_player_reaction_card_id": t.state.get("player_reaction_card_id"),
    }
    deck_mode = _deck_mode_now()
    if deck_mode != "off" and isinstance(t.combat_meta.get("pilhas"), dict):
        import copy as _copy

        t.combat_meta["pilhas"] = _copy.deepcopy(t.combat_meta["pilhas"])
        t.round_state["_piles"] = t.combat_meta["pilhas"]
        t.round_state["_deck_mode"] = deck_mode


def _combat_run_round(t: _CombatTurn) -> None:
    """Resolve a rodada no orquestrador de conflito e absorve o saber de fauna."""
    t.wounds_before = card_status.wound_counts(t.player)
    t.out = orch.run_round(
        t.scene,
        t.actors_by_id,
        t.sides,
        t.round_state,
        declarations={**t.order_decls, _PLAYER_ID: t.decl},
        prepared_abyss=t.scene.get("abyss_events"),
        initiator=t.initiator,
        rng=t.rng,
        **({"refusal": t.chase_refusal} if t.chase_refusal else {}),
        **(
            {"pressagios": t.combat_meta["pressagios"]}
            if _enemy_intent.active() and isinstance(t.combat_meta.get("pressagios"), dict)
            else {}
        ),
    )
    if t.chase_refusal or t.out.get("deck_refused"):
        t.combat_meta["round"] = max(0, int(t.combat_meta.get("round", 1) or 1) - 1)
        if t.prior_flee_attempts is not None:  # recusa não gasta nada: preserva o teto de fuga
            t.combat_meta["flee_attempts"] = t.prior_flee_attempts
    _sync_enemy_knowledge(t.enemies)
    _reveal_resistances(t.out.get("attacks") or [], t.enemies, t.sides)
    t.logs += t.weather_logs + t.order_logs + t.out["logs"]
    # SPEC-371 R3: telegrafo/assinatura -> save (texto-fonte vigiado: test_spec371_saber)
    is_simulation = t.is_simulation
    if not is_simulation and _fauna_saber.active():
        _alive_now = not (
            t.out.get("player_dead")
            or t.player.get("dead")
            or t.player.get("estado_terminal")
            or int(t.player.get("vitalidade", 0) or 0) <= 0
        )
        t.bestiary_knowledge, _saber_logs = _fauna_saber.absorb(
            t.bestiary_knowledge, t.scene, t.actors_by_id, _alive_now, t.turn
        )
        t.status_logs += _saber_logs  # R14: texto fixo no REGISTRO/mech_log, não na prosa
        t.bk_changed = True
        if _saber_logs:  # P2-5: revelado no meio da luta -> o chip já mostra "Você sabe:"
            for _enemy in t.enemies:
                if not _enemy.get("dead"):
                    _fauna_saber.stamp_actor(_enemy, t.bestiary_knowledge)
    elif t.is_simulation and isinstance(t.scene, dict):  # P2-7: a simulação não deixa lixo na cena
        t.scene.pop("saber_obs", None)
    # Gasto BRUTO da economia da Carta. O delta líquido antes/depois era
    # incorreto para classes cujo próprio uso repõe Entropia no mesmo turno.
    player_cards = [
        used for used in (t.out.get("cards_used") or []) if used.get("actor_id") == _PLAYER_ID
    ]
    t.player["_last_entropy_spent"] = sum(
        int((used.get("economy") or {}).get("cost", 0) or 0) for used in player_cards
    )
    t.player["_last_used_active"] = bool(player_cards)
    t.player["_last_ability_id"] = player_cards[-1].get("card_id") if player_cards else None


def _combat_aftermath(t: _CombatTurn) -> None:
    """Espelho de vitais, Cicatriz, mortos/derrubados, XP e vitória."""
    t.last_player_action = _canonical_player_action(
        t.resolved_decl,
        t.out,
        attempted=(
            t.hero_fled or t.flee_requested or _PLAYER_ID in (t.out.get("resolved_turns") or [])
        ),
        flee_requested=t.flee_requested,
        hero_fled=t.hero_fled,
        flee_destination_id=t.flee_dest_id,
        chase_state=t.chase_state if t.flee_requested else None,
    )

    # ---- Espelho de vitais + Cicatrizes obrigatórias ----
    _mirror_vitals(t.player)
    for e in t.enemies:
        _mirror_vitals(e)
    for ally in t.allies:
        _mirror_vitals(ally)
    if not (t.is_simulation or t.out.get("ended") or t.hero_fled or t.out.get("player_dead")):
        _advance_reinforcements(t.scene, t.enemies, t.actors_by_id, t.sides, t.combat_meta, t.logs)
    for sid in t.out.get("scars_pending", []):
        if sid == _PLAYER_ID and death_flow.check_scar_required(t.player):
            # SPEC-346 R2/D11: no `on` a rodada não chama LLM; a Cicatriz é a determinística.
            llm = (
                None if _deck_mode_now() == "on" else get_llm(temperature=0.6, tier=ModelTier.SMART)
            )
            death_flow.generate_scar(t.player, llm)

    t.dead = [e for e in t.enemies if e.get("dead") or e.get("status") == "morto"]
    # SPEC-226 R1: só quem transitou para morto NESTA rodada gera XP/kill/evento.
    t.newly_dead = [
        e
        for e in t.dead
        if not e.get("xp_awarded") and str(e.get("id") or e.get("name")) not in t.dead_before
    ]
    # SPEC-325 R9/D2: inimigo derrubado sem matar rende o mesmo XP/loot do abate.
    t.downed = [e for e in t.enemies if e.get("incapacitated") and e.get("nonlethal_by")]
    newly_downed = [
        e
        for e in t.downed
        if not e.get("xp_awarded") and str(e.get("id") or e.get("name")) not in t.dead_before
    ]
    for e in t.newly_dead + newly_downed:
        e["xp_awarded"] = True
    for e in t.dead + t.downed:
        e["xp_awarded"] = True
    t.fauna_sim = None
    if t.newly_dead:
        t.bestiary_knowledge = disc.record_kills(t.bestiary_knowledge, t.newly_dead, t.turn)
        t.bk_changed = True
        t.fauna_sim = _fauna_carcasses(t.state, t.newly_dead)  # SPEC-360 R11

    t.player_dead = bool(t.out.get("player_dead")) or bool(t.player.get("dead"))
    t.combat_over = bool(t.out.get("ended")) or t.hero_fled or t.player_dead
    # SPEC-371 R4: fim de combate (texto-fonte vigiado: test_spec371_saber)
    combat_over, is_simulation = t.combat_over, t.is_simulation
    if combat_over and not is_simulation and _fauna_saber.active():
        t.bestiary_knowledge, _saber_logs = _fauna_saber.finish_combat(
            t.bestiary_knowledge, t.enemies, t.turn
        )
        t.status_logs += _saber_logs  # R14
        t.bk_changed = True
    if t.combat_over and not t.player_dead:
        for participant in [t.player] + t.allies:
            if (
                not participant.get("dead")
                and not participant.get("estado_terminal")
                and not death_flow.critical_spaces_full(participant)
            ):
                death_flow.reset_terminal_episode(participant)  # SPEC-231 R6
            recovery_state = death_flow.post_combat_consciousness(participant)
            participant["post_combat_state"] = recovery_state
            if recovery_state == "inconsciente":
                participant["conscious"] = False
            elif recovery_state == "acordado":
                participant["conscious"] = True
    t.victory = t.combat_over and not t.player_dead and not t.hero_fled and bool(t.dead or t.downed)
    if t.scene.get("objetivo_resultado") == "falhou":  # SPEC-331 P2-1: objetivo falho = sem espólio
        t.victory = False

    # ---- XP determinístico (fugitivo/queda letal não contam) ----
    t.level_up_events: list[dict] = []
    t.kill_xp = 0  # SPEC-226 R10: ganho individual p/ o guard narrativo
    if (t.newly_dead or newly_downed) and not t.player_dead and not t.is_simulation:
        import progression as pg

        xp = pg.xp_for_kills(t.newly_dead + newly_downed)
        if xp:
            t.player, t.level_up_events = pg.grant_xp(t.player, xp)
            t.kill_xp = xp
            # SPEC-199 R1: XP/nível NÃO entram em `logs` (nem na prosa/fallbacks);
            # chegam à UI por `last_turn_outcome` -> `turn_outcome`.


def _combat_outcome_summary(t: _CombatTurn) -> None:
    """Desfecho do encontro e resumo canônico do conflito."""
    # ---- Narração ----
    from services import prose_guard

    t.aberturas = prose_guard.ultimas_aberturas(t.messages)
    t.loc = t.state.get("world", {}).get("current_location", "")
    t.board_on = _deck_mode_now() == "on" and not t.is_simulation  # SPEC-346: `on` não narra rodada
    t.outcome_now = (
        _encounter_outcome(
            player=t.player,
            enemies=t.enemies,
            hero_fled=t.hero_fled,
            player_dead=t.player_dead,
            objective_result=t.scene.get("objetivo_resultado"),
        )
        if t.combat_over
        else None
    )
    # ---- Resumo canônico do conflito (conflito-12): antes da narração (o fallback o usa) ----
    t.conflict_sum = None
    if t.combat_over:
        participants = [t.player] + t.enemies + t.allies
        t.conflict_sum = summ.build_summary(
            participants,
            scene=t.scene,
            extras={
                "turn": t.turn,
                "conflict_id": t.combat_meta.get("instance_id"),
                # Player saves historically do not persist ``id``. Carry both
                # the canonical role and the runtime display identity so the
                # summary cannot downgrade a recoverable fall into death.
                "downed_ids": (_downed_identity_tokens(t.player) if t.player_dead else []),
            },
        )


def _compose_board_narrative(
    state: dict,
    out: dict,
    actors_by_id: dict,
    status_logs: list[str],
    *,
    extra_lines: list[str],
    combat_over: bool,
    outcome: str | None,
    conflict_sum: dict | None,
    player: dict,
    enemies: list[dict],
    player_dead: bool,
    intent: str,
    manifest: dict | None,
    source_sink: dict | None = None,
) -> str:
    """SPEC-346 R4/R11: mensagem do turno `on` = registro da rodada; no fim do conflito,
    registro + (linha em branco) + o ÚNICO resumo da IA (+ a Roda do Abismo na queda)."""
    from services import prose_guard, round_log

    if out.get("action_refused"):  # recusa explicada (Carta fora da mão, Fôlego...): nada gasto
        return (
            round_log.humanize_ids(
                "\n".join(str(x) for x in out.get("logs") or [] if x), actors_by_id
            )
            or BOARD_FREETEXT_REFUSAL
        )
    registry = round_log.round_registry(out, actors_by_id, status_logs, extra_lines=extra_lines)
    body = "\n".join(registry) or "O combate segue."
    if not combat_over:
        return body
    loc = (state.get("world") or {}).get("current_location", "")
    pack = build_context_pack(
        state,
        query=f"{loc} {intent}",
        purpose="combat_narration",
        token_budget=1200,
        include_lore=False,
    )
    summary = _narrate_outcome(
        outcome or "victory",
        conflict_sum or {},
        player,
        enemies,
        out,
        intent,
        pack.world_state_block
        + "\n"
        + _ambient_for_combat(state.get("world") or {}, player)
        + _perceived_for_combat(state),
        manifest=manifest,
        withhold=_faction_withhold_clause(
            manifest, state.get("factions"), state.get("faction_intel")
        ),
        names={
            str(k): str(a.get("name"))
            for k, a in actors_by_id.items()
            if isinstance(a, dict) and a.get("name") and not a.get("is_player")
        },
        source_sink=source_sink,
    )
    summary = prose_guard.sanitize_meta_preamble(summary)
    if player_dead:
        summary = summary.rstrip() + "\n\n" + round_log.WHEEL_TEXT
    return f"{body}\n\n{summary}"


def _fauna_carcasses(state: dict, dead: list[dict]) -> dict | None:
    """SPEC-360 R11: criatura de fauna morta deixa carcaça no local (writer: services.fauna)."""
    from services import fauna as _fauna

    if _fauna.mode() != "on":  # R12: `shadow` so registra
        return None
    world = state.get("world") or {}
    loc = str(world.get("current_location_id") or "")
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    sim = state.get("world_sim") or {}
    changed = False
    for e in dead:
        cid = disc.normalize_bestiary_id(e)
        if cid and _fauna.entry(cid):
            sim = _fauna.record_kill(sim, cid, loc, day)
            changed = True
    return sim if changed else None


def _approach_context(state: dict) -> str:
    """SPEC-360 R17: a frase de aproximação da fauna vai para a abertura, na mesma chamada."""
    line = str(((state or {}).get("combat_encounter_hint") or {}).get("aproximacao") or "")
    if not line:
        return ""
    return f"\nAPROXIMAÇÃO (o que o herói viu chegar; não contradiga): {line}"


def _board_opening_result(
    state: dict,
    messages: list,
    *,
    player: dict,
    enemies: list[dict],
    allies: list[dict],
    party: list,
    scene: dict,
    combat_meta: dict,
    combat_target,
    actors_by_id: dict,
    sides: dict,
    spawn_meta: dict,
    spawned_flavor: str | None,
    status_logs: list[str],
    intent: str,
    bestiary_knowledge: dict,
    bk_changed: bool,
) -> dict:
    """SPEC-346 R1: a história abre o tabuleiro. Entrada narrada + mão distribuída; NENHUMA
    rodada resolvida (`round == 0`). Quem age primeiro vem da cena (D4)."""
    from services import encounter_manifest as em
    from services import prose_guard

    world = state.get("world") or {}
    initiator, why = _opening_initiator(world, str(combat_meta.get("origin") or ""), player)
    combat_meta["initiator"] = initiator
    combat_meta["initiator_reason"] = why
    # Presságio da rodada 1 já visível junto com a mão (a UI o mostra antes da jogada).
    if _enemy_intent.active():
        try:
            from services import enemy_decks as _enemy_decks

            first = cs.tactical_round(scene) + 1
            forecast = _enemy_intent.forecast_round(
                scene,
                actors_by_id,
                sides,
                random,
                scene_state=({"_rodada_decisao": first} if _enemy_decks.active() else None),
            )
            combat_meta["pressagios"] = forecast
            combat_meta["pressagios_publicos"] = _enemy_intent.public_round(
                forecast, actors_by_id, first
            )
        except Exception:  # cosmético: nunca derruba a abertura
            _log_event("combat", "pressagio_forecast_failed", level="warning")
    status_logs = _normalize_status_logs(status_logs, player)  # SPEC-363 R26
    if status_logs:
        combat_meta["last_mech_log"] = list(status_logs)
    loc = world.get("current_location", "")
    pack = build_context_pack(
        state,
        query=f"{loc} {intent}",
        purpose="combat_narration",
        token_budget=1200,
        include_lore=False,
    )
    more = bool(spawn_meta.get("cut_ids")) or int(spawn_meta.get("requested_total", 0) or 0) > len(
        enemies
    )
    narrative = _narrate_entrance(
        player,
        enemies,
        spawned_flavor,
        intent,
        pack.world_state_block
        + "\n"
        + _ambient_for_combat(world, player)
        + _perceived_for_combat(state)
        + _approach_context(state),
        manifest=combat_meta.get("encounter"),
        withhold=_faction_withhold_clause(
            combat_meta.get("encounter"), state.get("factions"), state.get("faction_intel")
        ),
        aberturas=prose_guard.ultimas_aberturas(messages),
        more_requested=more,
    )
    narrative = prose_guard.sanitize_meta_preamble(narrative)
    combat_meta = em.safe_transition(combat_meta, "active")
    combat_meta["idle_turns"] = 0
    result = {
        "messages": [AIMessage(content=narrative)],
        "player": player,
        "enemies": enemies,
        "combat": combat_meta,
        "combat_target": combat_target,
        "next": None,
        "archive_due": False,
        "party": _merge_formal_party(party, allies),
        "combat_declaration": None,
        "combat_origin_hint": None,
        "combat_encounter_hint": None,
        "combat_target_ref": None,
        "player_reaction_card_id": None,
    }
    if state.get("combat_flee_attempt"):
        result["combat_flee_attempt"] = False
        result["combat_flee_destination"] = None
    if bk_changed:
        result["bestiary_knowledge"] = bestiary_knowledge
    return result


# ===========================================================================
# Fuga (chase, conflito-09) + reflexos auxiliares
# ===========================================================================
def _can_attempt_flee(player: dict) -> bool:
    """Fuga exige protagonista em fase capaz de iniciar uma perseguição."""
    return (
        bool(player.get("conscious", True))
        and not bool(player.get("dead"))
        and not bool(player.get("estado_terminal"))
        and not bool(player.get("last_stand_pending"))
        and not bool(player.get("incapacitated"))
    )


def _attempt_flee(
    scene: dict,
    player: dict,
    active: list[dict],
    sides: dict,
    rng,
    *,
    existing_chase: dict | None = None,
    intent: str = "",
    force_escape: bool = False,
) -> FleeDecision:
    """Tenta escapar via motor de perseguição (09). Enredado (root) não foge.
    Sucesso na trilha (Escapou) encerra o combate; senão o herói segue preso.

    SPEC-325: `intent` escolhe a abordagem (R10, `RPG_CHASE_APPROACH`); `force_escape`
    é o sacrifício aceito (R13: o herói escapa nesta rodada, sem teste)."""
    import combat_mechanics as cm
    from services import chase, combat_flags, combat_intents
    from services.conflict_resolution import virtude_value

    if not _can_attempt_flee(player):
        return FleeDecision(
            False,
            [f"{player.get('name', 'O herói')} está em Estado Terminal e não pode fugir."],
            {"eligible": False, "blocked_reason": "lifecycle"},
        )
    if cm.has_control(player, "root"):
        return FleeDecision(
            False,
            [f"{player.get('name', 'O herói')} está ENREDADO — impossível fugir."],
            {
                "eligible": False,
                "blocked_reason": "rooted",
            },
        )
    chase_state = (
        dict(existing_chase)
        if chase.can_resume(existing_chase, _PLAYER_ID, active)
        else chase.start_chase(scene, _PLAYER_ID, active)
    )
    previous_track = chase_state.get("trilha")
    if force_escape:
        chase_state.update(trilha="escapou", escapou=True, alcancado=False, eligible=True)
        # SPEC-364 R1/P2-2: sem dado — o `_last` da rodada anterior não pode vazar para o mech_log
        chase_state["_last"] = {"de": previous_track, "sacrificio": True}
        return FleeDecision(
            True,
            ["Você aproveita a brecha e FOGE do combate."],
            chase_state,
        )
    difficulty = chase.chase_difficulty(active[0]) if active else 12
    virtude_key = "agilidade"
    approach_mode = combat_flags.mode("chase_approach")
    approach = combat_intents.chase_approach(intent) if approach_mode != "off" else None
    if approach_mode == "on":
        chase_state.pop("approach", None)  # a abordagem vale por rodada; sem palavra = Agilidade
    if approach:
        if approach_mode == "on":
            virtude_key = chase.approach_virtude(approach)
            chase_state["approach"] = approach
            _log_event("combat", "chase_approach", approach=approach)
        else:
            _log_event("combat", "chase_approach_shadow", approach=approach)
    ally_rolls = [(aid, chase.luck_roll(rng)) for aid in (sides or {}).get("ally") or []]
    chase.resolve_chase_round(
        chase_state,
        condutor_virtude=virtude_value(player, virtude_key),
        difficulty=difficulty,
        companion_luck=[roll for _aid, roll in ally_rolls],
        rng=rng,
    )
    chase_state["_last"] = {**(chase_state.get("_last") or {}), "de": previous_track}  # SPEC-364 R1
    if combat_flags.abandon_mode() == "on":
        # R12: Sorte por aliado da rodada, base do "deixar <nome>" da rodada seguinte.
        chase_state["last_luck"] = {str(aid): roll for aid, roll in ally_rolls}
    chase_state["eligible"] = True
    if chase_state.get("escapou"):
        return FleeDecision(True, ["Você rompe o cerco e FOGE do combate."], chase_state)
    if chase_state.get("alcancado"):
        log = "Você tenta fugir, mas os inimigos te alcançam."
    elif (chase_state.get("_last") or {}).get("sucesso"):
        log = (
            f"Você avança na fuga: {chase.track_label(previous_track)} → "
            f"{chase.track_label(chase_state.get('trilha'))}."
        )
    else:
        log = (
            f"Você perde terreno na fuga: {chase.track_label(previous_track)} → "
            f"{chase.track_label(chase_state.get('trilha'))}."
        )
    return FleeDecision(False, [log], chase_state)


def _apply_weather_hazard(player: dict, world: dict, *, rng=None) -> list[str]:
    """Clima continua mecânico no conflito v2. Dano ambiental exterior reduz
    Vitalidade (não HP d20); o espelho para HP é feito no fim da rodada."""
    from world_utils import weather_effects

    effects = weather_effects(world)
    dot = int(effects.get("dot_outdoor", 0) or 0)
    if dot <= 0:
        return []
    from services.conflict_damage import resolve_damage_and_wounds

    result = resolve_damage_and_wounds(
        player,
        damage_base=dot,
        damage_type="arcano",
        ignore_resistance=True,
        defensavel=False,
        bypass_armor=True,
        directed_region=None,
        rng=rng,
    )
    label = (
        effects.get("label")
        or world.get("weather", "")
        or world.get("weather_state", "clima hostil")
    )
    return [
        f"{player.get('name', 'O herói')} sofre {dot} pelo clima ({label}) "
        f"(Vitalidade {player['vitalidade']}).",
        *result["log"],
    ]


def _register_environmental_damage_terminal(player: dict, damage_logs: list[str]) -> None:
    """Fia dano pré-rodada ao mesmo fluxo terminal usado pelos ataques.

    O clima é resolvido antes da perseguição. Sem este gate, um herói podia
    preencher o último Crítico e ainda concluir a fuga, deixando um estado vivo
    impossível fora do combate.
    """
    if not damage_logs or not death_flow.critical_spaces_full(player):
        return
    if player.get("last_stand_resolved"):
        player["dead"] = True
        player["status"] = "morto"
        player["vitalidade"] = 0
        gamedata.sync_legacy_hp_aliases(player)
        return
    if death_flow.should_trigger_last_stand(player):
        death_flow.trigger_last_stand(player)


def _apply_flee_travel(
    state: dict, result: dict, flee_dest_id: str, player: dict, logs: list[str]
) -> None:
    import world_utils as wu
    from gamedata import get_location
    from services import npc_layers

    dest = get_location(flee_dest_id)
    if not dest:
        return
    base_world = result.get("world") or wu.ensure_world(dict(state.get("world") or {}))
    result["world"] = wu.apply_travel(base_world, dest)
    base_npcs = result.get("npcs")
    if base_npcs is None:
        base_npcs = state.get("npcs", {})
    result["npcs"] = npc_layers.reset_scene(base_npcs)
    previous_combat = result.get("combat") or {}
    result["combat"] = {
        "active": False,
        "round": int(previous_combat.get("round", 0) or 0),
        "idle_turns": 0,
        "scene": None,
        "origin": "unknown",
        # Recibo do turno atual: o harness o consome uma vez a partir do update
        # do nó. Não é estado de perseguição e preserva a auditabilidade.
        "last_player_action": dict(previous_combat.get("last_player_action") or {}),
    }
    # SPEC-203: o desfecho (fase/manifesto/resultado) sobrevive à viagem de fuga.
    for key in ("phase", "outcome", "encounter", "result"):
        if key in previous_combat:
            result["combat"][key] = previous_combat[key]
    result["enemies"] = []
    result["combat_target"] = None
    result["next"] = None
    result["needs_replan"] = True
    result["combat_origin_hint"] = None


def _reflect_scene_allies(
    state: dict, scene_tr: list[dict], allies: list[dict], combat_over: bool
) -> dict:
    """Aliado TRANSITÓRIO reflete Vitalidade/morte no NPC de origem (sem 'aliado
    imortal'). Não vira party permanente."""
    npcs_out = {**(state.get("npcs") or {})}
    by_name = {(a.get("name") or a.get("id")): a for a in allies}
    for tr in scene_tr:
        name = tr.get("name") or ""
        key = next(
            (
                k
                for k in npcs_out
                if k == name or (isinstance(npcs_out[k], dict) and npcs_out[k].get("name") == name)
            ),
            None,
        )
        if key is None or not isinstance(npcs_out.get(key), dict):
            continue
        live = by_name.get(name) or tr
        npc = {**npcs_out[key]}
        npc["vitalidade"] = int(live.get("vitalidade", 0) or 0)
        npc["max_vitalidade"] = int(live.get("max_vitalidade", 1) or 1)
        import gamedata

        gamedata.sync_legacy_hp_aliases(npc)
        if live.get("dead") or live.get("status") == "morto":
            # SPEC-230 R4: mesmo formato de apply_npc_death (status/in_scene/died_turn).
            npc["status"] = "morto"
            npc["in_scene"] = False
            npc.setdefault("died_turn", int((state.get("world") or {}).get("turn_count", 0) or 0))
        npcs_out[key] = npc
    return npcs_out


def _merge_formal_party(party: list[dict], live_allies: list[dict]) -> list[dict]:
    """Persiste a ficha v4 mutada dos companheiros formais (transitórios ficam fora)."""
    live_by_id = {
        str(a.get("id") or a.get("name")): a for a in live_allies if not a.get("transient")
    }
    merged: list[dict] = []
    for companion in party:
        key = str(companion.get("id") or companion.get("name"))
        live = dict(live_by_id.get(key) or companion)
        _mirror_vitals(live)
        merged.append(live)
    return merged
