"""SPEC-381: montagem de resposta da API (movida de api.py, sem mudanca)."""

import time
from typing import Any
from observability.telemetry import log_fallback
import gamedata
import persistence as persistence_module
import progression
from llm_setup import is_simulated
from persistence import _serialize_messages
from services import combat_flags
from services.checkout_retry import retry_once
from services import portrait_offer
from services.portrait_offer_log import log_offer_omitted
from services import enemy_intent as _enemy_intent
from services import npc_world as _npc_world
from services import quest_log
from services import state_views as sv
from services.visual_catalog import visual_response
from services.reputation import faction_tier
import api_core
from api_models import GameResponse


# --- HELPER: FORMATA RESPOSTA ---
def _npc_display_label(label: str, subject_id: str, state: dict | None) -> str:
    """Display name for an NPC art offer — never a raw `runtime_npc:<slug>` token."""
    from services.visual_catalog import _runtime_token

    for raw in (label, subject_id):
        if raw and not raw.startswith("runtime_npc:"):
            return raw
    token = subject_id or label
    for npc in ((state or {}).get("npcs") or {}).values():
        name = str((npc or {}).get("name") or "") if isinstance(npc, dict) else ""
        if name and _runtime_token(name) == token:
            return name
    slug = token.split(":", 1)[-1].replace("_", " ").strip()
    return slug[:1].upper() + slug[1:] if slug else ""


def _public_art_offer(row: dict, state: dict | None = None) -> dict:
    """Offer reference for the UI: id/type plus the (already sanitized) subject label so the
    client can name and dedupe per NPC."""
    out = {"offer_id": row["offer_id"], "type": row["type"]}
    if row.get("type") == "npc":
        trigger = row.get("trigger") if isinstance(row.get("trigger"), dict) else {}
        brief = row.get("brief") if isinstance(row.get("brief"), dict) else {}
        subject_id = str(trigger.get("subject_id") or "")
        label = _npc_display_label(str(brief.get("subject") or ""), subject_id, state)
        if subject_id:
            out["subject_id"] = subject_id
        if label:
            out["label"] = label
    return out


def _public_art_refs(state: dict) -> dict:
    """Public references from the owner-scoped save; private quotes never enter UI."""
    generations = []
    for row in state.get("art_generation_ledger") or []:
        image_type = row.get("subject_type") or (
            "player" if row.get("trigger_kind") == "player_portrait" else None
        )
        if row.get("generation_id") and image_type in {"player", "npc", "scene"}:
            generations.append(
                {
                    "generation_id": str(row["generation_id"]),
                    "type": image_type,
                    "subject_id": str(row.get("subject_id") or "player"),
                }
            )
    return {
        "art_generations": generations,
        "art_offers": [_public_art_offer(row, state) for row in state.get("art_offers") or []],
    }


def _response_speaker(state: dict) -> dict[str, str]:
    from services.interlocutor import response_speaker

    return response_speaker(state)


def format_response(state: dict, *, cue_action_key: str | None = None) -> GameResponse:
    """SPEC-293 R3: toda resposta de turno/estado passa pelo rótulo de exibição por
    observador (combatente de fação desconhecida aparece só pelo papel)."""
    from services.faction_display import conceal_payload, concealed_name_map

    response = _format_response_raw(state, cue_action_key=cue_action_key)
    mapping = concealed_name_map(state)
    if not mapping:
        return response
    return GameResponse.model_validate(conceal_payload(response.model_dump(), mapping))


def _format_response_raw(state: dict, *, cue_action_key: str | None = None) -> GameResponse:
    # Pega a última mensagem
    from services.turn_outcome import player_facing_message

    last_content = player_facing_message(state)

    from services.presentation_history import message_kind

    msg_type = message_kind(state)

    player = state["player"]
    vitality = int(player.get("vitalidade", 0) or 0)
    max_vitality = int(player.get("max_vitalidade", vitality) or vitality)
    simulation = dict(state.get("combat_simulation") or {})
    if simulation.get("enabled"):
        active = bool((state.get("combat") or {}).get("active"))
        simulation["finished"] = not active
        simulation["outcome"] = (
            "defeat" if state.get("death_pending") else "victory" if not active else None
        )
    from services.turn_outcome import public_outcome

    turn_outcome = (
        {} if simulation.get("enabled") else public_outcome(state.get("last_turn_outcome"))
    )
    from services.projections import projection_status_view

    return GameResponse(
        projections=projection_status_view(state),
        turn_outcome=turn_outcome,
        combat_result={} if simulation.get("enabled") else _combat_result(state),
        timeline_epoch=int((state.get("continuity") or {}).get("timeline_epoch", 0)),
        portrait_generation_id=next(
            (
                str(row["generation_id"])
                for row in reversed(state.get("art_generation_ledger") or [])
                if row.get("trigger_kind") == "player_portrait" and row.get("generation_id")
            ),
            None,
        ),
        game_id=state.get("game_id", "unknown"),
        message=last_content,
        message_type=msg_type,
        speaker=_response_speaker(state),
        player_stats={
            "name": player.get("name", "Herói"),
            "class_name": player.get("class_name") or player.get("class", ""),
            "race": player.get("race", ""),
            "vitalidade": vitality,
            "max_vitalidade": max_vitality,
            "ferimentos": player.get("ferimentos", {}),
            "dead": bool(player.get("dead")),
            "estado_terminal": bool(player.get("estado_terminal")),
            # aliases públicos derivados — nunca lidos de volta como mecânica
            "hp": vitality,
            "max_hp": max_vitality,
            # spec refatoracao-sistema-classes (R11): Entropia (barra) + Carga do
            # Abismo (chip por patamar). Médico é oculto (abyss.hidden) → label vago.
            "entropy": player.get("entropy", 0),
            "max_entropy": player.get("max_entropy", 0),
            "abyss_charge": player.get("abyss_charge", 0),
            "abyss_tier": _abyss_tier_view(player),
            "defense": player.get("defense", 0),
            "gold": player.get("gold", 0),
            "level": player.get("level", 1),
            "xp": player.get("xp", 0),
            "cards": _cards_block(player),
            # SPEC-209 R5/R9: aditivos — servidor decide se pode reorganizar; cicatrizes
            # são a projeção pública do que já está no save (sem inventar turno).
            "can_reorganize": _can_reorganize_view(state),
            "prepared_slots": _prepared_slots(player),
            **({"baralho": _deck_view(player)} if _deck_view(player) else {}),
            "scars": _scars_view(player),
            "subclass": str(player.get("subclass") or ""),
            "virtue_cards": _virtue_cards_view(player),
            "evolvable_card_ids": _evolvable_card_ids(player),
            "virtudes": dict(player.get("virtudes") or {}),
            "xp_next_level": progression.xp_to_next(int(player.get("level", 1) or 1)),
            "pending_choices": player.get("pending_choices", []) or [],
            "level_up": _levelup_block(player),
            **_card_reward_blocks(state),  # SPEC-333: so existem com RPG_CARD_REWARDS=on
        },
        inventory=_inventory_block(state["player"]),
        current_location=state["world"]["current_location"],
        narrative_summary=state.get("narrative_summary", ""),
        last_turn_log=_serialize_messages(state["messages"][-5:]),
        # Auditoria A4: espelha a decisão real do get_llm (qualquer provider conta)
        simulated=is_simulated(),
        world=_world_block(
            state.get("world", {}) or {},
            state.get("world_projection", {}) or {},
            state.get("event_log", []) or [],
            state.get("player", {}) or {},
            state.get("world_sim"),
            state=state,
        ),
        quest=_quest_block(
            state.get("campaign_plan") or {},
            _npc_world.public_quests(state),  # SPEC-304: missao de destino nao percebido
            state.get("world") or {},
        ),
        combat=_combat_block(state),
        npcs=_npcs_block(state.get("npcs", {}) or {}, state),
        **_public_art_refs(state),
        chronicle=_chronicle_block(state.get("chronicle", []) or []),
        party=[
            {
                "name": c.get("name", "?"),
                "vitalidade": int(c.get("vitalidade", 0) or 0),
                "max_vitalidade": int(c.get("max_vitalidade", 1) or 1),
                "hp": int(c.get("vitalidade", 0) or 0),
                "max_hp": int(c.get("max_vitalidade", 1) or 1),
                "active": bool(c.get("active")),
                "archetype": c.get("archetype", ""),
                "status": c.get("status", "ativo"),
                **_companion_labels(state, c),
            }
            for c in _npc_world.public_party(state)  # SPEC-304 P1-2: o que o jogador viu
        ],
        companion_feedback=_companion_feedback(state),
        reputation_notices=_reputation_notices(state),
        factions=_factions_block(
            state.get("factions", []) or [],
            state.get("faction_intel", {}) or {},
            (state.get("world", {}) or {}).get("turn_count", 0),
            state.get("event_log", []) or [],
            state.get("world_projection", {}) or {},
            state=state,
        ),
        death_pending=bool(state.get("death_pending", False)),
        game_over=bool(state.get("game_over", False)),
        death=_death_block(state),
        continuity=_continuity_block(state),
        combat_simulation=simulation,
        visual=visual_response(state, cue_action_key=cue_action_key),
    )


def _companion_labels(state: dict, comp: dict) -> dict[str, str]:
    """SPEC-300 R29: rótulos vagos do companheiro. NUNCA o número de aprovação nem os valores."""
    from services import companion_soul as cs

    if cs.mode() != "on":
        return {}
    soul = (state.get("companion_souls") or {}).get(cs.comp_id(comp)) or {}
    if not isinstance(soul, dict) or "approval" not in soul:
        return {}
    out = {"approval_label": cs.approval_label(soul.get("approval", 50))}
    if soul.get("romance") == "vinculo":
        out["bond_label"] = "vínculo"
    elif soul.get("romance") == "compromisso":
        out["bond_label"] = "compromisso"
    return out


def _companion_feedback(state: dict) -> list[str]:
    from services import companion_soul as cs

    if cs.mode() != "on":
        return []
    return [str(t) for t in (state.get("companion_feedback") or []) if isinstance(t, str)]


def _reputation_notices(state: dict) -> list[dict[str, str]]:
    """SPEC-298 R26: avisos do turno corrente, textos fixos, passados pela projeção SPEC-293."""
    from services.faction_display import conceal_for

    turn = int((state.get("world") or {}).get("turn_count", 0) or 0)
    rows = [
        {
            "kind": str(n.get("kind", "")),
            "subject_id": str(n.get("subject_id", "")),
            "text": str(n.get("text", "")),
        }
        for n in (state.get("reputation_notices") or [])
        if isinstance(n, dict) and int(n.get("turn", -1) or 0) == turn
    ]
    return conceal_for(state, rows)


def _inventory_block(player: dict) -> list[dict[str, Any]]:
    """Fase 4.3: inventário estruturado com nome canônico (nunca title() sobre id)."""
    import inventory as inv_mod
    from gamedata import ARTIFACTS_DB

    eq = player.get("equipment") or {}
    equipped = {v: k for k, v in eq.items() if v}
    out = []
    for e in player.get("inventory") or []:
        if not isinstance(e, dict):  # tolerância a estado antigo em memória
            e = inv_mod.make_entry(str(e), 1)
        item = ARTIFACTS_DB.get(e.get("id", "")) or {}
        out.append(
            {
                "id": e.get("id"),
                "name": inv_mod.item_display(e),
                "qty": int(e.get("qty", 1)),
                "type": item.get("type", "desconhecido"),
                "equipped": e.get("id") in equipped,
                "slot": equipped.get(e.get("id")) or inv_mod.slot_for(e.get("id", "")),
                "unique": bool(item.get("unique")),  # Fase 6.2: ◆ um por mundo
            }
        )
    return out


def _abyss_tier_view(player: dict) -> str:
    """spec refatoracao-sistema-classes (R11): patamar da Carga do Abismo p/ o HUD.
    Classe com `abyss.hidden` (Médico — Recidiva) NÃO expõe o valor: label enigmático."""
    import combat_mechanics as _cm

    cfg = _cm.entropy_config(player)
    if (cfg.get("abyss") or {}).get("hidden"):
        # SPEC-235 R8: sem Carga não há o que ocultar — chip some até acumular.
        return "?" if int(player.get("abyss_charge", 0) or 0) > 0 else "nenhum"
    return _cm.abyss_tier(player)


def _card_reward_blocks(state: dict) -> dict[str, Any]:
    """SPEC-333: blocos `espolio_pendente` (painel pos-conflito) e `forja` (aba Combate fora
    de encontro). Vazio com a flag `off`/sem o que mostrar: o contrato antigo nao muda."""
    from services import card_rewards

    out: dict[str, Any] = {}
    player = state.get("player") or {}
    pending = card_rewards.public_pending(player)
    if pending is not None:
        out["espolio_pendente"] = pending
    forge = card_rewards.public_forge(state)
    if forge is not None:
        out["forja"] = forge
    from services import card_shop  # SPEC-357: Técnicas à venda (mesma flag; D1)

    shop = card_shop.public_shop(state)
    if shop is not None:
        out["loja_cartas"] = shop
    return out


def _can_reorganize_view(state: dict) -> dict[str, Any]:
    from services import cards

    allowed, reason = cards.reorganize_status(state)
    return {"allowed": bool(allowed), "reason": reason}


def _deck_mode_on(player: dict) -> bool:
    from services import card_piles

    return card_piles.mode() == "on" and bool(player.get("deck"))


def _prepared_slots(player: dict) -> int:
    from services import cards

    if _deck_mode_on(player):  # SPEC-353 R31: com o Baralho `on` o teto que vale é o do Baralho
        return int(cards.DECK_MAX)
    return int(cards.prepare_slots_for_level(player.get("level", 1)))


def _deck_view(player: dict) -> dict[str, int] | None:
    """SPEC-353 R31: a API diz qual modelo vale (Baralho 12-24 em vez da Preparação por nível)."""
    from services import cards

    if not _deck_mode_on(player):
        return None
    deck = [str(c) for c in player.get("deck") or []]
    basics = {
        cid
        for ids in cards.basicas_for_class(str(player.get("class_name", ""))).values()
        for cid in ids
    }
    return {
        "total": len(deck),
        "minimo": int(cards.DECK_MIN),
        "maximo": int(cards.DECK_MAX),
        "do_acervo": sum(1 for c in deck if c not in basics),
    }


def _virtue_cards_view(player: dict) -> list[dict[str, Any]]:
    from services import cards

    out = []
    for row in player.get("virtue_cards") or []:
        cid = str(row.get("card_id") or "")
        card = cards.get_card(cid) or {}
        out.append(
            {
                "card_id": cid,
                "name": card.get("name", cid),
                "type": str(card.get("tipo", "")),
                "description": card.get("descricao", ""),
                "virtude": str(row.get("virtude") or ""),
                "mastery": int(row.get("mastery", 0) or 0),
                "effective_stage": int(row.get("effective_stage", 0) or 0),
            }
        )
    return out


def _evolvable_card_ids(player: dict) -> list[str]:
    from services import cards

    if int(player.get("level", 1) or 1) < 4:
        return []
    done = player.get("evolved_cards") or {}
    return [
        cid
        for cid in player.get("known_cards") or []
        if (cards.get_card(cid) or {}).get("evolucao") and cid not in done
    ]


def _scars_view(player: dict) -> list[dict[str, str]]:
    out = []
    for scar in player.get("scars") or []:
        if not isinstance(scar, dict):
            continue
        out.append(
            {
                k: str(scar.get(k) or "")
                for k in (
                    "id",
                    "origem",
                    "consequencia_negativa",
                    "habilidade_positiva_relacionada",
                )
            }
        )
    return out


def _cards_block(player: dict, *, prepared_only: bool = False) -> list[dict[str, Any]]:
    """View autoral + disponibilidade mecânica das Cartas.

    O frontend nunca tenta reproduzir frequência/custo por conta própria: recebe
    o contador já interpretado, mas o motor ainda revalida no uso.
    """
    import combat_mechanics as cm
    from services import card_piles, card_text, cards

    if card_piles.mode() == "off" and "prepared_cards_pre_deck" in player:
        player = dict(player)  # SPEC-368 R1: view sem mutar o chamador
        card_piles.sync_deck_mode(player)
    prepared = set(player.get("prepared_cards") or [])
    if _deck_mode_on(player):  # SPEC-353 R31: "preparada" = "está no baralho"
        prepared = set(player.get("deck") or [])
    evolved = player.get("evolved_cards") or {}
    entropy = int(player.get("entropy", 0) or 0)
    out = []
    for cid in player.get("known_cards") or []:
        card = cards.get_card(cid) or {}
        is_prepared = cid in prepared
        if prepared_only and not is_prepared:
            continue
        frequency = str(card.get("frequencia", "livre"))
        counter = cards.FREQ_COUNTER.get(frequency)
        usage = (player.get("card_usage") or {}).get(cid) or {}
        spent = bool(counter and int(usage.get(counter, 0) or 0) >= 1)
        base_cost = int(card.get("custo_entropia", 0) or 0)
        cost = cm.dependencia_cost(player, base_cost)
        kind = str(card.get("tipo", ""))
        effect_kind = str((card.get("efeito") or {}).get("kind") or "")
        friendly = effect_kind in {
            "cura",
            "estabilizar",
            "protecao",
            "reposicionar",
            "esconder",
            "purga_condicao",
            "vantagem",
            "buff_defesa",
            "buff_acerto",
            "buff_dano",
            "reduzir_carga_aliado",
        }
        ready = bool(is_prepared and kind in ("ativa", "reacao") and not spent and cost <= entropy)
        out.append(
            {
                "id": cid,
                "name": card.get("name", cid),
                "type": kind,
                "description": card.get("descricao", ""),
                "effect_kind": effect_kind,
                "target_kind": "self" if friendly else "enemy",
                "subclass": card_text.subclass_label(card),
                "prepared": is_prepared,
                "cost": cost,
                "base_cost": base_cost,
                "frequency": frequency,
                "spent": spent,
                "ready": ready,
                "has_rupture": bool(card.get("ruptura")),
                "rupture_ready": bool(ready and kind == "ativa" and card.get("ruptura")),
                "trigger": card.get("gatilho", ""),
                "evolved": evolved.get(cid),
                "texto": card_text.effective_rule_text(player, card),  # SPEC-353 R18
            }
        )
    return out


def _death_block(state: dict) -> dict[str, Any]:
    player = state.get("player") or {}
    combat = state.get("combat") or {}
    context = combat.get("death_context") or {}
    last_action = context.get("last_action") or combat.get("last_player_action")
    last_action_label = ""
    if isinstance(last_action, dict) and last_action.get("kind") == "card":
        from services import cards

        card = cards.get_card(str(last_action.get("card_id") or "")) or {}
        last_action_label = str(card.get("name") or last_action.get("card_id") or "")
    continuity = _continuity_block(state)
    canonical = int(continuity.get("canonical_turn", 0) or 0)
    # SPEC-228 R6/R10: o turno de retorno vem do checkpoint REAL em disco.
    checkpoint: int | None = None
    if state.get("game_id"):
        try:
            checkpoint = persistence_module.checkpoint_turn(str(state["game_id"]))
        except Exception:
            checkpoint = None
    return {
        "pending": bool(state.get("death_pending")),
        "last_action": last_action,
        "last_action_label": last_action_label,
        "entered_terminal": bool(context.get("entered_terminal") or player.get("estado_terminal")),
        "stabilization": context.get("stabilization", ""),
        "stabilization_attempts": int(
            context.get("stabilization_attempts", player.get("stabilization_attempts", 0)) or 0
        ),
        "killer": context.get("killer", ""),
        "will_restore_turn": checkpoint,
        "will_lose_turns": (max(0, canonical - checkpoint) if checkpoint is not None else None),
        "retained": ["histórico de mortes", "contagem de ações da sessão"],
        "reverted": ["mundo", "inventário", "posição e memória após o checkpoint"],
    }


def _continuity_block(state: dict) -> dict[str, Any]:
    from services.continuity import normalize

    canonical = int((state.get("world") or {}).get("turn_count", 0) or 0)
    meta = normalize(state.get("continuity"), canonical_turn=canonical)
    return {**meta, "canonical_turn": canonical}


def _levelup_block(player: dict) -> dict[str, Any]:
    """Escolhas pendentes + Cartas elegíveis/evoluções."""
    pending = player.get("pending_choices", []) or []
    if not pending:
        return {}
    from services import card_text, cards

    eligible = []
    for cid in progression.eligible_cards(player):
        card = cards.get_card(cid) or {}
        eligible.append(
            {
                "id": cid,
                "name": card.get("name", cid),
                "description": card.get("descricao", ""),
                "subclass": card_text.subclass_label(card),
                "tier": int(card.get("tier", 1) or 1),
                "tier_label": gamedata.TIER_LABELS.get(int(card.get("tier", 1) or 1), ""),
                "level_req": int(card.get("level_req", 1) or 1),
                "apex": bool(card.get("apex")),
                "cost": int(card.get("custo_entropia", 0) or 0),
                "frequency": card.get("frequencia", "livre"),
                "kind": card.get("tipo", "ativa"),
            }
        )
    evolvable = [
        {"id": cid, "name": (cards.get_card(cid) or {}).get("name", cid)}
        for cid in player.get("known_cards") or []
        if (cards.get_card(cid) or {}).get("evolucao")
        and cid not in (player.get("evolved_cards") or {})
        and int(player.get("level", 1) or 1) >= 4
    ]
    return {
        "pending": pending,
        "eligible": eligible,
        "evolvable": evolvable,
        "current_branch": progression.player_branch(player),
        "subclasses": progression.eligible_subclasses(player)
        if any(row.get("kind") == "subclass" for row in pending)
        else [],
        "virtue_cards": [
            {
                "card_id": row.get("card_id"),
                "virtude": row.get("virtude"),
                "mastery": int(row.get("mastery", 0) or 0),
                "effective_stage": progression.effective_virtue_card_stage(row),
            }
            for row in player.get("virtue_cards") or []
        ],
        "unlocked_tier": gamedata.card_tier_for_level(int(player.get("level", 1) or 1)),
        "prepared_slots": gamedata.prepared_slots_for_level(player.get("level", 1)),
    }


def _chronicle_block(chronicle: list) -> list[dict[str, Any]]:
    """Capítulos da crônica para o HUD (Fase 3.1) — filtra entradas vazias."""
    out: list[dict[str, Any]] = []
    for cap in chronicle:
        if not isinstance(cap, dict):
            continue
        entries = [
            e
            for e in (cap.get("entries") or [])
            if isinstance(e, dict) and str(e.get("text", "")).strip()
        ]
        out.append(
            {
                "chapter_id": cap.get("chapter_id", ""),
                "title": cap.get("title", ""),
                "started_turn": cap.get("started_turn", 0),
                "location": cap.get("location", ""),
                "entries": entries,
                "digest": cap.get("digest"),
                "entry_count": len(entries),
            }
        )
    return out


def _recent_changes(row: dict) -> list[dict[str, Any]]:
    """Até 3 mudanças recentes {turn, text} (avisos já emitidos; sem número)."""
    return [
        {"turn": int(r.get("turn", 0) or 0), "text": str(r.get("text", ""))}
        for r in (row.get("recent_changes") or [])
        if isinstance(r, dict)
    ][-3:]


def _factions_block(
    factions: list,
    intel: dict,
    turn: int = 0,
    event_log: list | None = None,
    projection: dict | None = None,
    state: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Fações para o HUD — não-onisciência: só as que o jogador CONHECE (intel.known).
    Objetivo só se aprendido; progresso é o SNAPSHOT que o jogador viu (nunca o ao vivo);
    fações eliminadas somem. Fase 3.4: history/stability_label são views derivadas do
    event_log/projection — só pra fações já filtradas por known (não vaza timeline de
    fação desconhecida).
    """
    intel = intel or {}
    out = []
    for f in factions:
        if not isinstance(f, dict):
            continue
        if f.get("defeated"):
            continue
        rec = intel.get(f.get("id", ""), {})
        if not rec.get("known"):
            continue  # jogador nunca ouviu falar desta facção
        knows_goal = bool(rec.get("knows_goal"))
        seen = rec.get("progress_seen")
        intel_turn = rec.get("intel_turn")
        stale = seen is not None and isinstance(intel_turn, int) and int(turn) > int(intel_turn)
        fid = f.get("id", "")
        # SPEC-301 R22: vínculo só como rótulos/texto (nunca mérito, influência ou awareness).
        membership = None
        if state is not None and state.get("faction_membership"):
            from services.faction_membership import membership_view

            membership = membership_view(state, fid)
        out.append(
            {
                "id": fid,
                "name": f.get("name", ""),
                "goal": f.get("goal", "") if knows_goal else "",
                "knows_goal": knows_goal,
                "region": f.get("region", ""),
                "progress": int(seen) if seen is not None else None,
                "intel_stale": bool(stale),
                # SPEC-298 R27: só rótulo + mudanças recentes (sem número de reputação).
                # D8: `standing_label` (faixa da fação) != `disposition` interna (hostil/neutro/aliado).
                "standing_label": faction_tier(f.get("reputation", 0)),
                "recent_changes": _recent_changes(f),
                "completed": bool(f.get("completed", False)),
                "stability_label": sv.stability_label(projection or {}, fid),
                **({"membership": membership} if membership else {}),
            }
        )
    return out


def _npcs_block(npcs: dict, state: dict | None = None) -> list[dict[str, Any]]:
    """Camada 2 (spec npcs-3-camadas): só NPCs conhecidos, com traits REVELADOS
    — hidden_traits NUNCA sai pela API (R9). SPEC-211: com `state`, NPC de entidade
    `hidden`/`secret` sem reveal aceito (regra fail-closed da SPEC-206) também some."""
    from services.npc_layers import visible_npc_view

    if state is not None:
        from services.entity_identity import resolve_npc_entity_id
        from services.player_knowledge import entity_is_player_visible

        npcs = {
            key: npc
            for key, npc in (npcs or {}).items()
            if not isinstance(npc, dict)
            or entity_is_player_visible(
                resolve_npc_entity_id(npc, str(npc.get("name", key))), state
            )
        }
    out = visible_npc_view(npcs, state)  # SPEC-304 R23: crenca do jogador, nao a verdade
    return out


def _simulation_manifest(enemies: list, game_id: str, scene: dict) -> dict:
    from services import encounter_manifest as em

    return em.build_manifest(
        enemies, source="simulation", origin="unknown", encounter_id=f"{game_id}:sim", scene=scene
    )


def _combat_result(state: dict) -> dict[str, Any]:
    """SPEC-203 R7: desfecho do turno de término, derivado de estado persistido."""
    from services import encounter_manifest as em
    from services.turn_outcome import public_outcome

    return em.result_view(state.get("combat"), public_outcome(state.get("last_turn_outcome")))


def _targeting_cards(state: dict, cards_view: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SPEC-205 R7: `valid_targets`/`invalid_reason` por Carta, calculados em Python."""
    from services import combat_targeting as targeting

    for row in cards_view:
        row.update(targeting.card_targeting(state, str(row.get("id"))))
    return cards_view


def _chase_live_for_api(chase: object) -> bool:
    return (
        isinstance(chase, dict)
        and chase.get("eligible") is not False
        and not chase.get("alcancado")
        and not chase.get("escapou")
    )


_PORTRAIT_PRICE_CACHE: dict[str, Any] = {"at": 0.0, "value": None, "milli": None}


_PORTRAIT_SIGN_CACHE: dict[tuple[str, str], tuple[float, str]] = {}


def _creature_art_live() -> bool:
    """SPEC-352: registro + oferta paga só com a flag `on`, perfil com banco e arte dinâmica ligada
    (SPEC-389: fonte única com a causa reportada, `portrait_offer.art_cause`)."""
    from services import creature_art as _art

    return portrait_offer.art_cause(_art.mode() == "on", api_core._database_profile()) is None


def _image_effect_open() -> bool:
    """SPEC-363 R2: mesmo portão da cotação como predicado sem exceção (SPEC-389: causa no tally)."""
    return portrait_offer.gate()[0]


def _portrait_offer_price() -> int | None:
    """SPEC-363 R2: preço da oferta paga; `None` quando a cotação seria recusada."""
    if not _image_effect_open():
        return None
    return _portrait_price_estilhas()


def _portrait_price_estilhas() -> int | None:
    """R11: teto da cotação em Estilhas INTEIRAS, só leitura, cache de 60 s só para preço válido."""
    return portrait_offer.price_estilhas(_PORTRAIT_PRICE_CACHE)


def _portrait_offer_milli(estilhas: int | None) -> int | None:
    """SPEC-364 R18: o teto exato em milli, só se bate com o inteiro cotado (cache coerente)."""
    milli = _PORTRAIT_PRICE_CACHE.get("milli")
    if not milli or estilhas is None or -(-int(milli) // 1000) != int(estilhas):
        return None
    return int(milli)


def _portrait_sign(store: str, key: str) -> str | None:
    """R11: URL assinada (1 h) do thumb, cache de 50 min por object key. Nunca devolve a key crua."""
    cache_key = (store, key)
    now = time.monotonic()
    hit = _PORTRAIT_SIGN_CACHE.get(cache_key)
    if hit and now - hit[0] < 50 * 60:
        return hit[1]
    try:
        from infrastructure.runtime import get_runtime

        runtime = get_runtime()
        blobs = runtime.shared_blob_store if store == "shared" else runtime.blob_store
        url = blobs.signed_url(key, 3600)
    except Exception as exc:
        log_fallback("creature_portrait", "sign_failed", exc)
        return None
    if len(_PORTRAIT_SIGN_CACHE) > 512:
        _PORTRAIT_SIGN_CACHE.clear()
    _PORTRAIT_SIGN_CACHE[cache_key] = (now, url)
    return url


def _portrait_store(runtime: Any = None):
    """Registro de retratos (`app.creature_portraits`); leitura só pelo dono `PostgresPortraitRegistry`."""
    from infrastructure.runtime import get_runtime
    from services.creature_portraits import PostgresPortraitRegistry

    return PostgresPortraitRegistry((runtime or get_runtime()).resources[0])


def _portrait_manifest_ctx(state: dict, meta: dict) -> tuple[dict | None, str | None]:
    from services import encounter_manifest as _em

    manifest = meta.get("encounter") if _em.is_valid_manifest(meta.get("encounter")) else None
    npc_entity_id = None
    ref = str((manifest or {}).get("target_ref") or "")
    if ref.startswith("npc:"):
        npc = (state.get("npcs") or {}).get(ref[4:]) or {}
        npc_entity_id = str(npc.get("entity_id") or "") or None
    return manifest, npc_entity_id


def _portrait_registry(state: dict, meta: dict, enemies: list[dict]):
    """R11: UMA leitura do registro por resposta (nunca uma por inimigo). `None` fora do perfil com banco."""
    if enemies:  # SPEC-389 R2: o offer_view é só de resposta com inimigo vivo
        portrait_offer.begin(_creature_art_live(), str(state.get("game_id") or ""))
    if not _creature_art_live():
        return None
    from services import creature_art as _art
    from services.creature_portraits import SnapshotRegistry

    game_id = str(state.get("game_id") or "")
    manifest, npc_entity_id = _portrait_manifest_ctx(state, meta)
    keys: list[str] = []
    known: list[str] = []
    for enemy in enemies:
        keys.append(
            _art.portrait_key(enemy, manifest, game_id=game_id, npc_entity_id=npc_entity_id)
        )
        keys.append(_art._type_key(enemy))
    if npc_entity_id:
        known.append(f"npc:{npc_entity_id}")  # o NPC está em cena: já é conhecido do jogador
    try:
        store = _portrait_store()
        rows = retry_once(lambda: store.get_many(keys, game_id=game_id, npc_known=known))
    except Exception as exc:
        log_offer_omitted("registry_read_failed", exc)
        return None
    return SnapshotRegistry(rows, sign=_portrait_sign)


def _enemy_portrait(
    state: dict, meta: dict, enemy: dict, registry: Any = None
) -> dict[str, Any] | None:
    """SPEC-347 R13.7 / SPEC-354 R6: `retrato` por inimigo SEMPRE (arte curada ou ícone da família), com a
    flag `RPG_CREATURE_ART` ligada ou não. Sem LLM, sem vazar ficha secreta: só id/nome/família. SPEC-352:
    com o registro (perfil com banco e flag `on`) a view mostra o retrato compartilhado e, se elegível,
    `gerar` (preço = teto da cotação); com a flag `off` não há registro nem oferta."""
    from services import creature_art as _art

    if _art.mode() != "on":
        registry = None
    manifest, npc_entity_id = _portrait_manifest_ctx(state, meta)
    offer_price = _portrait_offer_price() if registry is not None else None
    reasons: list[str] = []
    portrait = dict(
        _art.portrait_for(
            enemy,
            manifest,
            game_id=str(state.get("game_id") or ""),
            npc_entity_id=npc_entity_id,
            registry=registry,
            quote_price=offer_price,
            quote_milli=_portrait_offer_milli(offer_price),
            sign=_portrait_sign if registry is not None else None,
            reasons=reasons,
        )
    )
    portrait_offer.record(
        portrait,
        reasons,
        registry is not None,
        portrait_offer.art_cause(_art.mode() == "on", api_core._database_profile()),
    )
    return portrait


class _ParticipantNames(dict):
    """SPEC-353 R23: nome exibível do participante — nunca o id cru (cai em ``state["npcs"]`` e,
    por fim, em "Aliado"/"Inimigo")."""

    def __init__(self, state: dict, meta: dict, enemies: list) -> None:
        super().__init__()
        self._npcs = state.get("npcs") or {}
        self._enemy_ids = {str(e.get("id")) for e in enemies if isinstance(e, dict)}

    def get(self, key, default=None):  # type: ignore[override]
        if key in self:
            return self[key]
        key = str(key)
        for npc_key, npc in self._npcs.items() if isinstance(self._npcs, dict) else ():
            if isinstance(npc, dict) and key in (str(npc_key), str(npc.get("id"))):
                if npc.get("name"):
                    return str(npc["name"])
        return "Inimigo" if key in self._enemy_ids else "Aliado"


def _combat_block(state: dict) -> dict[str, Any]:
    """View tática pública do conflito, sem vazar ficha secreta de inimigo."""
    meta = state.get("combat") or {}
    enemies = state.get("enemies") or []
    player = state.get("player") or {}
    alive = [
        e
        for e in enemies
        if not e.get("dead")
        and e.get("status", "ativo") not in ("morto", "fugiu", "rendido", "incapacitado")
    ]

    gone_ids = {  # SPEC-345 R2/R3: quem saiu do combate sai da view (estado intacto)
        str(e.get("id") or e.get("name")) for e in enemies if isinstance(e, dict) and e not in alive
    }

    from services.card_effects import condition_label as _condition_label

    def _conds(
        entity,
    ):  # SPEC-389 R13: `name` = rótulo humano; `id` = nome gravado (o save não muda)
        return [
            {
                "id": c.get("name", ""),
                "name": (label := _condition_label(str(c.get("name", "")))),
                "label": label,
                "dot": c.get("dot", 0),
                "duration": c.get("duration", 0),
            }
            for c in (entity.get("active_conditions") or [])
            if isinstance(c, dict)
        ]

    from services import bestiary_knowledge as knowledge
    from services import cards
    from services import combat_targeting as _targeting

    initiative = list(meta.get("initiative") or [])
    scene = meta.get("scene") or {}
    participant_names = _ParticipantNames(state, meta, enemies)
    participant_names["player"] = player.get("name", "Protagonista")
    for entity in (
        list(enemies) + list(state.get("party") or []) + list(meta.get("scene_allies") or [])
    ):
        if isinstance(entity, dict):
            participant_names[str(entity.get("id") or entity.get("name"))] = entity.get("name", "?")

    scene_view = {"zones": [], "positions": []}
    scene_view["zones"] = [
        {
            "id": z.get("id", ""),
            "name": z.get("name", ""),
            "connections": list(z.get("connections") or []),
        }
        for z in (scene.get("zones") or [])
        if isinstance(z, dict)
    ]
    for participant_id, pos in (scene.get("positions") or {}).items():
        if not isinstance(pos, dict) or str(participant_id) in gone_ids:
            continue
        posture = pos.get("postura") or {}
        engaged = [
            str(value) for value in (pos.get("engaged_with") or []) if str(value) not in gone_ids
        ]
        scene_view["positions"].append(
            {
                "participant_id": str(participant_id),
                "participant_name": participant_names.get(str(participant_id), str(participant_id)),
                "zone_id": pos.get("zone_id", ""),
                "distance": pos.get("distance_state", "proximo"),
                "posture": posture.get("state", "neutro")
                if isinstance(posture, dict)
                else str(posture),
                "concealment": pos.get("ocultacao", "visivel"),
                "engaged_with": engaged,
                "engaged_names": [participant_names.get(value, value) for value in engaged],
            }
        )

    enemy_views = []
    portrait_registry = _portrait_registry(state, meta, alive)  # 1 query por resposta (SPEC-352)
    for enemy in alive:
        public = knowledge.public_panel(enemy)
        revealed_cards = []
        for card_id in enemy.get("revealed_cards") or []:
            card = cards.get_card(str(card_id)) or {}
            if card:
                revealed_cards.append({"id": str(card_id), "name": card.get("name", card_id)})
        vitality = int(public.get("vitalidade", enemy.get("vitalidade", 0)) or 0)
        max_vitality = int(public.get("max_vitalidade", enemy.get("max_vitalidade", 0)) or 0)
        enemy_views.append(
            {
                "id": str(enemy.get("id") or enemy.get("name", "")),
                "name": enemy.get("name", ""),
                "vitalidade": vitality,
                "max_vitalidade": max_vitality,
                "hp": vitality,
                "max_hp": max_vitality,
                "esquiva": public.get("esquiva"),
                "protecao": public.get("protecao"),
                "integridade_atual": public.get("integridade_atual"),
                "integridade_max": public.get("integridade_max"),
                "recursos_visiveis": public.get("recursos_visiveis") or {},
                "conditions": _conds(enemy),
                "revealed_cards": revealed_cards,
                "revealed_resistances": [
                    combat_flags.resistance_label(r)
                    for r in enemy.get("revealed_resistances") or []
                ],
            }
        )
        if (portrait := _enemy_portrait(state, meta, enemy, portrait_registry)) is not None:
            enemy_views[-1]["retrato"] = portrait
    portrait_offer.finish()  # SPEC-389 R2: 1 offer_view por resposta

    chase = meta.get("chase") or {}
    chase_view = (
        {
            "track": chase.get("trilha", "pressionado"),
            "steps": ["pressionado", "afastado", "quase_livre", "escapou"],
            "escaped": bool(chase.get("escapou")),
            "caught": bool(chase.get("alcancado")),
            "pursuers": list(chase.get("perseguidores") or []),
            "last_roll": dict(chase.get("_last") or {}),
        }
        if chase
        else {}
    )
    if chase_view and _chase_live_for_api(chase):
        # SPEC-325 D8: só com a flag `on`; nunca o `pending_fate` (regra de ouro).
        if combat_flags.active("chase_approach") and chase.get("approach"):
            chase_view["approach"] = str(chase["approach"])
        if combat_flags.abandon_mode() == "on":
            from services import chase as _chase_mod

            party_rows = [p for p in (state.get("party") or []) if isinstance(p, dict)]
            chase_view["abandon_candidates"] = [
                {"id": cid, "name": name}
                for cid, name in _chase_mod.abandon_candidates(chase, party_rows).items()
            ]
            offer = str(chase.get("sacrifice_offer") or "")
            offered = next(
                (p for p in party_rows if _chase_mod._ally_key(p) == offer and offer), None
            )
            if offered is not None:
                chase_view["sacrifice_offer"] = {
                    "id": offer,
                    "name": str(offered.get("name") or ""),
                }
    wounds = player.get("ferimentos") or {}
    from services import encounter_manifest as em

    manifest = meta.get("encounter") if em.is_valid_manifest(meta.get("encounter")) else None
    view: dict[str, Any] = {
        "active": bool(meta.get("active")) and bool(alive),
        "round": meta.get("round", 0),
        # SPEC-203: fase/elenco congelado (somente leitura no cliente).
        "phase": meta.get("phase") or ("active" if meta.get("active") else "ended"),
        "outcome": meta.get("outcome"),
        "encounter_id": (manifest or {}).get("encounter_id") or meta.get("instance_id"),
        "encounter_view": em.public_view(manifest, meta.get("scene")) if manifest else {},
        # Compat temporária do HUD atual: iniciativa agora é POR LADO.
        "order": [
            {
                "name": "Heróis" if side == "heroes" else "Inimigos",
                "side": "hero" if side == "heroes" else "enemy",
                "init": 0,
            }
            for side in initiative
        ],
        "initiative": initiative,
        "enemies": enemy_views,
        "cards": _targeting_cards(state, _cards_block(player, prepared_only=True)),
        "basic_actions": _targeting.basic_actions(state),
        "scene": scene_view,
        "wounds": {
            "vitality": int(player.get("vitalidade", 0) or 0),
            "max_vitality": int(player.get("max_vitalidade", 0) or 0),
            "slots": dict(player.get("ferimento_espacos") or {}),
            "by_severity": {
                severity: list(wounds.get(severity) or [])
                for severity in ("leve", "grave", "critico")
            },
        },
        "chase": chase_view,
        "player_conditions": _conds(player),
        "cooldowns": {},
        # Ponte até conflito-16: chips agora vêm das Cartas, não de habilidades d20.
        "suggestions": cards.combat_card_suggestions(player, enemies, meta),
        "last_player_action": meta.get("last_player_action"),
        "reactions": meta.get("last_reactions", []),
    }
    if _enemy_intent.active() and meta.get("pressagios_publicos"):
        view["pressagios_publicos"] = [  # SPEC-329 R2/R3 + SPEC-345 R3
            line
            for line in meta["pressagios_publicos"]
            if not (isinstance(line, dict) and str(line.get("actor_id")) in gone_ids)
        ]
    from services import scene_cards as _scene_cards

    if _scene_cards.active():  # SPEC-331 R3/R4: presságio de cena + objetivo público
        view["pressagios_cena"] = list(meta.get("pressagios_cena") or [])
        _names = {str(e.get("id")): e.get("name") for e in enemies if e.get("id")}
        _objective = _scene_cards.public_objective(meta.get("scene"), _names)
        if _objective:
            view["objetivo"] = _objective
        _cena = _scene_cards.public_scene(meta.get("scene"))  # SPEC-342 R2.1
        if _cena:
            view["cena"] = _cena
    from services import card_piles as _piles

    if _piles.mode() == "on" and isinstance(meta.get("pilhas"), dict):
        # SPEC-328 R16: mão completa + contagens; nunca a ordem do monte.
        view["pilhas"] = _piles.public_view(meta["pilhas"], player)
        for _row in view["pilhas"].get("mao") or []:  # SPEC-363 R19: alvos de TODA Carta da mão
            try:
                _row.update(_targeting.hand_card_targeting(state, str(_row.get("id"))))
            except Exception as exc:  # noqa: BLE001 - alvo é dica de UI; o motor revalida
                log_fallback("combat_view", "hand_targeting_failed", exc)
    # SPEC-353 R54 + SPEC-354 R4.1 (um só caminho): com o Baralho `on`, o registro da rodada vale durante o conflito
    # (há `pilhas`) e, depois dele, só no turno de término (`_combat_result`), não até o próximo conflito.
    _final_board = (
        not meta.get("active")
        and bool(meta.get("last_round_board"))
        and bool(_combat_result(state))
    )
    if _piles.mode() == "on" and (isinstance(meta.get("pilhas"), dict) or _final_board):
        view["mech_log"] = list(meta.get("last_mech_log") or [])  # SPEC-334 R6
        if meta.get("last_round_board"):  # SPEC-347 R14.2: registro estruturado (só Baralho on)
            view["registro_rodada"] = list(meta["last_round_board"])
    if combat_flags.active("nonlethal"):
        view["nonlethal_available"] = True  # SPEC-325 D8: chip "Sem matar" so com a flag `on`
    reinf = meta.get("reinforcement") or {}
    if (
        combat_flags.active("reinforcements")
        and reinf.get("warned_round") is not None
        and not reinf.get("fired")
        and not reinf.get("cancelled")
    ):
        view["reinforcement_warning"] = True  # SPEC-325 R16: só depois do aviso (regra de ouro)
    if combat_flags.active("objects"):
        # SPEC-325 R14/D8: so rotulo/custo/usos (nunca `effect`); secreto so depois de descoberto.
        from services import conflict_scene as _cs

        scene_view["objects"] = _cs.visible_objects(scene)
    if combat_flags.active("companion_orders"):
        view["companion_orders"] = [  # SPEC-325 R15/D8: chips "<aliado>, <verbo>"
            {"id": str(p.get("id") or p.get("name")), "name": str(p.get("name") or "")}
            for p in (state.get("party") or [])
            if isinstance(p, dict) and p.get("active") and not p.get("pending_fate")
        ]
    return view


def _quest_block(plan: dict, quests: list, world: dict | None = None) -> dict[str, Any]:
    """Fase 3.3: main (view do campaign_plan) + side quests + markers pro mapa."""
    plan = plan or {}
    beats = plan.get("beats", []) or []
    step = plan.get("current_step", 0)
    climax = plan.get("climax", "")
    from services.objectives import public_objective

    public = public_objective(plan, quests, world or {})
    main = {
        "objective": public["objective"],
        "objective_source": public["source"],
        "objective_quest_id": public["quest_id"],
        "climax": "",
        "current_step": step,
        "total": len(beats),
        "arc_title": plan.get("arc_title", ""),
        "beats": [
            {"description": f"Etapa {index + 1}", "status": b.get("status", "pending")}
            for index, b in enumerate(beats)
        ],
    }
    quests = [q for q in (quests or []) if isinstance(q, dict)]
    active = [q for q in quests if q.get("status") == "active"]
    resolved = sorted(
        (q for q in quests if q.get("status") != "active"),
        key=lambda q: q.get("resolved_turn", 0),
        reverse=True,
    )[:5]
    # SPEC-305 R20: lista branca — prazo exato, fonte, canal e motivo de falha nunca saem.
    day = int(((world or {}).get("world_clock") or {}).get("day", 1) or 1)
    side = [quest_log.public_quest_view(q, day) for q in active + resolved]
    return {"main": main, "side": side, "markers": quest_log.quest_markers(quests)}


def _world_block(
    w: dict,
    projection: dict | None = None,
    event_log: list | None = None,
    player: dict | None = None,
    world_sim: dict | None = None,
    state: dict | None = None,
) -> dict[str, Any]:
    # SPEC-308 R7/P1-3: o mapa mostra o que o heroi SABE (eventos do motor so apos percebidos)
    from services.world_perception import perceived_projection

    pstate = state or {
        "world": w,
        "world_sim": world_sim,
        "event_log": event_log or [],
        "world_projection": projection or {},
    }
    projection = perceived_projection(pstate, projection or {})
    clock = w.get("world_clock") or {}
    turn = w.get("turn_count", 0)
    # spec itens-vivos-e-luz (R7): estado de luz p/ o HUD (precisa do player p/
    # saber se ele carrega uma fonte de luz).
    from world_utils import light_level, weather_effects

    light = light_level(w, player or {})
    effective_weather = weather_effects(w)
    return {
        "location": w.get("current_location", ""),
        "location_id": w.get("current_location_id", ""),
        "day": clock.get("day", 1),
        "period": clock.get("period", "Amanhecer"),
        "visited": w.get("visited", []),
        "danger": w.get("danger_level", 1),
        "weather": effective_weather.get("label") or w.get("weather", ""),
        "weather_global": dict(w.get("weather_global") or {}),
        "light": {"dark": light["dark"], "lit": light["lit"], "label": light["label"]},
        "turn_count": turn,  # Fase 3.2: refetch do Codex quando o turno muda
        # Fase 3.4: controlador por local visitado (verdade 2.5+/projection vence o
        # legado da Fase 2; NOME, não id — ver services/state_views.visible_controllers).
        "controlled": sv.visible_controllers(w, projection or {}),
        "danger_overrides": dict(w.get("danger_overrides") or {}),
        "map_overlays": {
            "control_changes": sv.recent_control_changes(
                event_log or [], w.get("visited", []), turn, state=pstate
            ),
            "threats": sv.active_threats(w, turn),
            "looming_threat": w.get("looming_threat", ""),
        },
        # Fase 6.1: rotas comerciais bloqueadas (WorldMap traceja a conexão)
        # SPEC-302 (revisão P2-2): só rotas com ponta num local que o herói conhece.
        "blocked_routes": [
            {"a": r.get("a", ""), "b": r.get("b", "")}
            for r in (projection or {}).get("blocked_routes", []) or []
            if {r.get("a"), r.get("b")} & {*(w.get("visited") or []), w.get("current_location_id")}
        ],
        # spec mapa-sublocais (R7): interiores do local atual ("Locais daqui")
        # + caminho de volta quando o jogador está DENTRO de um interior.
        "interiors": _interiors_block(w.get("current_location_id", "")),
        # SPEC-296 R8 + SPEC-302 R31: só o rótulo vago do local ATUAL e as notícias
        # percebidas (lista branca de campos); pressões/world_sim/relações nunca saem.
        "location_state": _location_state_label(w.get("current_location_id", ""), projection),
        # SPEC-303 R22: estação com rótulo regional do local atual (só id+label; passos,
        # festas e parâmetros do calendário nunca saem)
        "season": _season_view(w),
        # SPEC-307 R16: data de Valoria derivada (pura) de world_sim.calendar; nunca sai
        # epoch_offset/year_offset/catalogo de festas.
        "date": _date_block(w, world_sim),
        "news": [
            {
                **{k: n.get(k, "") for k in ("day", "period", "location_name", "text", "turn")},
                "date_label": _news_date_label(n, world_sim),
                # SPEC-312 R17: unico campo derivado de rumor (nunca truth/rumor_id/expires_day)
                "kind": _rumors_public_kind(n),
            }
            for n in (w.get("news") or [])[-12:]
            if isinstance(n, dict) and not _rumor_news_expired(n, w)
        ],
    }


def _rumors_public_kind(entry: dict) -> str:
    from services import rumors

    return rumors.public_kind(entry)


def _rumor_news_expired(entry: dict, world: dict) -> bool:
    day = int((world.get("world_clock") or {}).get("day", 1) or 1)
    return entry.get("kind") == "rumor" and int(entry.get("expires_day", 0) or 0) < day


def _date_block(w: dict, world_sim: dict | None) -> dict[str, Any] | None:
    from services import world_calendar

    if world_calendar.mode() != "on":
        return None
    day = int((w.get("world_clock") or {}).get("day", 1) or 1)
    cal = world_calendar.calendar_for_read(world_sim, day)
    if not cal:
        return None
    v = world_calendar.date_view(cal, day)
    out = {
        k: v[k]
        for k in ("label", "day_of_month", "month", "month_id", "weekday", "year", "climate")
    }
    # D8: chip de estacao so onde a regiao tem rotulo proprio (Skallgard, Zhur)
    from services.world_pressures import region_of

    sid = world_calendar.active_season(w)
    region = region_of(str(w.get("current_location_id") or ""))
    out["season_chip"] = (
        world_calendar.label_for(sid, region)
        if sid and world_calendar.has_regional_label(sid, region)
        else ""
    )
    return out


def _news_date_label(item: dict, world_sim: dict | None) -> str:
    from services import world_calendar

    if world_calendar.mode() != "on":
        return ""
    try:
        day = int(item.get("day") or 0)
    except (TypeError, ValueError):
        return ""
    cal = world_calendar.calendar_for_read(world_sim, day) if day > 0 else None
    return world_calendar.date_label(cal, day) if cal else ""


def _season_view(w: dict) -> dict[str, str] | None:
    from services import world_calendar
    from services.world_pressures import region_of

    sid = world_calendar.active_season(w)
    if not sid:
        return None
    return {
        "id": sid,
        "label": world_calendar.label_for(sid, region_of(str(w.get("current_location_id") or ""))),
    }


def _location_state_label(loc_id: str, projection: dict | None) -> str:
    from services.location_states import location_state, public_label
    from services.world_engine import mode

    if mode() != "on":
        return ""
    return public_label(location_state({"world_projection": projection or {}}, loc_id))


def _interiors_block(loc_id: str) -> dict[str, Any]:
    from services.map_view import interiors_block

    return interiors_block(loc_id)
